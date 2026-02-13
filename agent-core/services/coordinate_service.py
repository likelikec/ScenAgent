"""坐标转换服务"""
from typing import List


class CoordinateService:
    """坐标转换服务类"""
    
    @staticmethod
    def convert_coordinate(
        coordinate: List[int],
        screen_width: int,
        screen_height: int
    ) -> List[int]:
        """将相对坐标（0-1000）转换为绝对坐标（像素）
        
        Args:
            coordinate: 相对坐标 [x, y]，范围0-1000
            screen_width: 屏幕宽度（像素）
            screen_height: 屏幕高度（像素）
            
        Returns:
            绝对坐标 [x, y]（像素）
        """
        if len(coordinate) < 2:
            return coordinate
        
        x = int(coordinate[0] / 1000 * screen_width)
        y = int(coordinate[1] / 1000 * screen_height)
        return [x, y]
    
    @staticmethod
    def convert_to_relative(
        coordinate: List[int],
        screen_width: int,
        screen_height: int
    ) -> List[int]:
        """将绝对坐标（像素）转换为相对坐标（0-1000）
        
        Args:
            coordinate: 绝对坐标 [x, y]（像素）
            screen_width: 屏幕宽度（像素）
            screen_height: 屏幕高度（像素）
            
        Returns:
            相对坐标 [x, y]，范围0-1000
        """
        if len(coordinate) < 2:
            return coordinate
        
        x = int(coordinate[0] / screen_width * 1000)
        y = int(coordinate[1] / screen_height * 1000)
        return [x, y]

