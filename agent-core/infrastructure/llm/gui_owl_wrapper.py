"""GUIOwlWrapper适配器：将原有GUIOwlWrapper适配为LLMProvider接口"""
from typing import Any, Optional, List, Union
import numpy as np
from .gui_owl_impl import GUIOwlWrapper

from .llm_provider import LLMProvider


class GUIOwlWrapperAdapter(LLMProvider):
    """GUIOwlWrapper适配器：将原有实现适配为LLMProvider接口"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        max_retry: int = 10,
        temperature: float = 0.0,
    ):
        """初始化适配器
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            model_name: 模型名称
            max_retry: 最大重试次数
            temperature: 温度参数
        """
        self.wrapper = GUIOwlWrapper(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            max_retry=max_retry,
            temperature=temperature,
        )
    
    def predict(
        self,
        text_prompt: str,
    ) -> tuple[str, Optional[Any], Any]:
        """调用文本LLM"""
        return self.wrapper.predict(text_prompt)
    
    def predict_mm(
        self,
        text_prompt: str,
        images: List[Union[str, np.ndarray]] = None,
        messages: Optional[List[dict]] = None
    ) -> tuple[str, Optional[Any], Any]:
        """调用多模态LLM
        
        Args:
            text_prompt: 文本提示
            images: 图片列表（路径或numpy数组）
            messages: 可选的消息历史
        """
        if images is None:
            images = []
        
        # 转换图片格式：将路径字符串转换为numpy数组（如果需要）
        # GUIOwlWrapper期望图片路径字符串
        image_paths = []
        for img in images:
            if isinstance(img, str):
                image_paths.append(img)
            elif isinstance(img, np.ndarray):
                # 如果是numpy数组，需要先保存为临时文件
                # 这里简化处理，假设调用方已经提供了路径
                raise ValueError("GUIOwlWrapperAdapter currently only supports image paths, not numpy arrays")
            else:
                raise ValueError(f"Unsupported image type: {type(img)}")
        
        # 调用原有实现
        if messages is not None:
            return self.wrapper.predict_mm(text_prompt, image_paths, messages)
        else:
            return self.wrapper.predict_mm(text_prompt, image_paths)

