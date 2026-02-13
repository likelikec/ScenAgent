from pathlib import Path
from typing import Optional, List
import os
import time


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_name(s: Optional[str]) -> str:
    invalid = '<>:"/\\|?*'
    v = "".join(ch for ch in (s or "") if ch not in invalid).strip()
    return v or "Unknown"


def tail_text(path: Path, max_chars: int = 2000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if len(data) <= max_chars:
        return data.strip()
    return data[-max_chars:].strip()


def list_run_dirs(run_root: Path) -> List[str]:
    try:
        dirs = [p for p in run_root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: (p.stat().st_mtime, p.name))
        return [str(p) for p in dirs]
    except Exception:
        return []


def is_within_root(root: Path, target: Path) -> bool:
    try:
        root_resolved = root.resolve()
        target_resolved = target.resolve()
        try:
            return target_resolved.is_relative_to(root_resolved)
        except AttributeError:
            root_str = str(root_resolved)
            target_str = str(target_resolved)
            if not root_str.endswith(os.sep):
                root_str += os.sep
            return target_str.startswith(root_str)
    except Exception:
        return False


def now_ts() -> str:
    return str(time.time())
