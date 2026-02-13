from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
from pathlib import Path
import uuid
import os
import json
import time
import threading
import subprocess
import sys
import shutil
from openai import OpenAI
from dotenv import load_dotenv
from .server_utils import ensure_dir, safe_name, tail_text, list_run_dirs, is_within_root, now_ts

# 加载 .env 文件
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 强制移除可能干扰输出目录的环境变量
if "MOBILE_V4_OUTPUT_DIR" in os.environ and os.environ["MOBILE_V4_OUTPUT_DIR"] == "output-frontend":
    print(f"WARNING: Found MOBILE_V4_OUTPUT_DIR={os.environ['MOBILE_V4_OUTPUT_DIR']} in env, removing it.")
    del os.environ["MOBILE_V4_OUTPUT_DIR"]

app = FastAPI()

cors_origins_env = os.getenv("MOBILE_V4_CORS_ORIGINS", "*").strip()
if cors_origins_env == "*":
    cors_allow_origins = ["*"]
else:
    cors_allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = Path(__file__).resolve().parent
DATA_DIR = WEB_ROOT / "data"
SCENARIO_DIR = DATA_DIR / "scenarios"
APK_DIR = DATA_DIR / "apks"
CONFIG_PATH = DATA_DIR / "config.json"
OUTPUT_ROOT = (PROJECT_ROOT / (os.getenv("MOBILE_V4_OUTPUT_DIR", "").strip() or "output")).resolve()
print(f"DEBUG: OUTPUT_ROOT is set to: {OUTPUT_ROOT}")
JOB_DIR = OUTPUT_ROOT / "jobs"


ensure_dir(DATA_DIR)
ensure_dir(SCENARIO_DIR)
ensure_dir(APK_DIR)
ensure_dir(JOB_DIR)


class ScenarioRef(BaseModel):
    type: Literal["uploaded", "path", "inline"]
    value: Union[str, Dict[str, Any]]


class ApkRef(BaseModel):
    type: Literal["uploaded", "path"]
    value: str


class SimpleTaskData(BaseModel):
    task_description: str
    package_name: str
    launch_activity: Optional[str] = None
    app_name: Optional[str] = None


class RunRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    mode: Literal["single", "range", "batch"]
    scenario_ref: Optional[ScenarioRef] = None
    apk_ref: Optional[ApkRef] = None
    simple_task: Optional[SimpleTaskData] = None
    app_id: Optional[str] = None
    scenario_id: Optional[str] = None
    scenario_start_id: Optional[str] = None
    scenario_end_id: Optional[str] = None
    run_config: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    device_profile: Optional[str] = "default_android"
    device_selector: Optional[Dict[str, Any]] = None
    model_profile: Optional[str] = "default_qwen_vl"
    lang: Optional[str] = "zh"


class ConfigRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    summary_api_key: Optional[str] = None
    summary_base_url: Optional[str] = None
    summary_model: Optional[str] = None


class JobStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.lock = threading.Lock()
        self.memory: Dict[str, Dict[str, Any]] = {}

    def _path(self, job_id: str) -> Path:
        return self.base_dir / f"{job_id}.json"

    def create(self, job: Dict[str, Any]) -> None:
        with self.lock:
            self.memory[job["job_id"]] = job
            self._write(job["job_id"], job)

    def update(self, job_id: str, updates: Dict[str, Any]) -> None:
        with self.lock:
            job = self.memory.get(job_id) or self._read(job_id) or {}
            job.update(updates)
            self.memory[job_id] = job
            self._write(job_id, job)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            job = self.memory.get(job_id)
            if job:
                return job
            job = self._read(job_id)
            if job:
                self.memory[job_id] = job
            return job

    def _read(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(job_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write(self, job_id: str, data: Dict[str, Any]) -> None:
        path = self._path(job_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


import queue

job_store = JobStore(JOB_DIR)
run_lock = threading.Lock() # 保持向后兼容，但之后会移除对它的依赖
proc_lock = threading.Lock()
RUNNING_PROCS: Dict[str, subprocess.Popen] = {}

# 服务化并发管理
class DevicePoolManager:
    def __init__(self, device_ids: List[str]):
        self.idle_devices = queue.Queue()
        for d in device_ids:
            self.idle_devices.put(d)
        self.lock = threading.Lock()
        self.all_devices = set(device_ids)
        self.adb_path = os.getenv("MOBILE_V4_ADB_PATH", "adb")

    def acquire(self, timeout: Optional[float] = None) -> Optional[str]:
        try:
            return self.idle_devices.get(timeout=timeout)
        except queue.Empty:
            return None

    def release(self, device_id: str):
        if device_id in self.all_devices:
            self.idle_devices.put(device_id)

    def ensure_connected(self, device_id: str) -> bool:
        """确保设备已连接"""
        print(f"Ensuring device connected: {device_id}")
        
        # 1. 检查设备是否在线 (适用于所有设备)
        if not self.is_offline(device_id):
            return True

        # 2. 如果离线且是网络设备（含冒号），尝试 adb connect
        if ":" in device_id:
            try:
                cmd = f"{self.adb_path} connect {device_id}"
                subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                time.sleep(1)
                return not self.is_offline(device_id)
            except Exception as e:
                print(f"Connect error for {device_id}: {e}")
                return False
                
        # 3. 如果是不含冒号的设备（如 emulator-5554 或物理机），且状态为 offline，则无法自动修复，返回 False
        return False

    def is_offline(self, device_id: str) -> bool:
        """检查设备是否离线"""
        try:
            cmd = f"{self.adb_path} -s {device_id} get-state"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            return "device" not in res.stdout
        except Exception:
            return True

# 默认手机池，数量为1（根据用户要求）
# 可以通过环境变量 MOBILE_V4_DEVICES 配置，逗号分隔
# 示例：MOBILE_V4_DEVICES=127.0.0.1:5555,127.0.0.1:5556
raw_devices = os.getenv("MOBILE_V4_DEVICES", "").strip()
if raw_devices:
    default_devices = [d.strip() for d in raw_devices.split(",") if d.strip()]
else:
    # 以前默认回退到 emulator-5554，现在为了支持真机调试，我们更严谨一点
    # 如果没有配置环境变量，我们在启动时尝试自动探测（仅限单设备场景）
    print("WARNING: MOBILE_V4_DEVICES not set. Attempting to auto-detect devices via ADB...")
    try:
        adb_path = os.getenv("MOBILE_V4_ADB_PATH", "adb")
        res = subprocess.run(f"{adb_path} devices", shell=True, capture_output=True, text=True, timeout=5)
        lines = res.stdout.strip().split("\n")[1:] # 跳过第一行 List of devices attached
        detected = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                detected.append(parts[0])
        
        if detected:
            print(f"Auto-detected devices: {detected}")
            default_devices = detected
        else:
            print("No devices detected. Fallback to 'emulator-5554' (may fail if not running).")
            default_devices = ["emulator-5554"]
    except Exception as e:
        print(f"Auto-detect failed: {e}. Fallback to 'emulator-5554'.")
        default_devices = ["emulator-5554"]

device_pool = DevicePoolManager(default_devices)

# 任务等待队列
task_queue = queue.Queue()

# 用户任务状态追踪
USER_RUNNING_JOBS: Dict[str, str] = {} # user_id -> job_id
user_lock = threading.Lock()


def ok(result: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=200, content={"code": 200, "message": "success", "result": result})


def err(code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=code, content={"code": code, "message": "error", "detail": detail})


def read_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_config(cfg: Dict[str, Any]) -> None:
    ensure_dir(CONFIG_PATH.parent)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def generate_scenario_name_with_llm(task_description: str) -> str:
    """Use LLM to generate a concise scenario name from task description.

    Args:
        task_description: Full task description

    Returns:
        A concise scenario name (fallback to truncated description if LLM fails)
    """
    try:
        cfg = read_config()
        summary_api_key = (
            cfg.get("summary_api_key")
            or os.getenv("MOBILE_V4_SUMMARY_API_KEY")
            or cfg.get("api_key")
            or os.getenv("MOBILE_V4_API_KEY")
        )
        summary_base_url = (
            cfg.get("summary_base_url")
            or os.getenv("MOBILE_V4_SUMMARY_BASE_URL")
            or cfg.get("base_url")
            or os.getenv("MOBILE_V4_BASE_URL")
        )
        summary_model = (
            cfg.get("summary_model")
            or os.getenv("MOBILE_V4_SUMMARY_MODEL")
            or cfg.get("model")
            or os.getenv("MOBILE_V4_MODEL")
        )

        if not all([summary_api_key, summary_base_url, summary_model]):
            raise ValueError("LLM config not available")

        client = OpenAI(api_key=summary_api_key, base_url=summary_base_url)

        contains_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in task_description)
        if contains_cjk:
            system_content = (
                "你是一个专业的测试场景命名助手。根据用户提供的任务描述，生成一个简洁的测试场景名称"
                "（5-15个字），只返回名称本身，不要有任何其他解释。"
            )
            user_content = f"任务描述：{task_description}\n\n请生成场景名称："
        else:
            system_content = (
                "You are a professional assistant for naming test scenarios. Based on the "
                "user's task description, generate a concise test scenario name (5–15 words "
                "or characters). Return only the name itself, with no additional explanation."
            )
            user_content = (
                f"Task description: {task_description}\n\n"
                "Please generate a scenario name:"
            )

        response = client.chat.completions.create(
            model=summary_model,
            messages=[
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            temperature=0.3,
            max_tokens=50,
            timeout=10,
        )

        choices = getattr(response, "choices", None)
        if not choices:
            raise ValueError("LLM response has no choices")

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None) if message is not None else None

        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM response has empty or invalid content")

        scenario_name = content.strip()
        
        quote_chars = "\"'\u201c\u201d\u2018\u2019"
        scenario_name = scenario_name.strip(quote_chars)

        if not scenario_name:
            raise ValueError("Scenario name is empty after processing")

        if len(scenario_name) > 50:
            scenario_name = scenario_name[:50]

        return scenario_name

    except Exception as e:
        print(f"Warning: Failed to generate scenario name with LLM: {e}")
        # Fallback to simple truncation
        scenario_name = task_description[:30]
        if len(task_description) > 30:
            scenario_name += "..."
        return scenario_name


def generate_simple_scenario(simple_task: SimpleTaskData) -> Dict[str, Any]:
    """Generate a complete scenario configuration from simple task data."""
    raw_package_name = (simple_task.package_name or "").strip()
    package_parts = [part for part in raw_package_name.split(".") if part] if raw_package_name else []
    
    if len(package_parts) >= 2:
        app_id = f"{package_parts[-2]}_{package_parts[-1]}"
    elif package_parts:
        app_id = package_parts[-1]
    else:
        app_id = "unknown_app"

    scenario_id = f"task_{uuid.uuid4().hex[:12]}"

    # Generate scenario name using LLM
    scenario_name = generate_scenario_name_with_llm(simple_task.task_description)

    scenario = {
        "apps": [
            {
                "id": app_id,
                "name": simple_task.app_name or app_id,
                "package": simple_task.package_name,
                "launch-activity": simple_task.launch_activity,
            }
        ],
        "scenarios": [
            {
                "id": scenario_id,
                "name": scenario_name,
                "description": simple_task.task_description,
                "extra-info": {},
            }
        ],
    }
    return scenario


def resolve_scenario_path(job_dir: Path, ref: ScenarioRef) -> Path:
    if ref.type == "uploaded":
        token = str(ref.value)
        if token.endswith(".json"):
            path = Path(token)
            if not path.is_absolute():
                path = SCENARIO_DIR / token
        else:
            path = SCENARIO_DIR / f"{token}.json"
        if not path.exists():
            raise ValueError("scenario_ref not found")
        return path
    if ref.type == "path":
        raw = str(ref.value)
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_ROOT / raw
        if not path.exists():
            raise ValueError("scenario_ref path not found")
        return path
    if ref.type == "inline":
        if not isinstance(ref.value, dict):
            raise ValueError("scenario_ref inline must be a JSON object")
        path = job_dir / "scenario_inline.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(ref.value, f, ensure_ascii=False, indent=2)
        return path
    raise ValueError("scenario_ref type not supported")


def list_output_dirs() -> List[str]:
    output_dir = OUTPUT_ROOT
    if not output_dir.exists():
        return []
    return [p.name for p in output_dir.iterdir() if p.is_dir() and p.name.startswith("T-")]


def resolve_apk_path(ref: ApkRef) -> Path:
    if ref.type == "uploaded":
        token = str(ref.value)
        path = APK_DIR / f"{token}.apk"
        if not path.exists():
            raise ValueError(f"APK token not found: {token}")
        return path
    if ref.type == "path":
        path = Path(str(ref.value))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise ValueError(f"APK path not found: {path}")
        return path
    raise ValueError(f"APK ref type not supported: {ref.type}")


def resolve_model_config(req: RunRequest) -> Dict[str, Any]:
    cfg = read_config()

    api_key = cfg.get("api_key") or os.getenv("MOBILE_V4_API_KEY")
    base_url = cfg.get("base_url") or os.getenv("MOBILE_V4_BASE_URL")
    model = cfg.get("model") or os.getenv("MOBILE_V4_MODEL")

    summary_api_key = (
        cfg.get("summary_api_key")
        or os.getenv("MOBILE_V4_SUMMARY_API_KEY")
        or api_key
    )
    summary_base_url = (
        cfg.get("summary_base_url")
        or os.getenv("MOBILE_V4_SUMMARY_BASE_URL")
        or base_url
    )
    summary_model = (
        cfg.get("summary_model")
        or os.getenv("MOBILE_V4_SUMMARY_MODEL")
        or model
    )

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "summary_api_key": summary_api_key,
        "summary_base_url": summary_base_url,
        "summary_model": summary_model,
    }


def resolve_device_config(req: RunRequest) -> Dict[str, Any]:
    adb_path = os.getenv("MOBILE_V4_ADB_PATH")
    hdc_path = os.getenv("MOBILE_V4_HDC_PATH")
    return {"adb_path": adb_path, "hdc_path": hdc_path}


def normalize_run_config(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("run_config item must be an object")
        app_id = item.get("app_id")
        if not app_id:
            raise ValueError("run_config item missing app_id")
        scenario_id = item.get("scenario_id") or item.get("specific_id")
        start_id = item.get("scenario_start_id") or item.get("start_id")
        end_id = item.get("scenario_end_id") or item.get("end_id")
        normalized.append(
            {
                "app_id": app_id,
                "start_id": start_id,
                "end_id": end_id,
                "specific_id": scenario_id,
            }
        )
    return normalized


def build_command(
    req: RunRequest,
    scenario_path: Path,
    job_dir: Path,
    run_dir: Optional[Path] = None,
    run_dir_prefix: Optional[Path] = None,
    device_id: Optional[str] = None,
) -> List[str]:
    model_cfg = resolve_model_config(req)
    api_key = model_cfg.get("api_key")
    base_url = model_cfg.get("base_url")
    model = model_cfg.get("model")
    summary_api_key = model_cfg.get("summary_api_key")
    summary_base_url = model_cfg.get("summary_base_url")
    summary_model = model_cfg.get("summary_model")
    if not base_url or not model:
        raise ValueError("base_url and model are required")
    if not api_key:
        raise ValueError("api_key is required")
    if not summary_base_url or not summary_model:
        raise ValueError("summary_base_url and summary_model are required")
    if not summary_api_key:
        raise ValueError("summary_api_key is required")

    device_cfg = resolve_device_config(req)
    adb_path = device_cfg.get("adb_path")
    hdc_path = device_cfg.get("hdc_path")

    args = [sys.executable, str(PROJECT_ROOT / "main.py")]
    if adb_path:
        args += ["--adb_path", str(adb_path)]
    if hdc_path:
        args += ["--hdc_path", str(hdc_path)]
    args += ["--api_key", str(api_key), "--base_url", str(base_url), "--model", str(model)]
    args += ["--summary_api_key", str(summary_api_key), "--summary_base_url", str(summary_base_url), "--summary_model", str(summary_model)]
    args += ["--scenario_file", str(scenario_path)]
    if run_dir is not None:
        args += ["--run_dir", str(run_dir)]
    if run_dir_prefix is not None:
        args += ["--run_dir_prefix", str(run_dir_prefix)]
    if device_id:
        args += ["--device_id", str(device_id)]

    if req.mode == "single":
        if not req.app_id or not req.scenario_id:
            raise ValueError("mode=single requires app_id and scenario_id")
        args += ["--app_id", req.app_id, "--scenario_id", req.scenario_id]
    elif req.mode == "range":
        if not req.app_id or not req.scenario_start_id or not req.scenario_end_id:
            raise ValueError("mode=range requires app_id, scenario_start_id, scenario_end_id")
        args += ["--app_id", req.app_id, "--scenario_start_id", req.scenario_start_id, "--scenario_end_id", req.scenario_end_id]
    else:
        if not req.run_config:
            raise ValueError("mode=batch requires run_config")
        normalized = normalize_run_config(req.run_config)
        run_config_path = job_dir / "run_config.json"
        with run_config_path.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        args += ["--run_config", str(run_config_path)]

    if req.lang:
        args += ["--output_lang", req.lang]

    return args


def run_job(job_id: str, req: RunRequest, device_id: Optional[str] = None) -> None:
    job_dir = JOB_DIR / job_id
    ensure_dir(job_dir)
    job_store.update(job_id, {"status": "running", "started_at": now_ts(), "device_id": device_id})
    error = None
    run_dirs: List[str] = []
    run_root = job_dir / "runs"
    ensure_dir(run_root)
    
    # 获取 ADB 路径
    device_cfg = resolve_device_config(req)
    adb_path = device_cfg.get("adb_path") or os.getenv("MOBILE_V4_ADB_PATH", "adb")

    try:
        # 1. 如果有 APK，先执行安装
        if req.apk_ref:
            try:
                apk_path = resolve_apk_path(req.apk_ref)
                print(f"[{job_id}] Installing APK: {apk_path} to {device_id}")
                install_cmd = f"{adb_path} -s {device_id} install -r {apk_path}"
                res = subprocess.run(install_cmd, shell=True, capture_output=True, text=True, timeout=120)
                
                # Write installation log to setup.log
                setup_log_path = job_dir / "setup.log"
                with setup_log_path.open("a", encoding="utf-8") as f:
                    f.write(f"[{now_ts()}] Installing APK: {apk_path}\n")
                    f.write(f"Command: {install_cmd}\n")
                    f.write(f"STDOUT:\n{res.stdout}\n")
                    f.write(f"STDERR:\n{res.stderr}\n")
                    f.write(f"Return Code: {res.returncode}\n\n")

                if res.returncode != 0:
                    raise RuntimeError(f"ADB install failed: {res.stderr}")
                print(f"[{job_id}] APK installed successfully")
            except Exception as e:
                print(f"[CRITICAL ERROR] Job {job_id} APK install failed: {e}")
                raise RuntimeError(f"Failed to install APK: {e}")

        scenario_path = resolve_scenario_path(job_dir, req.scenario_ref)

        planned_run_dir = None
        run_dir_prefix = None
        if req.mode == "single":
            # 计算绝对路径用于传给 subprocess
            run_dir_name = f"T-{safe_name(req.app_id)}-{safe_name(req.scenario_id)}"
            planned_run_dir = run_root / run_dir_name
            ensure_dir(planned_run_dir)
            
            # 数据库存相对路径
            rel_run_dir = str(Path("runs") / run_dir_name)
            job_store.update(job_id, {"run_dir": rel_run_dir})
        else:
            run_dir_prefix = run_root

        cmd = build_command(req, scenario_path, job_dir, run_dir=planned_run_dir, run_dir_prefix=run_dir_prefix, device_id=device_id)
        job_store.update(job_id, {"command": cmd})
        stdout_path = job_dir / "runner_stdout.log"
        stderr_path = job_dir / "runner_stderr.log"
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        with stdout_path.open("w", encoding="utf-8") as out_f, stderr_path.open("w", encoding="utf-8") as err_f:
            proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=out_f, stderr=err_f, text=True, env=env)
            with proc_lock:
                RUNNING_PROCS[job_id] = proc
            job_store.update(job_id, {"pid": proc.pid})

            last_seen: List[str] = []
            while proc.poll() is None:
                if req.mode != "single":
                    current = list_run_dirs(run_root)
                    if current != last_seen:
                        last_seen = current
                        # list_run_dirs 返回的是绝对路径，这里转换为相对路径
                        rel_run_dirs = []
                        for p in current:
                            try:
                                rel = Path(p).relative_to(job_dir)
                                rel_run_dirs.append(str(rel))
                            except ValueError:
                                rel_run_dirs.append(Path(p).name)
                                
                        job_store.update(
                            job_id,
                            {
                                "run_dirs": rel_run_dirs,
                                "run_dir": rel_run_dirs[-1] if rel_run_dirs else job_store.get(job_id).get("run_dir"),
                            },
                        )
                time.sleep(0.3)
            returncode = proc.wait()

        if req.mode == "single":
            run_dirs = []
        else:
            run_dirs = list_run_dirs(run_root)

        if returncode != 0:
            error = tail_text(stderr_path) or tail_text(stdout_path) or f"runner exit code: {returncode}"
            print(f"[CRITICAL ERROR] Job {job_id} runner failed: {error}")
    except Exception as exc:
        error = str(exc)
        print(f"[CRITICAL ERROR] Job {job_id} exception: {error}")
    finally:
        with proc_lock:
            if job_id in RUNNING_PROCS:
                del RUNNING_PROCS[job_id]

    # 检查是否已经被 api_stop 标记为 stopped
    current_job = job_store.get(job_id)
    if current_job and current_job.get("status") == "stopped":
        status = "stopped"
    else:
        status = "success" if not error else "failed"
        
    finished_at = now_ts()
    run_dir = job_store.get(job_id).get("run_dir") if job_store.get(job_id) else None
    if not run_dir and run_dirs:
        run_dir = run_dirs[-1]
    artifacts = {
        "stream": {
            "chat_log": "chat/chat_log.jsonl",
            "steps_dir": "Steps/",
            "images_dir": "images/",
        },
        "results": {
            "task_results": "task_results.json",
            "script": "script.json",
            "infopool": "infopool.json",
            "chat_log": "chat/chat_log.jsonl",
            "stdout": "terminallog/stdout.log",
            "zip": "zip",
        },
    }
    job_store.update(
        job_id,
        {
            "status": status,
            "finished_at": finished_at,
            "run_dir": run_dir,
            "run_dirs": run_dirs,
            "error": error,
            "artifacts": artifacts,
        },
    )


def worker_loop():
    """后台任务消费者"""
    while True:
        try:
            # 从队列中获取任务
            job_id, req = task_queue.get()
            
            # 等待可用手机
            device_id = device_pool.acquire()
            if not device_id:
                # 理论上不会发生，因为 acquire 是阻塞的，但这里做个保护
                time.sleep(1)
                task_queue.put((job_id, req))
                task_queue.task_done()
                continue
                
            try:
                # 任务执行前的连接预检
                if not device_pool.ensure_connected(device_id):
                    raise RuntimeError(f"Device {device_id} is offline and could not be reconnected.")
                
                run_job(job_id, req, device_id=device_id)
            except Exception as e:
                print(f"Error running job {job_id}: {e}")
                job_store.update(job_id, {"status": "failed", "error": str(e)})
            finally:
                # 任务结束，释放手机
                device_pool.release(device_id)
                # 移除用户活跃状态
                with user_lock:
                    if req.user_id in USER_RUNNING_JOBS and USER_RUNNING_JOBS[req.user_id] == job_id:
                        del USER_RUNNING_JOBS[req.user_id]
                task_queue.task_done()
        except Exception as e:
            print(f"Worker loop error: {e}")
            time.sleep(1)

# 启动 Worker 线程
# 这里的数量可以根据手机池的大小动态调整
# 启动与设备数量相等的 Worker 线程，实现真正的并行执行
num_workers = len(device_pool.all_devices)
print(f"[INIT] Starting {num_workers} worker threads for {num_workers} devices...")
for i in range(num_workers):
    t = threading.Thread(target=worker_loop, daemon=True, name=f"Worker-{i}")
    t.start()


def guarded_run_job(job_id: str, req: RunRequest) -> None:
    # 兼容旧逻辑，但现在改用队列了
    task_queue.put((job_id, req))


@app.post("/api/v1/stop/{job_id}")
def api_stop(job_id: str):
    job = job_store.get(job_id)
    if not job:
        return err(404, "job_id not found")
    status = job.get("status")
    if status in ("success", "failed", "stopped"):
        return ok(
            {
                "job_id": job_id,
                "status": status,
                "created_at": job.get("created_at"),
                "started_at": job.get("started_at"),
                "finished_at": job.get("finished_at"),
            }
        )
    proc = None
    with proc_lock:
        proc = RUNNING_PROCS.get(job_id)
    if not proc:
        job_store.update(
            job_id,
            {
                "status": "stopped",
                "finished_at": now_ts(),
                "error": job.get("error") or "stopped without active process",
            },
        )
        job = job_store.get(job_id)
        return ok(
            {
                "job_id": job_id,
                "status": job.get("status"),
                "created_at": job.get("created_at"),
                "started_at": job.get("started_at"),
                "finished_at": job.get("finished_at"),
            }
        )
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    job_store.update(
        job_id,
        {
            "status": "stopped",
            "finished_at": now_ts(),
            "error": job.get("error") or "stopped by user",
        },
    )
    with proc_lock:
        if job_id in RUNNING_PROCS:
            del RUNNING_PROCS[job_id]
    job = job_store.get(job_id)
    return ok(
        {
            "job_id": job_id,
            "status": job.get("status"),
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
        }
    )


@app.post("/api/v1/run")
def api_run(req: RunRequest, bg: BackgroundTasks):
    try:
        # 1. 用户任务并发拦截
        user_id = req.user_id or "default_user"
        with user_lock:
            if user_id in USER_RUNNING_JOBS:
                active_job_id = USER_RUNNING_JOBS[user_id]
                active_job = job_store.get(active_job_id)
                if active_job and active_job.get("status") in ("queued", "running"):
                    return err(400, f"User already has an active task: {active_job_id}. Please wait for it to finish or stop it first.")
            
            # 标记用户开始新任务
            # 注意：这里还没分配 job_id，先往后放一下

        # Handle simple task mode
        if req.simple_task:
            # Generate inline scenario from simple task
            scenario_data = generate_simple_scenario(req.simple_task)
            req.scenario_ref = ScenarioRef(type="inline", value=scenario_data)

            # Extract app_id from generated scenario
            app_id = scenario_data["apps"][0]["id"]
            scenario_id = scenario_data["scenarios"][0]["id"]

            # Force mode to single
            req.mode = "single"
            req.app_id = app_id
            req.scenario_id = scenario_id

        # Validate scenario_ref exists
        if not req.scenario_ref:
            return err(400, "scenario_ref or simple_task is required")

        if req.mode == "single":
            if not req.app_id or not req.scenario_id:
                return err(400, "mode=single requires app_id and scenario_id")
        if req.mode == "range":
            if not req.app_id or not req.scenario_start_id or not req.scenario_end_id:
                return err(400, "mode=range requires app_id, scenario_start_id, scenario_end_id")
        if req.mode == "batch":
            if not req.run_config:
                return err(400, "mode=batch requires run_config")
        job_id = str(uuid.uuid4())

        # 重新锁定并注册任务（防止并发间隙插入）
        with user_lock:
            if user_id in USER_RUNNING_JOBS:
                active_job_id = USER_RUNNING_JOBS[user_id]
                active_job = job_store.get(active_job_id)
                if active_job and active_job.get("status") in ("queued", "running"):
                    return err(400, f"User already has an active task: {active_job_id}")
            USER_RUNNING_JOBS[user_id] = job_id

        job_dir = JOB_DIR / job_id
        ensure_dir(job_dir)
        run_root = job_dir / "runs"
        ensure_dir(run_root)
        initial_run_dir = None
        if req.mode == "single":
            # 存储相对路径：runs/T-xxxx
            run_dir_name = f"T-{safe_name(req.app_id)}-{safe_name(req.scenario_id)}"
            initial_run_dir = str(Path("runs") / run_dir_name)
            
            # 实际创建目录需要绝对路径
            ensure_dir(job_dir / initial_run_dir)

        initial_artifacts = {
            "stream": {
                "chat_log": "chat/chat_log.jsonl",
                "steps_dir": "Steps/",
                "images_dir": "images/",
            },
            "results": {},
        }

        job_store.create(
            {
                "job_id": job_id,
                "status": "queued",
                "created_at": now_ts(),
                "started_at": None,
                "finished_at": None,
                "run_dir": initial_run_dir,
                "run_dirs": [],
                "error": None,
                "artifacts": initial_artifacts,
                "device_id": None,
                "device_snapshot": None,
            }
        )
        bg.add_task(guarded_run_job, job_id, req)
        return ok({"job_id": job_id, "status": "queued", "created_at": now_ts()})
    except Exception as exc:
        return err(500, str(exc))


@app.get("/api/v1/status/{job_id}")
def api_status(job_id: str):
    job = job_store.get(job_id)
    if not job:
        return err(404, "job_id not found")
    result = {
        "job_id": job_id,
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "run_dir": job.get("run_dir"),
        "run_dirs": job.get("run_dirs") or [],
        "error": job.get("error"),
        "artifacts": job.get("artifacts") or {},
        "device_id": job.get("device_id"),
        "device_snapshot": job.get("device_snapshot"),
        "command": job.get("command"),
    }
    return ok(result)


@app.get("/api/v1/download/{job_id}/{file_path:path}")
def api_download(job_id: str, file_path: str, run_dir: Optional[str] = Query(default=None)):
    job = job_store.get(job_id)
    if not job:
        return err(404, "job_id not found")
    base_run_dir = job.get("run_dir")
    
    if run_dir:
        base_run_dir = run_dir

    if not base_run_dir:
        return err(404, "run_dir not available yet")

    run_root = JOB_DIR / job_id / "runs"
    
    # 强制将 base_run_dir 视为相对路径处理
    # 移除可能存在的驱动器前缀 (E:) 和根路径前缀 (/ 或 \)
    rel_path_str = str(base_run_dir).lstrip("/\\")
    if ":" in rel_path_str:
        # 简单粗暴处理 Windows 盘符：E:\path -> path
        parts = rel_path_str.split(":", 1)
        if len(parts) > 1:
            rel_path_str = parts[1].lstrip("/\\")
            
    # 如果此时还是绝对路径（极少见情况），尝试转为相对路径
    try:
        # 尝试相对于 output 目录解析
        # 假设前端传来的可能是 output/jobs/job-id/runs/run-id
        # 或者 jobs/job-id/runs/run-id
        # 或者 E:\mobile_v4\output\jobs...
        
        # 我们的目标是找到 runs/xxxx 这一层
        path_obj = Path(base_run_dir)
        if path_obj.name.startswith("T-"):
             # 这是一个简单的启发式：如果最后一级目录是以 T- 开头，那它就是我们要找的 run 目录
             base_path = run_root / path_obj.name
        else:
             # 回退到直接拼接
             base_path = run_root / rel_path_str
    except Exception:
        base_path = run_root / rel_path_str

    if not is_within_root(run_root, base_path):
        # Double check: maybe base_run_dir IS the absolute path that is valid?
        # Only allow if it resolves to something inside run_root
        try:
            abs_candidate = Path(base_run_dir).resolve()
            if is_within_root(run_root, abs_candidate):
                base_path = abs_candidate
            else:
                 return err(403, "access denied")
        except Exception:
            return err(403, "access denied")
            
    if not base_path.exists():
        return err(404, f"run_dir not found: {base_path.name}")

    # Handle zip mapping
    if file_path == "zip":
        zip_path = base_path.with_suffix(".zip")
        if not zip_path.exists():
            shutil.make_archive(str(base_path), "zip", str(base_path))
        return FileResponse(str(zip_path), filename=zip_path.name)

    if file_path == "latest_screenshot":
        images_dir = base_path / "images"
        if not images_dir.exists() or not images_dir.is_dir():
            return err(404, "no screenshots yet")
        pngs = sorted(images_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
        if not pngs:
            return err(404, "no screenshots yet")
        latest = pngs[-1]
        return FileResponse(str(latest), filename=latest.name)
    
    # Handle aliases
    aliases = {
        "task_results": "task_results.json",
        "script": "script.json",
        "infopool": "infopool.json",
        "stdout": "terminallog/stdout.log",
        "chat_log": "chat/chat_log.jsonl",
    }
    
    target_path = None
    if file_path in aliases:
        target_path = base_path / aliases[file_path]
    else:
        # Direct path access (e.g. images/screenshot_1.png)
        # Security check: resolve path and ensure it's within base_path
        try:
            requested_path = (base_path / file_path).resolve()
            if not is_within_root(base_path, requested_path):
                return err(403, "access denied")
            target_path = requested_path
        except Exception:
            return err(400, "invalid path")

    if not target_path or not target_path.exists():
        return err(404, "artifact not found")
    
    return FileResponse(str(target_path), filename=target_path.name)


@app.post("/api/v1/config")
def api_config(req: ConfigRequest):
    cfg = read_config()
    for key in ("api_key", "base_url", "model", "summary_api_key", "summary_base_url", "summary_model"):
        value = getattr(req, key, None)
        if value is None:
            continue
        v = str(value).strip()
        if v:
            cfg[key] = v
        else:
            if key in cfg:
                del cfg[key]
    write_config(cfg)
    result = {k: cfg.get(k) for k in ("api_key", "base_url", "model", "summary_api_key", "summary_base_url", "summary_model") if cfg.get(k)}
    return ok(result)


@app.post("/api/v1/upload")
def api_upload(file: UploadFile = File(...)):
    if not file.filename:
        return err(400, "file is required")
    
    filename = file.filename
    suffix = Path(filename).suffix.lower()
    token = str(uuid.uuid4())

    if suffix == ".json":
        # 处理场景脚本
        save_path = SCENARIO_DIR / f"{token}.json"
        with save_path.open("wb") as f:
            f.write(file.file.read())
        return ok({"type": "scenario", "token": token, "filename": filename})
    
    elif suffix == ".apk":
        # 处理 APK 安装包
        save_path = APK_DIR / f"{token}.apk"
        with save_path.open("wb") as f:
            f.write(file.file.read())
        return ok({"type": "apk", "token": token, "filename": filename})
    
    else:
        return err(400, f"unsupported file type: {suffix}. Only .json and .apk are allowed.")


@app.post("/api/v1/upload/scenario")
def api_upload_scenario(file: UploadFile = File(...)):
    if not file.filename:
        return err(400, "file is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix != ".json":
        return err(400, "only .json is supported")
    token = str(uuid.uuid4())
    save_path = SCENARIO_DIR / f"{token}.json"
    with save_path.open("wb") as f:
        f.write(file.file.read())
    return ok({"scenario_token": token, "filename": file.filename})
