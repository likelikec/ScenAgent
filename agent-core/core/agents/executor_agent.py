
from typing import Dict, Any
import re
from .base_agent import BaseMobileAgent
from core.state.state_manager import StateManager
from infrastructure.llm.llm_provider import LLMProvider
from core.actions import (
    ANSWER, CLICK, TYPE, SYSTEM_BUTTON, SWIPE, WAIT, DELETE
)

# Constant migrated from original code
INPUT_KNOW = "If you have activated an input field, you will see \"ADB Keyboard {on}\" at the bottom of the screen. This phone does not display a soft keyboard. Therefore, if you see \"ADB Keyboard {on}\", you can input directly; otherwise, you need to click the correct input field first to activate it before inputting."

# VLLM Mode Action Descriptions (Simple, coordinate-focused)
ATOMIC_ACTION_SIGNITURES_VLLM = {
    ANSWER: {
        "arguments": ["text"],
        "description": "Answer the user's question. The action field in JSON must be 'answer'. Example usage: {\"action\": \"answer\", \"text\": \"answer_content\"}"
    },
    CLICK: {
        "arguments": ["coordinate"],
        "description": "Click a point on the screen at the specified coordinate (x, y). The action field in JSON must be 'click'. Example usage: {\"action\": \"click\", \"coordinate\": [x, y]}"
    },
    TYPE: {
        "arguments": ["text"],
        "description": "Input text in the currently activated input field or text field. If you have activated an input field, you will see \"ADB Keyboard {on}\" at the bottom of the screen. If not seen, click the input field again to confirm. Before inputting, make sure you have activated the correct input field. Note: Please strictly follow the user's instruction to input text, do not translate. The action field in JSON must be 'type'. Example usage: {\"action\": \"type\", \"text\": \"text_to_type\"}"
    },
    DELETE: {
        "arguments": ["count"],
        "description": "Delete text. If count is 1, simulate pressing the delete key once. If count is greater than 1, simulate pressing the delete key multiple times. The action field in JSON must be 'delete'. Example usage: {\"action\": \"delete\", \"count\": 1}"
    },
    WAIT: {
        "arguments": [],
        "description": "Wait for 2 seconds. The action field in JSON must be 'wait'. Example usage: {\"action\": \"wait\"}"
    },
    SYSTEM_BUTTON: {
        "arguments": ["button"],
        "description": "Press a system button, including back (return), home (homepage), enter (enter). The action field in JSON must be 'system_button'. Example usage: {\"action\":\"system_button\", \"button\": \"Home\"}"
    },
    SWIPE: {
        "arguments": ["coordinate", "coordinate2", "duration"],
        "description": "Swipe from one coordinate point to another coordinate point. Make sure the start and end points of the swipe are within the swipeable area and away from the keyboard (y1 < 1400). The action field in JSON must be 'swipe'. Example usage: {\"action\": \"swipe\", \"coordinate\": [x1, y1], \"coordinate2\": [x2, y2]}. Optional: \"duration\" in seconds (default 0.5). For dragging items (e.g. sliders), use a longer duration (e.g. 2.0)."
    }
}

# SoM Mode Action Descriptions (Mark-focused)
ATOMIC_ACTION_SIGNITURES_SOM = {
    ANSWER: {
        "arguments": ["text"],
        "description": "Answer the user's question. The action field in JSON must be 'answer'. Example usage: {\"action\": \"answer\", \"text\": \"answer_content\"}"
    },
    CLICK: {
        "arguments": ["coordinate"],
        "description": "Click an element using its mark number (e.g., '1', '2') from red boxes (clickable) or green boxes (scrollable). You can also use direct coordinates if needed. The action field in JSON must be 'click'. Example usage: {\"action\": \"click\", \"coordinate\": \"1\"} or {\"action\": \"click\", \"coordinate\": [x, y]}"
    },
    TYPE: {
        "arguments": ["text"],
        "description": "Input text in the currently activated input field or text field. If you have activated an input field, you will see \"ADB Keyboard {on}\" at the bottom of the screen. If not seen, click the input field again to confirm. Before inputting, make sure you have activated the correct input field. Note: Please strictly follow the user's instruction to input text, do not translate. The action field in JSON must be 'type'. Example usage: {\"action\": \"type\", \"text\": \"text_to_type\"}"
    },
    DELETE: {
        "arguments": ["count"],
        "description": "Delete text. If count is 1, simulate pressing the delete key once. If count is greater than 1, simulate pressing the delete key multiple times. The action field in JSON must be 'delete'. Example usage: {\"action\": \"delete\", \"count\": 1}"
    },
    WAIT: {
        "arguments": [],
        "description": "Wait for 2 seconds. The action field in JSON must be 'wait'. Example usage: {\"action\": \"wait\"}"
    },
    SYSTEM_BUTTON: {
        "arguments": ["button"],
        "description": "Press a system button, including back (return), home (homepage), enter (enter). The action field in JSON must be 'system_button'. Example usage: {\"action\":\"system_button\", \"button\": \"Home\"}"
    },
    SWIPE: {
        "arguments": ["target", "direction", "distance", "duration"],
        "description": "Swipe inside a marked SCROLLABLE area using its mark number. Provide target as the scrollable mark number, direction as one of 'up'/'down'/'left'/'right', and distance as a ratio between 0.1 and 0.9. The action field in JSON must be 'swipe'. Example usage: {\"action\": \"swipe\", \"target\": \"3\", \"direction\": \"up\", \"distance\": 0.6}. Optional: \"duration\" in seconds (default 0.5). For dragging items (e.g. sliders), use a longer duration (e.g. 1.0 or 2.0). If needed, you can still use direct coordinates: {\"action\": \"swipe\", \"coordinate\": [x1, y1], \"coordinate2\": [x2, y2], \"duration\": 2.0}"
    }
}


class ExecutorAgent(BaseMobileAgent):
    """Executor Agent：负责任务执行"""
    
    def get_prompt(self) -> str:
        """Generate execution prompt based on perception mode"""
        state = self.state_manager.get_state()
        perception_mode = state.task.perception_mode
        
        if perception_mode == "som":
            return self._build_som_prompt(state)
        else:
            return self._build_vllm_prompt(state)
    
    def _build_vllm_prompt(self, state) -> str:
        """Build prompt for VLLM mode (direct coordinate mode)"""
        prompt = "You are an Android execution agent that can strictly execute operations according to user requirements and the current interface state. Your sole goal is: based on the subgoal, choose the most reasonable, effective, and precise next atomic action.\n\n"
        
        prompt += "### User Instruction ###\n"
        prompt += f"{state.task.instruction}\n\n"
        
        prompt += "### Global Plan ###\n"
        prompt += f"{state.planning.plan}\n\n"
        
        prompt += "### Current Subgoal ###\n"
        if state.planning.current_subgoal:
            prompt += f"{state.planning.current_subgoal}\n\n"
        else:
            # If empty, dynamically extract from plan
            current_goal = state.planning.plan
            current_goal = re.split(r'(?<=\d)\. ', current_goal)
            num_subgoals = state.planning.num_current_subgoals
            truncated_current_goal = ". ".join(current_goal[:num_subgoals]) + '.'
            truncated_current_goal = truncated_current_goal[:-2].strip()
            prompt += f"{truncated_current_goal}\n\n"
        
        prompt += "### Progress Status ###\n"
        if state.planning.completed_plan_summary != "":
            prompt += f"{state.planning.completed_plan_summary}\n\n"
        else:
            prompt += "No progress yet.\n\n"
        
        if state.task.additional_knowledge_executor != "":
            prompt += "### Guidelines ###\n"
            prompt += f"{state.task.additional_knowledge_executor}\n"
        
        if "exact duplicates" in state.task.instruction:
            prompt += "Task-specific:\nOnly items with exactly the same name, date, and details can be considered duplicates.\n\n"
        elif "Audio Recorder" in state.task.instruction:
            prompt += "Task-specific:\nThe stop recording icon is a white square, located at the 4th position from the left at the bottom. Please do not click the circular pause icon in the middle.\n\n"
        else:
            prompt += "\n"
        
        prompt += "### Failure Rules (must obey, temporary) ###\n"
        prompt += "If your next action exactly matches any of the last failed attempts (same type and parameters), you must choose a different action or adjust parameters to avoid repeating the failure.\n"
        prompt += "For swipe: keep start and end points inside the visible content area and away from the keyboard region (y < 1400). If the previous swipe failed, adjust direction or distance.\n"
        prompt += "Before outputting JSON, check these rules; if matched, output a different corrected action.\n\n"
        
        prompt += "---\n"
        prompt += "Please carefully review the above information and decide the next action to execute. If you notice unresolved errors from the previous round, try to correct them like a human user would. You must choose one from the following atomic actions.\n\n"
        
        prompt += "#### Atomic Actions ####\n"
        prompt += "The following lists all available atomic actions in the format `action(arguments): description`:\n"
        
        for action, value in ATOMIC_ACTION_SIGNITURES_VLLM.items():
            prompt += f"- {action}({', '.join(value['arguments'])}): {value['description']}\n"
        
        prompt += "\n"
        prompt += self._build_action_history_section(state)
        
        prompt += "---\n"
        prompt += "Important:\n1. Do not repeat failed actions, multiple attempts are meaningless; please try other actions.\n"
        prompt += "2. Please prioritize completing the current subgoal.\n\n"
        prompt += "Please output in the following format (containing three parts):\n"
        prompt += "### Thought ###\n"
        prompt += "Use English to describe in detail your reasoning for choosing this action. The reasoning must be specific, based on visual/interface/history, not abstract nonsense.\n\n"
        
        prompt += "### Action ###\n"
        prompt += "Select only one action or shortcut.\n"
        prompt += "You must use valid JSON to specify the `action` and its parameters. **The `action` field value in JSON must strictly use English (e.g., 'click', 'swipe', 'type').** For example, to input text, write {\"action\":\"type\", \"text\": \"text_to_type\"}.\n\n"
        
        prompt += "### Description ###\n"
        prompt += "Provide a brief description of the selected action in English, do not describe the expected result.\n"
        
        return prompt
    
    def _build_som_prompt(self, state) -> str:
        """Build prompt for SoM mode (Set-of-Mark mode)"""
        prompt = "You are an Android execution agent that can strictly execute operations according to user requirements and the current interface state. Your sole goal is: based on the subgoal, choose the most reasonable, effective, and precise next atomic action.\n\n"
        
        # Add SoM-specific important notice
        prompt += "**IMPORTANT - MARKED ELEMENTS**: The screenshot you see has marked elements to help you interact with the interface:\n"
        prompt += "- **RED boxes with numbers at TOP-LEFT corner**: These are CLICKABLE elements. Use the number (e.g., '1', '2', '3') to click them.\n"
        prompt += "- **GREEN boxes with numbers at TOP-RIGHT corner**: These are SCROLLABLE areas. Use the number to interact with scrollable regions.\n"
        prompt += "You should primarily use these mark numbers for actions. For example, to click the element marked as '5', use {\"action\": \"click\", \"coordinate\": \"5\"}.\n\n"
        prompt += "To scroll inside a scrollable area marked as '3', use {\"action\": \"swipe\", \"target\": \"3\", \"direction\": \"up\", \"distance\": 0.6}.\n\n"
        
        prompt += "### User Instruction ###\n"
        prompt += f"{state.task.instruction}\n\n"
        
        prompt += "### Global Plan ###\n"
        prompt += f"{state.planning.plan}\n\n"
        
        prompt += "### Current Subgoal ###\n"
        if state.planning.current_subgoal:
            prompt += f"{state.planning.current_subgoal}\n\n"
        else:
            # If empty, dynamically extract from plan
            current_goal = state.planning.plan
            current_goal = re.split(r'(?<=\d)\. ', current_goal)
            num_subgoals = state.planning.num_current_subgoals
            truncated_current_goal = ". ".join(current_goal[:num_subgoals]) + '.'
            truncated_current_goal = truncated_current_goal[:-2].strip()
            prompt += f"{truncated_current_goal}\n\n"
        
        prompt += "### Progress Status ###\n"
        if state.planning.completed_plan_summary != "":
            prompt += f"{state.planning.completed_plan_summary}\n\n"
        else:
            prompt += "No progress yet.\n\n"
        
        if state.task.additional_knowledge_executor != "":
            prompt += "### Guidelines ###\n"
            prompt += f"{state.task.additional_knowledge_executor}\n"
        
        if "exact duplicates" in state.task.instruction:
            prompt += "Task-specific:\nOnly items with exactly the same name, date, and details can be considered duplicates.\n\n"
        elif "Audio Recorder" in state.task.instruction:
            prompt += "Task-specific:\nThe stop recording icon is a white square, located at the 4th position from the left at the bottom. Please do not click the circular pause icon in the middle.\n\n"
        else:
            prompt += "\n"
        
        prompt += "### Failure Rules (must obey, temporary) ###\n"
        prompt += "Do not repeat an identical failed action.\n"
        prompt += "In SoM mode: if clicking mark 'N' failed and the page did not change, do not click mark 'N' again; try alternative marks or strategies.\n"
        prompt += "For swipe: prefer {\"target\": \"N\", \"direction\": \"up/down\", \"distance\": 0.3–0.7}. If using coordinates, keep start and end inside bounds and away from the keyboard region.\n"
        prompt += "Before outputting JSON, check these rules; if matched, output a different corrected action.\n\n"
        
        prompt += "---\n"
        prompt += "Please carefully review the above information and decide the next action to execute. If you notice unresolved errors from the previous round, try to correct them like a human user would. You must choose one from the following atomic actions.\n\n"
        
        prompt += "#### Atomic Actions ####\n"
        prompt += "The following lists all available atomic actions in the format `action(arguments): description`:\n"
        
        for action, value in ATOMIC_ACTION_SIGNITURES_SOM.items():
            prompt += f"- {action}({', '.join(value['arguments'])}): {value['description']}\n"
        
        prompt += "\n"
        prompt += self._build_action_history_section(state)
        
        prompt += "---\n"
        prompt += "Important:\n1. Do not repeat failed actions, multiple attempts are meaningless; please try other actions.\n"
        prompt += "2. Please prioritize completing the current subgoal.\n"
        prompt += "3. When possible, use the mark numbers from the labeled elements for more reliable interactions.\n\n"
        prompt += "Please output in the following format (containing three parts):\n"
        prompt += "### Thought ###\n"
        prompt += "Use English to describe in detail your reasoning for choosing this action. The reasoning must be specific, based on visual/interface/history, not abstract nonsense.\n\n"
        
        prompt += "### Action ###\n"
        prompt += "Select only one action or shortcut.\n"
        prompt += "You must use valid JSON to specify the `action` and its parameters. **The `action` field value in JSON must strictly use English (e.g., 'click', 'swipe', 'type').** For example, to click mark '5', write {\"action\":\"click\", \"coordinate\": \"5\"}.\n\n"
        
        prompt += "### Description ###\n"
        prompt += "Provide a brief description of the selected action in English, do not describe the expected result.\n"
        
        return prompt
    
    def _build_action_history_section(self, state) -> str:
        """Build the action history section (shared by both modes)"""
        section = "### Recent Action History ###\n"
        if state.execution.action_history:
            section += "Actions you have previously executed and whether they succeeded:\n"
            num_actions = min(5, len(state.execution.action_history))
            recent_actions = state.execution.action_history[-num_actions:]
            recent_summary = state.execution.summary_history[-num_actions:]
            recent_outcomes = state.execution.action_outcomes[-num_actions:]
            error_descriptions = state.execution.error_descriptions[-num_actions:]
            for act, summ, outcome, err_des in zip(recent_actions, recent_summary, recent_outcomes, error_descriptions):
                if outcome == "S":
                    section += f"Action: {act} | Description: {summ} | Outcome: Success\n"
                else:
                    section += f"Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"
            section += "\n"
        else:
            section += "No actions have been executed yet.\n\n"
        
        return section
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Executor response"""
        if "### Thought ###" in response:
            if "### Action ###" in response:
                thought = response.split("### Thought ###")[-1].split("### Action ###")[0].replace("\n", " ").replace("  ", " ").strip()
                if "### Description ###" in response:
                    action = response.split("### Action ###")[-1].split("### Description ###")[0].replace("\n", " ").replace("  ", " ").strip()
                    description = response.split("### Description ###")[-1].replace("\n", " ").replace("  ", " ").strip()
                else:
                    action = response.split("### Action ###")[-1].replace("\n", " ").replace("  ", " ").strip()
                    description = ""
            else:
                thought = response.split("### Thought ###")[-1].replace("\n", " ").replace("  ", " ").strip()
                action = ""
                description = ""
        else:
            # If Thought section is missing, return empty values
            thought = ""
            action = ""
            description = ""
        return {"thought": thought, "action": action, "description": description}
