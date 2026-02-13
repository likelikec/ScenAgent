"""主入口：简化版，只负责参数解析和Orchestrator调用"""
import os
import sys

# 强制刷新输出
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("Main process starting...", flush=True)

import json
import time
import argparse
import subprocess
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

# 添加 agent-core 到 Python 路径（核心代码在 agent-core 下）
project_root = os.path.dirname(os.path.abspath(__file__))
agent_core_root = os.path.join(project_root, "agent-core")
if os.path.isdir(agent_core_root) and agent_core_root not in sys.path:
    sys.path.insert(0, agent_core_root)

# 导入新架构的组件
from infrastructure.llm.llm_factory import LLMFactory
from infrastructure.device.android_controller import AndroidController
from infrastructure.device.harmonyos_controller import HarmonyOSController
from infrastructure.storage.log_service import LogService
from infrastructure.storage.report_service import ReportService
from services.screenshot_service import ScreenshotService
from services.action_service import ActionService
from services.coordinate_service import CoordinateService
from core.state.state_manager import StateManager
from core.orchestration.task_orchestrator import TaskOrchestrator
from infrastructure.storage.excel_report import write_report_for_run
from config.settings import resolve_summary_llm_params, resolve_print_device_cmd


class StreamTee:
    def __init__(self, *targets):
        self.targets = targets

    def write(self, data):
        text = data if isinstance(data, str) else str(data)
        for target in self.targets:
            try:
                target.write(text)
            except UnicodeEncodeError:
                enc = getattr(target, "encoding", None) or "utf-8"
                try:
                    safe = text.encode(enc, errors="replace").decode(enc, errors="replace")
                except Exception:
                    safe = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                target.write(safe)
        self.flush()

    def flush(self):
        for target in self.targets:
            target.flush()


_LAST_RUN_DIR = None


def _sanitize_name(s: str) -> str:
    """清理名称，移除非法字符"""
    invalid = '<>:"/\\|?*'
    r = ''.join(ch for ch in (s or "") if ch not in invalid)
    r = r.strip()
    if len(r) == 0:
        r = "Unknown"
    return r


def _normalize_output_lang(output_lang: Optional[str]) -> str:
    v = (output_lang or "").strip().lower()
    if v in ("zh", "ch", "cn", "zh-cn", "zh_hans", "zh-hans"):
        return "zh"
    return "en"


def _load_tricks_hint(log_path: str, app_name: Optional[str], max_items: int = 6) -> str:
    if not app_name:
        return ""
    try:
        from infrastructure.storage.file_service import FileService
    except Exception:
        return ""

    tricks_path = os.path.join(log_path, "tricks.json")
    data = FileService.read_json(tricks_path) or {}
    if not isinstance(data, dict):
        return ""

    bucket = data.get(app_name)
    if not isinstance(bucket, list) or len(bucket) == 0:
        return ""

    lines = []
    for it in reversed(bucket):
        if not isinstance(it, dict):
            continue
        trick_type = str(it.get("type") or "").strip()
        title = str(it.get("title") or "").strip()
        content = str(it.get("content") or "").strip()
        if not title and not content:
            continue
        head = ""
        if trick_type and title:
            head = f"{trick_type}: {title}"
        elif title:
            head = title
        elif trick_type:
            head = trick_type
        if head and content:
            lines.append(f"- {head}: {content}")
        elif head:
            lines.append(f"- {head}")
        else:
            lines.append(f"- {content}")
        if len(lines) >= int(max_items or 0):
            break

    if len(lines) == 0:
        return ""
    return "Long-term memory (from previous runs, may be outdated):\n" + "\n".join(lines)


def resolve_app(scenario_data: dict, app_id: Optional[str]) -> dict:
    apps = scenario_data.get("apps") or []
    if not apps:
        raise ValueError("apps not found in scenario_file")
    if app_id:
        for a in apps:
            if a.get("id") == app_id:
                return a
        print(f"Warning: app_id not found: {app_id}, fallback to first app")
    return apps[0]


def resolve_scenarios(
    scenario_data: dict,
    start_id: Optional[str],
    end_id: Optional[str],
    specific_id: Optional[str],
) -> list:
    scenarios = scenario_data.get("scenarios") or []
    if not scenarios:
        raise ValueError("scenarios not found in scenario_file")

    if specific_id:
        selected = [s for s in scenarios if s.get("id") == specific_id]
        if len(selected) == 0:
            raise ValueError("scenario_id not found")
        return selected

    if start_id or end_id:
        ids = [s.get("id") for s in scenarios]
        start_idx = 0
        end_idx = len(scenarios) - 1
        if start_id:
            if start_id in ids:
                start_idx = ids.index(start_id)
            else:
                raise ValueError("scenario_start_id not found")
        if end_id:
            if end_id in ids:
                end_idx = ids.index(end_id)
            else:
                raise ValueError("scenario_end_id not found")
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
        return scenarios[start_idx : end_idx + 1]

    return scenarios


def _launch_app(app_pkg: str, app_activity: str, hdc_path: Optional[str] = None, adb_path: Optional[str] = None, device_id: Optional[str] = None) -> None:
    """启动应用"""
    if app_pkg and app_activity:
        print(f"Launching APP: {app_pkg}/{app_activity}")
        if hdc_path:
            # HarmonyOS
            subprocess.run(
                hdc_path + f" shell aa terminate -n {app_pkg}/{app_activity}",
                capture_output=True, text=True, shell=True
            )
            cmd = hdc_path + f" shell aa start -n {app_pkg}/{app_activity}"
        else:
            # Android
            adb_bin = adb_path or "adb"
            if device_id:
                adb_bin = f"{adb_bin} -s {device_id}"
            subprocess.run(
                adb_bin + f" shell am force-stop {app_pkg}",
                capture_output=True, text=True, shell=True
            )
            cmd = adb_bin + f" shell am start -W -S -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {app_pkg}/{app_activity}"
        
        print(f"Exec: {cmd}")
        res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if res.stdout:
            print(f"[Launch Output] {res.stdout.strip()}")
        if res.stderr:
            print(f"[Launch Error] {res.stderr.strip()}")
        time.sleep(3)


def run_instruction(
    adb_path: Optional[str],
    hdc_path: Optional[str],
    api_key: str,
    base_url: str,
    model: str,
    summary_api_key: Optional[str],
    summary_base_url: Optional[str],
    summary_model: Optional[str],
    output_lang: str,
    instruction: str,
    add_info: str,
    coor_type: str,
    if_notetaker: bool,
    run_dir: Optional[str] = None,
    print_device_cmd: Optional[bool] = None,
    perception_mode: str = "vllm",
    max_step: int = 25,
    log_path: str = "./output",
    scenario_name: Optional[str] = None,
    app_name: Optional[str] = None,
    planner_tricks: str = "off",
    planner_tricks_topk: int = 6,
    reflector_tree_check: str = "off",
    task_judge: str = "on",
    device_id: Optional[str] = None,
) -> str:
    """运行指令（重构后的版本）
    
    Args:
        adb_path: ADB路径
        hdc_path: HDC路径
        api_key: API密钥
        base_url: API基础URL
        model: 模型名称
        instruction: 任务指令
        add_info: 额外信息
        coor_type: 坐标类型
        if_notetaker: 是否启用Notetaker
        perception_mode: 感知模式 ("vllm" 或 "som")
        max_step: 最大步数
        log_path: 日志路径
        scenario_name: 场景名称
        app_name: 应用名称
        device_id: 设备序列号
        
    Returns:
        运行目录路径
    """
    if adb_path and hdc_path:
        raise ValueError("adb_path and hdc_path cannot be provided at the same time. Please specify only one of them.")
    output_lang = _normalize_output_lang(output_lang)
    effective_print_device_cmd = resolve_print_device_cmd(print_device_cmd)
    
    if run_dir:
        save_path = os.path.abspath(run_dir)
        os.makedirs(save_path, exist_ok=True)
        log_path = os.path.dirname(save_path)
    else:
        if not os.path.exists(log_path):
            os.mkdir(log_path)
        start_time = datetime.now()
        time_str = start_time.strftime("%Y%m%d_%H%M%S")
        safe_app = _sanitize_name(app_name)
        safe_sce = _sanitize_name(scenario_name)
        save_path = os.path.join(log_path, f"T-{safe_app}-{safe_sce}-{time_str}")
        os.mkdir(save_path)
    
    global _LAST_RUN_DIR
    _LAST_RUN_DIR = save_path
    
    # 创建设备控制器
    if hdc_path:
        device_controller = HarmonyOSController(hdc_path, print_device_cmd=effective_print_device_cmd)
    else:
        device_controller = AndroidController(adb_path, device_id=device_id, print_device_cmd=effective_print_device_cmd)
    
    screenshot_service = ScreenshotService(device_controller, os.path.join(save_path, "images"), perception_mode)
    coordinate_service = CoordinateService()
    action_service = ActionService(device_controller, coordinate_service, perception_mode)
    
    # 创建LLM提供者
    llm_provider = LLMFactory.create(
        provider_type="gui_owl",  # 使用原有实现保持兼容
        api_key=api_key,
        base_url=base_url,
        model_name=model
    )
    
    # 创建摘要LLM提供者
    summary_params = resolve_summary_llm_params(
        vllm_api_key=api_key,
        vllm_base_url=base_url,
        vllm_model_name=model,
        summary_api_key=summary_api_key,
        summary_base_url=summary_base_url,
        summary_model_name=summary_model,
    )
    effective_summary_api_key = summary_params.get("api_key") or api_key
    effective_summary_base_url = summary_params.get("base_url") or base_url
    effective_summary_model = summary_params.get("model_name") or model
    default_summary_temperature = summary_params.get("temperature", 0.0)
    default_summary_max_retry = summary_params.get("max_retry", 10)
    if (
        effective_summary_api_key == api_key
        and effective_summary_base_url == base_url
        and effective_summary_model == model
    ):
        summary_llm_provider = llm_provider
    else:
        summary_llm_provider = LLMFactory.create(
            provider_type="gui_owl",
            api_key=effective_summary_api_key,
            base_url=effective_summary_base_url,
            model_name=effective_summary_model,
            temperature=float(default_summary_temperature or 0.0),
            max_retry=int(default_summary_max_retry or 10),
        )
    log_service = LogService(save_path, translator_provider=summary_llm_provider, output_lang=output_lang)
    report_service = ReportService(translator_provider=summary_llm_provider, output_lang=output_lang)
    
    # 创建状态管理器
    state_manager = StateManager()
    state_manager.set_instruction(instruction)
    if scenario_name:
        state_manager.set_task_name(scenario_name)
    tricks_hint = ""
    topk = int(planner_tricks_topk or 0)
    if (planner_tricks or "").strip().lower() != "off" and topk > 0:
        tricks_hint = _load_tricks_hint(log_path, app_name, max_items=topk)
    if tricks_hint:
        if (add_info or "").strip():
            add_info = add_info.strip() + "\n\n" + tricks_hint
        else:
            add_info = tricks_hint
    state_manager.set_additional_knowledge(planner=add_info)

    enable_tree_stagnation_check = (reflector_tree_check or "").strip().lower() == "on"
    print(f"Reflector tree stagnation check: {'ON' if enable_tree_stagnation_check else 'OFF'}")
    
    # 创建任务编排器
    orchestrator = TaskOrchestrator(
        llm_provider=llm_provider,
        summary_llm_provider=summary_llm_provider,
        device_controller=device_controller,
        log_service=log_service,
        report_service=report_service,
        screenshot_service=screenshot_service,
        action_service=action_service,
        state_manager=state_manager,
        coor_type=coor_type,
        enable_notetaker=if_notetaker,
        enable_task_judge=(str(task_judge).strip().lower() == "on"),
        perception_mode=perception_mode,
        enable_tree_stagnation_check=enable_tree_stagnation_check,
    )
    
    # 运行任务
    return orchestrator.run(instruction, max_step)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Run Mobile-Agent-v4 with LangChain architecture"
    )
    parser.add_argument("--adb_path", type=str)
    parser.add_argument("--hdc_path", type=str)
    parser.add_argument("--api_key", type=str)
    parser.add_argument("--base_url", type=str)
    parser.add_argument("--model", type=str)
    parser.add_argument("--summary_api_key", type=str)
    parser.add_argument("--summary_base_url", type=str)
    parser.add_argument("--summary_model", type=str)
    parser.add_argument("--coor_type", type=str, default="qwen-vl")
    parser.add_argument("--notetaker", type=bool, default=False)
    parser.add_argument("--perception_mode", type=str, choices=["vllm", "som"], default="vllm", 
                        help="Perception mode: 'vllm' for direct explore mode, 'som' for Set-of-Mark mapping(Debug mode)")
    parser.add_argument("--output_lang", type=str, choices=["zh", "ch", "en"], default="zh")
    parser.add_argument("--print_device_cmd", type=bool, default=True)
    parser.add_argument("--scenario_file", type=str)
    parser.add_argument("--app_id", type=str)
    parser.add_argument("--scenario_id", type=str)
    parser.add_argument("--scenario_start_id", type=str)
    parser.add_argument("--scenario_end_id", type=str)
    parser.add_argument("--run_config", type=str)
    parser.add_argument("--run_dir", type=str)
    parser.add_argument("--run_dir_prefix", type=str)
    parser.add_argument("--device_id", type=str)
    parser.add_argument("--planner_tricks", type=str, choices=["on", "off"], default="off")
    parser.add_argument("--planner_tricks_topk", type=int, default=0)
    parser.add_argument("--reflector_tree_check", type=str, choices=["on", "off"], default="off")
    parser.add_argument("--task_judge", type=str, choices=["on", "off"], default="off")
    args = parser.parse_args()
    
    scenario_path = args.scenario_file
    if not scenario_path:
        default_path = os.path.join(os.path.dirname(__file__), "test.json")
        if os.path.exists(default_path):
            scenario_path = default_path
    
    if scenario_path and os.path.exists(scenario_path):
        with open(scenario_path, 'r', encoding='utf-8') as f:
            scenario_data = json.load(f)
        
        print("Initializing Environment")
        execution_plan = []
        if args.run_config:
            run_config_raw = args.run_config
            try:
                if os.path.exists(run_config_raw):
                    with open(run_config_raw, "r", encoding="utf-8") as f:
                        run_config = json.load(f)
                else:
                    run_config = json.loads(run_config_raw)
            except Exception as exc:
                raise ValueError("--run_config must be a JSON string or a JSON file path") from exc
            if not isinstance(run_config, list):
                raise ValueError("--run_config must be a JSON array")
            for item in run_config:
                if not isinstance(item, dict):
                    raise ValueError("--run_config items must be JSON objects")
                item_app_id = item.get("app_id")
                if not item_app_id:
                    raise ValueError("--run_config item missing app_id")
                app_info = resolve_app(scenario_data, item_app_id)
                selected_scenarios = resolve_scenarios(
                    scenario_data,
                    item.get("start_id"),
                    item.get("end_id"),
                    item.get("specific_id") or item.get("scenario_id"),
                )
                app_name = app_info.get("name") or ""
                print(f"Starting execution for App: {app_name} ({item_app_id}) with {len(selected_scenarios)} scenarios.")
                for sc in selected_scenarios:
                    execution_plan.append((item_app_id, app_info, sc))
        else:
            app_info = resolve_app(scenario_data, args.app_id)
            app_id = args.app_id or app_info.get("id")
            selected_scenarios = resolve_scenarios(
                scenario_data,
                args.scenario_start_id,
                args.scenario_end_id,
                args.scenario_id,
            )
            app_name = app_info.get("name") or ""
            print(f"Starting execution for App: {app_name} ({app_id}) with {len(selected_scenarios)} scenarios.")
            for sc in selected_scenarios:
                execution_plan.append((app_id, app_info, sc))

        total_runs = len(execution_plan)
        multi_run = total_runs > 1

        run_dir_base = None
        if args.run_dir_prefix:
            run_dir_base = args.run_dir_prefix
        elif args.run_dir and multi_run:
            run_dir_base = args.run_dir

        for idx, (current_app_id, current_app, sc) in enumerate(execution_plan):
            app_name = current_app.get("name")
            app_pkg = current_app.get("package")
            app_activity = current_app.get("launch-activity")
            _launch_app(app_pkg, app_activity, args.hdc_path, args.adb_path, device_id=args.device_id)
            instruction_text = sc.get('description', '')
            extra_info = sc.get('extra-info', {})
            # Handle case where extra-info might be a string instead of dict
            if isinstance(extra_info, str):
                add_info_value = extra_info
            elif isinstance(extra_info, dict):
                add_info_value = extra_info.get('value')
                if add_info_value is None:
                    try:
                        add_info_value = json.dumps(extra_info, ensure_ascii=False)
                    except Exception:
                        add_info_value = ""
            else:
                add_info_value = ""
            composed_add_info = add_info_value
            if app_name:
                composed_add_info = f"Target app: {app_name}. Extra: {add_info_value}".strip()
            
            run_dir = None
            run_error = None
            effective_run_dir = None
            if run_dir_base:
                safe_app = _sanitize_name(app_name)
                safe_sce = _sanitize_name(sc.get('name') or instruction_text)
                safe_case = _sanitize_name(str(sc.get('id') or f"idx_{idx + 1}"))
                effective_run_dir = os.path.join(run_dir_base, f"T-{safe_app}-{safe_sce}-{safe_case}")
            elif args.run_dir and not multi_run:
                effective_run_dir = args.run_dir

            terminal_log_file = None
            terminal_log_path = None
            if effective_run_dir:
                run_dir_candidate = os.path.abspath(effective_run_dir)
                terminallog_dir = os.path.join(run_dir_candidate, "terminallog")
                os.makedirs(terminallog_dir, exist_ok=True)
                terminal_log_path = os.path.join(terminallog_dir, "stdout.log")
                terminal_log_file = open(terminal_log_path, 'w', encoding='utf-8')

            buffer = io.StringIO()
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            if terminal_log_file:
                sys.stdout = StreamTee(original_stdout, buffer, terminal_log_file)
                sys.stderr = StreamTee(original_stderr, buffer, terminal_log_file)
            else:
                sys.stdout = StreamTee(original_stdout, buffer)
                sys.stderr = StreamTee(original_stderr, buffer)
            try:
                run_dir = run_instruction(
                    args.adb_path,
                    args.hdc_path,
                    args.api_key,
                    args.base_url,
                    args.model,
                    args.summary_api_key,
                    args.summary_base_url,
                    args.summary_model,
                    args.output_lang,
                    instruction_text,
                    composed_add_info,
                    args.coor_type,
                    args.notetaker,
                    effective_run_dir,
                    args.print_device_cmd,
                    args.perception_mode,
                    scenario_name=sc.get('name') or instruction_text,
                    app_name=app_name,
                    planner_tricks=args.planner_tricks,
                    planner_tricks_topk=args.planner_tricks_topk,
                    reflector_tree_check=args.reflector_tree_check,
                    task_judge=args.task_judge,
                    device_id=args.device_id,
                )
            except Exception as exc:
                run_error = exc
                run_dir = _LAST_RUN_DIR
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                if terminal_log_file:
                    terminal_log_file.flush()
                    terminal_log_file.close()

            if run_dir and not terminal_log_file:
                terminallog_dir = os.path.join(run_dir, "terminallog")
                os.makedirs(terminallog_dir, exist_ok=True)
                terminal_log_path = os.path.join(terminallog_dir, "stdout.log")
                with open(terminal_log_path, 'w', encoding='utf-8') as terminal_log_file_fallback:
                    terminal_log_file_fallback.write(buffer.getvalue())
            buffer.close()
            
            if run_error:
                raise run_error
            
            write_report_for_run(
                run_dir,
                scenario_path,
                current_app_id,
                sc.get('id'),
                output_lang=args.output_lang,
                vllm_api_key=args.api_key,
                vllm_base_url=args.base_url,
                vllm_model_name=args.model,
                summary_api_key=args.summary_api_key,
                summary_base_url=args.summary_base_url,
                summary_model_name=args.summary_model,
            )
            time.sleep(2)
    else:
        raise ValueError("scenario_file not found")
