"""状态管理器：管理所有状态，提供更新、查询、持久化接口"""
from typing import Optional, Dict, Any
import json
from .state_schema import MobileAgentState, TaskState, PlanningState, ExecutionState, ReflectionState
from infrastructure.storage.file_service import FileService


class StateManager:
    """状态管理器类"""
    
    def __init__(self, initial_state: Optional[MobileAgentState] = None):
        """初始化状态管理器
        
        Args:
            initial_state: 初始状态，如果为None则创建新状态
        """
        if initial_state is None:
            self.state = MobileAgentState()
        else:
            self.state = initial_state
    
    # ========== 任务状态相关方法 ==========
    
    def set_instruction(self, instruction: str) -> None:
        """设置任务指令"""
        self.state.task.instruction = instruction
    
    def get_instruction(self) -> str:
        """获取任务指令"""
        return self.state.task.instruction

    def set_task_name(self, task_name: str) -> None:
        """设置任务名称"""
        self.state.task.task_name = task_name or ""

    def get_task_name(self) -> str:
        """获取任务名称"""
        return self.state.task.task_name
    
    def set_additional_knowledge(self, planner: str = "", executor: str = "") -> None:
        """设置额外知识"""
        if planner:
            self.state.task.additional_knowledge_planner = planner
        if executor:
            self.state.task.additional_knowledge_executor = executor
    
    def set_perception_mode(self, mode: str) -> None:
        """设置感知模式"""
        self.state.task.perception_mode = mode
    
    def get_perception_mode(self) -> str:
        """获取感知模式"""
        return self.state.task.perception_mode
    
    # ========== 规划状态相关方法 ==========
    
    def set_plan(self, plan: str) -> None:
        """设置计划"""
        self.state.planning.plan = plan
    
    def get_plan(self) -> str:
        """获取计划"""
        return self.state.planning.plan
    
    def append_completed_subgoal(self, subgoal: str) -> None:
        """追加已完成的子目标"""
        # Support both English and Chinese for backward compatibility
        if subgoal and subgoal not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]:
            # Check both English and Chinese for backward compatibility
            if self.state.planning.completed_plan and self.state.planning.completed_plan not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]:
                self.state.planning.completed_plan = self.state.planning.completed_plan + " " + subgoal
            else:
                self.state.planning.completed_plan = subgoal
            
            if self.state.planning.completed_plan_summary and self.state.planning.completed_plan_summary not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]:
                self.state.planning.completed_plan_summary = self.state.planning.completed_plan_summary + " " + subgoal
            else:
                self.state.planning.completed_plan_summary = subgoal
    
    def set_completed_plan_summary(self, summary: str) -> None:
        """设置已完成计划的摘要（覆盖而非追加）"""
        self.state.planning.completed_plan_summary = summary
    
    def set_current_subgoal(self, subgoal: str) -> None:
        """设置当前子目标"""
        self.state.planning.current_subgoal = subgoal
    
    def get_current_subgoal(self) -> str:
        """获取当前子目标"""
        return self.state.planning.current_subgoal
    
    def set_current_step_completed_subgoal(self, subgoal: str) -> None:
        """设置当前步骤新完成的子目标"""
        self.state.planning.current_step_completed_subgoal = subgoal
    
    def get_current_step_completed_subgoal(self) -> str:
        """获取当前步骤新完成的子目标"""
        return self.state.planning.current_step_completed_subgoal
    
    def reset_current_step_completed_subgoal(self) -> None:
        """重置当前步骤新完成的子目标"""
        self.state.planning.current_step_completed_subgoal = ""
    
    def set_error_flag_plan(self, flag: bool) -> None:
        """设置规划错误标志"""
        self.state.planning.error_flag_plan = flag
    
    def get_error_flag_plan(self) -> bool:
        """获取规划错误标志"""
        return self.state.planning.error_flag_plan
    
    def check_error_threshold(self, threshold: Optional[int] = None) -> bool:
        """检查是否达到错误阈值
        
        Args:
            threshold: 错误阈值，如果为None则使用state中的阈值
            
        Returns:
            是否达到阈值
        """
        if threshold is None:
            threshold = self.state.planning.err_to_planner_thresh
        
        if len(self.state.execution.action_outcomes) >= threshold:
            latest_outcomes = self.state.execution.action_outcomes[-threshold:]
            count = sum(1 for outcome in latest_outcomes if outcome in ["B", "C", "N"])
            return count == threshold
        return False
    
    # ========== 执行状态相关方法 ==========
    
    def append_action(self, action: dict, summary: str, outcome: str, error_description: str = "") -> None:
        """追加动作记录
        
        Args:
            action: 动作字典
            summary: 动作描述
            outcome: 动作结果 (A/B/C)
            error_description: 错误描述
        """
        self.state.execution.action_history.append(action)
        self.state.execution.summary_history.append(summary)
        self.state.execution.action_outcomes.append(outcome)
        self.state.execution.error_descriptions.append(error_description)
    
    def set_last_action(self, action: dict, summary: str = "", thought: str = "") -> None:
        """设置最后一次动作"""
        self.state.execution.last_action = action
        if summary:
            self.state.execution.last_summary = summary
        if thought:
            self.state.execution.last_action_thought = thought
    
    def get_last_action(self) -> dict:
        """获取最后一次动作"""
        return self.state.execution.last_action
    
    def get_recent_actions(self, num: int = 5) -> list:
        """获取最近的动作记录
        
        Args:
            num: 返回的记录数
            
        Returns:
            最近的动作记录列表，每个元素包含(action, summary, outcome, error_description)
        """
        actions = self.state.execution.action_history[-num:]
        summaries = self.state.execution.summary_history[-num:]
        outcomes = self.state.execution.action_outcomes[-num:]
        errors = self.state.execution.error_descriptions[-num:]
        
        return list(zip(actions, summaries, outcomes, errors))
    
    # ========== 反思状态相关方法 ==========
    
    def set_progress_status(self, status: str) -> None:
        """设置进度状态"""
        self.state.reflection.progress_status = status
        self.state.reflection.progress_status_history.append(status)
    
    def get_progress_status(self) -> str:
        """获取进度状态"""
        return self.state.reflection.progress_status
    
    def set_important_notes(self, notes: str) -> None:
        """设置重要笔记"""
        self.state.reflection.important_notes = notes
    
    def get_important_notes(self) -> str:
        """获取重要笔记"""
        return self.state.reflection.important_notes
    
    def set_prev_action_images(self, before: str, after: str) -> None:
        """设置上一步操作的截图路径"""
        self.state.reflection.prev_action_image_before = before
        self.state.reflection.prev_action_image_after = after
    
    def get_prev_action_images(self) -> tuple[str, str]:
        """获取上一步操作的截图路径"""
        return (
            self.state.reflection.prev_action_image_before,
            self.state.reflection.prev_action_image_after
        )
    
    # ========== 状态持久化方法 ==========
    
    def save_to_file(self, file_path: str) -> bool:
        """保存状态到文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否成功
        """
        try:
            state_dict = self.state.to_dict()
            return FileService.write_json(file_path, state_dict)
        except Exception as e:
            print(f"Failed to save state to {file_path}: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, file_path: str) -> Optional['StateManager']:
        """从文件加载状态
        
        Args:
            file_path: 文件路径
            
        Returns:
            StateManager实例，如果加载失败返回None
        """
        try:
            data = FileService.read_json(file_path)
            if data is None:
                return None
            state = MobileAgentState.from_dict(data)
            return cls(initial_state=state)
        except Exception as e:
            print(f"Failed to load state from {file_path}: {e}")
            return None
    
    # ========== 获取完整状态 ==========
    
    def get_state(self) -> MobileAgentState:
        """获取完整状态对象"""
        return self.state
    
    def get_state_dict(self) -> dict:
        """获取状态字典（用于序列化）"""
        return self.state.to_dict()
    
    # ========== 兼容性方法（保持与InfoPool类似的接口）==========
    
    def __getattr__(self, name: str):
        """提供对state属性的直接访问（兼容性）"""
        if hasattr(self.state, name):
            return getattr(self.state, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
