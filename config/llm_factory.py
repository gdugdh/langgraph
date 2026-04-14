from __future__ import annotations
import os
from models import ServiceError

from langchain.chat_models import init_chat_model

def build_chat_llm(model_env_var: str) -> tuple[object | None, ServiceError | None]:
    print(f"[LLMFactory] start build_chat_llm model_env_var={model_env_var}")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        model = os.getenv(model_env_var, os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"))
        llm = init_chat_model(
            f"openai:{model}",
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )
        print(f"[LLMFactory] end build_chat_llm provider=openrouter model={model}")
        return llm, None

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        model = os.getenv(model_env_var, os.getenv("OPENAI_MODEL", "openai:gpt-4o-mini"))
        llm = init_chat_model(model)
        print(f"[LLMFactory] end build_chat_llm provider=openai model={model}")
        return llm, None

    print(f"[LLMFactory] fallback build_chat_llm provider=none model_env_var={model_env_var}")
    return None, ServiceError(
                code="cant_connect_to_llm",
                message="Cant connect to llm. "
            )
