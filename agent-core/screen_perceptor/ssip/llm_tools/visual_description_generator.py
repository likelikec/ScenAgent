import asyncio
import concurrent

try:
    from Citlali.models.entity import ChatMessage
    from Citlali.models.openai.client import OpenAIChatClient
    from Citlali.utils.image import Image as CitlaliImage
    CITLALI_AVAILABLE = True
except ImportError:
    CITLALI_AVAILABLE = False
    ChatMessage = None
    OpenAIChatClient = None
    CitlaliImage = None

from ...core.interfaces import ModelConfig
from ...entity import ScreenFileInfo


class VisualDescriptionGenerator:
    def __init__(self, visual_prompt_model_config: ModelConfig):
        if not CITLALI_AVAILABLE:
            raise ImportError("Citlali is required for VisualDescriptionGenerator. Please install it.")
        
        self._model_client = OpenAIChatClient({
            'model': visual_prompt_model_config.model_name,
            'base_url': visual_prompt_model_config.api_base,
            'api_key': visual_prompt_model_config.api_key,
            'model_info': {"vision": True}
        })

    async def _request_llm(self, content, image: CitlaliImage):
        # 检查image, 宽高小于10的直接忽略
        if image.image.height <= 10 or image.image.width <= 10:
            return None

        user_message = ChatMessage(content=[content]+[image], type="UserMessage", source="user")
        response = await self._model_client.create(
            [user_message]
        )
        return response.content

    async def generate_visual_description(self, screenshot_file: ScreenFileInfo, image_coordinates):
        prompt = 'This image is an icon/image from a phone screen. Please briefly describe it in one sentence.'
        cropped_images = self._image_split(screenshot_file, image_coordinates)
        tasks = [
            self._request_llm(prompt, image) for image in cropped_images
        ]
        results = await asyncio.gather(*tasks)
        return {i: result for i, result in enumerate(results)}

    def _image_split(self, screenshot_file: ScreenFileInfo, image_coordinates_list):
        image = screenshot_file.get_screenshot_PILImage_file() # PILImage
        # 保存分割图像的列表
        cropped_images = []
        for coordinates in image_coordinates_list:
            (x1, y1), (x2, y2) = coordinates
            # 裁剪区域并添加到列表中
            cropped_image = image.crop((x1, y1, x2, y2))
            # cropped_image.save(screenshot_file.file_path + f"/t/image_{x1}_{y1}_{x2}_{y2}.png")
            cropped_images.append(CitlaliImage(cropped_image)) # Citlali Image
        return cropped_images

