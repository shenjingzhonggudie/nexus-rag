"""HTTP API：把检索+生成暴露成机器可读的 JSON 端点，并提供内置 Web UI。

壳与芯分离（第 17 轮契约）：
- 各 ``_*_payload`` 是纯逻辑芯（search → 组装 dict），不碰 socket，可直调单元测试；
- handler 只做 HTTP 细节（解析 body、翻译状态码、写日志）；
- 领域层（generation）仍返回结构化 Answer，**格式化/翻译零进领域层**
  ——CLI 的 print 与这里的 JSON 共享的是 Answer 契约，不是格式化函数。

端点与错误翻译表（契约）：
- ``GET  /``              内置 UI 页面（静态 HTML）
- ``GET  /healthz``       服务版本与索引块数
- ``GET  /api/knowledge`` 知识库结构：文档列表 + 每篇块数
- ``GET  /api/chunks?doc=`` 某篇文档的全部块（懒加载，供 UI 展开查看）
- ``POST /ask``           问答：检索 + 拒答 + 生成，返回 Answer
- ``POST /api/search``    只检索：返回前 final_k 个块的**原始结果**（scroll 原文与分数）
- 200 = 请求合法且处理完成（**拒答也是 200**，用 refused 字段表达——与 CLI
  拒答=退出码 0 同一个语义：拒答是业务正常结果）；
- 400 = 请求体问题（非 JSON / 缺 query / query 非 str）；404 = 路径不存在；
- 405 = 方法不对；500 = 未知异常（对外只给分类，**不泄堆栈**——读者分层：
  用户要分类与指引，开发者去日志里查，堆栈不进响应体）。
"""

import json
import logging
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ragkit import __version__
from ragkit.config import AppConfig
from ragkit.generation import answer_question
from ragkit.index.assets import BuiltIndex
from ragkit.retrieval.pipeline import search

logger = logging.getLogger("ragkit.api")

# 静态资源目录：与 server.py 同包（editable 安装下直接从源码读）
_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _is_refused(results, match_score: float | None, threshold: float) -> bool:
    """与 ``answer_question`` 同源的拒答判定：空结果，或覆盖率低于阈值。

    ``match_score is None``（稀疏腿关闭 / 无长实词）时不启用阈值判据——
    UI 要如实展示"检索器给了什么"，不能因为算不出覆盖率就谎称拒答。
    """
    if not results:
        return True
    if match_score is None:
        return False
    return match_score < threshold


def _answer_payload(query: str, built: BuiltIndex, cfg: AppConfig) -> dict:
    """纯逻辑芯：一次问答的完整流水线，返回 Answer 的字典形式。

    Args:
        query: 用户问题。
        built: 常驻索引（启动时加载一次，请求间复用）。
        cfg: 应用配置（retrieval 开关与 llm 行为来自它）。

    Returns:
        dict: Answer.to_dict() 的结果，可直接 json 序列化。
    """
    result = search(
        query,
        bm25=built.bm25,
        store=built.store,
        id_to_chunk=built.id_to_chunk,
        dim=built.dim,
        retrieval=cfg.retrieval,
    )
    answer = answer_question(
        query, result, llm=cfg.llm, refuse_threshold=cfg.retrieval.refuse_threshold
    )
    return answer.to_dict()


def _search_payload(query: str, built: BuiltIndex, cfg: AppConfig) -> dict:
    """纯逻辑芯：只做检索，返回前 final_k 个块的原始结果（不走生成）。

    UI 要的是"返回前五的块"——块原文、分数、来源，而不是生成后的答案。
    这与 ``/ask`` 是两种消费方式，所以单列端点。
    """
    result = search(
        query,
        bm25=built.bm25,
        store=built.store,
        id_to_chunk=built.id_to_chunk,
        dim=built.dim,
        retrieval=cfg.retrieval,
    )
    return {
        "query": query,
        "refused": _is_refused(
            result.results, result.match_score, cfg.retrieval.refuse_threshold
        ),
        "match_score": result.match_score,
        "results": [
            {
                "rank": rank,
                "score": round(scored.score, 6),
                "chunk_id": scored.chunk.chunk_id,
                "doc_id": scored.chunk.doc_id,
                "title": scored.chunk.title,
                "text": scored.chunk.text,
                "stage": scored.stage,
                "ordinal": scored.chunk.ordinal,
            }
            for rank, scored in enumerate(result.results, start=1)
        ],
        "latency_ms": round(result.trace.total_latency_ms(), 2),
    }


def _knowledge_payload(built: BuiltIndex) -> dict:
    """纯逻辑芯：知识库结构（每篇文档的块数），供 UI 左栏渲染。"""
    docs: dict[str, dict] = {}
    for chunk in built.id_to_chunk.values():
        entry = docs.setdefault(
            chunk.doc_id,
            {"doc_id": chunk.doc_id, "title": chunk.title, "chunks": 0},
        )
        entry["chunks"] += 1
    ordered = sorted(docs.values(), key=lambda item: item["doc_id"])
    return {
        "total_docs": len(ordered),
        "total_chunks": len(built.id_to_chunk),
        "docs": ordered,
    }


def _chunks_payload(built: BuiltIndex, doc_id: str) -> dict:
    """纯逻辑芯：某篇文档的全部块（按 ordinal 排序），供 UI 展开查看。"""
    rows = sorted(
        (c for c in built.id_to_chunk.values() if c.doc_id == doc_id),
        key=lambda c: c.ordinal,
    )
    return {
        "doc_id": doc_id,
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "ordinal": c.ordinal,
                "title": c.title,
                "text": c.text,
            }
            for c in rows
        ],
    }


def make_handler(built: BuiltIndex, cfg: AppConfig) -> type[BaseHTTPRequestHandler]:
    """闭包工厂：把常驻索引与配置注入 handler 类，handler 只写 HTTP 细节。"""

    class ApiHandler(BaseHTTPRequestHandler):
        """处理健康检查、知识库浏览、检索与问答请求的 HTTP handler。

        闭包捕获 ``built`` 与 ``cfg``，使每个请求复用启动时加载的索引，
        而不是重复读盘或重建索引。
        """

        # 避免每请求向 stderr 打 BaseHTTPRequestHandler 的默认访问行（我们自己记结构化日志）
        def log_message(self, fmt, *args):  # noqa: A003
            """禁用基类的非结构化访问日志，由本 handler 统一记录。"""
            pass

        # ---------- 工具 ----------

        def _send_json(self, status: int, payload: dict) -> None:
            """将 payload 以 UTF-8 JSON 响应体发送，并设置必要的响应头。"""
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, name: str) -> bool:
            """发送 static/ 下的文件；文件不存在或越界时返回 False。"""
            target = (_STATIC_DIR / name).resolve()
            if _STATIC_DIR not in target.parents or not target.is_file():
                return False
            body = target.read_bytes()
            content_type = (
                "text/html; charset=utf-8"
                if target.suffix == ".html"
                else "application/octet-stream"
            )
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # 开发期改完 HTML 刷新即生效：不让浏览器缓存旧页面。
            # 这是内部工具，缓存带来的困惑大于省下的带宽。
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return True

        # ---------- GET ----------

        def do_GET(self):
            """处理 GET：UI 页面、健康检查、知识库结构、文档块列表。"""
            started = time.perf_counter()
            parsed = urlparse(self.path)
            path = parsed.path

            if path in ("/", "/index.html"):
                if not self._send_static("index.html"):
                    self._send_json(404, {"error": "not found"})
                logger.info(
                    "GET %s | 200 | %.1fms", path, (time.perf_counter() - started) * 1000
                )
                return

            if path == "/healthz":
                self._send_json(
                    200,
                    {"version": __version__, "chunks": len(built.store), "status": "ok"},
                )
                logger.info(
                    "GET /healthz | 200 | %.1fms", (time.perf_counter() - started) * 1000
                )
                return

            if path == "/api/knowledge":
                self._send_json(200, _knowledge_payload(built))
                logger.info(
                    "GET /api/knowledge | 200 | %.1fms",
                    (time.perf_counter() - started) * 1000,
                )
                return

            if path == "/api/chunks":
                doc_id = (parse_qs(parsed.query).get("doc") or [""])[0]
                if not doc_id:
                    self._send_json(400, {"error": "缺少查询参数 doc"})
                else:
                    self._send_json(200, _chunks_payload(built, doc_id))
                logger.info(
                    "GET /api/chunks | 200 | %.1fms",
                    (time.perf_counter() - started) * 1000,
                )
                return

            self._send_json(404, {"error": "not found"})
            logger.info(
                "GET %s | 404 | %.1fms", path, (time.perf_counter() - started) * 1000
            )

        # ---------- POST ----------

        def do_POST(self):
            """处理 POST：``/ask`` 问答、``/api/search`` 纯检索。

            请求体必须是含非空字符串 ``query`` 的 JSON 对象。请求格式错误
            返回 400，未知的处理异常记录堆栈后返回不含内部细节的 500。
            """
            started = time.perf_counter()
            status = 500
            raw = b""
            path = urlparse(self.path).path

            if path not in ("/ask", "/api/search"):
                status = 404
                self._send_json(status, {"error": "not found"})
            else:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length) if length else b""
                    data = json.loads(raw) if raw else {}
                except (ValueError, UnicodeDecodeError):
                    status = 400
                    self._send_json(status, {"error": "请求体必须是合法 JSON"})
                else:
                    query = data.get("query") if isinstance(data, dict) else None
                    if not isinstance(query, str) or not query:
                        status = 400
                        self._send_json(
                            status, {"error": "缺少字符串字段 query（非空）"}
                        )
                    else:
                        try:
                            if path == "/ask":
                                payload = _answer_payload(query, built, cfg)
                            else:
                                payload = _search_payload(query, built, cfg)
                        except Exception:  # noqa: BLE001
                            # 对外只给分类，不泄堆栈（读者分层：开发者查日志）
                            logger.exception("POST %s 处理失败", path)
                            status = 500
                            self._send_json(status, {"error": "internal"})
                        else:
                            status = 200  # 拒答也是 200，refused 字段表达
                            self._send_json(status, payload)

            logger.info(
                "POST %s | %d | %.1fms | body_len=%d",
                path,
                status,
                (time.perf_counter() - started) * 1000,
                len(raw),
            )

        def do_PUT(self):
            """拒绝不支持的 PUT 请求；DELETE 和 PATCH 复用此实现。"""
            self._send_json(405, {"error": "method not allowed"})

        do_DELETE = do_PUT
        do_PATCH = do_PUT

    return ApiHandler


def _warm_up_embedding(built: BuiltIndex) -> None:
    """启动时预热 embedding 通道，避免首次查询等几十秒。

    直接跑一次 ``dense_search``：hashing 瞬间完成（无模型可加载），
    bge 会在这里把模型加载完（``load_index`` 只读向量、不加载模型）。

    **不按 ``cfg.embedding.provider`` 判断**：索引自描述的 provider 优先
    （manifest 里写 bge，而配置默认 hashing，两者可能不一致）——按配置
    判断会漏掉真正需要预热的场景。
    """
    from ragkit.retrieval.dense import dense_search

    started = time.perf_counter()
    try:
        dense_search(
            "预热",
            store=built.store,
            id_to_chunk=built.id_to_chunk,
            dim=built.dim,
            top_k=1,
        )
    except Exception:  # noqa: BLE001
        # 预热失败不该阻止服务启动：首次查询会重新尝试，只是慢
        logger.warning("embedding 预热失败，首次查询会较慢", exc_info=True)
    else:
        logger.info("embedding 预热完成 | %.1fs", time.perf_counter() - started)


def create_server(
    host: str, port: int, built: BuiltIndex, cfg: AppConfig
) -> ThreadingHTTPServer:
    """构造就绪但未启动的 HTTP 服务器，serve_forever 由调用方控制。

    Args:
        host: 监听地址；本地使用建议 127.0.0.1。
        port: 监听端口；测试传 0 由系统随机分配。
        built: 常驻索引（启动时加载一次）。
        cfg: 应用配置。

    Returns:
        ThreadingHTTPServer: 已绑定端口的线程安全服务器；调 serve_forever() 开始服务。
    """
    _warm_up_embedding(built)
    server = ThreadingHTTPServer((host, port), make_handler(built, cfg))
    logger.info(
        "ragkit %s | 监听 %s:%d | 索引 %d 块 | UI / | POST /ask | POST /api/search",
        __version__,
        host,
        server.server_address[1],
        len(built.store),
    )
    return server
