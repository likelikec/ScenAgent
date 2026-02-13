"""LLM提供者接口定义"""
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Union
import numpy as np


class LLMProvider(ABC):
    """LLM提供者抽象接口"""
    
    @abstractmethod
    def predict(
        self,
        text_prompt: str,
    ) -> tuple[str, Optional[Any], Any]:
        """调用文本LLM
        
        Args:
            text_prompt: 文本提示
            
        Returns:
            (输出文本, 消息历史, 原始响应)
        """
        pass
    
    @abstractmethod
    def predict_mm(
        self,
        text_prompt: str,
        images: List[Union[str, np.ndarray]],
        messages: Optional[List[dict]] = None
    ) -> tuple[str, Optional[Any], Any]:
        """调用多模态LLM
        
        Args:
            text_prompt: 文本提示
            images: 图片列表（路径或numpy数组）
            messages: 可选的消息历史
            
        Returns:
            (输出文本, 消息历史, 原始响应)
        """
        pass

