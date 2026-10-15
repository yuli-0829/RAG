"""接口数据模型。"""
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    strategy: str | None = Field(
        None, description="检索策略: direct / hyde / subquery / step_back"
    )


class ContextItem(BaseModel):
    doc_id: int
    doc_name: str
    score: float
    rerank_score: float
    content: str


class QueryResponse(BaseModel):
    answer: str
    category: str
    strategy: str
    sources: list[str]
    contexts: list[ContextItem]


class DocumentItem(BaseModel):
    doc_id: int
    doc_name: str
    upload_time: str
    file_type: str
    status: str


class DocsResponse(BaseModel):
    total: int
    documents: list[DocumentItem]
