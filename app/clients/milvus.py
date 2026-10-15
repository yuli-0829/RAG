"""Milvus 向量库封装（父子分块共存一个集合）。"""
import json
import re

from pymilvus import DataType, MilvusClient

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

_URI = f"http://{settings.milvus_host}:{settings.milvus_port}"
_CHILD = "child"
_PARENT = "parent"
_NAME_RE = re.compile(r"[^0-9a-zA-Z_]")

_client = None


def _sanitize(name, fallback):
    """Milvus 的库名/集合名只允许数字、字母、下划线。"""
    cleaned = _NAME_RE.sub("_", name or "").strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if cleaned != name:
        log.warning("Milvus 名称含非法字符, 已自动调整: %s -> %s", name, cleaned)
    return cleaned


_DB = _sanitize(settings.milvus_database, "default")
_COLL = _sanitize(settings.milvus_collection, "rag")


def get_client():
    global _client
    if _client is None:
        _client = MilvusClient(uri=_URI, db_name=_DB)
    return _client


def _ensure_database():
    if _DB == "default":
        return
    root = MilvusClient(uri=_URI)
    try:
        if _DB not in root.list_databases():
            root.create_database(_DB)
            log.info("Milvus 数据库已创建: %s", _DB)
    finally:
        root.close()


def ensure_collection():
    _ensure_database()
    client = get_client()
    if client.has_collection(_COLL):
        client.load_collection(_COLL)
        return

    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("pk", DataType.INT64, is_primary=True)
    schema.add_field("doc_id", DataType.INT64)
    schema.add_field("parent_id", DataType.VARCHAR, max_length=128)
    schema.add_field("chunk_type", DataType.VARCHAR, max_length=16)
    schema.add_field("content", DataType.VARCHAR, max_length=16384)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=settings.milvus_dim)

    index = client.prepare_index_params()
    index.add_index(
        field_name="vector",
        index_type=settings.milvus_index,
        metric_type=settings.milvus_metric,
        params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(
        collection_name=_COLL,
        schema=schema,
        index_params=index,
        consistency_level="Strong",
    )
    log.info("Milvus 集合已创建: %s.%s", _DB, _COLL)


def check_connection():
    root = MilvusClient(uri=_URI)
    try:
        root.list_collections()
        return True
    finally:
        root.close()


def delete_by_doc(doc_id):
    get_client().delete(collection_name=_COLL, filter=f"doc_id == {int(doc_id)}")


def insert_rows(rows):
    if not rows:
        return
    get_client().insert(collection_name=_COLL, data=rows)


def count_by_doc(doc_id):
    res = get_client().query(
        collection_name=_COLL,
        filter=f"doc_id == {int(doc_id)}",
        output_fields=["count(*)"],
    )
    return int(res[0]["count(*)"]) if res else 0


def search_children(vector, limit):
    res = get_client().search(
        collection_name=_COLL,
        data=[vector],
        limit=max(1, int(limit)),
        filter=f'chunk_type == "{_CHILD}"',
        output_fields=["doc_id", "parent_id", "content"],
        search_params={"metric_type": settings.milvus_metric, "params": {"ef": 128}},
    )
    return res[0] if res else []


def query_parents(parent_ids):
    ids = list({str(p) for p in parent_ids})
    if not ids:
        return []
    res = get_client().query(
        collection_name=_COLL,
        filter=f'chunk_type == "{_PARENT}" and parent_id in {json.dumps(ids)}',
        output_fields=["doc_id", "parent_id", "content"],
        limit=len(ids),
    )
    return res
