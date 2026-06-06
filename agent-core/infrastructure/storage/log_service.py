"""Log persistence service."""
import json
import os
from typing import Any, Dict, Optional

from .file_service import FileService


class LogService:
    def __init__(self, log_dir: str, translator_provider=None, output_lang: str = "en"):
        self.log_dir = log_dir
        self.output_lang = self._normalize_lang(output_lang)
        FileService.ensure_dir(log_dir)

        self.chat_dir = os.path.join(log_dir, "chat")
        self.terminallog_dir = os.path.join(log_dir, "terminallog")
        self.steps_dir = os.path.join(log_dir, "Steps")
        FileService.ensure_dir(self.chat_dir)
        FileService.ensure_dir(self.terminallog_dir)
        FileService.ensure_dir(self.steps_dir)

        self.chat_log_path = os.path.join(self.chat_dir, "chat_log.jsonl")

    def _normalize_lang(self, output_lang: Optional[str]) -> str:
        v = (output_lang or "en").strip().lower()
        if v in ("zh", "ch", "cn", "zh-cn", "zh_hans", "zh-hans"):
            return "zh"
        return "en"

    def append_chat_log(
        self,
        role: str,
        content: str,
        step_id: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "step": step_id,
            "role": role,
            "output": content,
        }
        if extra:
            entry.update(extra)

        with open(self.chat_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False))
            f.write("\n")

    def save_step_message(
        self,
        step_id: int,
        agent_name: str,
        messages: Any,
        response: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        step_dir = os.path.join(self.steps_dir, f"step_{step_id}")
        FileService.ensure_dir(step_dir)

        message_file = os.path.join(step_dir, f"{agent_name}.json")
        message_data = {
            "name": agent_name,
            "messages": messages,
            "response": response,
            "step_id": step_id,
        }
        if extra:
            message_data.update(extra)

        FileService.write_json(message_file, message_data)
        return message_file

    def save_terminal_log(self, content: str) -> str:
        terminal_log_path = os.path.join(self.terminallog_dir, "stdout.log")
        with open(terminal_log_path, "w", encoding="utf-8") as f:
            f.write(content)
        return terminal_log_path
