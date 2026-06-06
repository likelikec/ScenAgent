import os
from typing import Any, Dict, Optional

from .file_service import FileService


class ReportService:
    def __init__(self, translator_provider=None, output_lang: str = "zh"):
        v = (output_lang or "zh").strip().lower()
        self.output_lang = "zh" if v in ("zh", "ch", "cn", "zh-cn", "zh_hans", "zh-hans") else "en"

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
        execution_steps: int = 0,
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
            "test_status_report": test_status_report,
        }
        task_result_data.pop("hit_step_limit", None)
        task_result_data.pop("status_reason", None)
        task_result_data.pop("status_reason_zh", None)
        if token_usage is not None:
            task_result_data["token_usage"] = token_usage
        task_result_data["total_tokens"] = int(total_tokens or 0)
        task_result_data["execution_steps"] = int(execution_steps or 0)
        FileService.write_json(task_result_path, task_result_data)
        return task_result_path

    def save_script_data(self, run_dir: str, total_plan: str, subgoals: list) -> str:
        script_path = os.path.join(run_dir, "script.json")
        FileService.write_json(
            script_path,
            {
                "total_plan": total_plan,
                "subgoals": subgoals,
            },
        )
        return script_path

    def save_infopool_data(
        self,
        run_dir: str,
        plans: list,
        completed_subgoals: list,
        completed_subgoals_summary: list,
        progress: list,
        total_plan: str,
    ) -> str:
        infopool_path = os.path.join(run_dir, "infopool.json")
        infopool_data = {
            "plans": plans,
            "completed_subgoals": completed_subgoals,
            "completed_subgoals_summary": completed_subgoals_summary,
            "progress": progress,
            "total_plan": total_plan,
        }
        FileService.write_json(infopool_path, infopool_data)
        return infopool_path
