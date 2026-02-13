
from typing import Dict, Any
from .base_agent import BaseMobileAgent
from core.state.state_manager import StateManager
from infrastructure.llm.llm_provider import LLMProvider


class ReflectorAgent(BaseMobileAgent):
    """Reflector Agent：负责操作结果评估"""
    
    def get_prompt(self) -> str:
        """Generate reflection prompt"""
        state = self.state_manager.get_state()
        prompt = "You are an intelligent agent that can operate Android phones on behalf of users. Your goal is to verify whether the previous operation produced the expected behavior and track overall progress.\n\n"
        
        prompt += "### User Request ###\n"
        prompt += f"{state.task.instruction}\n\n"
        
        prompt += "### Progress Status ###\n"
        if state.planning.completed_plan_summary != "":
            prompt += f"{state.planning.completed_plan_summary}\n\n"
        else:
            prompt += "No progress yet.\n\n"
        
        prompt += "---\n"
        prompt += "The two attached images are screenshots of the phone before and after your previous operation.\n"
        
        prompt += "---\n"
        prompt += "### Latest Operation ###\n"
        prompt += f"Action: {state.execution.last_action}\n"
        prompt += f"Expectation: {state.execution.last_summary}\n\n"
        
        prompt += "---\n"
        prompt += "Please carefully examine the above information to determine whether the previous operation produced the expected behavior. If the operation succeeded, please update the progress status accordingly. If the operation failed, identify the failure pattern and provide reasoning about the potential causes that led to this failure.\n\n"
        prompt += "Note: For operations that swipe the screen to view more content, if the content displayed before and after the swipe is exactly the same, then consider the swipe operation as S: Partially successful. The previous operation did not produce any changes. This may be because the content has already been scrolled to the bottom.\n"
        prompt += "Note: If the previous step was an 'answer' action and the content meets expectations, directly mark it as S, because this action usually does not change the screen state.\n\n"
        
        prompt += "Please output in the following format containing two parts:\n"
        prompt += "### Outcome ###\n"
        prompt += "Choose from the following options. You must answer with an English letter: \"S\", \"B\", or \"C\":\n"
        prompt += "S: Success or partial success. The result of the previous operation meets expectations.\n"
        prompt += "B: Failed. The previous operation led to entering the wrong page. I need to return to the previous state.\n"
        prompt += "C: Failed. The previous operation did not produce any changes.\n\n"
        
        prompt += "### Error Description ###\n"
        prompt += "If the operation failed, please describe the error in detail and the potential causes that led to this failure. If the operation succeeded, please fill in \"None\" here.\n"
        
        return prompt
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Reflector response"""
        if "### Outcome ###" in response:
            if "### Error Description ###" in response:
                outcome = response.split("### Outcome ###")[-1].split("### Error Description ###")[0].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
                error_description = response.split("### Error Description ###")[-1].replace("\n", " ").replace("###", "").replace("  ", " ").strip()
            else:
                outcome = response.split("### Outcome ###")[-1].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
                error_description = ""
        else:
            # If Outcome section is missing, return empty values
            outcome = ""
            error_description = ""
        
        return {"outcome": outcome, "error_description": error_description}

