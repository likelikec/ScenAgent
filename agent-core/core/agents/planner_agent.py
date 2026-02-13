"""Planner Agent：规划Agent"""
from typing import Dict, Any
import re
from .base_agent import BaseMobileAgent
from core.state.state_manager import StateManager
from infrastructure.llm.llm_provider import LLMProvider


class PlannerAgent(BaseMobileAgent):
    """Planner Agent：负责任务规划和管理"""
    
    def get_prompt(self) -> str:
        state = self.state_manager.get_state()
        prompt = "You are an intelligent agent that can operate Android phones on behalf of users. Your goal is to understand the user's ultimate true intent, strictly track task progress, and create a high-level plan that starts from the current page, is executable, and can achieve the goal.\n\n"
        prompt += "### User Instruction ###\n"
        prompt += f"{state.task.instruction}\n\n"
        
        task_specific_note = ""
        if ".html" in state.task.instruction:
            task_specific_note = "Note: .html files may contain interactive elements (such as drawing canvases or games). Do not open other applications before the .html file task is completed."
        elif "Audio Recorder" in state.task.instruction:
            task_specific_note = "Note: The stop recording icon is a white square, located at the 4th position from left to right at the bottom. Do not click the circular pause icon in the middle."
        
        if state.planning.plan == "":
            # Initial planning
            prompt += "---\n"
            prompt += "Please create a high-level plan to complete the user's request. If the request is complex, break it down into several subgoals. The current screenshot shows the initial state of the phone.\n"
            prompt += "Important: For requests that clearly require an answer, you must add 'Execute the `answer` action' as the last step of the plan! All step descriptions in the plan (e.g., 'click xxx', 'input xxx') must be in English.\n\n"
            if task_specific_note != "":
                prompt += f"{task_specific_note}\n\n"
            
            prompt += "### Guidelines ###\n"
            prompt += "The following guidelines will help you with planning.\n"
            prompt += "General:\n"
            prompt += "If applicable, use the search function to quickly locate files or entries with specific names. User instructions may contain errors, be incomplete, or be misremembered when describing page names, button text, or path structures. However, the user's ultimate goal is usually correct and needs to be achieved.\n"
            prompt += "For drag-and-drop operations (e.g., moving an icon or list item), do NOT decompose it into 'Long-press' and 'Drag' steps. Instead, describe it as a single 'Drag' step (e.g., 'Drag the \"Paris\" entry to the top').\n"
            prompt += "Task-specific Guidelines:\n"
            if state.task.additional_knowledge_planner != "":
                prompt += f"{state.task.additional_knowledge_planner}\n\n"
                prompt += "If extra-info provides 'Prerequisites', first output a plan for fulfilling the prerequisites.\n "
                prompt += "If it provides 'Key Information', you MUST explicitly incorporate these specific steps or logic into your plan, as they describe critical business rules or hidden paths (e.g., 'Click the hidden menu on the top right').\n"
                prompt += "If it provides 'Input Data', treat the key-value pairs inside it as required input. When the plan involves filling forms or searching, use these exact values corresponding to their keys.\n\n"
            
            else:
                prompt += f"{state.task.add_info_token}\n\n"
            
            prompt += "Please output in the following format, containing two parts:\n"
            prompt += "### Thought ###\n"
            prompt += "Use English to explain in detail the reasoning behind your plan and the breakdown of subgoals.\n\n"
            prompt += "### Plan ###\n"
            prompt += "Use a numbered list starting from 1. Each step should be on a separate line, formatted as 'n. step'. Do not use '-' items or merge multiple steps into one line.\n"
            prompt += "1. First subgoal\n"
            prompt += "2. Second subgoal\n"
            prompt += "...\n"

        else:
            # Subsequent planning
            if state.planning.completed_plan_summary != "" and state.planning.completed_plan_summary != "No completed subgoal.":
                prompt += "### Completed Subgoals ###\n"
                prompt += "Completed operation records:\n"
                prompt += f"{state.planning.completed_plan_summary}\n\n"
                prompt += "**CRITICAL!!!**: If the above history contains [Explored Component: \"component_name\", \"operation_description\"] markers, this indicates that the entry point has been explored but did not reach the goal. You must NOT include these marked components in the new plan! For example, if [Explored Component: \"Playback Settings\"] appears, do not plan to enter \"Playback Settings\" again; instead, try alternative paths or entry points that have not been marked as explored.\n\n"
            
            prompt += "### Plan-Guard (must obey, temporary) ###\n"
            prompt += "Before outputting the updated plan, scan the plan for any entry points marked as [Explored Component: \"...\"] in Completed Subgoals. If your plan includes any explored component as an entry point for the same goal, you must revise the plan to use a different path.\n"
            prompt += "If the task appears stuck on the same page (repeated failures), revise the plan to change the approach (e.g., use search, go back, open a different menu) instead of repeating the same entry step.\n\n"
            
            prompt += "### Plan ###\n"
            prompt += f"{state.planning.plan}\n\n"
            prompt += f"### Last Action ###\n"
            prompt += f"{state.execution.last_action}\n\n"
            prompt += f"### Last Action Description ###\n"
            prompt += f"{state.execution.last_summary}\n\n"
            prompt += "### Important Notes ###\n"
            if state.reflection.important_notes != "":
                prompt += f"{state.reflection.important_notes}\n\n"
            else:
                prompt += "No important notes currently.\n\n"
            prompt += "### Guidelines ###\n"
            prompt += "The following guidelines will help you with planning.\n"
            prompt += "General:\n"
            prompt += "If applicable, use the search function to quickly locate files or entries with specific names.\n"
            prompt += "For drag-and-drop operations (e.g., moving an icon or list item), do NOT decompose it into 'Long-press' and 'Drag' steps. Instead, describe it as a single 'Drag' step (e.g., 'Drag the \"Paris\" entry to the top').\n"
            prompt += "Task-specific Guidelines:\n"
            if state.task.additional_knowledge_planner != "":
                prompt += f"{state.task.additional_knowledge_planner}\n\n"
                prompt += "If extra-info provides 'Prerequisites', first output a plan for fulfilling the prerequisites.\n "
                prompt += "If it provides 'Key Information', you MUST explicitly incorporate these specific steps or logic into your plan, as they describe critical business rules or hidden paths (e.g., 'Click the hidden menu on the top right').\n"
                prompt += "If it provides 'Input Data', treat the key-value pairs inside it as required input. When the plan involves filling forms or searching, use these exact values corresponding to their keys.\n\n"
           
            else:
                prompt += f"{state.task.add_info_token}\n\n"
            
            if state.planning.error_flag_plan:
                prompt += "### Task Potentially Stuck! ###\n"
                prompt += "You have encountered consecutive failures. The following are recent failure logs:\n"
                k = state.planning.err_to_planner_thresh
                recent_actions = state.execution.action_history[-k:]
                recent_summaries = state.execution.summary_history[-k:]
                recent_err_des = state.execution.error_descriptions[-k:]
                for i, (act, summ, err_des) in enumerate(zip(recent_actions, recent_summaries, recent_err_des)):
                    prompt += f"- Attempt: Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"
            
            prompt += "---\n"
            prompt += "Please carefully evaluate the current state and the provided screenshot, and check whether the existing plan needs revision. Determine whether the user's request has been fully completed; if you are certain that no further actions are needed, mark the plan as \"Finished\" in your output. **Note: The \"Finished\" marker must be strictly in English, do not translate it to Chinese.** If not yet completed, please update the plan. If blocked by errors, think step by step about whether a comprehensive revision of the plan is needed to resolve the errors.\n"
            prompt += "Instructions: 1) If the current situation hinders the original plan or requires user clarification, make reasonable assumptions without violating the context and revise the plan accordingly; 2) If the first subgoal in the plan has been completed, update the plan in time based on the screenshot and progress, ensuring the next subgoal is always at the top of the plan; 3) If the first subgoal is not completed, copy the previous plan or update it based on completion status.\n"
            prompt += "Important: If the previous step successfully executed the `answer` action (Outcome: Success), you may mark the plan as \"Finished\" only if the task is completed and the 'Expected Result' (if provided in extra-info) is satisfied.\n"
            if task_specific_note != "":
                prompt += f"{task_specific_note}\n\n"
            
            prompt += "Please output in the following format, containing three parts:\n\n"
            prompt += "### Thought ###\n"
            prompt += "Explain your reasoning for the updated plan and current subgoal.\n\n"
            prompt += "### Completed Subgoals ###\n"
            prompt += "Critical: You must only output the newly completed subgoal from the previous round (i.e., the first item in the current plan that was completed in the previous round).\n"
            prompt += "Do not output all historical operations; do not copy the complete completed history.\n"
            prompt += "If there was no newly completed subgoal in the previous round, strictly output: \"No completed subgoal.\"\n"
            prompt += "Example: If the previous round completed \"Click on the Settings button\", only output that content, do not output the complete history.\n\n"
            prompt += "### Plan ###\n"
            prompt += "Please update or copy the existing plan based on the current page and progress. Pay close attention to historical operations; unless you can determine from the screen state that a subgoal is indeed not completed, do not repeat planning for completed content.\n"
        return prompt
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Planner response"""
        # Support both English and Chinese headers for backward compatibility
        if "### Completed Subgoals ###" in response or "### 历史操作 ###" in response:
            # Try English first, fallback to Chinese
            if "### Completed Subgoals ###" in response:
                thought = response.split("### Thought ###")[-1].split("### Completed Subgoals ###")[0].replace("\n", " ").replace("  ", " ").strip()
                completed_subgoal = response.split("### Completed Subgoals ###")[-1].split("### Plan ###")[0].strip()
            else:
                thought = response.split("### Thought ###")[-1].split("### Completed Subgoals ###")[0].replace("\n", " ").replace("  ", " ").strip()
                completed_subgoal = response.split("### Completed Subgoals ###")[-1].split("### Plan ###")[0].strip()
            # Remove possible markdown code block markers or extra ###
            completed_subgoal = completed_subgoal.replace("```", "").strip()
        else:
            if "### Thought ###" in response:
                if "### Plan ###" in response:
                    thought = response.split("### Thought ###")[-1].split("### Plan ###")[0].replace("\n", " ").replace("  ", " ").strip()
                else:
                    thought = response.split("### Thought ###")[-1].replace("\n", " ").replace("  ", " ").strip()
            else:
                thought = ""
            completed_subgoal = "No completed subgoal."
        
        # Compatibility handling: handle both Chinese and English variants
        # Also handle empty string cases
        if completed_subgoal in ["", "无已完成子目标。", "无已完成子目标", "No completed subgoal.", "No completed subgoal"]:
            completed_subgoal = "No completed subgoal."
        
        if "### Plan ###" in response:
            plan = response.split("### Plan ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        else:
            # If Plan section is missing, return empty plan
            plan = ""
        return {"thought": thought, "completed_subgoal": completed_subgoal, "plan": plan}
