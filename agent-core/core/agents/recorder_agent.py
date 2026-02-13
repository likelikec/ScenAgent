
from typing import Dict, Any
from .base_agent import BaseMobileAgent
from core.state.state_manager import StateManager
from infrastructure.llm.llm_provider import LLMProvider


class RecorderAgent(BaseMobileAgent):
    """Recorder Agent：负责重要信息记录"""

    def get_prompt(self) -> str:
        """Generate note-taking prompt"""
        state = self.state_manager.get_state()
        prompt = "You are an AI assistant capable of operating phones. Your goal is to record important content related to the user's request.\n\n"
        
        prompt += "### User Request ###\n"
        prompt += f"{state.task.instruction}\n\n"
        
        prompt += "### Progress Status ###\n"
        prompt += f"{state.reflection.progress_status}\n\n"
        
        prompt += "### Existing Important Notes ###\n"
        if state.reflection.important_notes != "":
            prompt += f"{state.reflection.important_notes}\n\n"
        else:
            prompt += "No important notes currently.\n\n"
        
        if "transactions" in state.task.instruction and "Simple Gallery" in state.task.instruction:
            prompt += "### Guidelines ###\nYou can only record transaction information in DCIM, because other transactions are not related to the task.\n"
        elif "enter their product" in state.task.instruction:
            prompt += "### Guidelines ###\nPlease record each number that appears, so that their product can be calculated at the end.\n"
        
        prompt += "---\n"
        prompt += "Please carefully examine the above information to identify any important content on the current screen that needs to be recorded.\n"
        prompt += "Important:\nDo not record low-level operations; only track key text or visual information related to the user's request. Do not repeat the user's request or progress status. Do not fabricate content you are uncertain about.\n\n"
        
        prompt += "Please output in the following format:\n"
        prompt += "### Important Notes ###\n"
        prompt += "Updated important notes, combining old notes and new content. If there is no new content to record, copy the existing important notes.\n"
        
        return prompt
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Recorder response"""
        if "### Important Notes ###" in response:
            important_notes = response.split("### Important Notes ###")[-1].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
        else:
            # If Important Notes section is missing, return empty string
            important_notes = ""
        return {"important_notes": important_notes}

