
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from infrastructure.llm.llm_provider import LLMProvider
from core.state.state_manager import StateManager


class BaseMobileAgent(ABC):
    """移动Agent基础抽象类"""
    
    def __init__(self, llm_provider: LLMProvider, state_manager: StateManager):
        """初始化Agent
        
        Args:
            llm_provider: LLM提供者
            state_manager: 状态管理器
        """
        self.llm_provider = llm_provider
        self.state_manager = state_manager
    
    @abstractmethod
    def get_prompt(self) -> str:
        """生成提示模板
        
        Returns:
            提示字符串
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应
        
        Args:
            response: LLM响应文本
            
        Returns:
            解析后的字典
        """
        pass
    
    def invoke(
        self,
        images: Optional[List[str]] = None,
        messages: Optional[List[dict]] = None
    ) -> tuple[str, Optional[Any], Any]:
        """调用Agent
        
        Args:
            images: 图片列表（路径）
            messages: 可选的消息历史
            
        Returns:
            (输出文本, 消息历史, 原始响应)
        """
        prompt = self.get_prompt()
        
        if images is None:
            images = []
        
        if messages is None:
            output, msg_history, raw_response = self.llm_provider.predict_mm(
                prompt, images
            )
        else:
            output, msg_history, raw_response = self.llm_provider.predict_mm(
                prompt, images, messages
            )
        
        return output, msg_history, raw_response
    
    def run(self, images: Optional[List[str]] = None) -> Dict[str, Any]:
        """运行Agent并返回解析后的结果
        
        Args:
            images: 图片列表（路径）
            
        Returns:
            解析后的结果字典
        """
        output, msg_history, raw_response = self.invoke(images)
        parsed = self.parse_response(output)
        parsed["_raw_response"] = raw_response
        parsed["_msg_history"] = msg_history
        return parsed

