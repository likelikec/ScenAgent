"""状态数据模型：使用Pydantic定义状态结构"""
from pydantic import BaseModel, Field
from typing import List, Optional
from dataclasses import dataclass, field


class TaskState(BaseModel):
    """任务相关状态"""
    instruction: str = ""
    task_name: str = ""
    additional_knowledge_planner: str = ""
    additional_knowledge_executor: str = ""
    add_info_token: str = "[add_info]"
    perception_mode: str = "vllm"  # "vllm" or "som"
    
    class Config:
        arbitrary_types_allowed = True


class PlanningState(BaseModel):
    """规划相关状态"""
    plan: str = ""
    completed_plan: str = ""  # 完整的历史记录，用于数据存储
    completed_plan_summary: str = ""  # 摘要后的历史记录，用于提示词注入
    current_subgoal: str = ""  # 当前子目标
    current_step_completed_subgoal: str = ""  # 当前步骤新完成的子目标
    num_current_subgoals: int = 1  # 用于提取当前子目标时指定提取前N个子目标
    error_flag_plan: bool = False  # 是否需要重新规划
    error_description_plan: str = ""  # 规划错误描述
    err_to_planner_thresh: int = 2  # 错误阈值
    
    class Config:
        arbitrary_types_allowed = True


class ExecutionState(BaseModel):
    """执行相关状态"""
    action_history: List[dict] = Field(default_factory=list)  # 动作历史
    summary_history: List[str] = Field(default_factory=list)  # 动作描述历史
    last_action: dict = Field(default_factory=dict)  # 最后一次动作
    last_summary: str = ""  # 最后一次动作描述
    last_action_thought: str = ""  # 最后一次动作思考
    action_outcomes: List[str] = Field(default_factory=list)  # 动作结果 (A/B/C)
    error_descriptions: List[str] = Field(default_factory=list)  # 错误描述列表
    
    class Config:
        arbitrary_types_allowed = True


class ReflectionState(BaseModel):
    """反思相关状态"""
    progress_status: str = ""  # 当前进度状态
    progress_status_history: List[str] = Field(default_factory=list)  # 进度历史
    important_notes: str = ""  # 重要笔记
    prev_action_image_before: str = ""  # 上一步操作前的截图路径
    prev_action_image_after: str = ""  # 上一步操作后的截图路径
    
    class Config:
        arbitrary_types_allowed = True


class MobileAgentState(BaseModel):
    """移动Agent完整状态（组合所有子状态）"""
    task: TaskState = Field(default_factory=TaskState)
    planning: PlanningState = Field(default_factory=PlanningState)
    execution: ExecutionState = Field(default_factory=ExecutionState)
    reflection: ReflectionState = Field(default_factory=ReflectionState)
    
    # 预留字段（保持兼容性）
    ui_elements_list_before: str = ""
    ui_elements_list_after: str = ""
    action_pool: List[dict] = Field(default_factory=list)
    future_tasks: List[str] = Field(default_factory=list)
    finish_thought: str = ""
    
    class Config:
        arbitrary_types_allowed = True
    
    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MobileAgentState':
        """从字典创建（用于反序列化）"""
        return cls(**data)
    
    # 兼容性方法：提供类似InfoPool的访问方式
    @property
    def instruction(self) -> str:
        return self.task.instruction
    
    @instruction.setter
    def instruction(self, value: str):
        self.task.instruction = value
    
    @property
    def plan(self) -> str:
        return self.planning.plan
    
    @plan.setter
    def plan(self, value: str):
        self.planning.plan = value
    
    @property
    def completed_plan(self) -> str:
        return self.planning.completed_plan
    
    @completed_plan.setter
    def completed_plan(self, value: str):
        self.planning.completed_plan = value
    
    @property
    def completed_plan_summary(self) -> str:
        return self.planning.completed_plan_summary
    
    @completed_plan_summary.setter
    def completed_plan_summary(self, value: str):
        self.planning.completed_plan_summary = value
    
    @property
    def current_subgoal(self) -> str:
        return self.planning.current_subgoal
    
    @current_subgoal.setter
    def current_subgoal(self, value: str):
        self.planning.current_subgoal = value
    
    @property
    def action_history(self) -> List[dict]:
        return self.execution.action_history
    
    @property
    def summary_history(self) -> List[str]:
        return self.execution.summary_history
    
    @property
    def action_outcomes(self) -> List[str]:
        return self.execution.action_outcomes
    
    @property
    def error_descriptions(self) -> List[str]:
        return self.execution.error_descriptions
    
    @property
    def last_action(self) -> dict:
        return self.execution.last_action
    
    @last_action.setter
    def last_action(self, value: dict):
        self.execution.last_action = value
    
    @property
    def last_summary(self) -> str:
        return self.execution.last_summary
    
    @last_summary.setter
    def last_summary(self, value: str):
        self.execution.last_summary = value
    
    @property
    def last_action_thought(self) -> str:
        return self.execution.last_action_thought
    
    @last_action_thought.setter
    def last_action_thought(self, value: str):
        self.execution.last_action_thought = value
    
    @property
    def important_notes(self) -> str:
        return self.reflection.important_notes
    
    @important_notes.setter
    def important_notes(self, value: str):
        self.reflection.important_notes = value
    
    @property
    def progress_status(self) -> str:
        return self.reflection.progress_status
    
    @progress_status.setter
    def progress_status(self, value: str):
        self.reflection.progress_status = value
    
    @property
    def error_flag_plan(self) -> bool:
        return self.planning.error_flag_plan
    
    @error_flag_plan.setter
    def error_flag_plan(self, value: bool):
        self.planning.error_flag_plan = value

