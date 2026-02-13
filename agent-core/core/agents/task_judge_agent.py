"""TaskJudge Agent：任务评估Agent"""
import json
import re
from typing import Dict, Any, List, Optional

from .base_agent import BaseMobileAgent
from core.state.state_manager import StateManager
from infrastructure.llm.llm_provider import LLMProvider


class TaskJudgeAgent(BaseMobileAgent):
    """TaskJudge Agent：负责任务完成评估"""

    def get_prompt(self) -> str:
        state = self.state_manager.get_state()
        prompt = (
            "You are an expert evaluator for mobile automation tasks. "
            "Analyze the full execution history and determine whether the task succeeded or failed.\n\n"
        )

        prompt += "### User's Original Request ###\n"
        prompt += f"{state.task.instruction}\n\n"

        if state.task.additional_knowledge_planner:
            prompt += "### Context (Additional Info) ###\n"
            prompt += f"{state.task.additional_knowledge_planner}\n\n"

        prompt += "### Original Plan ###\n"
        if state.planning.completed_plan and state.planning.completed_plan != "No completed subgoal.":
            prompt += f"{state.planning.completed_plan}\n\n"
        else:
            prompt += "No plan information.\n\n"

        prompt += "### Execution History ###\n"
        if state.execution.action_history and len(state.execution.action_history) > 0:
            prompt += "The following are all executed operations:\n"
            for i, (action, summary, outcome, error) in enumerate(
                zip(
                    state.execution.action_history,
                    state.execution.summary_history,
                    state.execution.action_outcomes,
                    state.execution.error_descriptions,
                ),
                1,
            ):
                prompt += f"{i}. Action: {action}\n"
                prompt += f"   Description: {summary}\n"
                if outcome == "S":
                    prompt += "   Result:  Success\n"
                else:
                    prompt += f"   Result:  Fail ({outcome})\n"
                    if error and error.lower() != "none":
                        prompt += f"   Error: {error}\n"
                prompt += "\n"
        else:
            prompt += "No actions executed.\n\n"

        prompt += "### Current Progress ###\n"
        if state.reflection.progress_status:
            prompt += f"{state.reflection.progress_status}\n\n"
        else:
            prompt += "No progress records.\n\n"

        if state.reflection.important_notes:
            prompt += "### Important Notes ###\n"
            prompt += f"{state.reflection.important_notes}\n\n"

        prompt += "---\n"
        prompt += "Based on the above information, evaluate whether the user's request has been successfully completed.\n\n"
        prompt += "Consider:\n"
        prompt += "- Has the execution reached the expected final state?\n"
        prompt += "- Does the execution history satisfy the user's request?\n\n"
        prompt += "Output a single JSON object only, no markdown, no extra text.\n"
        prompt += "Required keys: task_status, status_reason, app_tricks.\n"
        prompt += "task_status must be \"Success\" or \"Failed\" only.\n"
        prompt += "status_reason must be a concise English analysis.\n"
        prompt += (
            "app_tricks must be a JSON array (or [] if none). Each item is an object with:\n"
            "- type: one of [\"Misclick risk\",\"Hidden entry\",\"Critical step\",\"Counterintuitive\"]\n"
            "- title: short title\n"
            "- content: ONE short sentence describing the tip\n"
            "- evidence_steps: array of integers referencing the action indices in Execution History\n"
        )

        return prompt

    def parse_response(self, response: str) -> Dict[str, Any]:
        task_status = ""
        status_reason = ""
        app_tricks: List[Dict[str, Any]] = []

        def _extract_section(text: str, start_marker: str, end_markers: List[str]) -> str:
            start_idx = text.find(start_marker)
            if start_idx < 0:
                return ""
            start_idx += len(start_marker)
            rest = text[start_idx:]
            end_positions = []
            for m in end_markers:
                p = rest.find(m)
                if p >= 0:
                    end_positions.append(p)
            if end_positions:
                rest = rest[: min(end_positions)]
            return rest.strip()

        def _strip_code_fences(s: str) -> str:
            t = (s or "").strip()
            if t.startswith("```"):
                t = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", t)
                t = re.sub(r"\n```$", "", t)
                t = t.strip()
            return t

        def _ensure_trick_item(obj: Any) -> Optional[Dict[str, Any]]:
            if not isinstance(obj, dict):
                return None
            trick_type = str(obj.get("type") or obj.get("kind") or "").strip()
            title = str(obj.get("title") or "").strip()
            content = str(obj.get("content") or obj.get("tip") or "").strip()
            evidence_steps = obj.get("evidence_steps")
            tags = obj.get("tags")

            if not isinstance(tags, list):
                tags = []
            tags = [str(x).strip() for x in tags if str(x).strip()]

            if not isinstance(evidence_steps, list):
                evidence_steps = []
            cleaned_steps = []
            for x in evidence_steps:
                try:
                    cleaned_steps.append(int(x))
                except Exception:
                    continue
            cleaned_steps = [x for x in cleaned_steps if x > 0]

            if not title and content:
                title = content[:32]
            if not title and not content:
                return None

            if trick_type not in [
                "Misclick risk",
                "Hidden entry",
                "Critical step",
                "Counterintuitive",
                "易错点",
                "隐形入口",
                "关键步骤",
                "反常识",
            ]:
                trick_type = ""

            return {
                "type": trick_type,
                "title": title,
                "content": content,
                "tags": tags,
                "evidence_steps": cleaned_steps,
            }

        text = response or ""
        
        # 0. 优先尝试直接提取并解析整个 JSON 对象
        try:
            # 寻找最外层的 {}
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            if first_brace >= 0 and last_brace > first_brace:
                potential_json = text[first_brace : last_brace + 1]
                data = json.loads(potential_json)
                
                # 如果成功解析为字典，尝试提取字段
                if isinstance(data, dict):
                    # 提取 Task Status
                    for k in ["Task Status", "task_status", "TaskStatus", "Status", "status"]:
                        if k in data and isinstance(data[k], str):
                            task_status = data[k]
                            break
                    
                    # 提取 Status Reason
                    for k in ["Status Reason", "status_reason", "StatusReason", "Reason", "reason"]:
                        if k in data and isinstance(data[k], str):
                            status_reason = data[k]
                            break
                            
                    # 提取 App Tricks
                    tricks_data = None
                    for k in ["App Tricks", "app_tricks", "AppTricks", "Tricks", "tricks"]:
                        if k in data:
                            tricks_data = data[k]
                            break
                    
                    if isinstance(tricks_data, list):
                        for it in tricks_data:
                            normalized = _ensure_trick_item(it)
                            if normalized:
                                app_tricks.append(normalized)
                                
                    # 如果成功提取了至少一个关键字段，就直接返回
                    if task_status or status_reason or app_tricks:
                        # 规范化状态
                        normalized_status = (task_status or "").strip()
                        status_lower = normalized_status.lower()
                        if status_lower in ["success", "completed", "成功", "完成"]:
                            normalized_status = "Success"
                        elif status_lower in ["failed", "fail", "失败"]:
                            normalized_status = "Failed"
                            
                        return {
                            "task_status": normalized_status,
                            "status_reason": status_reason,
                            "app_tricks": app_tricks,
                        }
        except Exception:
            # JSON 解析失败，继续尝试后续的文本解析逻辑
            pass

        if "### Task Status ###" in text:
            task_status = _extract_section(
                text,
                "### Task Status ###",
                ["### Status Reason ###", "### App Tricks ###"],
            )
            status_reason = _extract_section(
                text,
                "### Status Reason ###",
                ["### App Tricks ###"],
            )
            tricks_raw = _extract_section(text, "### App Tricks ###", [])
            tricks_raw = _strip_code_fences(tricks_raw)
            if tricks_raw:
                try:
                    loaded = json.loads(tricks_raw)
                    if isinstance(loaded, dict) and isinstance(loaded.get("app_tricks"), list):
                        loaded = loaded.get("app_tricks")
                    if isinstance(loaded, list):
                        for it in loaded:
                            normalized = _ensure_trick_item(it)
                            if normalized:
                                app_tricks.append(normalized)
                except Exception:
                    pass
        else:
            # 宽松匹配 Status
            m = re.search(r"Task\s*Status\s*[:：]\s*(Success|Failed|Completed|成功|失败|完成)", text, flags=re.IGNORECASE)
            if m:
                task_status = m.group(1).strip()
            
            # 宽松匹配 Reason
            m = re.search(
                r"Status\s*Reason\s*[:：]\s*(.+?)(?:\nApp\s*Tricks\s*[:：]|$)",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if m:
                status_reason = " ".join((m.group(1) or "").split())
            else:
                # 如果没找到明确的 Reason 标记，且没有 Status 标记，可能整个文本就是 Reason
                # 但要避免把 App Tricks 当作 Reason
                if "App Tricks" not in text and len(text) < 500:
                     status_reason = text.strip()

            m = re.search(
                r"App\s*Tricks\s*[:：]\s*(.+)$",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if m:
                raw = _strip_code_fences(m.group(1) or "").strip()
                if raw:
                    try:
                        loaded = json.loads(raw)
                        if isinstance(loaded, dict) and isinstance(loaded.get("app_tricks"), list):
                            loaded = loaded.get("app_tricks")
                        if isinstance(loaded, list):
                            for it in loaded:
                                normalized = _ensure_trick_item(it)
                                if normalized:
                                    app_tricks.append(normalized)
                    except Exception:
                        pass

        normalized_status = (task_status or "").strip()
        
        # 状态规范化
        status_lower = normalized_status.lower()
        if status_lower in ["success", "completed", "成功", "完成"]:
            normalized_status = "Success"
        elif status_lower in ["failed", "fail", "失败"]:
            normalized_status = "Failed"
        elif not normalized_status and status_reason:
             # 如果只有 Reason 没有 Status，尝试从 Reason 推断
             if "success" in status_reason.lower() or "completed" in status_reason.lower():
                 normalized_status = "Success"
             elif "fail" in status_reason.lower():
                 normalized_status = "Failed"

        return {
            "task_status": normalized_status,
            "status_reason": status_reason,
            "app_tricks": app_tricks,
        }

