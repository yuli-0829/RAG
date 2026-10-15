"""微调 bert-base-chinese，产出 new_bert 问题分类模型。"""
import json
import os

import torch
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

LABELS = ["通用知识", "专业知识"]
LABEL2ID = {label: index for index, label in enumerate(LABELS)}
ID2LABEL = {index: label for label, index in LABEL2ID.items()}

DATA_PATH = os.path.join(settings.base_dir, "bert_data", "bert_train.jsonl")
BASE_MODEL = os.path.join(settings.base_dir, "models", "bert-base-chinese")
OUTPUT_DIR = settings.classifier_path

MAX_LEN = 64
BATCH_SIZE = 16
EPOCHS = 5
LR = 2e-5
SEED = 42
VAL_RATIO = 0.2


class QueryDataset(Dataset):
    def __init__(self, texts, labels, tokenizer):
        self.encodings = tokenizer(
            texts, truncation=True, padding="max_length", max_length=MAX_LEN
        )
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        item = {key: torch.tensor(value[index]) for key, value in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[index])
        return item


def load_samples():
    with open(DATA_PATH, encoding="utf-8") as file:
        rows = [json.loads(line) for line in file if line.strip()]
    unknown = {row["label"] for row in rows} - set(LABELS)
    if unknown:
        raise ValueError(f"存在未知标签: {unknown}")
    return [row["query"] for row in rows], [LABEL2ID[row["label"]] for row in rows]


def evaluate(model, loader, device):
    model.eval()
    predictions, truths = [], []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            predictions.extend(logits.argmax(dim=-1).cpu().tolist())
            truths.extend(batch["labels"].cpu().tolist())
    return accuracy_score(truths, predictions), predictions, truths


def train():
    torch.manual_seed(SEED)
    device = torch.device(settings.model_device)

    texts, labels = load_samples()
    log.info("样本数 %s | 标签分布 %s", len(texts), {LABELS[i]: labels.count(i) for i in range(len(LABELS))})

    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=VAL_RATIO, random_state=SEED, stratify=labels
    )
    log.info("训练集 %s | 验证集 %s", len(train_texts), len(val_texts))

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID
    ).to(device)

    train_loader = DataLoader(
        QueryDataset(train_texts, train_labels, tokenizer), batch_size=BATCH_SIZE, shuffle=True
    )
    val_loader = DataLoader(
        QueryDataset(val_texts, val_labels, tokenizer), batch_size=BATCH_SIZE
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad()
            loss = model(**batch).loss
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        accuracy, _, _ = evaluate(model, val_loader, device)
        log.info(
            "epoch %s/%s | loss %.4f | val_acc %.4f",
            epoch, EPOCHS, total_loss / len(train_loader), accuracy,
        )

    accuracy, predictions, truths = evaluate(model, val_loader, device)
    print(classification_report(truths, predictions, target_names=LABELS, digits=4))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    log.info("模型已保存到 %s | 验证集准确率 %.4f", OUTPUT_DIR, accuracy)
    return accuracy


if __name__ == "__main__":
    train()
