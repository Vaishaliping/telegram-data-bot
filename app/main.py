"""
Main FastAPI + Telegram bot app — WEBHOOK mode for Koyeb free hosting.

Architecture:
  - Telegram sends POST /webhook/{BOT_TOKEN} for each message
  - Bot processes message, calls LLM, uploads JSONL log to GitHub Gist
  - Replies with exactly: {"answer": <json_obj>, "log_url": "<gist_raw_url>"}
  - GET /health is pinged by UptimeRobot to keep Koyeb instance awake
"""

import json
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.config import BOT_TOKEN, WEBHOOK_URL
from app.llm import ask_llm, extract_json
from app.logger import RunLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Per-chat conversation history (in-memory, cleared on restart) ──────────
chat_history: dict[int, list[dict]] = {}

# ── Build the telegram Application (no updater — webhook mode) ─────────────
telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()


# ── Handlers ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_history[chat_id] = []          # reset history
    await update.message.reply_text(
        "👋 Hello! I'm your TDS Data Analyst Bot.\n"
        "Send me a data-analysis question and I'll reply with a JSON answer."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me any data question — I'll answer with a JSON object.\n"
        "Example: Which state has the highest maternal mortality rate based on MOSPI data?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()

    run_log = RunLogger(chat_id)
    run_log.log("user", user_text)

    # Maintain conversation history for multi-turn support
    if chat_id not in chat_history:
        chat_history[chat_id] = []

    chat_history[chat_id].append({"role": "user", "content": user_text})

    try:
        # Call LLM with full conversation history
        llm_reply = ask_llm(chat_history[chat_id])
        run_log.log("assistant", llm_reply)

        chat_history[chat_id].append({"role": "assistant", "content": llm_reply})

        # Extract the inner JSON answer object
        answer_obj = extract_json(llm_reply)

        # Upload log → get public URL
        log_url = run_log.upload_gist()

        if answer_obj is not None:
            # Perfect — wrap in the required format
            final_reply = json.dumps(
                {"answer": answer_obj, "log_url": log_url},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            # LLM didn't return clean JSON — wrap raw text as string answer
            run_log.log("system", "Could not extract JSON from LLM reply; using raw text")
            final_reply = json.dumps(
                {"answer": llm_reply, "log_url": log_url},
                ensure_ascii=False,
                separators=(",", ":"),
            )

        await update.message.reply_text(final_reply)

    except Exception as e:
        logger.exception("Error handling message")
        run_log.log("error", str(e))
        try:
            log_url = run_log.upload_gist()
        except Exception:
            log_url = "upload-failed"
        await update.message.reply_text(
            json.dumps({"error": str(e), "log_url": log_url}, separators=(",", ":"))
        )


# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)


# ── FastAPI lifespan (startup / shutdown) ──────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await telegram_app.initialize()
    await telegram_app.start()

    if WEBHOOK_URL:
        webhook_endpoint = f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
        await telegram_app.bot.set_webhook(
            url=webhook_endpoint,
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set to: {webhook_endpoint}")
    else:
        logger.warning("WEBHOOK_URL not set — webhook not registered with Telegram")

    yield

    # Shutdown
    await telegram_app.stop()
    await telegram_app.shutdown()


app = FastAPI(lifespan=lifespan)


# ── Routes ─────────────────────────────────────────────────────────────────

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    """Receive updates pushed by Telegram."""
    if token != BOT_TOKEN:
        return Response(content="Unauthorized", status_code=403)

    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return Response(content="ok")


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    """Keep-alive endpoint — pin this URL in UptimeRobot every 5 minutes."""
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"status": "TDS Data Analyst Bot is running", "mode": "webhook"}

@app.get("/debug")
async def debug():
    return {
        "token_prefix": BOT_TOKEN[:10],
        "webhook": WEBHOOK_URL
    }