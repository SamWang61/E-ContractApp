"""Render（或任何 Docker 主機）用的網頁伺服器。

一個容器同時提供：
  - 前端網頁：firebase/public（含 /sign/*、/contracts/* 等前端路由，一律回 index.html）
  - 後端 API：/api/*，直接呼叫 functions/main.py 的 api()，與 Firebase Functions 版本完全相同

資料仍然存放在 Firebase（Firestore、Storage、Authentication），
所以 Render 版和 https://mycontractapp-911.web.app 看到的是同一批合約。

需要的環境變數見 docs/RENDER_DEPLOY.md。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("render-server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

APP_DIR = Path(__file__).resolve().parent.parent          # .../firebase
PUBLIC_DIR = Path(os.getenv("PUBLIC_DIR", APP_DIR / "public")).resolve()
FUNCTIONS_DIR = Path(os.getenv("FUNCTIONS_DIR", APP_DIR / "functions")).resolve()
SECRET_FILE = Path("/etc/secrets/firebase-service-account.json")  # Render Secret File 的預設位置


def _prepare_environment() -> dict:
    """在匯入後端之前，備妥 Firebase 憑證與專案設定。"""
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT") or "mycontractapp-911"
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project)
    os.environ.setdefault("GCLOUD_PROJECT", project)
    bucket = os.getenv("STORAGE_BUCKET") or f"{project}.firebasestorage.app"
    os.environ.setdefault("STORAGE_BUCKET", bucket)
    # firebase_admin.initialize_app() 會讀這個變數取得 projectId / storageBucket
    os.environ.setdefault("FIREBASE_CONFIG", json.dumps({"projectId": project, "storageBucket": bucket}))

    # 簽署連結與 Email 內的網址：未指定時使用 Render 自動提供的網址
    if not os.getenv("APP_BASE_URL") and os.getenv("RENDER_EXTERNAL_URL"):
        os.environ["APP_BASE_URL"] = os.environ["RENDER_EXTERNAL_URL"]

    # 服務帳戶金鑰：三種提供方式擇一
    source = "none"
    raw = (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
    if raw:
        if not raw.startswith("{"):          # 也接受 base64 編碼後的 JSON
            raw = base64.b64decode(raw).decode("utf-8")
        info = json.loads(raw)
        path = Path("/tmp/firebase-service-account.json")
        path.write_text(json.dumps(info), encoding="utf-8")
        path.chmod(0o600)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
        source = "env:FIREBASE_SERVICE_ACCOUNT_JSON"
    elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        source = "env:GOOGLE_APPLICATION_CREDENTIALS"
    elif SECRET_FILE.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(SECRET_FILE)
        source = "secret-file"
    elif os.getenv("FUNCTIONS_EMULATOR") == "true":
        source = "emulator"
    else:
        log.error("找不到 Firebase 服務帳戶金鑰：請設定 FIREBASE_SERVICE_ACCOUNT_JSON，"
                  "或在 Render 加上 Secret File『firebase-service-account.json』。")

    return {
        "project": project,
        "storageBucket": bucket,
        "credentials": source,
        "appBaseUrl": os.getenv("APP_BASE_URL", ""),
        "smtp": bool(os.getenv("SMTP_HOST")),
        "signingKey": bool(os.getenv("SIGNING_TOKEN_ENCRYPTION_KEY")),
    }


STATUS = _prepare_environment()
if not STATUS["signingKey"]:
    log.warning("尚未設定 SIGNING_TOKEN_ENCRYPTION_KEY：請填入與 Firebase 版相同的金鑰，否則舊連結無法提醒／下載。")

sys.path.insert(0, str(FUNCTIONS_DIR))
os.chdir(FUNCTIONS_DIR)  # pdf_export 等模組以相對位置讀取字型
import main as backend  # noqa: E402  （必須在備妥環境變數後才匯入）

from flask import Flask, abort, request, send_from_directory  # noqa: E402

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 10 MB 檔案經 base64 後約 14 MB


@app.route("/healthz")
def healthz():
    """Render 健康檢查：不連資料庫，只回報設定是否齊全（不含任何密碼）。"""
    ok = STATUS["credentials"] != "none" and STATUS["signingKey"]
    return {"ok": ok, "service": "mycontractapp-render", **STATUS}, (200 if ok else 503)


@app.route("/api", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/<path:_sub>", methods=["GET", "POST", "OPTIONS"])
def api(_sub: str = ""):
    return backend.api(request._get_current_object())


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def frontend(path: str):
    if path.startswith("api/"):
        abort(404)
    target = (PUBLIC_DIR / path).resolve()
    if path and target.is_file() and PUBLIC_DIR in target.parents:
        resp = send_from_directory(PUBLIC_DIR, path)
    elif Path(path).suffix and not path.startswith(("sign/", "contracts/")):
        abort(404)  # 找不到的檔案（.js/.css/圖片）回 404，不要回首頁
    else:
        resp = send_from_directory(PUBLIC_DIR, "index.html")  # 前端路由（/sign/*、/contracts/*）
    return resp


@app.after_request
def headers(resp):
    p = request.path
    if p.endswith((".js", ".css", ".html")) or not Path(p).suffix:
        resp.headers["Cache-Control"] = "no-cache"
    if p.startswith("/sign/"):
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp


if __name__ == "__main__":  # 本機測試：python firebase/render/server.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
