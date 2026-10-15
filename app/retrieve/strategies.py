"""检索策略调度：直接检索 / 假设问题 / 子问题 / 回溯问题。"""
from app.config import settings
from app.llm.qwen import chat
from logger import get_logger

log = get_logger(__name__)

STRATEGIES = ("direct", "hyde", "subquery", "step_back")

_HYDE_PROMPT = (
    "请针对下面的问题，写一段简短、直接的回答，用于语义检索。只输出回答内容。\n问题：{query}"
)
_SUBQUERY_PROMPT = (
    "请把下面的问题拆解成 3 个更具体的子问题，每行一个，不要编号，不要其他内容。\n问题：{query}"
)
_STEP_BACK_PROMPT = (
    "请把下面的问题抽象成一个更宏观、更基础的问题，用于检索背景知识。只输出问题本身。\n问题：{query}"
)


def _lines(text, limit=3):
    items = []
    for line in text.splitlines():
        cleaned = line.strip().lstrip("-*0123456789.、) ").strip()
        if cleaned:
            items.append(cleaned)
    return items[:limit]


def expand(query, strategy=None):
    strategy = (strategy or settings.default_strategy or "direct").lower()
    if strategy == "direct" or strategy not in STRATEGIES:
        return [query]
    try:
        if strategy == "hyde":
            return [query, chat(_HYDE_PROMPT.format(query=query))]
        if strategy == "subquery":
            return [query] + _lines(chat(_SUBQUERY_PROMPT.format(query=query)))
        if strategy == "step_back":
            return [query, chat(_STEP_BACK_PROMPT.format(query=query))]
    except Exception as exc:
        log.warning("策略 %s 生成查询失败, 回退直接检索: %s", strategy, exc)
    return [query]
