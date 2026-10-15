"""Qwen（OpenAI 兼容接口）调用。"""
from openai import OpenAI

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

_DEFAULT_SYSTEM = "你是电商售后知识库助手，回答简洁准确。"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key, base_url=settings.llm_base_url, timeout=60
        )
    return _client


def chat(prompt, system=None, temperature=None):
    try:
        response = get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system or _DEFAULT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.llm_temperature if temperature is None else temperature,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        log.error("LLM 调用失败: %s", exc)
        raise
