"""
Abstract interfaces for screen perceptor configuration and dependencies.
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Protocol
from enum import Enum

from ..entity import ScreenFileInfo, ActivityInfo


class ScreenPerceptionType(Enum):
    """Screen perception type enumeration."""
    SSIP = "SSIP"


class MobileControllerType(Enum):
    """Mobile controller type enumeration."""
    UIAutomator = "UI_AUTOMATOR"
    ADB = "ADB"


class ModelConfig(Protocol):
    """Protocol for model configuration."""
    model_name: str
    model_temperature: float
    model_info: Optional[dict]
    api_base: Optional[str]
    api_key: Optional[str]
    timeout: int
    stream: bool


class ScreenPerceptorConfig(ABC):
    """Abstract base class for screen perceptor configuration."""
    
    @property
    @abstractmethod
    def screen_perception_type(self) -> ScreenPerceptionType:
        """Get the screen perception type."""
        pass
    
    @property
    @abstractmethod
    def screenshot_getter_type(self) -> MobileControllerType:
        """Get the screenshot getter type."""
        pass
    
    @property
    @abstractmethod
    def visual_prompt_model_config(self) -> Optional[ModelConfig]:
        """Get visual prompt model configuration."""
        pass
    
    @property
    @abstractmethod
    def text_summarization_model_config(self) -> Optional[ModelConfig]:
        """Get text summarization model configuration."""
        pass
    
    @property
    @abstractmethod
    def non_visual_mode(self) -> bool:
        """Get non-visual mode setting."""
        pass


class MobileScreenCapturer(ABC):
    """Abstract interface for mobile screen capturer."""
    
    @abstractmethod
    async def get_screen(self) -> Tuple[ScreenFileInfo, Optional[str]]:
        """
        Get screen screenshot and UI hierarchy.
        
        Returns:
            Tuple of (screenshot_file_info, ui_hierarchy_xml)
            ui_hierarchy_xml can be None if not available
        """
        pass
    
    @abstractmethod
    async def get_current_activity(self) -> ActivityInfo:
        """Get current activity information."""
        pass
    
    @abstractmethod
    async def get_keyboard_activation_status(self) -> Tuple[str, bool]:
        """
        Get keyboard activation status.
        
        Returns:
            Tuple of (status_string, is_activated)
        """
        pass

