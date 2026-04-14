from __future__ import annotations

import os

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

from models import ServiceError


def _read_env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip().strip('"').strip("'")


def build_openrouter_chat_llm(model_env_var: str) -> tuple[object | None, ServiceError | None]:
    api_key = _read_env("OPENROUTER_API_KEY")
    if not api_key:
        return None, ServiceError(
            code="openrouter_not_configured",
            message="OPENROUTER_API_KEY is empty.",
        )
    if ChatOpenAI is None:
        return None, ServiceError(
            code="langchain_openai_missing",
            message="langchain-openai is not installed.",
        )

    model = _read_env(model_env_var) or _read_env("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    # print(f"[LLMFactory] end build_chat_llm provider=openrouter model={model}")
    return (
        ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        ),
        None,
    )


def build_openai_chat_llm(model_env_var: str) -> tuple[object | None, ServiceError | None]:
    api_key = _read_env("OPENAI_API_KEY")
    if not api_key:
        return None, ServiceError(
            code="openai_not_configured",
            message="OPENAI_API_KEY is empty.",
        )
    if ChatOpenAI is None:
        return None, ServiceError(
            code="langchain_openai_missing",
            message="langchain-openai is not installed.",
        )

    model = _read_env(model_env_var) or _read_env("OPENAI_MODEL", "gpt-4o-mini")
    # print(f"[LLMFactory] end build_chat_llm provider=openai model={model}")
    return (
        ChatOpenAI(
            model=model,
            api_key=api_key,
        ),
        None,
    )


def build_ollama_chat_llm(model_env_var: str) -> tuple[object | None, ServiceError | None]:
    base_url = _read_env("OLLAMA_BASE_URL", "http://localhost:11434")
    model = _read_env(model_env_var) or _read_env("OLLAMA_MODEL", "llama3.2:1b")
    if ChatOllama is None:
        return None, ServiceError(
            code="langchain_ollama_missing",
            message="langchain-ollama is not installed.",
        )
    # print(f"[LLMFactory] end build_chat_llm provider=ollama model={model} base_url={base_url}")
    return (
        ChatOllama(
            model=model,
            base_url=base_url,
        ),
        None,
    )


def build_chat_llm(model_env_var: str) -> tuple[object | None, ServiceError | None]:
    # print(f"[LLMFactory] start build_chat_llm model_env_var={model_env_var}")

    openrouter_key = _read_env("OPENROUTER_API_KEY")
    if openrouter_key:
        return build_openrouter_chat_llm(model_env_var)

    openai_key = _read_env("OPENAI_API_KEY")
    if openai_key:
        return build_openai_chat_llm(model_env_var)

    return build_ollama_chat_llm(model_env_var)
