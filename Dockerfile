# RAGKit —— HTTP 服务镜像
#
# 重要：镜像**不含语料与索引**。两者都是"可再生产物"，被 .gitignore 排除：
#   - data/raw    由 scripts/fetch_docs.py 从公开仓库拉取（第三方文档，不宜再分发）
#   - data/index  由 ragkit build 生成（依赖语料与 embedding 模型）
#
# 所以运行时必须把 data/ 挂载进去：
#
#   docker build -t ragkit .
#   docker run --rm -p 8000:8000 -v "${PWD}/data:/app/data" ragkit
#
# 前提：宿主机上已经执行过 `ragkit build`（或在容器里先跑一次 build）。
# 没有索引时 serve 会直接报错退出 —— 这是预期行为，不是镜像的问题。
#
# 备注：本文件尚未在真实 Docker 环境验证过（开发机未安装 Docker）。

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 分两步 COPY：先只拷"打包必需"的文件，装完依赖再拷配置，
# 这样改 configs/ 不会击穿依赖层缓存。
# pyproject.toml 里 readme = "README.md"，缺了 README 会让 pip install 失败。
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install .

COPY configs/ ./configs/

# 非 root 运行
RUN useradd --create-home --uid 1000 ragkit \
    && chown -R ragkit:ragkit /app
USER ragkit

EXPOSE 8000

# 必须绑 0.0.0.0：默认的 127.0.0.1 在容器内外部访问不到
ENTRYPOINT ["ragkit", "serve", "--host", "0.0.0.0", "--port", "8000"]
