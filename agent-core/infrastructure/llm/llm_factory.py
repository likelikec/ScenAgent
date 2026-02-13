"""LLM工厂：用于创建LLM实例"""
from typing import Optional
from .llm_provider import LLMProvider
from .langchain_llm import LangChainLLMProvider
from .gui_owl_wrapper import GUIOwlWrapperAdapter


class LLMFactory:
    """LLM工厂类"""
    
    @staticmethod
    def create(
        provider_type: str = "langchain",
        api_key: str = None,
        base_url: str = None,
        model_name: str = None,
        temperature: float = 0.0,
        max_retry: int = 10,
        **kwargs
    ) -> LLMProvider:
        """创建LLM提供者实例
        
        Args:
            provider_type: 提供者类型 ("langchain" 或 "gui_owl")
            api_key: API密钥
            base_url: API基础URL
            model_name: 模型名称
            temperature: 温度参数
            max_retry: 最大重试次数
            **kwargs: 其他参数
            
        Returns:
            LLMProvider实例
            
        Raises:
            ValueError: 如果provider_type不支持
        """
        if not api_key or not base_url or not model_name:
            raise ValueError("api_key, base_url, and model_name are required")
        
        if provider_type == "langchain":
            return LangChainLLMProvider(
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                temperature=temperature,
                max_retries=max_retry,
            )
        elif provider_type == "gui_owl":
            return GUIOwlWrapperAdapter(
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                temperature=temperature,
                max_retry=max_retry,
            )
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}. Use 'langchain' or 'gui_owl'")
    
    @staticmethod
    def create_from_config(config: dict) -> LLMProvider:
        """从配置字典创建LLM提供者
        
        Args:
            config: 配置字典，包含provider_type、api_key、base_url、model等字段
            
        Returns:
            LLMProvider实例
        """
        return LLMFactory.create(
            provider_type=config.get("provider_type", "langchain"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            model_name=config.get("model") or config.get("model_name"),
            temperature=config.get("temperature", 0.0),
            max_retry=config.get("max_retry", 10),
        )

