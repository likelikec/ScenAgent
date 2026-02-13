"""截图服务"""
import os
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Tuple, Any
from PIL import Image
from infrastructure.device.device_controller import DeviceController
from infrastructure.storage.file_service import FileService
from services.som_service import SoMService


class ScreenshotService:
    """截图服务类"""
    
    def __init__(
        self, 
        device_controller: DeviceController, 
        image_save_dir: str,
        perception_mode: str = "vllm"
    ):
        """初始化截图服务
        
        Args:
            device_controller: 设备控制器
            image_save_dir: 图片保存目录
            perception_mode: 感知模式 ("vllm" 或 "som")
        """
        self.device_controller = device_controller
        self.image_save_dir = image_save_dir
        self.perception_mode = perception_mode
        self.som_service = None
        self.current_som_mapping: Dict[str, Any] = {}
        
        FileService.ensure_dir(image_save_dir)
        
        # Initialize SoM service if needed
        if self.perception_mode == "som":
            try:
                self.som_service = SoMService()
                # Create marked subfolder
                marked_dir = os.path.join(image_save_dir, "marked")
                FileService.ensure_dir(marked_dir)
            except ImportError as e:
                error_msg = str(e)
                print(f"Warning: SoM mode requested but dependencies not available: {error_msg}")
                if "loguru" in error_msg.lower():
                    print("Hint: Install missing dependency with: pip install loguru")
                print("Falling back to VLLM mode")
                self.perception_mode = "vllm"
    
    def take_screenshot(self, retry_count: int = 5, retry_delay: int = 6) -> Optional[str]:
        """获取截图
        
        Args:
            retry_count: 重试次数
            retry_delay: 重试延迟（秒）
            
        Returns:
            截图文件路径（如果是SoM模式，返回marked图片路径），如果失败返回None
        """
        # 生成文件名
        current_time = datetime.now()
        formatted_time = current_time.strftime(
            f'%Y-%m-%d-{current_time.hour * 3600 + current_time.minute * 60 + current_time.second}-{str(uuid.uuid4().hex[:8])}'
        )
        screenshot_path = os.path.join(self.image_save_dir, f"screenshot_{formatted_time}.png")
        
        # 尝试获取截图
        for _ in range(retry_count):
            if self.device_controller.get_screenshot(screenshot_path):
                if os.path.exists(screenshot_path):
                    # Process with SoM if needed
                    if self.perception_mode == "som" and self.som_service:
                        return self._process_som(screenshot_path)
                    return screenshot_path
            print("Get screenshot failed, retry.")
            time.sleep(retry_delay)
        
        return None
    
    def _process_som(self, screenshot_path: str) -> Optional[str]:
        """Process screenshot with SoM marking
        
        Args:
            screenshot_path: Original screenshot path
            
        Returns:
            Marked screenshot path, or original if processing fails
        """
        try:
            # Get corresponding XML path
            xml_path = os.path.splitext(screenshot_path)[0] + ".xml"
            
            if not os.path.exists(xml_path):
                print(f"Warning: XML file not found for SoM processing: {xml_path}")
                print("Falling back to original screenshot")
                return screenshot_path
            
            # Process with SoM
            marked_dir = os.path.join(self.image_save_dir, "marked")
            marked_image_path, mapping_json_path, som_mapping = self.som_service.process_screenshot(
                screenshot_path,
                xml_path,
                marked_dir,
                target_app=None  # Could be extended to pass app package
            )
            
            # Store current mapping
            self.current_som_mapping = som_mapping
            
            print(f"SoM processing complete: {len(som_mapping)} elements marked")
            return marked_image_path
            
        except Exception as e:
            print(f"Error during SoM processing: {e}")
            print("Falling back to original screenshot")
            return screenshot_path
    
    def get_som_mapping(self) -> Dict[str, Any]:
        """Get current SoM mapping
        
        Returns:
            Dictionary mapping mark strings to coordinates
        """
        return self.current_som_mapping
    
    def get_image_size(self, image_path: str) -> Optional[tuple[int, int]]:
        """获取图片尺寸
        
        Args:
            image_path: 图片路径
            
        Returns:
            (width, height) 元组，如果失败返回None
        """
        try:
            img = Image.open(image_path)
            return img.size
        except Exception as e:
            print(f"Failed to get image size: {e}")
            return None

