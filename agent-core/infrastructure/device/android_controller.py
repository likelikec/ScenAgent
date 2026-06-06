"""Android设备控制器实现"""
import os
import time
import shutil
import tempfile
import subprocess
from urllib.parse import quote
from .device_controller import DeviceController


class AndroidController(DeviceController):
    """Android设备控制器"""
    
    def __init__(self, adb_path: str = None, device_id: str = None, print_device_cmd: bool = False):
        """初始化Android控制器
        
        Args:
            adb_path: ADB可执行文件路径，默认为"adb"
            device_id: 设备序列号 (UDID)
            print_device_cmd: 是否打印设备命令，默认为True
        """
        self.adb_path = adb_path or "adb"
        self.device_id = device_id
        self.print_device_cmd = bool(print_device_cmd)
        
        # 基础命令前缀，包含设备定向
        self.adb_base = f"{self.adb_path}"
        if self.device_id:
            self.adb_base += f" -s {self.device_id}"
    
    # 单条 adb 命令的最长等待时间（秒）。设备 offline/半死时 adb 客户端可能阻塞，
    # 没有超时会让整个 agent 永久卡死，故所有命令都强制超时。
    CMD_TIMEOUT = 20

    def _run_command(self, command: str, emit: bool = False, timeout: int = None) -> subprocess.CompletedProcess:
        """执行命令并处理编码问题（带超时，防止 adb 阻塞导致 agent 卡死）"""
        # 如果命令不是以 adb_base 开头，且是 adb 命令，则自动补充
        if command.startswith("adb "):
            # 替换原始的 adb 路径为带 -s 的基础路径
            command = command.replace("adb", self.adb_base, 1)
        elif command.startswith(self.adb_path) and self.device_id and f" -s {self.device_id}" not in command:
            # 替换原始的 adb 路径为带 -s 的基础路径
            command = command.replace(self.adb_path, self.adb_base, 1)

        if emit and self.print_device_cmd:
            print(self._format_cmd_for_print(command))
        effective_timeout = self.CMD_TIMEOUT if timeout is None else timeout
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=True,
                encoding='utf-8',
                errors='ignore',
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired:
            # 超时视为该命令失败：返回一个失败结果，让上层走重试/优雅退出，
            # 而不是无限阻塞。
            if emit and self.print_device_cmd:
                print(f"[ADB][TIMEOUT after {effective_timeout}s] {command}")
            return subprocess.CompletedProcess(
                command,
                returncode=124,
                stdout="",
                stderr=f"TimeoutExpired after {effective_timeout}s",
            )
        if emit and self.print_device_cmd:
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            if out:
                print(out)
            if err:
                print(err)
        return result

    def _format_cmd_for_print(self, command: str) -> str:
        prefix = f"{self.adb_path} shell "
        if command.startswith(prefix):
            rest = command[len(prefix):]
            rest = (rest or "").replace('"', '\\"')
            return f'[ADB] {self.adb_path} shell "{rest}"'
        return f"[ADB] {command}"

    def _pull_to_unicode_path(self, remote: str, save_path: str) -> bool:
        """adb pull 到可能含中文的本地路径。

        Windows 下 subprocess shell=True 经 cmd.exe 传参会用 GBK 编码，含中文的
        目标路径会被损坏（adb 报 No such file or directory）。这里先 pull 到纯
        ASCII 临时文件，再用 Python（Unicode 安全）移动到最终路径。
        """
        suffix = os.path.splitext(save_path)[1] or ""
        fd, tmp_path = tempfile.mkstemp(prefix="_mav4_pull_", suffix=suffix)
        os.close(fd)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        command = self.adb_path + f" pull {remote} \"{tmp_path}\""
        self._run_command(command, emit=True)
        if os.path.exists(tmp_path):
            try:
                parent = os.path.dirname(save_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                if os.path.exists(save_path):
                    os.remove(save_path)
                shutil.move(tmp_path, save_path)
            except Exception:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return os.path.exists(save_path)

    def get_screenshot(self, save_path: str) -> bool:
        """获取屏幕截图和DOM树"""
        # 获取截图
        command = self.adb_path + " shell rm /sdcard/screenshot.png"
        self._run_command(command, emit=True)
        time.sleep(0.5)
        command = self.adb_path + " shell screencap -p /sdcard/screenshot.png"
        self._run_command(command, emit=True)
        time.sleep(0.5)
        self._pull_to_unicode_path("/sdcard/screenshot.png", save_path)

        # 获取DOM树
        try:
            xml_save_path = os.path.splitext(save_path)[0] + ".xml"
            for _ in range(3):
                command = self.adb_path + " shell rm /sdcard/window_dump.xml"
                self._run_command(command, emit=True)
                command = self.adb_path + " shell uiautomator dump /sdcard/window_dump.xml"
                self._run_command(command, emit=True)
                time.sleep(0.5)
                self._pull_to_unicode_path("/sdcard/window_dump.xml", xml_save_path)
                if os.path.exists(xml_save_path):
                    break
        except Exception:
            pass

        return os.path.exists(save_path)
    
    def tap(self, x: int, y: int) -> str:
        """点击坐标"""
        command = self.adb_path + f" shell input tap {x} {y}"
        self._run_command(command, emit=True)
        return command
    
    def _sh_quote(self, s: str) -> str:
        return "'" + (s or "").replace("'", "'\\''") + "'"

    def _encode_for_input_text(self, s: str) -> str:
        encoded = quote(s or "", safe="-_.~")
        return encoded.replace("%20", "%s")

    def type(self, text: str) -> str:
        """输入文本"""
        commands = []

        normalized = (text or "").replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")

        def send_input_text_segment(seg: str) -> None:
            if not seg:
                return
            encoded = self._encode_for_input_text(seg)
            command = self.adb_path + f" shell input text {self._sh_quote(encoded)}"
            self._run_command(command, emit=True)
            commands.append(command)

        def send_adbkeyboard_char(ch: str) -> None:
            command = self.adb_path + f" shell am broadcast -a ADB_INPUT_TEXT --es msg {self._sh_quote(ch)}"
            self._run_command(command, emit=True)
            commands.append(command)

        def send_enter() -> None:
            command = self.adb_path + " shell input keyevent 66"
            self._run_command(command, emit=True)
            commands.append(command)

        for i, line in enumerate(lines):
            buf = ""
            for ch in line:
                if ord(ch) < 128:
                    buf += ch
                else:
                    send_input_text_segment(buf)
                    buf = ""
                    send_adbkeyboard_char(ch)
            send_input_text_segment(buf)

            if i != len(lines) - 1:
                send_enter()
        return "; ".join(commands)
    
    def delete(self, count: int = 1) -> str:
        """删除文本"""
        commands = []
        for _ in range(count):
            command = self.adb_path + f" shell input keyevent 67"
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
        command = self.adb_path + f" shell input swipe {x1} {y1} {x2} {y2} {duration}"
        self._run_command(command, emit=True)
        return command
    
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: int = 1000) -> str:
        """拖拽 (input draganddrop)
        
        Args:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 拖拽持续时间(ms)，默认1000ms（注：adb input draganddrop 命令本身不接受 duration 参数，此处仅为接口一致性保留参数，实际不使用）
        """
        command = self.adb_path + f" shell input draganddrop {x1} {y1} {x2} {y2}"
        self._run_command(command, emit=True)
        return command
    
    def back(self) -> str:
        """返回键"""
        command = self.adb_path + f" shell input keyevent 4"
        self._run_command(command, emit=True)
        return command
    
    def home(self) -> str:
        """主页键"""
        command = self.adb_path + f" shell am start -a android.intent.action.MAIN -c android.intent.category.HOME"
        self._run_command(command, emit=True)
        return command

    def enter(self) -> str:
        """回车键"""
        command = self.adb_path + " shell input keyevent 66"
        self._run_command(command, emit=True)
        return command
