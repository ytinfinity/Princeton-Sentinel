import json

from fastapi import WebSocket


# =======================
# Smart interruption helper
# =======================
async def handle_speech_started_event(
    openai_ws, websocket: WebSocket, stream_sid: str | None
):
    """Truncate Sally's audio precisely where caller interrupts."""
    # Ask the server to use the latest audio input immediately.
    try:
        await openai_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await websocket.send_json({"event": "clear", "streamSid": stream_sid})
        print("Interruption handled - ready for caller input")
    except Exception as e:
        print(f"Interruption handler error: {e}")
