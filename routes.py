import datetime

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from twilio.twiml.voice_response import Connect, VoiceResponse

from app_instance import app
from db_utils import get_call_records, get_db_connection, insert_call_record


# =======================
# HTTP routes
# =======================
@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Princeton Insurance Twilio Media Stream Server is running!"}


@app.get("/health", response_class=JSONResponse)
async def health():
    return {"ok": True}


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Return TwiML to connect the call to our /media-stream WebSocket."""
    response = VoiceResponse()
    response.pause(length=1)
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")


# =======================
# Debug endpoints
# =======================
@app.get("/debug/db", response_class=JSONResponse)
async def debug_db_connection():
    """Debug endpoint to test database connection."""
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "Failed to connect to database"}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            return {"ok": True, "database_version": version}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


@app.get("/debug/insert", response_class=JSONResponse)
async def debug_insert():
    """Debug endpoint to test inserting a call record."""
    print("[DEBUG] Testing database insert...", flush=True)

    result = insert_call_record(
        caller_phone="14155551234",
        task_type="Debug Test",
        call_summary="Test call from /debug/insert endpoint",
        detail_info="This is a test record created for debugging purposes",
    )

    print(f"[DEBUG] Insert result: {result}", flush=True)
    return result


@app.get("/debug/records", response_class=JSONResponse)
async def debug_records(limit: int = 10):
    """Debug endpoint to retrieve recent call records."""
    print(f"[DEBUG] Fetching {limit} recent records...", flush=True)

    result = get_call_records(limit=limit)

    print(f"[DEBUG] Retrieved {result.get('count', 0)} records", flush=True)
    return result


@app.get("/debug/simulate-function-call", response_class=JSONResponse)
async def debug_simulate_function_call():
    """Debug endpoint to simulate the exact function call process."""
    print("[DEBUG] Simulating function call...", flush=True)

    result = insert_call_record(
        caller_phone="14155559999",
        task_type="Question",
        call_summary="Test call from debug endpoint - simulating real function call",
        detail_info=f"Simulated call at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )

    print(f"[DEBUG] Function call simulation result: {result}", flush=True)
    return result
