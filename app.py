import logging
import os
from typing import Any

import requests
from flask import Flask, jsonify, request
from google import genai

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("zalo-gemini-bot")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

ZALO_TOKEN = os.getenv("ZALO_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
ZALO_API_BASE = "https://bot-api.zaloplatforms.com"

_http = requests.Session()
_gemini = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def extract_message(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Read common Zalo Bot update shapes without assuming every event is a message."""
    candidates = [
        payload.get("message"),
        payload.get("msg"),
        (payload.get("update") or {}).get("message")
        if isinstance(payload.get("update"), dict) else None,
        payload,
    ]

    for item in candidates:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        chat = item.get("chat")
        sender = item.get("from") or item.get("sender")
        chat_id = (
            (chat.get("id") if isinstance(chat, dict) else None)
            or item.get("chat_id")
            or (sender.get("id") if isinstance(sender, dict) else None)
        )
        if isinstance(text, str) and text.strip() and chat_id is not None:
            return str(chat_id), text.strip()
    return None, None


def ask_gemini(message: str) -> str:
    if _gemini is None:
        raise RuntimeError("GEMINI_API_KEY chưa được cấu hình.")
    response = _gemini.models.generate_content(
        model=GEMINI_MODEL,
        contents=message[:12000],
    )
    answer = (response.text or "").strip()
    return answer or "Mình chưa tạo được câu trả lời. Bạn thử hỏi lại nhé."


def send_zalo_message(chat_id: str, text: str) -> None:
    if not ZALO_TOKEN:
        raise RuntimeError("ZALO_TOKEN chưa được cấu hình.")
    url = f"{ZALO_API_BASE}/bot{ZALO_TOKEN}/sendMessage"
    # Zalo Bot API giới hạn nội dung tin nhắn văn bản tối đa 2.000 ký tự.
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
    })


@app.post("/webhook")
def webhook():
    if WEBHOOK_SECRET:
        supplied = request.headers.get("X-Webhook-Secret", "")
        if supplied != WEBHOOK_SECRET:
            return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid JSON"}), 400

    chat_id, message_text = extract_message(payload)
    if not chat_id or not message_text:
        # Acknowledge non-message events so the provider does not retry them.
        return jsonify({"status": "ignored"}), 200

    try:
        answer = ask_gemini(message_text)
        send_zalo_message(chat_id, answer)
        return jsonify({"status": "ok"}), 200
    except requests.RequestException:
        logger.exception("Zalo API request failed")
        return jsonify({"status": "error", "message": "Zalo API request failed"}), 502
    except Exception:
        logger.exception("Webhook processing failed")
        return jsonify({"status": "error", "message": "Bot processing failed"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
