"""本地文档读取，优先 MinerU，缺失时回退轻量解析。"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

from app.config import settings
from logger import get_logger

log = get_logger(__name__)

SUPPORTED = {".md", ".txt", ".pdf", ".docx"}

_server_ready = False


def _read_text(path):
    for encoding in ("utf-8", "gbk"):
        try:
            with open(path, encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法解码文件: {path}")


def _read_pdf(path):
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(path):
    from docx import Document

    return "\n\n".join(p.text for p in Document(path).paragraphs if p.text.strip())


def _ensure_mineru_server():
    """MinerU 4.x 需要本地服务, 重复调用是幂等的。"""
    global _server_ready
    if _server_ready:
        return
    try:
        subprocess.run(
            [_mineru_command(), "server", "start"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except Exception as exc:
        log.warning("MinerU 服务启动失败: %s", exc)
    _server_ready = True


def _mineru_command():
    exe = shutil.which("mineru")
    if exe:
        return exe
    candidate = os.path.join(sys.prefix, "Scripts" if os.name == "nt" else "bin", "mineru")
    if os.name == "nt":
        candidate += ".exe"
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError("未找到 mineru 命令, 请先安装 MinerU")


def _read_with_mineru(path):
    """MinerU 4.x: mineru parse <file> --format markdown --tier <tier> --pages all"""
    _ensure_mineru_server()
    with tempfile.TemporaryDirectory() as out_dir:
        target = os.path.join(out_dir, "parsed.md")
        result = subprocess.run(
            [
                _mineru_command(),
                "parse",
                path,
                "--format",
                "markdown",
                "--tier",
                settings.mineru_tier,
                "--pages",
                "all",
                "--output",
                target,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "未知错误").strip()[-300:])
        if not os.path.exists(target):
            raise RuntimeError("MinerU 未生成解析结果")
        return _read_text(target)


_READERS = {
    ".md": _read_text,
    ".txt": _read_text,
    ".pdf": _read_pdf,
    ".docx": _read_docx,
}


def scan_files(data_dir=None):
    data_dir = data_dir or settings.data_dir
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")
    for root, _, files in os.walk(data_dir):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in SUPPORTED:
                yield os.path.join(root, name)


def file_hash(path):
    digest = hashlib.md5()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    ext = os.path.splitext(path)[1].lower()
    reader = _READERS.get(ext)
    if reader is None:
        raise ValueError(f"不支持的文件类型: {ext}")

    if settings.use_mineru and ext in {".pdf", ".docx"}:
        try:
            return _read_with_mineru(path).strip()
        except Exception as exc:
            log.warning("MinerU 解析失败, 回退内置解析 (%s): %s", os.path.basename(path), exc)
    return reader(path).strip()
