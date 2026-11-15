import logging
import hmac
from io import BytesIO
import os
import time
from typing import Any
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, jsonify, request, send_file
from google import genai
from google.genai import types
from connections import connection_status
from studio import generate_file

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("zalo-gemini-bot")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

ZALO_TOKEN = os.getenv("ZALO_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
STUDIO_API_KEY = os.getenv("STUDIO_API_KEY", "").strip()
ZALO_API_BASE = "https://bot-api.zaloplatforms.com"

_http = requests.Session()
_gemini = (
    genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=15000))
    if GEMINI_API_KEY else None
)
_message_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zalo-reply")


def extract_message(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Extract a text message from flat or result-wrapped Zalo Bot updates."""
    candidates: list[dict[str, Any]] = []
    current: Any = payload

    # Zalo Bot updates may be flat or wrapped as {"ok": true, "result": {...}}.
    for _ in range(3):
        if not isinstance(current, dict):
            break
        candidates.append(current)
        nested = current.get("result") or current.get("update")
        if not isinstance(nested, dict) or nested is current:
            break
        current = nested

    event_name = next(
        (item.get("event_name") for item in candidates
         if isinstance(item.get("event_name"), str)),
        None,
    )

    for container in candidates:
        for item in (container.get("message"), container.get("msg"), container):
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            chat = item.get("chat")
            sender = item.get("from") or item.get("sender")
            recipient = item.get("recipient")
            chat_id = (
                (chat.get("id") if isinstance(chat, dict) else None)
                or item.get("chat_id")
                or (sender.get("id") if isinstance(sender, dict) else None)
                or (recipient.get("id") if isinstance(recipient, dict) else None)
            )
            if isinstance(text, str) and text.strip() and chat_id is not None:
                return str(chat_id), text.strip(), event_name

    return None, None, event_name


class GeminiTemporaryError(RuntimeError):
    """Gemini is temporarily unavailable after retrying."""


def ask_gemini(message: str) -> str:
    if _gemini is None:
        raise RuntimeError("GEMINI_API_KEY chưa được cấu hình.")

    # Retry only transient capacity/rate-limit/server errors. Do not retry
    # authentication, invalid-request, or other permanent client errors.
    retryable_codes = {429, 500, 502, 503, 504}
    for attempt in range(2):
        try:
            response = _gemini.models.generate_content(
                model=GEMINI_MODEL,
                contents=("Trả lời bằng tiếng Việt nếu người dùng dùng tiếng Việt. Trả lời ngắn gọn, trực tiếp.\n\n" + message[:6000]),
                config=types.GenerateContentConfig(max_output_tokens=512),
            )
            answer = (response.text or "").strip()
            return answer or "Mình chưa tạo được câu trả lời. Bạn thử hỏi lại nhé."
        except Exception as exc:
            code = (
                getattr(exc, "code", None)
                or getattr(exc, "status_code", None)
                or getattr(getattr(exc, "response", None), "status_code", None)
            )
            message_upper = str(exc).upper()
            is_transient = (
                code in retryable_codes
                or any(token in message_upper for token in (
                    "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED",
                    "429", "INTERNAL", "502", "504",
                ))
            )
            if not is_transient:
                raise
            if attempt == 1:
                raise GeminiTemporaryError(
                    "Gemini remained unavailable after 2 attempts."
                ) from exc

            delay = 0.5
            logger.warning(
                "Gemini temporary error (attempt %s/2); retrying in %s seconds: %s",
                attempt + 1, delay, type(exc).__name__,
            )
            time.sleep(delay)

    raise GeminiTemporaryError("Gemini retry loop ended unexpectedly.")


def send_zalo_message(chat_id: str, text: str) -> None:
    if not ZALO_TOKEN:
        raise RuntimeError("ZALO_TOKEN chưa được cấu hình.")
    url = f"{ZALO_API_BASE}/bot{ZALO_TOKEN}/sendMessage"
    for start in range(0, len(text), 1900):
        part = text[start:start + 1900]
        response = _http.post(
            url,
            json={"chat_id": chat_id, "text": part},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("ok") is False:
            raise RuntimeError(data.get("description", "Zalo API trả về lỗi."))


@app.get("/api/connections")
def api_connections():
    return jsonify({"providers": connection_status()})


@app.get("/api/plugins")
def api_plugins():
    return jsonify({"plugins": [
        {"id":"file_studio","name":"File Studio","status":"available","formats":["html","txt","md","pdf","docx","pptx","xlsx","zip"]},
        {"id":"codex","name":"CODEX","status":"planned_integration"},
        {"id":"canva","name":"Canva Connect","status":"requires_oauth_setup"},
        {"id":"vscode","name":"VS Code Connector","status":"extension_scaffold"},
        {"id":"image_studio","name":"Image Studio","status":"requires_image_provider"},
        {"id":"web_search","name":"Web Search","status":"requires_search_provider"},
        {"id":"github","name":"GitHub","status":"requires_token"},
        {"id":"render","name":"Render","status":"requires_api_key"}
    ]})


@app.post("/api/files/generate")
def api_generate_file():
    # Keep file-generation endpoints private; configure STUDIO_API_KEY in Render.
    if not STUDIO_API_KEY:
        return jsonify({"error":"File Studio chưa được mở. Hãy cấu hình STUDIO_API_KEY trên Render."}), 503
    supplied = request.headers.get("X-Studio-Key", "")
    if not hmac.compare_digest(supplied, STUDIO_API_KEY):
        return jsonify({"error":"unauthorized"}), 401
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error":"invalid JSON"}), 400
    try:
        filename, data, mime = generate_file(
            str(body.get("format", "")),
            str(body.get("filename", "ducmanh-ai")),
            str(body.get("content", "")),
        )
        logger.info("File generated: %s (%s bytes)", filename, len(data))
        return send_file(BytesIO(data), mimetype=mime, as_attachment=True, download_name=filename)
    except ValueError as exc:
        return jsonify({"error":str(exc)}), 400
    except Exception:
        logger.exception("File generation failed")
        return jsonify({"error":"file_generation_failed"}), 500


@app.get("/")
def index():
    return jsonify({
        "name": "Zalo Gemini Bot",
        "status": "running",
        "health": "/health",
        "webhook": "/webhook",
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "zalo_configured": bool(ZALO_TOKEN),
        "gemini_configured": bool(GEMINI_API_KEY),
        "webhook_registration": WEBHOOK_STATUS,
    })


@app.post("/webhook")
def webhook():
    if WEBHOOK_SECRET:
        supplied = request.headers.get("X-Bot-Api-Secret-Token", "")
        if supplied != WEBHOOK_SECRET:
            logger.warning("Rejected webhook request: secret header mismatch")
            return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        logger.warning("Ignored webhook request: body was not a JSON object")
        return jsonify({"error": "invalid JSON"}), 400

    chat_id, message_text, event_name = extract_message(payload)
    if not chat_id or not message_text:
        logger.info(
            "Webhook event ignored: event_name=%s top_level_keys=%s",
            event_name or "unknown",
            sorted(payload.keys()),
        )
        return jsonify({"status": "ignored"}), 200

    if event_name and event_name not in ("message.text.received", "user_send_text"):
        logger.info("Webhook event ignored: unsupported event_name=%s", event_name)
        return jsonify({"status": "ignored"}), 200

    logger.info("Text message received; queueing background reply; event_name=%s",
                event_name or "unspecified")
    _message_pool.submit(process_message, chat_id, message_text)
    return jsonify({"status": "accepted"}), 200


def process_message(chat_id: str, message_text: str) -> None:
    try:
        answer = ask_gemini(message_text)
        logger.info("Gemini generated a reply")
        send_zalo_message(chat_id, answer)
        logger.info("Reply sent successfully to Zalo")
    except Exception:
        logger.exception("Background message processing failed; chat_id=%s", chat_id)


WEBHOOK_STATUS = "not_checked"


def register_webhook() -> None:
    """Register and verify this Render service as the Zalo webhook."""
    global WEBHOOK_STATUS

    base_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    missing = [
        name for name, value in (
            ("ZALO_TOKEN", ZALO_TOKEN),
            ("WEBHOOK_SECRET", WEBHOOK_SECRET),
            ("RENDER_EXTERNAL_URL", base_url),
        ) if not value
    ]
    if missing:
        WEBHOOK_STATUS = "missing_config"
        logger.warning(
            "Webhook registration skipped; missing environment variables: %s",
            ", ".join(missing),
        )
        return

    if len(WEBHOOK_SECRET) < 8 or len(WEBHOOK_SECRET) > 256:
        WEBHOOK_STATUS = "invalid_secret"
        logger.error("WEBHOOK_SECRET must contain 8 to 256 characters.")
        return

    webhook_url = f"{base_url}/webhook"
    try:
        response = _http.post(
            f"{ZALO_API_BASE}/bot{ZALO_TOKEN}/setWebhook",
            json={"url": webhook_url, "secret_token": WEBHOOK_SECRET},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict) or data.get("ok") is not True:
            WEBHOOK_STATUS = "registration_failed"
            logger.error("Zalo rejected webhook registration (response omitted)")
            return

        info_response = _http.post(
            f"{ZALO_API_BASE}/bot{ZALO_TOKEN}/getWebhookInfo",
            timeout=20,
        )
        info_response.raise_for_status()
        info = info_response.json()
        actual_url = (
            (info.get("result") or {}).get("url")
            if isinstance(info, dict) else None
        )

        if isinstance(info, dict) and info.get("ok") is True and actual_url == webhook_url:
            WEBHOOK_STATUS = "registered"
            logger.info("Zalo webhook registered and verified: %s", webhook_url)
        else:
            WEBHOOK_STATUS = "registered_unverified"
            logger.warning("Zalo webhook registration could not be verified")
    except Exception:
        WEBHOOK_STATUS = "registration_error"
        logger.exception("Could not register or verify Zalo webhook")


register_webhook()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
