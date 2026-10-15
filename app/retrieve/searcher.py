"""向量召回 -> 阈值过滤 -> 去重初排 -> 二次重排。"""
from app.clients import milvus
from app.config import settings
from app.encoder.embedding import embed_texts
from app.encoder.reranker import rerank
from app.retrieve.strategies import expand
from logger import get_logger

log = get_logger(__name__)


def _recall(queries, limit):
    hits = []
    for vector in embed_texts(queries):
        hits.extend(milvus.search_children(vector, limit))
    return hits


def coarse_rank(hits):
    """按父子块聚合去重，保留每个父块的最高相似度。"""
    best = {}
    for hit in hits:
        entity = hit["entity"]
        parent_id = entity["parent_id"]
        score = float(hit["distance"])
        if parent_id not in best or score > best[parent_id]["score"]:
            best[parent_id] = {
                "parent_id": parent_id,
                "doc_id": entity["doc_id"],
                "score": score,
            }
    return sorted(best.values(), key=lambda item: item["score"], reverse=True)


def search(query, strategy=None):
    queries = expand(query, strategy)
    candidates = coarse_rank(_recall(queries, settings.retrieval_k * 3))

    filtered = [
        item for item in candidates if item["score"] >= settings.score_threshold
    ][: settings.retrieval_k]
    if not filtered:
        log.info("无片段通过相似度阈值 %s", settings.score_threshold)
        return []

    contents = {
        item["parent_id"]: item
        for item in milvus.query_parents([item["parent_id"] for item in filtered])
    }
    contexts = []
    for item in filtered:
        node = contents.get(item["parent_id"])
        if not node:
            continue
        contexts.append(
            {
                "parent_id": item["parent_id"],
                "doc_id": item["doc_id"],
                "score": item["score"],
                "content": node["content"],
            }
        )

    ranked = rerank(query, contexts)[: settings.candidate_m]
    log.info("召回 %s 个父块, 重排后保留 %s 条上下文", len(contexts), len(ranked))
    return ranked
