import os
from typing import Any, Dict

from .file_service import FileService


class FinalTranslationService:
    def __init__(self, translator_provider):
        self.translator_provider = translator_provider
        self._cache: Dict[str, str] = {}

    def translate_run_dir(self, run_dir: str) -> None:
        if not self.translator_provider or not run_dir or not os.path.isdir(run_dir):
            return
        self._translate_steps(run_dir)
        self._translate_task_results(run_dir)
        self._translate_script(run_dir)

    def _translate(self, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        if t in self._cache:
            return self._cache[t]
        prompt = (
            "Translate to Chinese. Keep JSON, code, filenames/paths, coordinates, adb/hdc commands, "
            "and action names unchanged. Do not add or remove information. Output only the translated text.\n\n"
            f"{t}"
        )
        try:
            out, _, _ = self.translator_provider.predict(prompt)
            translated = (out or "").strip() or t
        except Exception:
            translated = t
        self._cache[t] = translated
        return translated

    def _translate_steps(self, run_dir: str) -> None:
        steps_dir = os.path.join(run_dir, "Steps")
        if not os.path.isdir(steps_dir):
            return
        for step_name in os.listdir(steps_dir):
            step_dir = os.path.join(steps_dir, step_name)
            if not os.path.isdir(step_dir):
                continue
            for file_name in os.listdir(step_dir):
                if not file_name.endswith(".json") or file_name.endswith(".zh.json"):
                    continue
                path = os.path.join(step_dir, file_name)
                data = FileService.read_json(path)
                if not isinstance(data, dict):
                    continue
                zh_data = dict(data)
                zh_data["response"] = self._translate(str(data.get("response") or ""))
                zh_path = os.path.join(step_dir, file_name[:-5] + ".zh.json")
                FileService.write_json(zh_path, zh_data)

    def _translate_task_results(self, run_dir: str) -> None:
        path = os.path.join(run_dir, "task_results.json")
        data = FileService.read_json(path)
        if not isinstance(data, dict):
            return
        report = str(data.get("test_status_report") or "")
        if report:
            data["test_status_report_zh"] = self._translate(report)
            FileService.write_json(path, data)

    def _translate_script(self, run_dir: str) -> None:
        path = os.path.join(run_dir, "script.json")
        data = FileService.read_json(path)
        if not isinstance(data, dict):
            return
        translated_subgoals = []
        for subgoal in data.get("subgoals") or []:
            if isinstance(subgoal, dict):
                item = dict(subgoal)
                item["subgoal"] = self._translate(str(item.get("subgoal") or ""))
                translated_subgoals.append(item)
            else:
                translated_subgoals.append(subgoal)
        zh_data = {
            "total_plan": self._translate(str(data.get("total_plan") or "")),
            "subgoals": translated_subgoals,
        }
        FileService.write_json(os.path.join(run_dir, "script.zh.json"), zh_data)
