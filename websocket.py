# websocket_bridge.py
import asyncio
import base64
import json
import traceback
from typing import Dict

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app_instance import (
    LOG_EVENT_TYPES,
    OPENAI_API_KEY,
    SHOW_TIMING_MATH,
    TEMPERATURE,
    app,
)
from db_utils import insert_call_record
from interruption import handle_speech_started_event
from session_setup import initialize_session
from telephony_transfer import get_transfer_status, transfer_call_via_url

# Map line_number -> phone number (used when model chooses a line)
LINE_MAP = {
    "1": "+13526659393",
    "2": "+12125551234",
    "3": "+17185551234",
}


async def try_send_media(websocket: WebSocket, payload: dict) -> bool:
    """
    Safely send JSON to Twilio WebSocket. Returns False if the WS is already closed.
    """
    try:
        if websocket.client_state != WebSocketState.CONNECTED:
            return False
        await websocket.send_json(payload)
        return True
    except Exception:
        return False


# =======================
# Twilio <-> OpenAI Realtime bridge
# =======================
@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Bridge audio and events between Twilio and OpenAI Realtime."""
    print("Client connected to Princeton Insurance system")
    await websocket.accept()

    # Initialize - will be populated from Twilio's 'start' event
    caller_phone = ""
    call_sid = ""
    stream_sid = None

    # buffers for function args (call_id -> json string)
    function_arg_buffers: Dict[str, str] = {}

    async with websockets.connect(
        f"wss://api.openai.com/v1/realtime?model=gpt-realtime&temperature={TEMPERATURE}",
        extra_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
    ) as openai_ws:
        await initialize_session(openai_ws)

        # per-connection state
        transferred = False
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None
        last_interruption_time = 0

        async def receive_from_twilio():
            nonlocal stream_sid, call_sid, caller_phone, latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)

                    if data["event"] == "media" and openai_ws.state.name == "OPEN":
                        latest_media_timestamp = int(data["media"]["timestamp"])
                        await openai_ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": data["media"]["payload"],
                                }
                            )
                        )

                    elif data["event"] == "start":
                        stream_sid = data["start"]["streamSid"]
                        call_sid = data["start"].get("callSid", "")

                        # ⭐ Extract caller info from customParameters
                        custom_params = data["start"].get("customParameters", {})
                        caller_phone = custom_params.get("caller_phone", "")

                        # ⭐ ENHANCED LOGGING - This is where caller info gets logged
                        print("=" * 70, flush=True)
                        print("🔵 PRINCETON INSURANCE CALL STARTED", flush=True)
                        print("=" * 70, flush=True)
                        print(
                            f"📞 CALLER PHONE:  {caller_phone or '⚠️ MISSING'}",
                            flush=True,
                        )
                        print(f"📋 CALL SID:      {call_sid}", flush=True)
                        print(f"🌊 STREAM SID:    {stream_sid}", flush=True)
                        print(f"📦 CUSTOM PARAMS: {custom_params}", flush=True)
                        print("=" * 70, flush=True)

                        # ⭐ Validation - warn if caller_phone is missing
                        if not caller_phone:
                            print(
                                "⚠️⚠️⚠️ WARNING: caller_phone is EMPTY! Check TwiML <Parameter> tags ⚠️⚠️⚠️",
                                flush=True,
                            )

                        # ⭐ Update OpenAI session metadata with caller info
                        try:
                            await openai_ws.send(
                                json.dumps(
                                    {
                                        "type": "session.update",
                                        "session": {
                                            "metadata": {
                                                "caller_phone": caller_phone,
                                                "call_sid": call_sid,
                                                "stream_sid": stream_sid,
                                            }
                                        },
                                    }
                                )
                            )
                            print(
                                f"✅ Updated OpenAI session metadata with caller: {caller_phone}",
                                flush=True,
                            )
                        except Exception as e:
                            print(
                                f"❌ Failed to update session metadata: {e}", flush=True
                            )

                        reset_state()

                    elif data["event"] == "mark":
                        if mark_queue:
                            mark_queue.pop(0)

            except WebSocketDisconnect:
                print("=" * 70, flush=True)
                print(
                    f"🔴 CALL DISCONNECTED - Caller: {caller_phone}, CallSid: {call_sid}",
                    flush=True,
                )
                print("=" * 70, flush=True)
                if openai_ws.state.name == "OPEN":
                    await openai_ws.close()

        def reset_state():
            nonlocal \
                latest_media_timestamp, \
                last_assistant_item, \
                response_start_timestamp_twilio, \
                last_interruption_time
            latest_media_timestamp = 0
            response_start_timestamp_twilio = None
            last_assistant_item = None
            last_interruption_time = 0
            mark_queue.clear()

        async def send_to_twilio():
            nonlocal \
                stream_sid, \
                last_assistant_item, \
                response_start_timestamp_twilio, \
                last_interruption_time, \
                transferred
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    evt_type = response.get("type")

                    # If we've transferred, close Realtime socket and stop loop
                    if transferred:
                        try:
                            await openai_ws.close()
                        except Exception:
                            pass
                        return

                    # lightweight logging
                    if evt_type in LOG_EVENT_TYPES:
                        if evt_type == "response.output_audio.delta":
                            clean = {
                                "type": evt_type,
                                "response_id": response.get("response_id"),
                                "item_id": response.get("item_id"),
                                "delta_length": len(response.get("delta", ""))
                                if "delta" in response
                                else 0,
                            }
                            print(f"Received event: {evt_type}", clean)
                        else:
                            print(f"Received event: {evt_type}")

                    if evt_type == "response.done":
                        print(
                            f"[AI] Response completed. Status: {response.get('response', {}).get('status')}",
                            flush=True,
                        )

                    if evt_type == "conversation.item.created":
                        item = response.get("item", {})
                        print(
                            f"[CONVERSATION] New item: {item.get('type')} from {item.get('role')}",
                            flush=True,
                        )
                        if item.get("type") == "function_call":
                            print(
                                f"[CONVERSATION] AI wants to call function: {item.get('name')}",
                                flush=True,
                            )

                    # ----- stream audio back to Twilio -----
                    if (
                        evt_type == "response.output_audio.delta"
                        and "delta" in response
                    ):
                        # Realtime returns base64-encoded μ-law. Twilio expects base64 again.
                        audio_payload = base64.b64encode(
                            base64.b64decode(response["delta"])
                        ).decode("utf-8")

                        ok = await try_send_media(
                            websocket,
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": audio_payload},
                            },
                        )
                        if not ok:
                            # Twilio WS closed—stop loop
                            return

                        # track start of assistant response for smart interruption
                        if (
                            response.get("item_id")
                            and response["item_id"] != last_assistant_item
                        ):
                            response_start_timestamp_twilio = latest_media_timestamp
                            last_assistant_item = response["item_id"]
                            if SHOW_TIMING_MATH:
                                print(
                                    f"Sally started new response @ {response_start_timestamp_twilio}ms (ID: {last_assistant_item})"
                                )

                        if not await send_mark(websocket, stream_sid):
                            return

                    # ----- intelligent interruption: caller started talking -----
                    if evt_type == "input_audio_buffer.speech_started":
                        if last_assistant_item:
                            speaking_dur = latest_media_timestamp - (
                                response_start_timestamp_twilio or 0
                            )
                            since_last = latest_media_timestamp - last_interruption_time
                            if speaking_dur > 500 and since_last > 1000:
                                last_interruption_time = latest_media_timestamp
                                await handle_speech_started_event(
                                    openai_ws, websocket, stream_sid
                                )

                    # ====== FUNCTION CALL HANDLING ======
                    if evt_type.startswith("response.function_call"):
                        print(f"[FUNCTION] Event: {evt_type} - {response}", flush=True)

                    # 1) accumulate streamed JSON args
                    if evt_type == "response.function_call_arguments.delta":
                        cid = response["call_id"]
                        delta = response.get("delta", "")
                        function_arg_buffers[cid] = (
                            function_arg_buffers.get(cid, "") + delta
                        )
                        print(
                            f"[FUNCTION] Accumulating args for {cid}: +'{delta}' (total: '{function_arg_buffers[cid]}')",
                            flush=True,
                        )

                    # 2) on done, dispatch the tool
                    elif evt_type == "response.function_call_arguments.done":
                        cid = response["call_id"]
                        tool_name = response.get("name")
                        raw_args = function_arg_buffers.pop(cid, "{}")

                        print(
                            f"[FUNCTION] Function call complete: {tool_name}",
                            flush=True,
                        )
                        print(f"[FUNCTION] Raw arguments: '{raw_args}'", flush=True)

                        try:
                            args = json.loads(raw_args) if raw_args else {}
                            print(f"[FUNCTION] Parsed arguments: {args}", flush=True)
                        except Exception as e:
                            print(
                                f"[FUNCTION] Failed to parse args for {tool_name}: {e}",
                                flush=True,
                            )
                            args = {}

                        print(
                            f"[FUNCTION] Executing tool: {tool_name} with args: {args}",
                            flush=True,
                        )

                        # Handle each tool
                        if tool_name == "record_call_data":
                            # 🚫 Never trust the model's caller_phone. Always use the server's.
                            def normalize_e164(num: str) -> str:
                                # very light normalization; tweak as needed
                                return num.replace(" ", "").replace("-", "")

                            server_phone = normalize_e164(caller_phone or "")
                            if (
                                not server_phone.startswith("+")
                                or len(server_phone) < 8
                            ):
                                # Fail fast if we truly don't have it; better than saving a fake number.
                                raise RuntimeError(
                                    f"Missing/invalid server caller_phone: '{server_phone}'. "
                                    "Refusing to insert with placeholder."
                                )

                            print(
                                f"📝 Recording call data for: {server_phone}",
                                flush=True,
                            )

                            tool_output = insert_call_record(
                                caller_phone=server_phone,  # ← force the real one
                                task_type=args.get("task_type", ""),
                                call_summary=args.get("call_summary", ""),
                                detail_info=args.get("detail_info", ""),
                            )

                            print(f"✅ Call record inserted: {tool_output}", flush=True)

                        elif tool_name == "check_status":
                            # simple deterministic mock: line 1 busy, others free
                            req_lines = args.get("line_numbers", [])
                            tool_output = {
                                "ok": True,
                                "status": {
                                    str(n): ("busy" if int(n) == 1 else "available")
                                    for n in req_lines
                                },
                            }

                        elif tool_name == "end_call":
                            print(
                                f"📞 Ending call - Reason: {args.get('reason', 'N/A')}",
                                flush=True,
                            )
                            tool_output = {
                                "ended": True,
                                "reason": args.get("reason", ""),
                            }

                        elif tool_name == "transfer_to_human":
                            # Allow either line_number (preferred) or target_number
                            line_number = args.get("line_number")
                            target = args.get("target_number")

                            if line_number is not None and target is None:
                                try:
                                    target = LINE_MAP[str(int(line_number))]
                                except Exception:
                                    tool_output = {
                                        "ok": False,
                                        "error": f"invalid line_number: {line_number}",
                                    }
                                    await openai_ws.send(
                                        json.dumps({"type": "response.create"})
                                    )
                                    continue

                            if not target:
                                tool_output = {
                                    "ok": False,
                                    "error": "missing line_number or target_number",
                                }
                            elif not call_sid:
                                tool_output = {"ok": False, "error": "missing_call_sid"}
                            else:
                                try:
                                    print(
                                        f"📞 Transferring {caller_phone} to {target}...",
                                        flush=True,
                                    )

                                    # Redirect active leg to our TwiML route
                                    transfer_call_via_url(call_sid, target)

                                    # Wait for Dial action webhook to set final status
                                    timeout_sec = 70
                                    poll_every = 0.5
                                    waited = 0.0
                                    final_status = None

                                    while waited < timeout_sec:
                                        status = get_transfer_status(call_sid)
                                        if status and status not in (
                                            "pending",
                                            "queued",
                                            "ringing",
                                            "in-progress",
                                            "initiated",
                                        ):
                                            final_status = status
                                            break
                                        await asyncio.sleep(poll_every)
                                        waited += poll_every

                                    if final_status in ("answered", "completed"):
                                        print(
                                            f"✅ Transfer successful: {final_status}",
                                            flush=True,
                                        )
                                        tool_output = {
                                            "ok": True,
                                            "transferred_to": target,
                                            "status": final_status,
                                        }
                                        transferred = True
                                        try:
                                            await openai_ws.close()
                                        except Exception:
                                            pass
                                    elif final_status in (
                                        "busy",
                                        "no-answer",
                                        "failed",
                                    ):
                                        print(
                                            f"❌ Transfer failed: {final_status}",
                                            flush=True,
                                        )
                                        tool_output = {
                                            "ok": False,
                                            "transferred_to": target,
                                            "status": final_status,
                                            "error": "transfer_failed",
                                        }
                                    else:
                                        print(
                                            f"⏳ Transfer timeout: {final_status}",
                                            flush=True,
                                        )
                                        tool_output = {
                                            "ok": True,
                                            "transferred_to": target,
                                            "status": "pending_timeout",
                                        }

                                except Exception as e:
                                    print(f"❌ Transfer error: {e}", flush=True)
                                    tool_output = {"ok": False, "error": str(e)}

                        else:
                            tool_output = {
                                "ok": False,
                                "error": f"Unknown tool {tool_name}",
                            }

                        print(f"[FUNCTION] Tool output: {tool_output}", flush=True)

                        # Send function output back to OpenAI
                        await openai_ws.send(
                            json.dumps(
                                {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": cid,
                                        "output": json.dumps(tool_output),
                                    },
                                }
                            )
                        )

                        # Continue conversation if not transferred
                        if not transferred:
                            await openai_ws.send(
                                json.dumps({"type": "response.create"})
                            )

            except Exception as e:
                print(f"Error in send_to_twilio: {e}")
                traceback.print_exc()

        async def send_mark(connection: WebSocket, stream_sid_val: str | None) -> bool:
            if stream_sid_val:
                try:
                    await connection.send_json(
                        {
                            "event": "mark",
                            "streamSid": stream_sid_val,
                            "mark": {"name": "part"},
                        }
                    )
                    mark_queue.append("part")
                    return True
                except Exception:
                    return False
            return False

        await asyncio.gather(receive_from_twilio(), send_to_twilio())
