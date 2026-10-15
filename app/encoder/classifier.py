"""new_bert 问题分类（专业知识 / 通用知识）。"""
import os

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

DEFAULT_LABEL = "专业知识"

_model = None
_tokenizer = None
_unavailable = False


def _load():
    global _model, _tokenizer, _unavailable
    if _model is not None or _unavailable:
        return
    if not os.path.isdir(settings.classifier_path):
        log.warning("分类模型缺失, 默认按 %s 处理: %s", DEFAULT_LABEL, settings.classifier_path)
        _unavailable = True
        return
    _tokenizer = AutoTokenizer.from_pretrained(settings.classifier_path)
    _model = AutoModelForSequenceClassification.from_pretrained(settings.classifier_path)
    _model.eval()
    _model.to(settings.model_device)
    log.info("分类模型加载完成: %s", settings.classifier_path)


def classify(text):
    _load()
    if _model is None or _tokenizer is None:
        return DEFAULT_LABEL
    try:
        inputs = _tokenizer(
            text, return_tensors="pt", truncation=True, max_length=128
        ).to(settings.model_device)
        with torch.no_grad():
            logits = _model(**inputs).logits
        index = int(logits.argmax(dim=-1))
        label = _model.config.id2label.get(index, "")
        if label in settings.classifier_labels:
            return label
        if index < len(settings.classifier_labels):
            return settings.classifier_labels[index]
        return DEFAULT_LABEL
    except Exception as exc:
        log.error("问题分类失败, 回退 %s: %s", DEFAULT_LABEL, exc)
        return DEFAULT_LABEL
