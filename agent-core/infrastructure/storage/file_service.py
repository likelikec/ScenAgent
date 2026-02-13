"""文件操作服务"""
import os
import json
import time
from typing import Optional, Dict, Any
from pathlib import Path


class FileService:
    """文件操作服务类"""
    
    @staticmethod
    def ensure_dir(path: str) -> None:
        """确保目录存在"""
        os.makedirs(path, exist_ok=True)
    
    @staticmethod
    def read_json(file_path: str, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[Dict[str, Any]]:
        """安全地读取JSON文件，带重试机制
        
        Args:
            file_path: JSON文件路径
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        
        Returns:
            解析后的JSON数据，如果读取失败返回None
        """
        for attempt in range(max_retries):
            if not os.path.exists(file_path):
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except (json.JSONDecodeError, IOError, ValueError) as e:
                if attempt == max_retries - 1:
                    print(f"Failed to read JSON file {file_path} after {max_retries} attempts: {e}")
                    return None
                time.sleep(retry_delay)
        
        return None
    
    @staticmethod
    def write_json(file_path: str, data: Dict[str, Any], ensure_ascii: bool = False, indent: int = 4) -> bool:
        """写入JSON文件
        
        Args:
            file_path: JSON文件路径
            data: 要写入的数据
            ensure_ascii: 是否确保ASCII编码
            indent: 缩进空格数
            
        Returns:
            是否成功写入
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            return True
        except Exception as e:
            print(f"Failed to write JSON file {file_path}: {e}")
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        invalid = '<>:"/\\|?*'
        sanitized = ''.join(ch for ch in filename if ch not in invalid)
        sanitized = sanitized.strip()
        if len(sanitized) == 0:
            sanitized = "Unknown"
        return sanitized
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(file_path)
    
    @staticmethod
    def create_file_path(base_dir: str, *parts: str) -> str:
        """创建文件路径
        
        Args:
            base_dir: 基础目录
            *parts: 路径部分
            
        Returns:
            完整的文件路径
        """
        return os.path.join(base_dir, *parts)

