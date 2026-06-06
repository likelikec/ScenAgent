"""Factory for GUI-Owl compatible LLM providers."""
from .llm_provider import LLMProvider
from .gui_owl_wrapper import GUIOwlWrapperAdapter


class LLMFactory:
    """Create LLM provider instances."""

    @staticmethod
    def create(
        provider_type: str = "gui_owl",
        api_key: str = None,
        base_url: str = None,
        model_name: str = None,
        temperature: float = 0.0,
        max_retry: int = 10,
        **kwargs
    ) -> LLMProvider:
        if not api_key or not base_url or not model_name:
            raise ValueError("api_key, base_url, and model_name are required")

        if provider_type != "gui_owl":
            raise ValueError(f"Unsupported provider type: {provider_type}. Use 'gui_owl'")

        return GUIOwlWrapperAdapter(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            max_retry=max_retry,
        )

    @staticmethod
    def create_from_config(config: dict) -> LLMProvider:
        return LLMFactory.create(
            provider_type=config.get("provider_type", "gui_owl"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            model_name=config.get("model") or config.get("model_name"),
            temperature=config.get("temperature", 0.0),
            max_retry=config.get("max_retry", 10),
        )
