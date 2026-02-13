
from typing import Dict, Any
from .base_agent import BaseMobileAgent
from core.state.state_manager import StateManager
from infrastructure.llm.llm_provider import LLMProvider


class PathSummarizerAgent(BaseMobileAgent):
    """PathSummarizer Agent：负责路径摘要"""
    
    def get_prompt(self) -> str:
        """Generate path summary prompt"""
        state = self.state_manager.get_state()
        prompt = "You are a mobile automation path analysis expert. Based on the following completed goal history, generate a concise summary while preserving key details:\n\n"
        
        prompt += "### Completed Goal History ###\n"
        prompt += f"{state.planning.completed_plan}\n\n"
        
        prompt += "### Core Instructions ###\n"
        prompt += "1. Merge consecutive identical/similar operations (e.g., multiple 'scroll down' → 'scroll down multiple times');\n"
        prompt += "2. Summarize completed unsuccessful exploration paths (enter page → multiple operations → target not found → return) into one sentence;\n"
        prompt += "3. **Critical**: When summarizing unsuccessful exploration paths, you must identify and explicitly mark explored entry components/entry points. Use the format: [Explored Component: \"component_name\", \"summary of operation description\"] to mark components that have been explored but did not find the target. **This tells the planning agent not to try this entry point again.**\n"
        prompt += "4. Only process completely finished paths (already returned); keep ongoing explorations (not returned) steps unchanged;\n"
        prompt += "5. Preserve normal navigation (e.g., 'click xxx to enter xxx page') and successful operations without modification.\n\n"
        
        prompt += "### Unsuccessful Exploration Example ###\n"
        prompt += "Original: 1. Click Playback Settings to enter Playback Settings page 2. Scroll down the page 3. Continue scrolling down 4. Continue scrolling 5. Return to previous menu 6. Click Settings to enter Settings page\n"
        prompt += "Summary: 1. [Explored Component: \"Playback Settings\", scrolled multiple times in Playback Settings page (target not found), returned to previous menu.] 2. Click Settings to enter Settings page\n\n"
        prompt += "**Explanation**: [Explored Component: \"Playback Settings\", scrolled multiple times in Playback Settings page (target not found), returned to previous menu.], indicates that the \"Playback Settings\" entry point has been explored but did not lead to the target. Should not plan to enter \"Playback Settings\" again to search for the same target.\n\n"
        
        prompt += "### Output Format ###\n"
        prompt += "### Summary ###\n"
        prompt += "A concise summary of the completed goal history generated following the above instructions."
        
        return prompt
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse PathSummarizer response"""
        if "### Summary ###" in response:
            summary = response.split("### Summary ###")[-1].replace("\n", " ").replace("###", "").replace("  ", " ").strip()
        else:
            # If Summary section is missing, use the entire response as fallback
            summary = response.strip()
        return {"summary": summary}

