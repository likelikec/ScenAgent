"""设备控制器抽象接口"""
from abc import ABC, abstractmethod


class DeviceController(ABC):
    """设备控制器抽象基类"""
    
    @abstractmethod
    def get_screenshot(self, save_path: str) -> bool:
        """获取屏幕截图和DOM树
        
        Args:
            save_path: 保存路径
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def tap(self, x: int, y: int) -> str:
        """点击坐标
        
        Args:
            x: X坐标
            y: Y坐标
            
        Returns:
            执行的命令字符串
        """
        pass
    
    @abstractmethod
    def type(self, text: str) -> str:
        """输入文本
        
        Args:
            text: 要输入的文本
            
        Returns:
            执行的命令字符串
        """
        pass
    
    @abstractmethod
    def delete(self, count: int = 1) -> str:
        """删除文本
        
        Args:
            count: 删除次数
            
        Returns:
            执行的命令字符串
        """
        pass
    
    @abstractmethod
    def slide(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """滑动
        
        Args:
            x1: 起始X坐标
            y1: 起始Y坐标
            x2: 结束X坐标
            y2: 结束Y坐标
            
        Returns:
            执行的命令字符串
        """
        pass
    
    @abstractmethod
    def back(self) -> str:
        """返回键
        
        Returns:
            执行的命令字符串
        """
        pass
    
    @abstractmethod
    def home(self) -> str:
        """主页键
        
        Returns:
            执行的命令字符串
        """
        pass

