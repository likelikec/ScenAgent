"""日志服务"""
import os
import json
from typing import Optional, Dict, Any
from datetime import datetime
import stat
from .file_service import FileService


class LogService:
    """日志服务类"""
    
    def __init__(self, log_dir: str, translator_provider=None, output_lang: str = "en"):
        """初始化日志服务
        
        Args:
            log_dir: 日志目录路径
        """
        self.log_dir = log_dir
        self.translator_provider = translator_provider
        self.output_lang = (output_lang or "en").strip().lower()
        if self.output_lang in ("ch", "cn", "zh-cn", "zh_hans", "zh-hans"):
            self.output_lang = "zh"
        if self.output_lang != "zh":
            self.output_lang = "en"
        self._translate_cache: Dict[str, str] = {}
        FileService.ensure_dir(log_dir)
        
        # 创建子目录
        self.chat_dir = os.path.join(log_dir, "chat")
        self.terminallog_dir = os.path.join(log_dir, "terminallog")
        self.steps_dir = os.path.join(log_dir, "Steps")
        FileService.ensure_dir(self.chat_dir)
        FileService.ensure_dir(self.terminallog_dir)
        FileService.ensure_dir(self.steps_dir)
        
        # 初始化聊天日志
        self.chat_log_path = os.path.join(self.chat_dir, "chat_log.jsonl")

    def _translate(self, text: str) -> str:
        if self.output_lang != "zh" or not self.translator_provider:
            return text or ""
        t = (text or "").strip()
        if not t:
            return ""
        if t in self._translate_cache:
            return self._translate_cache[t]
        prompt = (
            "Translate to Chinese. Keep any JSON, code, filenames/paths, coordinates, and adb/hdc commands unchanged. "
            "Do not add or remove information. Output only the translated text.\n\n"
            f"{t}"
        )
        try:
            out, _, _ = self.translator_provider.predict(prompt)
            r = (out or "").strip() or t
        except Exception:
            r = t
        self._translate_cache[t] = r
        return r

    def _write_readonly_json(self, file_path: str, data: Dict[str, Any]) -> None:
        if os.path.exists(file_path):
            try:
                os.chmod(file_path, stat.S_IWRITE)
            except Exception:
                pass
        FileService.write_json(file_path, data)
        try:
            os.chmod(file_path, stat.S_IREAD)
        except Exception:
            pass
    
    def append_chat_log(
        self,
        role: str,
        content: str,
        step_id: int,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """追加聊天日志
        
        Args:
            role: 角色（planner, operator, reflector等）
            content: 内容
            step_id: 步骤ID
            extra: 额外信息
        """
        entry = {
            "step": step_id,
            "role": role,
            "output": content
        }
        if extra:
            entry.update(extra)
        
        with open(self.chat_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False))
            f.write("\n")
    
    def save_step_message(
        self,
        step_id: int,
        agent_name: str,
        messages: Any,
        response: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> str:
        """保存步骤消息
        
        Args:
            step_id: 步骤ID
            agent_name: Agent名称
            messages: 消息历史
            response: 响应内容
            extra: 额外信息
            
        Returns:
            保存的文件路径
        """
        step_dir = os.path.join(self.steps_dir, f"step_{step_id}")
        FileService.ensure_dir(step_dir)
        
        message_file = os.path.join(step_dir, f"{agent_name}.json")
        message_data = {
            "name": agent_name,
            "messages": messages,
            "response": response,
            "step_id": step_id
        }
        if extra:
            message_data.update(extra)
        
        FileService.write_json(message_file, message_data)
        if self.output_lang == "zh":
            zh_file = os.path.join(step_dir, f"{agent_name}.zh.json")
            zh_data = {
                **message_data,
                "response": self._translate(response),
            }
            self._write_readonly_json(zh_file, zh_data)
        return message_file
    
    def save_terminal_log(self, content: str) -> str:
        """保存终端日志
        
        Args:
            content: 日志内容
            
        Returns:
            保存的文件路径
        """
        terminal_log_path = os.path.join(self.terminallog_dir, "stdout.log")
        with open(terminal_log_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return terminal_log_path

