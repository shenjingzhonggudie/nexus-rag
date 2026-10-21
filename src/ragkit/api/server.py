"""HTTP API：把检索+生成暴露成机器可读的 JSON 端点。

壳与芯分离（第 17 轮契约）：
- `_answer_payload` 是纯逻辑芯（search → answer_question → Answer.to_dict()），
  不碰 socket，可直调单元测试；
- handler 只做 HTTP 细节（解析 body、翻译状态码、写日志）；
- 领域层（generation）仍返回结构化 Answer，**格式化/翻译零进领域层**
  ——CLI 的 print 与这里的 JSON 共享的是 Answer 契约，不是格式化函数。

错误翻译表（契约）：
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

from ragkit import __version__
from ragkit.config import AppConfig
from ragkit.generation import answer_question
from ragkit.index.assets import BuiltIndex
from ragkit.retrieval.pipeline import search

logger = logging.getLogger("ragkit.api")


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


def make_handler(built: BuiltIndex, cfg: AppConfig) -> type[BaseHTTPRequestHandler]:
    """闭包工厂：把常驻索引与配置注入 handler 类，handler 只写 HTTP 细节。"""

    class ApiHandler(BaseHTTPRequestHandler):
        """处理健康检查和问答请求的 HTTP handler。

        闭包捕获 ``built`` 与 ``cfg``，使每个请求复用启动时加载的索引，
        而不是重复读盘或重建索引。
        """

        # 避免每请求向 stderr 打 BaseHTTPRequestHandler 的默认访问行（我们自己记结构化日志）
        def log_message(self, fmt, *args):  # noqa: A003
            """禁用基类的非结构化访问日志，由本 handler 统一记录。"""
            pass

        # ---------- 工具 ----------

        def _send_json(self, status: int, payload: dict) -> None:
            """将 payload 以 UTF-8 JSON 响应体发送，并设置必要的响应头。

            Args:
                status: HTTP 响应状态码。
                payload: 可 JSON 序列化的响应内容。
            """
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # ---------- GET：/healthz ----------

        def do_GET(self):
            """处理 GET 请求；仅 ``/healthz`` 返回服务版本和索引状态。"""
            started = time.perf_counter()
            if self.path == "/healthz":
                self._send_json(
                    200,
                    {"version": __version__, "chunks": len(built.store), "status": "ok"},
                )
                logger.info(
                    "GET /healthz | 200 | %.1fms", (time.perf_counter() - started) * 1000
                )
                return
            self._send_json(404, {"error": "not found"})
            logger.info("GET %s | 404 | %.1fms", self.path, (time.perf_counter() - started) * 1000)

        # ---------- POST：/ask ----------

        def do_POST(self):
            """处理 ``POST /ask``：校验 JSON 查询、执行问答，并返回结构化结果。

            请求体必须是含非空字符串 ``query`` 的 JSON 对象。请求格式错误
            返回 400，未知的处理异常记录堆栈后返回不含内部细节的 500。
            """
            started = time.perf_counter()
            status = 500
            raw = b""

            if self.path != "/ask":
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
                            payload = _answer_payload(query, built, cfg)
                        except Exception:  # noqa: BLE001
                            # 对外只给分类，不泄堆栈（读者分层：开发者查日志）
                            logger.exception("POST /ask 处理失败")
                            status = 500
                            self._send_json(status, {"error": "internal"})
                        else:
                            status = 200  # 拒答也是 200，refused 字段表达
                            self._send_json(status, payload)

            logger.info(
                "POST %s | %d | %.1fms | body_len=%d",
                self.path,
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
    server = ThreadingHTTPServer((host, port), make_handler(built, cfg))
    logger.info(
        "ragkit %s | 监听 %s:%d | 索引 %d 块 | POST /ask | GET /healthz",
        __version__,
        host,
        server.server_address[1],
        len(built.store),
    )
    return server
