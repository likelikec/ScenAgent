"""执行Chain：连接ExecutorAgent和设备控制"""
from typing import Dict, Any, Optional
import json
import time
import os
from core.agents.executor_agent import ExecutorAgent
from core.state.state_manager import StateManager
from services.action_service import ActionService
from services.screenshot_service import ScreenshotService
from services.som_service import SoMService
from core.actions import ANSWER


class ExecutionChain:
    """执行Chain：负责执行阶段的处理"""
    
    def __init__(
        self,
        executor_agent: ExecutorAgent,
        state_manager: StateManager,
        action_service: ActionService,
        screenshot_service: ScreenshotService,
        perception_mode: str = "vllm"
    ):
        """初始化执行Chain
        
        Args:
            executor_agent: Executor Agent
            state_manager: 状态管理器
            action_service: 动作执行服务
            screenshot_service: 截图服务
            perception_mode: 感知模式
        """
        self.executor_agent = executor_agent
        self.state_manager = state_manager
        self.action_service = action_service
        self.screenshot_service = screenshot_service
        self.perception_mode = perception_mode
    
    def run(
        self,
        screenshot_path: Optional[str] = None,
        coor_type: str = "abs",
        is_first_step: bool = False
    ) -> Dict[str, Any]:
        """运行执行Chain
        
        Args:
            screenshot_path: 截图路径（如果是SoM模式，这是marked图片路径）
            coor_type: 坐标类型
            is_first_step: 是否是第一步
            
        Returns:
            执行结果字典
        """
        # Load SoM mapping if in SoM mode
        if self.perception_mode == "som" and screenshot_path:
            som_mapping = self.screenshot_service.get_som_mapping()
            if som_mapping:
                self.action_service.set_som_mapping(som_mapping)
            else:
                # Try to load from JSON file
                mapping_path = self._get_mapping_path(screenshot_path)
                if mapping_path and os.path.exists(mapping_path):
                    som_mapping = SoMService.load_mapping_json(mapping_path)
                    self.action_service.set_som_mapping(som_mapping)
        
        # 准备图片
        images = []
        if screenshot_path:
            images.append(screenshot_path)
        
        # 调用Executor Agent
        result = self.executor_agent.run(images)
        
        action_thought = result.get('thought', '')
        action_object_str = result.get('action', '')
        action_description = result.get('description', '')
        
        # 更新状态
        self.state_manager.set_last_action({}, action_description, action_thought)
        
        # 验证动作格式
        if not action_thought or not action_object_str:
            print('Action prompt output is not in the correct format.')
            # DEBUG: 打印原始输出以便调试
            print(f"[DEBUG] Invalid Format - Thought: {action_thought}")
            print(f"[DEBUG] Invalid Format - Action String: {action_object_str}")
            
            self.state_manager.set_last_action({"action": "invalid"}, action_description)
            self.state_manager.append_action(
                {"action": "invalid"},
                action_description,
                "N",
                "invalid action format, do nothing."
            )
            return result
        
        # 解析动作
        action_object = self.action_service.parse_action_string(action_object_str)
        
        # 将解析后的动作对象加入结果
        result['action_object'] = action_object
        
        if not action_object:
            # DEBUG: 打印解析失败的字符串
            print(f"[DEBUG] Parse Failed - Action String: {action_object_str}")
            
            self.state_manager.set_last_action({"action": "invalid"}, action_description)
            self.state_manager.append_action(
                {"action": "invalid"},
                action_description,
                "N",
                "invalid action format, do nothing."
            )
            return result
        
        # 处理answer动作
        if action_object.get('action') == ANSWER:
            # answer动作不需要设备操作
            self.state_manager.set_last_action(action_object, action_description)
            self.state_manager.append_action(
                action_object,
                action_description,
                "S",
                "None"
            )
            return result
        
        # 获取屏幕尺寸（用于坐标转换）
        screen_width, screen_height = None, None
        if screenshot_path:
            size = self.screenshot_service.get_image_size(screenshot_path)
            if size:
                screen_width, screen_height = size
        
        # 执行动作
        command_str = self.action_service.execute_action(
            action_object,
            coor_type,
            screen_width,
            screen_height
        )
        
        # 更新状态
        self.state_manager.set_last_action(action_object, action_description)
        
        # 等待（第一步等待时间更长）
        if is_first_step:
            time.sleep(8)  # 首次打开应用可能有弹窗
        time.sleep(2)
        
        # Get mark if used
        last_mark = self.action_service.get_last_used_mark() if self.perception_mode == "som" else None
        
        return {
            **result,
            "action_object": action_object,
            "command_str": command_str,
            "som_mark": last_mark
        }
    
    def _get_mapping_path(self, screenshot_path: str) -> Optional[str]:
        """Get corresponding mapping JSON path for a marked screenshot
        
        Args:
            screenshot_path: Path to marked screenshot
            
        Returns:
            Path to mapping JSON or None
        """
        if not screenshot_path:
            return None
        
        # If it's a marked image, construct the mapping path
        if "_marked.png" in screenshot_path:
            return screenshot_path.replace("_marked.png", "_mapping.json")
        
        return None

