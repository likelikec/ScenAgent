"""规划Chain：连接PlannerAgent和状态更新"""
from typing import Dict, Any, Optional, List
from core.agents.planner_agent import PlannerAgent
from core.state.state_manager import StateManager
import re


class PlanningChain:
    """规划Chain：负责规划阶段的处理"""
    
    def __init__(self, planner_agent: PlannerAgent, state_manager: StateManager):
        """初始化规划Chain
        
        Args:
            planner_agent: Planner Agent
            state_manager: 状态管理器
        """
        self.planner_agent = planner_agent
        self.state_manager = state_manager
    
    def run(
        self,
        screenshot_path: Optional[str] = None,
        skip_if_invalid: bool = False
    ) -> Dict[str, Any]:
        """运行规划Chain
        
        Args:
            screenshot_path: 截图路径
            skip_if_invalid: 如果上一轮动作为invalid，是否跳过规划
            
        Returns:
            规划结果字典
        """
        # 检查是否需要跳过规划
        if skip_if_invalid:
            last_action = self.state_manager.get_last_action()
            if last_action and last_action.get('action') == 'invalid':
                # 跳过规划，返回空结果
                return {
                    "thought": "",
                    "completed_subgoal": "No completed subgoal.",
                    "plan": self.state_manager.get_plan()
                }
        
        # 准备图片
        images = []
        if screenshot_path:
            images.append(screenshot_path)
        
        # 调用Planner Agent
        result = self.planner_agent.run(images)
        
        # 更新状态
        new_completed_subgoal = result.get('completed_subgoal', 'No completed subgoal.')
        plan = result.get('plan', '')
        thought = result.get('thought', '')
        
        # 保存当前步骤的新完成子目标
        self.state_manager.set_current_step_completed_subgoal(new_completed_subgoal)
        
        # 更新计划
        self.state_manager.set_plan(plan)
        
        # 追加已完成的子目标
        if new_completed_subgoal and new_completed_subgoal != "No completed subgoal.":
            self.state_manager.append_completed_subgoal(new_completed_subgoal)
        
        # 提取当前子目标
        self._update_current_subgoal(plan)
        
        return result
    
    def _update_current_subgoal(self, plan: str) -> None:
        """从计划中提取当前子目标并更新状态"""
        if plan and "Finished" not in plan:
            # 增强正则以支持中文全角点、顿号等
            plan_lines = re.split(r'(?<=\d)[\.、．] ', plan)
            if len(plan_lines) == 1: # Fallback for lines without space after dot
                plan_lines = re.split(r'(?<=\d)[\.、．]', plan)
            
            num_to_extract = min(
                self.state_manager.get_state().planning.num_current_subgoals,
                len(plan_lines) - 1
            )
            if num_to_extract > 0:
                extracted_goals = []
                for i in range(1, num_to_extract + 1):
                    if i < len(plan_lines):
                        goal_text = plan_lines[i].split('\n')[0].strip()
                        extracted_goals.append(f"{i}. {goal_text}")
                self.state_manager.set_current_subgoal(" ".join(extracted_goals))
            else:
                self.state_manager.set_current_subgoal(plan.strip())
        else:
            self.state_manager.set_current_subgoal("")

