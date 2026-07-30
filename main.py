import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from openai import OpenAI
from pydantic import BaseModel
from pypdf import PdfReader


load_dotenv()

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "platform.db"))
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
SESSION_HOURS = 12

app = FastAPI(title="Y's AI Workshop", version="2.0.0")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str


class TextRequest(BaseModel):
    text: str
    provider: str = "deepseek"


class SceneRequest(BaseModel):
    scene: str
    provider: str = "deepseek"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000
    ).hex()


def create_user(
    connection: sqlite3.Connection,
    username: str,
    password: str,
    display_name: str,
    role: str = "user",
) -> None:
    exists = connection.execute(
        "SELECT 1 FROM users WHERE username = ?", (username,)
    ).fetchone()
    if exists:
        return
    salt = secrets.token_hex(16)
    connection.execute(
        """
        INSERT INTO users (username, password_hash, salt, display_name, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (username, hash_password(password, salt), salt, display_name, role, utc_now()),
    )


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                input_preview TEXT NOT NULL DEFAULT '',
                output_preview TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                error TEXT,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_activity_user_created
            ON activity_logs(user_id, created_at DESC);
            """
        )
        initial_admin_username = os.getenv("INITIAL_ADMIN_USERNAME", "").strip().lower()
        initial_admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        if bool(initial_admin_username) != bool(initial_admin_password):
            raise RuntimeError(
                "INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD must be configured together"
            )
        if initial_admin_username and initial_admin_password:
            if not re.fullmatch(r"[a-z0-9_]{3,32}", initial_admin_username):
                raise RuntimeError("INITIAL_ADMIN_USERNAME has an invalid format")
            if not 8 <= len(initial_admin_password) <= 128:
                raise RuntimeError("INITIAL_ADMIN_PASSWORD has an invalid length")
            if not re.search(r"[A-Za-z]", initial_admin_password) or not re.search(
                r"\d", initial_admin_password
            ):
                raise RuntimeError(
                    "INITIAL_ADMIN_PASSWORD must contain letters and numbers"
                )
            create_user(
                connection,
                initial_admin_username,
                initial_admin_password,
                "Administrator",
                "admin",
            )
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (utc_now(),))


def public_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
    }


def require_user(
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    if not x_session_token:
        raise HTTPException(status_code=401, detail="请先登录")
    with get_db() as connection:
        row = connection.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
            """,
            (x_session_token, utc_now()),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return public_user(row)


def require_admin(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user


def record_activity(
    user_id: int,
    feature: str,
    input_preview: str,
    output_preview: str,
    status: str,
    duration_ms: int,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO activity_logs
                (user_id, feature, input_preview, output_preview, status, error,
                 duration_ms, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                feature,
                input_preview[:500],
                output_preview[:500],
                status,
                error[:500] if error else None,
                duration_ms,
                json.dumps(metadata or {}, ensure_ascii=False),
                utc_now(),
            ),
        )


def call_llm(prompt: str, provider: str) -> str:
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="未配置 DEEPSEEK_API_KEY")
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是专业、准确、简洁的中文 AI 助手。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content or ""

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="未配置 ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=1800,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if hasattr(block, "text"))

    raise HTTPException(status_code=400, detail="不支持的模型提供商")


def run_tracked(
    user: dict[str, Any],
    feature: str,
    input_preview: str,
    operation: Callable[[], str],
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    started = time.perf_counter()
    try:
        result = operation()
        record_activity(
            user["id"],
            feature,
            input_preview,
            result,
            "success",
            int((time.perf_counter() - started) * 1000),
            metadata=metadata,
        )
        return {"reply": result, "result": result}
    except HTTPException as exc:
        record_activity(
            user["id"],
            feature,
            input_preview,
            "",
            "error",
            int((time.perf_counter() - started) * 1000),
            error=str(exc.detail),
            metadata=metadata,
        )
        raise
    except Exception as exc:
        message = f"服务调用失败：{exc}"
        record_activity(
            user["id"],
            feature,
            input_preview,
            "",
            "error",
            int((time.perf_counter() - started) * 1000),
            error=message,
            metadata=metadata,
        )
        raise HTTPException(status_code=502, detail=message) from exc


async def read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件不能超过 20MB")
    return content


def decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="CSV 编码无法识别")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (ROOT / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": str(DB_PATH.name)}


@app.post("/auth/login")
def login(data: LoginRequest) -> dict[str, Any]:
    username = data.username.strip().lower()
    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
        ).fetchone()
        if not row or not hmac.compare_digest(
            row["password_hash"], hash_password(data.password, row["salt"])
        ):
            raise HTTPException(status_code=401, detail="账号或密码错误")
        token = secrets.token_urlsafe(32)
        connection.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (
                token,
                row["id"],
                utc_now(),
                (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).isoformat(),
            ),
        )
    return {"token": token, "user": public_user(row)}


@app.post("/auth/register", status_code=201)
def register(data: RegisterRequest) -> dict[str, Any]:
    username = data.username.strip().lower()
    display_name = data.display_name.strip()
    password = data.password

    if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
        raise HTTPException(
            status_code=400,
            detail="账号需为 3-32 位小写字母、数字或下划线",
        )
    if not 1 <= len(display_name) <= 30:
        raise HTTPException(status_code=400, detail="姓名需为 1-30 个字符")
    if not 8 <= len(password) <= 128:
        raise HTTPException(status_code=400, detail="密码需为 8-128 个字符")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="密码必须同时包含字母和数字")

    salt = secrets.token_hex(16)
    now = utc_now()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    ).isoformat()
    try:
        with get_db() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users
                    (username, password_hash, salt, display_name, role, created_at)
                VALUES (?, ?, ?, ?, 'user', ?)
                """,
                (username, hash_password(password, salt), salt, display_name, now),
            )
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            token = secrets.token_urlsafe(32)
            connection.execute(
                """
                INSERT INTO sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, row["id"], now, expires_at),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="该账号已被注册") from exc

    return {"token": token, "user": public_user(row)}


@app.post("/auth/logout")
def logout(
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, bool]:
    if x_session_token:
        with get_db() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (x_session_token,))
    return {"ok": True}


@app.get("/auth/me")
def me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"user": user}


@app.post("/resume")
def resume(data: TextRequest, user: dict[str, Any] = Depends(require_user)) -> dict[str, str]:
    prompt = f"请优化以下简历内容，突出量化成果、专业能力和岗位匹配度，并给出结构清晰的中文版本：\n\n{data.text}"
    return run_tracked(user, "resume", data.text, lambda: call_llm(prompt, data.provider), {"provider": data.provider})


@app.post("/copywrite")
def copywrite(data: SceneRequest, user: dict[str, Any] = Depends(require_user)) -> dict[str, str]:
    prompt = f"请根据以下场景描述生成高质量中文文案，保留事实，提升吸引力，并直接给出成稿：\n\n{data.scene}"
    return run_tracked(user, "copywrite", data.scene, lambda: call_llm(prompt, data.provider), {"provider": data.provider})


@app.post("/translate")
def translate(data: TextRequest, user: dict[str, Any] = Depends(require_user)) -> dict[str, str]:
    prompt = f"请准确翻译以下内容。自动判断源语言：中文翻译为自然英文，其他语言翻译为自然中文。只输出译文：\n\n{data.text}"
    return run_tracked(user, "translate", data.text, lambda: call_llm(prompt, data.provider), {"provider": data.provider})


@app.post("/pdf-summary")
async def pdf_summary(
    file: UploadFile = File(...),
    provider: str = "deepseek",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, str]:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")
    content = await read_upload(file)
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [(page.extract_text() or "") for page in reader.pages[:8]]
        text = "\n".join(pages).strip()[:12000]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PDF 解析失败：{exc}") from exc
    if not text:
        raise HTTPException(status_code=400, detail="PDF 中没有可提取的文字")
    prompt = f"请总结以下 PDF 内容，输出核心结论、关键数据和行动建议，使用清晰的小标题：\n\n{text}"
    return run_tracked(user, "pdf_summary", file.filename or "PDF", lambda: call_llm(prompt, provider), {"provider": provider, "bytes": len(content)})


@app.post("/csv-preview")
async def csv_preview(
    file: UploadFile = File(...),
    provider: str = "deepseek",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, str]:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传 CSV 文件")
    content = await read_upload(file)
    decoded = decode_csv(content)
    rows = list(csv.reader(io.StringIO(decoded)))
    if not rows:
        raise HTTPException(status_code=400, detail="CSV 中没有数据")
    sample = "\n".join(", ".join(cell[:120] for cell in row[:20]) for row in rows[:30])
    prompt = f"请分析以下 CSV 数据样本。说明字段含义、数据规模、质量问题、明显趋势和建议的后续分析：\n\n总行数：{len(rows)}\n样本：\n{sample}"
    return run_tracked(user, "csv_preview", file.filename or "CSV", lambda: call_llm(prompt, provider), {"provider": provider, "rows": len(rows), "bytes": len(content)})


@app.get("/admin/users")
def admin_users(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    del admin
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT u.id, u.username, u.display_name, u.role, u.created_at,
                   COUNT(a.id) AS request_count,
                   SUM(CASE WHEN a.status = 'success' THEN 1 ELSE 0 END) AS success_count,
                   SUM(CASE WHEN a.status = 'error' THEN 1 ELSE 0 END) AS error_count,
                   MAX(a.created_at) AS last_active_at
            FROM users u
            LEFT JOIN activity_logs a ON a.user_id = u.id
            GROUP BY u.id
            ORDER BY request_count DESC, u.id ASC
            """
        ).fetchall()
    users = [dict(row) for row in rows]
    return {
        "users": users,
        "summary": {
            "total_users": len(users),
            "total_requests": sum(row["request_count"] for row in users),
            "total_errors": sum(row["error_count"] or 0 for row in users),
        },
    }


@app.get("/admin/logs")
def admin_logs(
    limit: int = 100,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    del admin
    limit = max(1, min(limit, 500))
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT a.id, u.username, u.display_name, a.feature, a.status,
                   a.duration_ms, a.input_preview, a.error, a.created_at
            FROM activity_logs a
            JOIN users u ON u.id = a.user_id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {"logs": [dict(row) for row in rows]}
