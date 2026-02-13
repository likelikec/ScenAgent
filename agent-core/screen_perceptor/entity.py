"""
Entity classes for screen perception.
"""
import string
import random
from datetime import datetime
from typing import Optional
from loguru import logger

try:
    from Citlali.utils.image import Image
    CITLALI_AVAILABLE = True
except ImportError:
    CITLALI_AVAILABLE = False
    Image = None

from PIL import Image as PILImage


class ScreenFileInfo:
    """Information about a screenshot file."""
    
    def __init__(self, file_path, file_name, file_type, file_build_timestamp=None):
        self.file_path = file_path
        self.file_name = file_name
        self.file_extra_name = None
        self.file_type = file_type
        self.file_build_timestamp = int(datetime.now().timestamp()) if file_build_timestamp is None else file_build_timestamp

    def set_extra_name(self, extra_name):
        self.file_extra_name = extra_name

    def get_screenshot_filename(self, no_type: bool = False) -> str:
        return (f"{self.file_name}_"
                f"{str(self.file_build_timestamp)}{'' if self.file_extra_name is None else f'_{self.file_extra_name}'}"
                f"{''if no_type else f'.{self.file_type}'}")

    def get_screenshot_fullpath(self):
        return f"{self.file_path}/{self.get_screenshot_filename()}"

    def get_screenshot_PILImage_file(self):
        return PILImage.open(self.get_screenshot_fullpath())

    def get_screenshot_Image_file(self):
        if not CITLALI_AVAILABLE:
            raise ImportError("Citlali is not available. Please install it or use get_screenshot_PILImage_file() instead.")
        return Image(PILImage.open(self.get_screenshot_fullpath()))

    def compress_image_to_jpeg(self, quality=50):
        with PILImage.open(self.get_screenshot_fullpath()) as img:
            img = img.convert('RGB')
            self.file_type = 'jpeg'
            img.save(self.get_screenshot_fullpath(), 'JPEG', quality=quality)


class ActivityInfo:
    """Information about the current Android activity."""
    
    def __init__(self, package_name, activity, user_id, window_id):
        self.package_name = package_name
        self.activity = activity
        self.user_id = user_id
        self.window_id = window_id


class ScreenPerceptionInfo:
    """Base class for screen perception information."""
    
    def __init__(self, width, height, perception_infos, keyboard_status=None, use_set_of_marks_mapping=False):
        self.width = width
        self.height = height
        self.infos = perception_infos
        self.keyboard_status = keyboard_status

        self.use_set_of_marks_mapping = use_set_of_marks_mapping

        self.log_tag = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        logger.bind(log_tag="screen_perception").debug(f"Screen Info [{self.log_tag}]\n{self._perception_infos_to_str()}")

    def _perception_infos_to_str(self):
        return self.infos

    def __str__(self):
        return (f"\n---Screen Perception Info---\n"
                f" - Use SoM Mapping: {self.use_set_of_marks_mapping}\n"
                f" - Screen Width: {self.width}\n"
                f" - Screen Height: {self.height}\n"
                f" - Screen Info: RECORDED IN THE LOG {self.log_tag}\n"
                f" - Keyboard Status: {self.keyboard_status}")

    def convert_marks_to_coordinates(self, mark):
        """Convert a mark to coordinates. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement convert_marks_to_coordinates")

    def get_screen_info_prompt(self, extra_suffix=None):
        """Get screen info prompt. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement get_screen_info_prompt")

    def get_screen_info_note_prompt(self, description_prefix):
        """Get screen info note prompt. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement get_screen_info_note_prompt")

