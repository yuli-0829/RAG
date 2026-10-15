"""FastAPI 接口层。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.clients import mysql
from app.config import settings
from app.ingest.pipeline import init_data
from app.rag import answer
from app.schemas import DocsResponse, QueryRequest, QueryResponse
from logger import get_logger

log = get_logger(__name__)

_STATIC_DIR = os.path.join(settings.base_dir, "static")
_SWAGGER_DIR = "/static/swagger-ui"


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        mysql.ensure_table()
    except Exception as exc:
        log.error("MySQL 初始化失败: %s", exc)
    yield


# docs_url=None: 关闭默认文档路由, 改用本地静态资源托管, 避免 cdn.jsdelivr.net 不可达导致白屏
app = FastAPI(
    title="电商 RAG 知识库",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def api_index():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


@app.get("/docs", include_in_schema=False)
def api_docs():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url=f"{_SWAGGER_DIR}/swagger-ui-bundle.js",
        swagger_css_url=f"{_SWAGGER_DIR}/swagger-ui.css",
        swagger_favicon_url="data:,",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )


@app.get("/docs/oauth2-redirect", include_in_schema=False)
def api_oauth2_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.post("/init_data", summary="加载本地数据集入库")
def api_init_data():
    try:
        return init_data()
    except Exception as exc:
        log.exception("init_data 异常")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query", response_model=QueryResponse, summary="知识库问答")
def api_query(req: QueryRequest):
    try:
        return answer(req.question, req.strategy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        log.exception("query 异常")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/docs_list", response_model=DocsResponse, summary="文档列表")
def api_docs_list():
    try:
        rows = mysql.list_docs()
    except Exception as exc:
        log.exception("docs_list 异常")
        raise HTTPException(status_code=500, detail=str(exc))
    documents = [
        {
            "doc_id": row["doc_id"],
            "doc_name": row["doc_name"],
            "upload_time": row["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "file_type": row["file_type"],
            "status": row["status"],
        }
        for row in rows
    ]
    return {"total": len(documents), "documents": documents}
