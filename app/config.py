"""统一配置读取。"""
import os
from configparser import ConfigParser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG = ConfigParser()
_CONFIG.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")


def _str(section, option, default=""):
    if _CONFIG.has_option(section, option):
        return _CONFIG.get(section, option).strip()
    return default


def _int(section, option, default=0):
    try:
        return int(_str(section, option, str(default)))
    except ValueError:
        return default


def _float(section, option, default=0.0):
    try:
        return float(_str(section, option, str(default)))
    except ValueError:
        return default


def _bool(section, option, default=False):
    return _str(section, option, str(default)).lower() in {"1", "true", "yes", "on"}


def resolve(path):
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


class Settings:
    base_dir = BASE_DIR

    mysql_host = _str("mysql", "host", "localhost")
    mysql_port = _int("mysql", "port", 3306)
    mysql_user = _str("mysql", "user", "root")
    mysql_password = _str("mysql", "password", "")
    mysql_database = _str("mysql", "database", "e-commerce")
    mysql_charset = _str("mysql", "charset", "utf8mb4")

    milvus_host = _str("milvus", "host", "localhost")
    milvus_port = _int("milvus", "port", 19530)
    milvus_database = _str("milvus", "database_name", "default")
    milvus_collection = _str("milvus", "collection_name", "rag")
    milvus_metric = _str("milvus", "metric_type", "COSINE")
    milvus_index = _str("milvus", "index_type", "HNSW")
    milvus_dim = _int("milvus", "dim", 1024)

    llm_model = _str("llm", "model", "qwen-plus")
    llm_temperature = _float("llm", "temperature", 0.1)
    llm_api_key = _str("llm", "dashscope_api_key", "")
    llm_base_url = _str("llm", "dashscope_base_url", "")

    bge_m3_path = resolve(_str("model", "bge_m3_path", "models/bge-m3"))
    reranker_path = resolve(_str("model", "reranker_path", "models/bge-reranker-v2-m3"))
    classifier_path = resolve(_str("model", "classifier_path", "models/new_bert"))
    classifier_labels = [
        item.strip()
        for item in _str("model", "classifier_labels", "通用知识,专业知识").split(",")
        if item.strip()
    ]
    model_device = _str("model", "device", "cpu")
    model_batch_size = _int("model", "batch_size", 8)
    use_mineru = _bool("model", "use_mineru", False)
    mineru_tier = _str("model", "mineru_tier", "flash")

    parent_chunk_size = _int("retrieval", "parent_chunk_size", 1200)
    child_chunk_size = _int("retrieval", "child_chunk_size", 300)
    chunk_overlap = _int("retrieval", "chunk_overlap", 50)
    retrieval_k = _int("retrieval", "retrieval_k", 5)
    candidate_m = _int("retrieval", "candidate_m", 5)
    score_threshold = _float("retrieval", "score_threshold", 0.4)
    default_strategy = _str("retrieval", "default_strategy", "direct")

    data_dir = resolve(_str("ingest", "data_dir", "knowledge_data"))

    api_host = _str("api", "host", "0.0.0.0")
    api_port = _int("api", "port", 8000)


settings = Settings()
