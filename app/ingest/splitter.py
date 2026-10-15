"""父子分块：父块用于上下文，子块用于向量检索。"""
import re
from dataclasses import dataclass, field

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[。！？；!?;\n])")


@dataclass
class ParentChunk:
    parent_id: str
    content: str
    children: list[str] = field(default_factory=list)


def _normalize(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_long(text, max_size):
    chunks, buffer = [], ""
    for sentence in _SENTENCE.split(text):
        if not sentence:
            continue
        if buffer and len(buffer) + len(sentence) > max_size:
            chunks.append(buffer)
            buffer = sentence
        else:
            buffer += sentence
    if buffer:
        chunks.append(buffer)
    return chunks


def _blocks(text, max_size):
    result = []
    for paragraph in _PARAGRAPH.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        result.extend(
            _split_long(paragraph, max_size) if len(paragraph) > max_size else [paragraph]
        )
    return result


def _pack(blocks, size, overlap):
    chunks, buffer = [], ""
    for block in blocks:
        if buffer and len(buffer) + len(block) + 1 > size:
            chunks.append(buffer)
            buffer = (buffer[-overlap:] + "\n" + block).strip() if overlap else block
        else:
            buffer = f"{buffer}\n{block}".strip() if buffer else block
    if buffer:
        chunks.append(buffer)
    return chunks


def split_parent_child(text, parent_size, child_size, overlap, prefix):
    parents = _pack(_blocks(_normalize(text), parent_size), parent_size, overlap)
    chunks = []
    for index, content in enumerate(parents):
        children = _pack(_blocks(content, child_size), child_size, overlap)
        chunks.append(ParentChunk(f"{prefix}_{index}", content, children))
    return chunks
