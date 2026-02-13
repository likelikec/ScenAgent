import os
from typing import Optional, Dict, Any
from .file_service import FileService


class ReportService:
    def __init__(self, translator_provider=None, output_lang: str = "zh"):
        self.translator_provider = translator_provider
        v = (output_lang or "zh").strip().lower()
        if v in ("zh", "ch", "cn", "zh-cn", "zh_hans", "zh-hans"):
            self.output_lang = "zh"
        else:
            self.output_lang = "en"
        self._cache: Dict[str, str] = {}
        self._term_map = {
            "component-not-found": "未找到组件",
            "navigation-timeout": "页面导航超时",
            "permission-denied": "权限被拒绝",
            "network-error": "网络错误",
            "unknown-failure": "未知失败"
        }

    def _translate(self, text: str, target_lang: str) -> str:
        key = f"{target_lang}:{text}"
        if key in self._cache:
            return self._cache[key]
        if not text or not self.translator_provider or target_lang not in ("zh", "en"):
            return text or ""
        if text in self._term_map and target_lang == "zh":
            r = self._term_map[text]
            self._cache[key] = r
            return r
        prompt = (
            f"Translate to {('Chinese' if target_lang=='zh' else 'English')} concisely without changing meaning. "
            "Keep any JSON, code, filenames/paths, coordinates, and adb/hdc commands unchanged. "
            "Do not add or remove information. Output only the translated text.\n\n"
            f"{text}"
        )
        try:
            out, _, _ = self.translator_provider.predict(prompt)
            r = (out or "").strip()
        except Exception:
            r = text
        self._cache[key] = r
        return r

    def save_task_results(
        self,
        run_dir: str,
        goal: str,
        start_time: str,
        finish_time: str,
        step_limit: float,
        task_status: str = "",
        test_status_report: str = "",
        token_usage: Optional[Dict[str, Any]] = None,
        total_tokens: int = 0,
        execution_steps: int = 0
    ) -> str:
        task_result_path = os.path.join(run_dir, "task_results.json")
        existing = FileService.read_json(task_result_path) or {}
        task_result_data = {
            **existing,
            "goal": goal,
            "start_dtime": start_time,
            "finish_dtime": finish_time,
            "step_limit": step_limit,
            "task_status": task_status,
            "test_status_report": test_status_report
        }
        if "hit_step_limit" in task_result_data:
            task_result_data.pop("hit_step_limit", None)
        if "status_reason" in task_result_data:
            task_result_data.pop("status_reason", None)
        if "status_reason_zh" in task_result_data:
            task_result_data.pop("status_reason_zh", None)
        if self.output_lang == "zh":
            task_result_data["test_status_report_zh"] = self._translate(test_status_report, "zh")
        if token_usage is not None:
            task_result_data["token_usage"] = token_usage
        task_result_data["total_tokens"] = int(total_tokens or 0)
        task_result_data["execution_steps"] = int(execution_steps or 0)
        FileService.write_json(task_result_path, task_result_data)
        return task_result_path

    def save_script_data(
        self,
        run_dir: str,
        total_plan: str,
        subgoals: list
    ) -> str:
        script_path = os.path.join(run_dir, "script.json")
        if self.output_lang == "zh":
            translated_subgoals = []
            for sg in subgoals or []:
                if isinstance(sg, dict):
                    tsg = dict(sg)
                    if "subgoal" in tsg:
                        tsg["subgoal"] = self._translate(str(tsg.get("subgoal") or ""), "zh")
                    translated_subgoals.append(tsg)
                else:
                    translated_subgoals.append(sg)
            script_data = {
                "total_plan": self._translate(total_plan or "", "zh"),
                "subgoals": translated_subgoals
            }
        else:
            script_data = {
                "total_plan": total_plan,
                "subgoals": subgoals
            }
        FileService.write_json(script_path, script_data)
        return script_path

    def save_infopool_data(
        self,
        run_dir: str,
        plans: list,
        completed_subgoals: list,
        completed_subgoals_summary: list,
        progress: list,
        total_plan: str
    ) -> str:
        infopool_path = os.path.join(run_dir, "infopool.json")
        infopool_data = {
            "plans": plans,
            "completed_subgoals": completed_subgoals,
            "completed_subgoals_summary": completed_subgoals_summary,
            "progress": progress,
            "total_plan": total_plan
        }
        FileService.write_json(infopool_path, infopool_data)
        return infopool_path
