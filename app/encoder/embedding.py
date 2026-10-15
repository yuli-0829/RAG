"""BGE-M3 向量化。"""
from sentence_transformers import SentenceTransformer

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

_model = None


def get_model():
    global _model
    if _model is None:
        log.info("加载 Embedding 模型: %s", settings.bge_m3_path)
        _model = SentenceTransformer(settings.bge_m3_path, device=settings.model_device)
    return _model


def embed_texts(texts):
    texts = [t for t in texts if t and t.strip()]
    if not texts:
        return []
    vectors = get_model().encode(
        texts,
        batch_size=settings.model_batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embed_text(text):
    vectors = embed_texts([text])
    return vectors[0] if vectors else []
