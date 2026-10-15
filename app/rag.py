"""RAG 问答编排。"""
from app.clients import mysql
from app.config import settings
from app.encoder.classifier import classify
from app.llm.qwen import chat
from app.retrieve.searcher import search
from logger import get_logger

log = get_logger(__name__)

NO_RESULT = "知识库无相关内容"

_RAG_SYSTEM = """你是电商售后知识库问答助手，必须遵守以下规则：
1. 只允许依据【参考资料】作答，禁止编造、推测或引入资料之外的知识。
2. 参考资料无法回答时，只回复：知识库无相关内容
3. 直接给出结论，不要复述"参考资料""根据资料"等字样，不要输出来源信息。"""


def _build_context(contexts, names):
    blocks = []
    for index, item in enumerate(contexts, 1):
        blocks.append(f"[{index}] 文档：{names.get(item['doc_id'], '未知文档')}\n{item['content']}")
    return "\n\n".join(blocks)


def answer(question, strategy=None):
    question = (question or "").strip()
    if not question:
        raise ValueError("问题不能为空")

    category = classify(question)
    if category != "专业知识":
        log.info("通用知识问题, 直接调用 LLM: %s", question)
        return {
            "answer": chat(question),
            "category": category,
            "strategy": "none",
            "sources": [],
            "contexts": [],
        }

    used_strategy = (strategy or settings.default_strategy).lower()
    contexts = search(question, used_strategy)
    if not contexts:
        return {
            "answer": NO_RESULT,
            "category": category,
            "strategy": used_strategy,
            "sources": [],
            "contexts": [],
        }

    names = mysql.get_doc_names({item["doc_id"] for item in contexts})
    prompt = f"【参考资料】\n{_build_context(contexts, names)}\n\n【用户问题】\n{question}"
    content = chat(prompt, system=_RAG_SYSTEM)

    sources = []
    for item in contexts:
        name = names.get(item["doc_id"])
        if name and name not in sources:
            sources.append(name)
    if NO_RESULT not in content:
        content = f"{content}\n\n来源：{'、'.join(sources)}"

    for item in contexts:
        item["doc_name"] = names.get(item["doc_id"], "未知文档")

    return {
        "answer": content,
        "category": category,
        "strategy": used_strategy,
        "sources": sources,
        "contexts": contexts,
    }
