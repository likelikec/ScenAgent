"""动作执行服务"""
import json
from typing import Dict, Any, Optional, Tuple, Union, List
from infrastructure.device.device_controller import DeviceController
from .coordinate_service import CoordinateService
from core.actions import ANSWER, CLICK, SWIPE, TYPE, SYSTEM_BUTTON, WAIT, DELETE
import time



class ActionService:
    """动作执行服务类"""
    
    def __init__(
        self,
        device_controller: DeviceController,
        coordinate_service: CoordinateService,
        perception_mode: str = "vllm"
    ):
        """初始化动作执行服务
        
        Args:
            device_controller: 设备控制器
            coordinate_service: 坐标转换服务
            perception_mode: 感知模式 ("vllm" 或 "som")
        """
        self.device_controller = device_controller
        self.coordinate_service = coordinate_service
        self.perception_mode = perception_mode
        self.som_mapping: Dict[str, Any] = {}
        self.last_used_mark: Optional[str] = None  # Track last mark for script recording
    
    def set_som_mapping(self, mapping: Dict[str, Any]) -> None:
        """Set SoM mapping for current screenshot
        
        Args:
            mapping: Mark to coordinate mapping
        """
        self.som_mapping = mapping
        self.last_used_mark = None
    
    def get_last_used_mark(self) -> Optional[str]:
        """Get the last mark used in an action
        
        Returns:
            Last mark string or None
        """
        return self.last_used_mark
    
    def _resolve_coordinate(
        self,
        coord: Union[str, List[int], Tuple[int, int]],
        coor_type: str,
        screen_width: Optional[int],
        screen_height: Optional[int]
    ) -> Optional[Tuple[int, int]]:
        """Resolve coordinate from mark or direct value
        
        Args:
            coord: Coordinate (can be mark string or [x, y])
            coor_type: Coordinate type
            screen_width: Screen width
            screen_height: Screen height
            
        Returns:
            Resolved (x, y) tuple or None
        """
        # Handle SoM mark (string)
        if isinstance(coord, str):
            if self.perception_mode == "som" and coord in self.som_mapping:
                self.last_used_mark = coord
                value = self.som_mapping[coord]
                if isinstance(value, dict):
                    center = value.get("center")
                    if isinstance(center, (list, tuple)) and len(center) >= 2:
                        return (int(center[0]), int(center[1]))
                    return None
                if isinstance(value, (list, tuple)) and len(value) >= 2:
                    return (int(value[0]), int(value[1]))
                return None
            else:
                print(f"Warning: Mark '{coord}' not found in SoM mapping")
                return None
        
        # Handle direct coordinates
        if isinstance(coord, (list, tuple)) and len(coord) >= 2:
            # Convert if needed
            if coor_type != "abs" and screen_width and screen_height:
                converted = self.coordinate_service.convert_coordinate(
                    list(coord), screen_width, screen_height
                )
                return tuple(converted)
            return (coord[0], coord[1])
        
        return None

    def _resolve_som_bounds(self, mark: str) -> Optional[Tuple[int, int, int, int]]:
        if not isinstance(mark, str):
            return None
        if self.perception_mode != "som":
            return None
        value = self.som_mapping.get(mark)
        if not isinstance(value, dict):
            return None
        bounds = value.get("bounds")
        if not bounds or not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            return None
        p1, p2 = bounds[0], bounds[1]
        if not isinstance(p1, (list, tuple)) or not isinstance(p2, (list, tuple)) or len(p1) < 2 or len(p2) < 2:
            return None
        left, top = int(p1[0]), int(p1[1])
        right, bottom = int(p2[0]), int(p2[1])
        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom

    def _compute_swipe_points_from_target(
        self,
        target: str,
        direction: str,
        distance: Any,
        screen_width: Optional[int],
        screen_height: Optional[int]
    ) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        direction_norm = str(direction).strip().lower()
        try:
            dist = float(distance)
        except Exception:
            dist = 0.6
        dist = max(0.1, min(0.9, dist))

        bounds = self._resolve_som_bounds(target)
        if bounds:
            left, top, right, bottom = bounds
            w = right - left
            h = bottom - top
            margin_x = max(10, int(w * 0.1))
            margin_y = max(10, int(h * 0.1))
            usable_w = max(1, w - 2 * margin_x)
            usable_h = max(1, h - 2 * margin_y)
            min_px = 50

            if direction_norm in ("up", "down"):
                x = left + w // 2
                if direction_norm == "up":
                    start_y = top + margin_y + int(0.8 * usable_h)
                    swipe_len = max(min_px, int(dist * usable_h))
                    end_y = max(top + margin_y, start_y - swipe_len)
                else:
                    start_y = top + margin_y + int(0.2 * usable_h)
                    swipe_len = max(min_px, int(dist * usable_h))
                    end_y = min(bottom - margin_y, start_y + swipe_len)
                return (x, start_y), (x, end_y)

            if direction_norm in ("left", "right"):
                y = top + h // 2
                if direction_norm == "left":
                    start_x = left + margin_x + int(0.8 * usable_w)
                    swipe_len = max(min_px, int(dist * usable_w))
                    end_x = max(left + margin_x, start_x - swipe_len)
                else:
                    start_x = left + margin_x + int(0.2 * usable_w)
                    swipe_len = max(min_px, int(dist * usable_w))
                    end_x = min(right - margin_x, start_x + swipe_len)
                return (start_x, y), (end_x, y)

        if screen_width and screen_height:
            w = int(screen_width)
            h = int(screen_height)
            min_px = 200
            if direction_norm == "up":
                start = (w // 2, int(h * 0.75))
                end = (w // 2, max(0, start[1] - max(min_px, int(dist * h * 0.5))))
                return start, end
            if direction_norm == "down":
                start = (w // 2, int(h * 0.25))
                end = (w // 2, min(h - 1, start[1] + max(min_px, int(dist * h * 0.5))))
                return start, end
            if direction_norm == "left":
                start = (int(w * 0.8), h // 2)
                end = (max(0, start[0] - max(min_px, int(dist * w * 0.5))), h // 2)
                return start, end
            if direction_norm == "right":
                start = (int(w * 0.2), h // 2)
                end = (min(w - 1, start[0] + max(min_px, int(dist * w * 0.5))), h // 2)
                return start, end

        return None
    
    def execute_action(
        self,
        action_object: Dict[str, Any],
        coor_type: str = "abs",
        screen_width: Optional[int] = None,
        screen_height: Optional[int] = None
    ) -> Optional[str]:
        """执行动作
        
        Args:
            action_object: 动作对象（JSON格式）
            coor_type: 坐标类型 ("abs" 或 "qwen-vl")
            screen_width: 屏幕宽度（用于坐标转换）
            screen_height: 屏幕高度（用于坐标转换）
            
        Returns:
            执行的命令字符串，如果失败返回None
        """
        try:
            action = action_object.get('action')
            
            if action == ANSWER:
                # answer动作不需要设备操作
                return None
            
            # Reset last used mark
            self.last_used_mark = None
            
            # 执行动作
            if action == CLICK:
                coord_raw = action_object.get('coordinate')
                if coord_raw:
                    coord = self._resolve_coordinate(coord_raw, coor_type, screen_width, screen_height)
                    if coord:
                        return self.device_controller.tap(coord[0], coord[1])
            
            elif action == SWIPE:
                target = action_object.get("target")
                direction = action_object.get("direction")
                distance = action_object.get("distance", 0.6)
                duration = int(float(action_object.get("duration", 0.5)) * 1000)  # Convert seconds to ms
                
                if target and direction:
                    if isinstance(target, str) and self.perception_mode == "som" and target in self.som_mapping:
                        self.last_used_mark = target
                    points = self._compute_swipe_points_from_target(
                        str(target),
                        str(direction),
                        distance,
                        screen_width,
                        screen_height
                    )
                    if points:
                        (x1, y1), (x2, y2) = points
                        if duration >= 1000:
                            return self.device_controller.drag(x1, y1, x2, y2, duration)
                        else:
                            return self.device_controller.slide(x1, y1, x2, y2, duration)

                coord1_raw = action_object.get('coordinate')
                coord2_raw = action_object.get('coordinate2')
                if coord1_raw and coord2_raw:
                    coord1 = self._resolve_coordinate(coord1_raw, coor_type, screen_width, screen_height)
                    coord2 = self._resolve_coordinate(coord2_raw, coor_type, screen_width, screen_height)
                    if coord1 and coord2:
                        if duration >= 1000:
                            return self.device_controller.drag(coord1[0], coord1[1], coord2[0], coord2[1], duration)
                        else:
                            return self.device_controller.slide(coord1[0], coord1[1], coord2[0], coord2[1], duration)
            
            elif action == TYPE:
                text = action_object.get('text')
                if text:
                    return self.device_controller.type(text)
            
            elif action == DELETE:
                count = action_object.get('count', 1)
                return self.device_controller.delete(count)
            
            elif action == SYSTEM_BUTTON:
                button = action_object.get('button')
                if button == "Back":
                    return self.device_controller.back()
                elif button == "Home":
                    return self.device_controller.home()
            
            elif action == WAIT:
                time.sleep(2)
                return "wait"

            return None
            
        except Exception as e:
            print(f"Failed to execute action: {e}")
            return None
    
    def parse_action_string(self, action_str: str) -> Optional[Dict[str, Any]]:
        """解析动作字符串为JSON对象
        
        Args:
            action_str: 动作字符串（JSON格式）
            
        Returns:
            解析后的动作对象，如果失败返回None
        """
        try:
            # 清理字符串
            action_str = action_str.replace("```", "").replace("json", "").strip()
            return json.loads(action_str)
        except Exception as e:
            print(f"Failed to parse action string: {e}")
            return None

