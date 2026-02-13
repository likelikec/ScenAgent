"""LangChain LLM提供者实现"""
from typing import Any, Optional, List, Union
import numpy as np
from PIL import Image
from io import BytesIO
import base64

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None

from .llm_provider import LLMProvider


def image_to_base64(image: Union[str, np.ndarray, Image.Image]) -> str:
    """将图片转换为base64字符串"""
    if isinstance(image, str):
        # 如果是路径，读取图片
        img = Image.open(image)
    elif isinstance(image, np.ndarray):
        # 如果是numpy数组，转换为PIL Image
        img = Image.fromarray(image)
    elif isinstance(image, Image.Image):
        img = image
    else:
        raise ValueError(f"Unsupported image type: {type(image)}")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class LangChainLLMProvider(LLMProvider):
    """基于LangChain的LLM提供者实现"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float = 0.0,
        max_retries: int = 3,
    ):
        """初始化LangChain LLM提供者
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            model_name: 模型名称
            temperature: 温度参数
            max_retries: 最大重试次数
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is not available. Please install it with: "
                "pip install langchain langchain-openai"
            )
        
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            max_retries=max_retries,
            timeout=30,
        )
        self.model_name = model_name
    
    def predict(
        self,
        text_prompt: str,
    ) -> tuple[str, Optional[Any], Any]:
        """调用文本LLM"""
        return self.predict_mm(text_prompt, [])
    
    def predict_mm(
        self,
        text_prompt: str,
        images: List[Union[str, np.ndarray]] = None,
        messages: Optional[List[dict]] = None
    ) -> tuple[str, Optional[Any], Any]:
        """调用多模态LLM
        
        Args:
            text_prompt: 文本提示
            images: 图片列表
            messages: 可选的消息历史（如果提供，将使用此而非text_prompt）
        """
        if images is None:
            images = []
        
        try:
            if messages is None:
                # 构建消息
                content = [{"type": "text", "text": text_prompt}]
                
                # 添加图片
                for image in images:
                    if isinstance(image, str):
                        # 如果是路径，转换为base64
                        img_data = image_to_base64(image)
                    elif isinstance(image, np.ndarray):
                        # 如果是numpy数组，转换为base64
                        img_data = image_to_base64(image)
                    else:
                        continue
                    
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_data}"
                        }
                    })
                
                langchain_messages = [HumanMessage(content=content)]
            else:
                # 转换消息格式
                langchain_messages = []
                for msg in messages:
                    role = msg.get('role', 'user')
                    content = msg.get('content', [])
                    
                    if isinstance(content, str):
                        content = [{"type": "text", "text": content}]
                    
                    # 处理多模态内容
                    processed_content = []
                    for item in content:
                        if isinstance(item, dict):
                            if 'text' in item:
                                processed_content.append({"type": "text", "text": item['text']})
                            elif 'image' in item:
                                img_data = image_to_base64(item['image'])
                                processed_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_data}"
                                    }
                                })
                        else:
                            processed_content.append({"type": "text", "text": str(item)})
                    
                    if role == 'system':
                        langchain_messages.append(SystemMessage(content=processed_content))
                    else:
                        langchain_messages.append(HumanMessage(content=processed_content))
            
            # 调用LLM
            response = self.llm.invoke(langchain_messages)
            
            # 提取响应内容
            if hasattr(response, 'content'):
                output_text = response.content
            else:
                output_text = str(response)
            
            return (output_text, messages, response)
            
        except Exception as e:
            print(f'Error calling LangChain LLM: {e}')
            return (f"Error: {str(e)}", None, None)

