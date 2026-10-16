# 全球化合約管理系統：Render（或任何 Docker 主機）部署用
# 一個容器同時提供前端網頁與 /api 後端；資料仍存放在 Firebase（Firestore／Storage／Auth）。
# 環境變數設定見 firebase/docs/RENDER_DEPLOY.md
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000

WORKDIR /app

# 先裝依賴（利用 Docker 快取，程式改動時不必重裝）
COPY firebase/functions/requirements.txt functions/requirements.txt
COPY firebase/render/requirements.txt render/requirements.txt
RUN pip install -r functions/requirements.txt -r render/requirements.txt

# 程式、字型與前端網頁
COPY firebase/functions/ functions/
COPY firebase/render/ render/
COPY firebase/public/ public/

# 以非 root 使用者執行
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','10000'), timeout=4)" || exit 1

# Render 會提供 PORT；簽署與 PDF 產生最長約 2 分鐘
CMD ["sh", "-c", "exec gunicorn --chdir /app/render server:app --bind 0.0.0.0:${PORT:-10000} --workers ${WEB_CONCURRENCY:-2} --threads 4 --timeout 120 --access-logfile -"]
