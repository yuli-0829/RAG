"""MySQL 文档元信息存储。"""
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

_CREATE_DATABASE = (
    f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
    "DEFAULT CHARACTER SET utf8mb4"
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS document_info (
    doc_id       BIGINT       NOT NULL AUTO_INCREMENT COMMENT '文档ID',
    doc_name     VARCHAR(255) NOT NULL              COMMENT '文档名称',
    upload_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    file_type    VARCHAR(32)  NOT NULL              COMMENT '文件类型',
    status       VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT '状态',
    content_hash CHAR(32)     NOT NULL              COMMENT '内容MD5,用于重复校验',
    PRIMARY KEY (doc_id),
    UNIQUE KEY uk_content_hash (content_hash),
    KEY idx_doc_name (doc_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档元信息表'
"""


def _connect(with_database=True):
    kwargs = {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password,
        "charset": settings.mysql_charset,
        "cursorclass": DictCursor,
        "autocommit": True,
    }
    if with_database:
        kwargs["database"] = settings.mysql_database
    return pymysql.connect(**kwargs)


@contextmanager
def _cursor(with_database=True):
    conn = _connect(with_database)
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def ensure_table():
    with _cursor(with_database=False) as cur:
        cur.execute(_CREATE_DATABASE)
    with _cursor() as cur:
        cur.execute(_CREATE_TABLE)
    log.info("MySQL 库表就绪: %s.document_info", settings.mysql_database)


def get_doc_by_hash(content_hash):
    with _cursor() as cur:
        cur.execute("SELECT * FROM document_info WHERE content_hash = %s", (content_hash,))
        return cur.fetchone()


def insert_doc(doc_name, file_type, content_hash):
    with _cursor() as cur:
        cur.execute(
            "INSERT INTO document_info (doc_name, file_type, status, content_hash) "
            "VALUES (%s, %s, 'pending', %s)",
            (doc_name, file_type, content_hash),
        )
        return cur.lastrowid


def update_status(doc_id, status):
    with _cursor() as cur:
        cur.execute(
            "UPDATE document_info SET status = %s WHERE doc_id = %s", (status, int(doc_id))
        )


def delete_doc(doc_id):
    with _cursor() as cur:
        cur.execute("DELETE FROM document_info WHERE doc_id = %s", (int(doc_id),))


def list_docs():
    with _cursor() as cur:
        cur.execute(
            "SELECT doc_id, doc_name, upload_time, file_type, status "
            "FROM document_info ORDER BY doc_id"
        )
        return cur.fetchall()


def get_doc_names(doc_ids):
    ids = sorted({int(i) for i in doc_ids})
    if not ids:
        return {}
    placeholders = ", ".join(["%s"] * len(ids))
    with _cursor() as cur:
        cur.execute(
            f"SELECT doc_id, doc_name FROM document_info WHERE doc_id IN ({placeholders})",
            ids,
        )
        return {row["doc_id"]: row["doc_name"] for row in cur.fetchall()}
