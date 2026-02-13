"""
Core screen perceptor class without Worker and event system dependencies.
"""
from loguru import logger
from typing import Optional

from ..entity import ScreenFileInfo, ScreenPerceptionInfo
from ..core.interfaces import (
    ScreenPerceptorConfig,
    MobileScreenCapturer,
    ScreenPerceptionType
)


class ScreenPerceptor:
    """
    Core screen perceptor class.
    This is a standalone version without Worker and event system dependencies.
    """
    
    def __init__(self, config: ScreenPerceptorConfig, screenshot_tool: MobileScreenCapturer):
        """
        Initialize the screen perceptor.
        
        Args:
            config: Screen perceptor configuration
            screenshot_tool: Mobile screen capturer instance
        """
        self.config = config
        self.screenshot_tool = screenshot_tool
        
        # Validate configuration
        if (config.screen_perception_type == ScreenPerceptionType.SSIP and 
            config.screenshot_getter_type.value == "ADB"):
            raise ValueError("SSIP requires uiautomator screenshot tool, but adb is used.")
    
    async def get_screen_description(self, target_app: Optional[str] = None) -> tuple[ScreenFileInfo, ScreenPerceptionInfo]:
        """
        Get screen description with perception information.
        
        Args:
            target_app: Target app package name (optional)
            
        Returns:
            Tuple of (screenshot_file_info, perception_infos)
        """
        # Get screen screenshot and UI hierarchy
        screenshot_file_info, ui_hierarchy_xml = await self.screenshot_tool.get_screen()
        screenshot_file_info.compress_image_to_jpeg()  # Compress image
        
        # Get keyboard activation status
        keyboard_status_result = await self.screenshot_tool.get_keyboard_activation_status()
        
        # Use appropriate perception type
        if self.config.screen_perception_type == ScreenPerceptionType.SSIP:
            from ..ssip.perceptor import ScreenStructuredInfoPerception
            
            ssip = ScreenStructuredInfoPerception(
                self.config.visual_prompt_model_config,
                self.config.text_summarization_model_config
            )
            screenshot_file_info, perception_infos = await ssip.get_perception_infos(
                screenshot_file_info,
                ui_hierarchy_xml,
                non_visual_mode=self.config.non_visual_mode,
                target_app=target_app
            )
        else:
            raise RuntimeError(
                f"Unsupported screen perception type: {self.config.screen_perception_type}"
            )
        
        # Set keyboard status
        perception_infos.keyboard_status = keyboard_status_result[1] == "true"
        
        return screenshot_file_info, perception_infos
    
    async def perceive_screen(self, target_app: Optional[str] = None) -> tuple[ScreenFileInfo, ScreenPerceptionInfo]:
        """
        Main method to perceive screen.
        This is a convenience method that gets current activity and then perceives screen.
        
        Args:
            target_app: Target app package name (optional, will use current activity if not provided)
            
        Returns:
            Tuple of (screenshot_file_info, perception_infos)
        """
        # Get current activity if target_app not provided
        if target_app is None:
            current_activity = await self.screenshot_tool.get_current_activity()
            target_app = current_activity.package_name
        
        return await self.get_screen_description(target_app)

