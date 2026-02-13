"""配置类"""
import os
from typing import Optional, Dict, Any

PRINT_DEVICE_CMD = True


def get_project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resolve_print_device_cmd(cli_value: Optional[bool] = None) -> bool:
    if cli_value is not None:
        return bool(cli_value)
    env = (os.getenv("MOBILE_V4_PRINT_DEVICE_CMD") or "").strip().lower()
    if env in ("1", "true", "yes", "y", "on"):
        return True
    if env in ("0", "false", "no", "n", "off"):
        return False
    return bool(PRINT_DEVICE_CMD)


def resolve_summary_llm_params(
    vllm_api_key: Optional[str],
    vllm_base_url: Optional[str],
    vllm_model_name: Optional[str],
    summary_api_key: Optional[str] = None,
    summary_base_url: Optional[str] = None,
    summary_model_name: Optional[str] = None,
) -> Dict[str, Any]:
    provider_type = "gui_owl"
    temperature = 0.0
    max_retry = 10

    api_key = summary_api_key or vllm_api_key
    base_url = summary_base_url or vllm_base_url
    model_name = summary_model_name or vllm_model_name

    return {
        "provider_type": provider_type,
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
        "temperature": temperature,
        "max_retry": max_retry,
    }
