"""bge-reranker-v2-m3 二次重排。"""
from sentence_transformers import CrossEncoder

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

_model = None


def get_model():
    global _model
    if _model is None:
        log.info("加载重排模型: %s", settings.reranker_path)
        _model = CrossEncoder(
            settings.reranker_path, max_length=512, device=settings.model_device
        )
    return _model


def rerank(query, contexts):
    if not contexts:
        return []
    pairs = [[query, item["content"]] for item in contexts]
    scores = get_model().predict(pairs)
    for item, score in zip(contexts, scores):
        item["rerank_score"] = float(score)
    return sorted(contexts, key=lambda item: item["rerank_score"], reverse=True)
