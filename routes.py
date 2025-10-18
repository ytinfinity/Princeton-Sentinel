import datetime

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from app_instance import app
from db_utils import get_call_records, get_db_connection, insert_call_record


# =======================
# HTTP routes
# =======================
@app.api_route("/", methods=["GET", "HEAD"], response_class=JSONResponse)
async def index_page():
    return {"message": "Princeton Insurance Twilio Media Stream Server is running!"}


@app.api_route("/health", methods=["GET", "HEAD"], response_class=JSONResponse)
async def health():
    return {"ok": True}


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Return TwiML to connect the call to our /media-stream WebSocket."""
    response = VoiceResponse()
    response.pause(length=1)
    host = request.url.hostname

    # Get caller's phone number from Twilio
    form_data = await request.form()
    caller_phone = form_data.get("From", "") or ""
    call_sid = form_data.get("CallSid", "") or ""

    print(f"[INCOMING CALL] From: {caller_phone}, CallSid: {call_sid}", flush=True)

    # Build <Connect><Stream> and pass data with <Parameter>
    connect = Connect()
    stream = Stream(url=f"wss://{host}/media-stream")

    # Reliable path for metadata into the media WebSocket
    stream.parameter(name="caller_phone", value=caller_phone)
    if call_sid:
        stream.parameter(name="call_sid", value=call_sid)

    connect.append(stream)
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


@app.get("/admin/calls", response_class=JSONResponse)
async def admin_get_calls(
    limit: int = 50, phone: str = None, task_type: str = None, date: str = None
):
    """
    Admin endpoint to retrieve and filter call records.

    Query parameters:
    - limit: Number of records to return (default: 50)
    - phone: Filter by caller phone number
    - task_type: Filter by task type
    - date: Filter by call date (YYYY-MM-DD)
    """
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "Database connection failed"}

    try:
        # Build dynamic query based on filters
        query = """
            SELECT id, caller_phone, call_date, call_time, task_type, 
                   call_summary, detail_info, created_at
            FROM post_call_analysis
            WHERE 1=1
        """
        params = []

        if phone:
            query += " AND caller_phone = %s"
            params.append(phone)

        if task_type:
            query += " AND task_type = %s"
            params.append(task_type)

        if date:
            query += " AND call_date = %s"
            params.append(date)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

            records = []
            for row in rows:
                records.append(
                    {
                        "id": row[0],
                        "caller_phone": row[1],
                        "call_date": str(row[2]) if row[2] else None,
                        "call_time": str(row[3]) if row[3] else None,
                        "task_type": row[4],
                        "call_summary": row[5],
                        "detail_info": row[6],
                        "created_at": str(row[7]) if row[7] else None,
                    }
                )

            return {"ok": True, "records": records, "count": len(records)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


@app.get("/admin/stats", response_class=JSONResponse)
async def admin_get_stats():
    """Get call statistics."""
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "Database connection failed"}

    try:
        stats = {}

        with conn.cursor() as cur:
            # Total calls
            cur.execute("SELECT COUNT(*) FROM post_call_analysis")
            stats["total_calls"] = cur.fetchone()[0]

            # Calls today
            cur.execute("""
                SELECT COUNT(*) FROM post_call_analysis 
                WHERE call_date = CURRENT_DATE
            """)
            stats["calls_today"] = cur.fetchone()[0]

            # Calls by task type
            cur.execute("""
                SELECT task_type, COUNT(*) as count 
                FROM post_call_analysis 
                WHERE task_type IS NOT NULL
                GROUP BY task_type 
                ORDER BY count DESC
            """)
            stats["by_task_type"] = [
                {"task_type": row[0], "count": row[1]} for row in cur.fetchall()
            ]

            # Top callers
            cur.execute("""
                SELECT caller_phone, COUNT(*) as count 
                FROM post_call_analysis 
                GROUP BY caller_phone 
                ORDER BY count DESC 
                LIMIT 10
            """)
            stats["top_callers"] = [
                {"phone": row[0], "count": row[1]} for row in cur.fetchall()
            ]

            # Recent calls (last 24 hours)
            cur.execute("""
                SELECT COUNT(*) FROM post_call_analysis 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
            stats["calls_last_24h"] = cur.fetchone()[0]

        return {"ok": True, "stats": stats}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


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
