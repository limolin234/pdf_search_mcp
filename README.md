# pdf_search

基于官方 Python `mcp` SDK (`FastMCP`) 的 stdio MCP server。它递归提取 PDF 文本并使用 `rg` 搜索，文本按 PDF SHA-256 缓存。

## MCP 配置

```toml
[mcp_servers.pdf_search]
command = "/home/limolin/.venvs/default/bin/python"
args = ["/home/limolin/Myapps/pdf_search/server.py"]
```

工具 `pdf_search` 参数为 `path`、`query`，可选 `fixed_string`、`case_sensitive`、`max_results`。依赖系统命令 `pdftotext` 和 `rg`；Python 依赖安装在默认 uv 虚拟环境中：`uv pip install --python /home/limolin/.venvs/default/bin/python mcp`。
