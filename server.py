"""MCP server for recursively searching text extracted from PDF files."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any
from mcp.server.mcpserver import MCPServer

CACHE_DIR = Path(os.environ.get("PDF_RG_CACHE_DIR", "/var/tmp/pdf_rg"))
mcp = MCPServer(
    "pdf_search",
    version="1.0.0",
    instructions=(
        "基于pdftotext和rg递归搜索指定路径中的PDF,有pdftotext缓存用来加速。"
    ),
)

def cache_dir() -> Path:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR
    except OSError:
        fallback = Path("/tmp/pdf_rg")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def pdf_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".pdf" else []
    if not root.is_dir():
        return []
    return sorted((p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"), key=str)

def cached_text(pdf: Path, digest: str) -> Path:
    directory = cache_dir()
    target = directory / f"{digest}.txt"
    if target.is_file():
        return target
    fd, temporary = tempfile.mkstemp(prefix=f".{digest}.", suffix=".tmp", dir=directory)
    os.close(fd)
    temporary_path = Path(temporary)
    try:
        result = subprocess.run(["pdftotext", "-layout", str(pdf), str(temporary_path)], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or f"pdftotext exited with {result.returncode}")
        os.replace(temporary_path, target)
        return target
    finally:
        temporary_path.unlink(missing_ok=True)

@mcp.tool(
    description=(
        "path 为 PDF 文件或目录路径；query 默认使用 rg 正则表达式。"
        "fixed_string=true 使用字面匹配，默认 false；"
        "case_sensitive=true 区分大小写，默认 false；"
        "max_results 为最多返回的匹配条数，默认 200，限制在 1 至 2000。"
        "返回的 matches[].path 是原始 PDF 路径，matches[].line 是提取文本中的行号。"
    ),
    structured_output=True,
)
def pdf_search(
    path: str,
    query: str,
    fixed_string: bool = False,
    case_sensitive: bool = False,
    max_results: int = 200,
) -> dict[str, Any]:
    """Search PDF text with rg and return original PDF paths."""
    root = Path(path).expanduser()
    if not query:
        raise ValueError("query is required")
    if not root.exists():
        raise ValueError(f"path does not exist: {root}")
    limit = max(1, min(int(max_results), 2000))
    files = pdf_files(root)
    by_cache: dict[Path, list[Path]] = {}
    errors: list[dict[str, str]] = []
    for pdf in files:
        try:
            text = cached_text(pdf, sha256_file(pdf))
            by_cache.setdefault(text, []).append(pdf)
        except (OSError, RuntimeError) as exc:
            errors.append({"path": str(pdf), "error": str(exc)})
    matches: list[dict[str, Any]] = []
    if by_cache:
        command = ["rg", "--line-number", "--no-heading", "--color", "never"]
        if not case_sensitive:
            command.append("--ignore-case")
        if fixed_string:
            command.append("--fixed-strings")
        command += ["--", query, *map(str, by_cache)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        for line in result.stdout.splitlines():
            cache_name, separator, rest = line.partition(":")
            if not separator:
                continue
            line_number, separator, excerpt = rest.partition(":")
            if not separator:
                continue
            for pdf in by_cache.get(Path(cache_name), []):
                matches.append({"path": str(pdf), "line": int(line_number), "text": excerpt})
                if len(matches) >= limit:
                    break
            if len(matches) >= limit:
                break
    return {"query": query, "matches": matches, "truncated": len(matches) >= limit, "pdf_count": len(files), "cache_count": len(by_cache), "errors": errors}

if __name__ == "__main__":
    mcp.run(transport="stdio")
