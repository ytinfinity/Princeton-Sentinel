# app_instance.py
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from prompt import System_message
from telephony_transfer import router as transfer_router

load_dotenv(override=True)


# === Environment & Configuration ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 5050))
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.8))
VOICE = os.getenv("VOICE", "marin")

SYSTEM_MESSAGE = System_message
SHOW_TIMING_MATH = True
LOG_EVENT_TYPES = {
    "error",
    "response.content.done",
    "rate_limits.updated",
    "response.done",
    "input_audio_buffer.committed",
    "input_audio_buffer.speech_stopped",
    "input_audio_buffer.speech_started",
    "session.created",
    "session.updated",
    "conversation.item.truncate",
    "response.output_audio.delta",
}

# Validate required environment variables
if not OPENAI_API_KEY:
    raise ValueError("Missing the OpenAI API key. Set it in .env or environment.")

if not DATABASE_URL:
    print("[WARN] DATABASE_URL is not set. Database writes will fail.", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events."""
    # --- Startup ---
    print("[STARTUP] Initializing Princeton Insurance application...", flush=True)
    print(f"[STARTUP] Port: {PORT}", flush=True)
    print(f"[STARTUP] Voice: {VOICE}", flush=True)
    print(f"[STARTUP] Temperature: {TEMPERATURE}", flush=True)

    # Test database connection
    if DATABASE_URL:
        try:
            import psycopg2

            conn = psycopg2.connect(DATABASE_URL)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            print("[STARTUP] Database connection successful", flush=True)
        except Exception as e:
            print(f"[STARTUP] Database connection failed: {e}", flush=True)

    print("[STARTUP] Application initialized successfully", flush=True)

    # Yield to run the app
    yield

    # --- Shutdown ---
    print("[SHUTDOWN] Shutting down Princeton Insurance application...", flush=True)
    print("[SHUTDOWN] Done", flush=True)


# Create the FastAPI app
app = FastAPI(lifespan=lifespan)

# Mount transfer router
app.include_router(transfer_router)
