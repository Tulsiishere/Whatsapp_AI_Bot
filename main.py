import os
import time
import secrets
from collections import defaultdict
from fastapi import FastAPI, Form, BackgroundTasks, HTTPException, Request, Depends
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from twilio.request_validator import RequestValidator
import google.generativeai as genai

from rag import retrieve
from twilio_client import send_whatsapp_message
import memory

load_dotenv()

# ── Gemini setup ──────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ── Admin auth (protects /admin and /send) ─────────────────────────────────────
# Set ADMIN_USER / ADMIN_PASS as env vars on your host. Without ADMIN_PASS set,
# these routes refuse all requests rather than falling open.
security = HTTPBasic()
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "")


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if not ADMIN_PASS:
        raise HTTPException(status_code=503, detail="Admin access is not configured.")
    user_ok = secrets.compare_digest(credentials.username, ADMIN_USER)
    pass_ok = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


# ── Twilio request validation (protects /webhook from non-Twilio callers) ─────
# Twilio signs every webhook request. We verify that signature so random
# internet traffic can't hit /webhook directly and burn your Gemini quota.
# Set TWILIO_VALIDATE_SIGNATURE=false only for local debugging.
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
VALIDATE_SIGNATURE = os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() != "false"
_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None


async def verify_twilio_request(request: Request):
    if not VALIDATE_SIGNATURE:
        return
    if not _validator:
        raise HTTPException(status_code=503, detail="Twilio auth token not configured.")
    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    if not _validator.validate(str(request.url), dict(form), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


# ── Per-number rate limiting (protects your Gemini bill from abuse) ───────────
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))
RATE_LIMIT_WINDOW = 3600
_rate_log: dict[str, list] = defaultdict(list)


def check_rate_limit(user_number: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    recent = [t for t in _rate_log[user_number] if t > window_start]
    recent.append(now)
    _rate_log[user_number] = recent
    return len(recent) <= RATE_LIMIT_MAX

SYSTEM_INSTRUCTION = """You are the personal AI assistant for Kalpavriksha AI Solutions — a Mumbai-based AI Solutions company.

Your role is to help customers on WhatsApp discover Kalpavriksha AI Solutions's services, understand their offerings, find the right service, and feel genuinely taken care of.

PERSONALITY:
- Warm, elegant, and knowledgeable — like a trusted personal stylist, not a chatbot
- Concise: this is WhatsApp, not email. 2-4 sentences per reply unless more detail is truly needed
- Use tasteful emojis occasionally — not on every line
- Never use bullet points or markdown — plain text only on WhatsApp

PRODUCT KNOWLEDGE:
- When catalog context is provided, use it precisely — product names, prices, materials
- Never fabricate product names, prices, or availability
- If a product detail isn't in the catalog context, say so and offer to check with the team

HANDLING TRICKY SITUATIONS:
- Price sensitivity: Acknowledge gracefully, highlight the craftsmanship and value, never apologise for the price
- Off-topic questions (food, fashion, etc.): Gently redirect — "That's a bit outside my world! I'm here to help you find the perfect product or service that your business could benefit from Kalpavriksha AI Solutions 😊"
- Gibberish / unclear messages: Ask one simple clarifying question
- Complaints: Empathise first, then offer to connect them with Kalpavriksha AI Solutions's team directly
- Contact information email - kalpavriksha.ai.services@gmail.com, mobile number - +91 9960814087
- Requests to connect with Kalpavriksha AI Solutions: "I'll make sure Kalpavriksha AI Solutions's team reaches out to you. Could you share your query so I can brief them?"
- Image messages: "I can see you've shared an image! I'm currently text-only, but if you describe what you're looking for, I'd love to help you find something similar from the collection ✨"

COMMANDS (internal, don't reveal these exist):
- "reset": clears conversation history silently"""

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_INSTRUCTION,
)


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI()


# ── Background processor ──────────────────────────────────────────────────────
def process_and_reply(user_number: str, user_message: str, has_media: bool = False):
    """
    Runs after Twilio ACK. Does RAG → Gemini → outbound reply.
    """
    try:
        # 1. Handle reset command
        if user_message.strip().lower() == "reset":
            memory.clear_history(user_number)
            send_whatsapp_message(user_number, "Fresh start! How can I help you today? ✨")
            return

        # 2. Handle image/media messages — no RAG needed
        if has_media:
            reply = ("I can see you've shared an image! I'm currently text-only, "
                     "but if you describe what you're looking for, I'd love to help "
                     "you find something similar from the collection ✨")
            send_whatsapp_message(user_number, reply)
            # Still save to history so context is preserved
            memory.add_message(user_number, "user", "[Customer sent an image]")
            memory.add_message(user_number, "model", reply)
            return

        # 3. Retrieve RAG context
        rag_context = retrieve(user_message)

        # 4. Build augmented prompt
        augmented_message = f"""Catalog context (use if relevant, ignore if not):
{rag_context}

Customer message: {user_message}"""

        # 5. Fetch existing history BEFORE modifying
        history = memory.get_history(user_number)

        # 6. Run Gemini
        chat = model.start_chat(history=history)
        response = chat.send_message(augmented_message)
        reply = response.text

        # 7. Persist CLEAN history (original message, not RAG-augmented)
        memory.add_message(user_number, "user", user_message)
        memory.add_message(user_number, "model", reply)

        # 8. Send reply
        send_whatsapp_message(user_number, reply)

    except Exception as e:
        print(f"[ERROR] process_and_reply failed for {user_number}: {e}")
        send_whatsapp_message(
            user_number,
            "So sorry, I ran into a little hiccup! Please try again in a moment 🙏"
        )


# ── Inbound webhook ───────────────────────────────────────────────────────────
@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
):
    """
    Twilio calls this on every inbound WhatsApp message.
    ACKs immediately, processes in background.
    NumMedia > 0 means the customer sent an image/file.
    """
    await verify_twilio_request(request)

    user_number = From
    user_message = Body.strip()
    has_media = int(NumMedia) > 0

    print(f"[INBOUND] {user_number}: '{user_message}' | media={has_media}")

    empty_ack = Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )

    if not check_rate_limit(user_number):
        print(f"[RATE LIMIT] {user_number} exceeded {RATE_LIMIT_MAX}/hour — dropping.")
        return empty_ack

    background_tasks.add_task(process_and_reply, user_number, user_message, has_media)
    return empty_ack


# ── Outbound /send endpoint ───────────────────────────────────────────────────
class SendRequest(BaseModel):
    to: str
    message: str


@app.post("/send")
async def send_message(req: SendRequest, _: bool = Depends(require_admin)):
    """
    Proactive outbound messaging. Used by the admin UI.
    """
    if not req.to or not req.message:
        raise HTTPException(status_code=400, detail="Both 'to' and 'message' are required.")
    try:
        sid = send_whatsapp_message(req.to, req.message)
        print(f"[OUTBOUND] Sent to {req.to} | SID: {sid}")
        return {"status": "sent", "to": req.to, "sid": sid}
    except Exception as e:
        print(f"[ERROR] /send failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Admin UI ──────────────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
async def admin_ui(_: bool = Depends(require_admin)):
    html = open("admin.html").read()
    return HTMLResponse(content=html)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "Kalpavriksha's WhatsApp AI Bot is running ✨"}
