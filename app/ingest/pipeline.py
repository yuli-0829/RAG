"""本地数据集入库流程，可重复执行。"""
import os

from app.clients import milvus, mysql
from app.config import settings
from app.encoder.embedding import embed_texts
from app.ingest import loader
from app.ingest.splitter import split_parent_child
from logger import get_logger

log = get_logger(__name__)


def _build_rows(doc_id, parents):
    rows, texts = [], []
    for parent in parents:
        rows.append(
            {
                "doc_id": doc_id,
                "parent_id": parent.parent_id,
                "chunk_type": "parent",
                "content": parent.content,
            }
        )
        texts.append(parent.content)
        for child in parent.children:
            rows.append(
                {
                    "doc_id": doc_id,
                    "parent_id": parent.parent_id,
                    "chunk_type": "child",
                    "content": child,
                }
            )
            texts.append(child)
    return rows, texts


def ingest_file(path):
    name = os.path.basename(path)
    file_type = os.path.splitext(name)[1].lower().lstrip(".")
    digest = loader.file_hash(path)

    existing = mysql.get_doc_by_hash(digest)
    if existing and existing["status"] == "completed":
        log.info("文档已入库, 跳过: %s", name)
        return {"doc_name": name, "doc_id": existing["doc_id"], "status": "skipped"}
    if existing:
        milvus.delete_by_doc(existing["doc_id"])
        mysql.delete_doc(existing["doc_id"])

    text = loader.load(path)
    if not text:
        raise ValueError(f"文档内容为空: {name}")

    doc_id = mysql.insert_doc(name, file_type, digest)
    mysql.update_status(doc_id, "processing")
    try:
        parents = split_parent_child(
            text,
            settings.parent_chunk_size,
            settings.child_chunk_size,
            settings.chunk_overlap,
            str(doc_id),
        )
        rows, texts = _build_rows(doc_id, parents)
        for row, vector in zip(rows, embed_texts(texts)):
            row["vector"] = vector

        milvus.delete_by_doc(doc_id)
        milvus.insert_rows(rows)
        mysql.update_status(doc_id, "completed")
        log.info("文档入库完成: %s (父块 %s, 向量 %s)", name, len(parents), len(rows))
        return {
            "doc_name": name,
            "doc_id": doc_id,
            "status": "success",
            "parents": len(parents),
            "chunks": len(rows),
        }
    except Exception:
        mysql.update_status(doc_id, "failed")
        log.exception("文档入库失败: %s", name)
        raise


def init_data():
    mysql.ensure_table()
    milvus.ensure_collection()
    results = []
    for path in loader.scan_files():
        try:
            results.append(ingest_file(path))
        except Exception as exc:
            log.error("处理失败: %s", exc)
            results.append(
                {"doc_name": os.path.basename(path), "status": "failed", "error": str(exc)}
            )
    summary = {
        "success": sum(1 for r in results if r["status"] == "success"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }
    log.info("init_data 完成: %s", summary)
    return {"total": len(results), "summary": summary, "results": results}
