"""HarmonyOS设备控制器实现"""
import os
import time
import subprocess
from .device_controller import DeviceController


class HarmonyOSController(DeviceController):
    """HarmonyOS设备控制器"""
    
    def __init__(self, hdc_path: str, print_device_cmd: bool = False):
        """初始化HarmonyOS控制器
        
        Args:
            hdc_path: HDC可执行文件路径
        """
        self.hdc_path = hdc_path
        self.print_device_cmd = bool(print_device_cmd)

    def _run_command(self, command: str, emit: bool = False) -> subprocess.CompletedProcess:
        if emit and self.print_device_cmd:
            print(self._format_cmd_for_print(command))
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if emit and self.print_device_cmd:
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            if out:
                print(out)
            if err:
                print(err)
        return result

    def _format_cmd_for_print(self, command: str) -> str:
        prefix = f"{self.hdc_path} shell "
        if command.startswith(prefix):
            rest = command[len(prefix):]
            rest = (rest or "").replace('"', '\\"')
            return f'[HDC] {self.hdc_path} shell "{rest}"'
        return f"[HDC] {command}"
    
    def get_screenshot(self, save_path: str) -> bool:
        """获取屏幕截图和DOM树"""
        # 获取截图
        command = self.hdc_path + " shell rm /data/local/tmp/screenshot.png"
        self._run_command(command, emit=True)
        time.sleep(0.5)
        command = self.hdc_path + " shell uitest screenCap -p /data/local/tmp/screenshot.png"
        self._run_command(command, emit=True)
        time.sleep(0.5)
        command = self.hdc_path + " file recv /data/local/tmp/screenshot.png \"" + save_path + "\""
        self._run_command(command, emit=True)
        time.sleep(0.5)
        
        # 获取DOM树
        try:
            xml_save_path = os.path.splitext(save_path)[0] + ".xml"
            # 尝试使用 dumpLayout 命令
            # 注意：HarmonyOS uitest 的具体 dump 命令可能因版本而异，这里假设为 dumpLayout 并捕获输出
            # 如果 uitest 支持导出到文件，应调整命令
            command = self.hdc_path + " shell uitest dumpLayout"
            result = self._run_command(command, emit=True)
            
            if result.returncode == 0 and result.stdout:
                # 如果输出包含 XML 声明或标签，则认为是 XML 内容
                if "<Hierarchy" in result.stdout or "<?xml" in result.stdout:
                    with open(xml_save_path, "w", encoding="utf-8") as f:
                        f.write(result.stdout)
                else:
                    # 尝试查找是否生成了默认文件，例如 /data/local/tmp/layout.xml
                    # 这里是一个备用策略
                    pass
        except Exception as e:
            print(f"Failed to get HarmonyOS DOM XML: {e}")

        return os.path.exists(save_path)
    
    def tap(self, x: int, y: int) -> str:
        """点击坐标"""
        command = self.hdc_path + f" shell uitest uiInput click {x} {y}"
        self._run_command(command, emit=True)
        return command
    
    def type(self, text: str) -> str:
        """输入文本"""
        text = text.replace("\\n", "_").replace("\n", "_")
        commands = []
        for char in text:
            if char == ' ':
                command = self.hdc_path + f" shell uitest uiInput keyEvent 2050"
                self._run_command(command, emit=True)
                commands.append(command)
            elif char == '_':
                command = self.hdc_path + f" shell uitest uiInput keyEvent 2054"
                self._run_command(command, emit=True)
                commands.append(command)
            elif 'a' <= char <= 'z' or 'A' <= char <= 'Z' or char.isdigit():
                command = self.hdc_path + f" shell uitest uiInput inputText 1 1 {char}"
                self._run_command(command, emit=True)
                commands.append(command)
            elif char in '-.,!?@\'°/:;()':
                command = self.hdc_path + f" shell uitest uiInput inputText 1 1 \"{char}\""
                self._run_command(command, emit=True)
                commands.append(command)
            else:
                command = self.hdc_path + f" shell uitest uiInput inputText 1 1 {char}"
                self._run_command(command, emit=True)
                commands.append(command)
        return "; ".join(commands)
    
    def delete(self, count: int = 1) -> str:
        """删除文本"""
        commands = []
        for _ in range(count):
            # 尝试使用 Delete 键
            command = self.hdc_path + " shell uitest uiInput keyEvent Delete"
            self._run_command(command, emit=True)
            commands.append(command)
        return "; ".join(commands)
    
    def slide(self, x1: int, y1: int, x2: int, y2: int, duration: int = 500) -> str:
        """滑动
        
        Args:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 滑动持续时间(ms)，默认500ms
        """
        command = self.hdc_path + f" shell uitest uiInput swipe {x1} {y1} {x2} {y2} {duration}"
        self._run_command(command, emit=True)
        return command
    
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: int = 1000) -> str:
        """拖拽 (封装slide，HarmonyOS暂无独立drag命令)
        
        Args:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 拖拽持续时间(ms)，默认1000ms（注：HarmonyOS暂无独立drag命令，使用slide模拟并忽略duration，以确保拖拽行为）
        """
        # 强制使用较长的 duration 以模拟拖拽行为，或者忽略传入的 duration 确保使用默认值
        # 这里为了确保拖拽效果，我们透传 duration，因为 slide 支持 duration
        return self.slide(x1, y1, x2, y2, duration)
    
    def back(self) -> str:
        """返回键"""
        command = self.hdc_path + " shell uitest uiInput keyEvent Back"
        self._run_command(command, emit=True)
        return command
    
    def home(self) -> str:
        """主页键"""
        command = self.hdc_path + " shell uitest uiInput keyEvent Home"
        self._run_command(command, emit=True)
        return command

