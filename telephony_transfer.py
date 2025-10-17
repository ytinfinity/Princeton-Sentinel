# telephony_transfer.py
import os
from typing import Dict, Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.rest import Client
from twilio.twiml.voice_response import Dial, Number, VoiceResponse

load_dotenv(override=True)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TRANSFER_WEBHOOK_URL = os.getenv(
    "TRANSFER_WEBHOOK_URL", ""
)  # e.g. https://YOURDOMAIN/twiml/transfer
TWILIO_CALLBACK_BASE = os.getenv(
    "TWILIO_CALLBACK_BASE", ""
)  # e.g. https://YOURDOMAIN  (NO trailing slash)
TWILIO_CALLER_ID = os.getenv(
    "TWILIO_CALLER_ID"
)  # optional: your Twilio number in E.164

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN are required")

if not TRANSFER_WEBHOOK_URL:
    raise RuntimeError(
        "TRANSFER_WEBHOOK_URL is required (e.g. https://YOURDOMAIN/twiml/transfer)"
    )
if not TWILIO_CALLBACK_BASE:
    raise RuntimeError("TWILIO_CALLBACK_BASE is required (e.g. https://YOURDOMAIN)")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
router = APIRouter()

# ----------------------------
# In-memory transfer state
# ----------------------------
#  call_sid -> {"status": "pending"|"answered"|"busy"|"no-answer"|"failed"|"completed", "to": "+1..."}
TRANSFER_STATE: Dict[str, Dict[str, str]] = {}


def set_transfer_pending(call_sid: str, to_number: str):
    TRANSFER_STATE[call_sid] = {"status": "pending", "to": to_number}


def set_transfer_status(call_sid: str, status: str):
    if call_sid in TRANSFER_STATE:
        TRANSFER_STATE[call_sid]["status"] = status


def get_transfer_status(call_sid: str) -> Optional[str]:
    return TRANSFER_STATE.get(call_sid, {}).get("status")


def _clean_e164(num: str) -> str:
    if not num:
        return num
    return "+" + "".join(ch for ch in num if ch.isdigit())


def _build_transfer_twiml(target_number: str, call_sid: str) -> str:
    """Return TwiML that dials the human and reports back via action/status callbacks."""
    to = _clean_e164(target_number or "+13526659393")

    vr = VoiceResponse()

    # Add a brief prompt if you like:
    # vr.say("Connecting you now.")

    # /twilio/dial-action will be called when the <Dial> verb completes (success or fail)
    dial_action_url = f"{TWILIO_CALLBACK_BASE}/twilio/dial-action?call_sid={call_sid}"

    if TWILIO_CALLER_ID:
        d = Dial(
            answer_on_bridge=True,
            timeout=25,
            caller_id=_clean_e164(TWILIO_CALLER_ID),
            action=dial_action_url,
            method="POST",
        )
    else:
        d = Dial(
            answer_on_bridge=True, timeout=25, action=dial_action_url, method="POST"
        )

    # Per-number status callback for detailed lifecycle updates
    number_status_cb = (
        f"{TWILIO_CALLBACK_BASE}/twilio/number-status?call_sid={call_sid}"
    )

    n = Number(
        to,
        status_callback=number_status_cb,
        status_callback_method="POST",
        status_callback_event=[
            "initiated",
            "ringing",
            "answered",
            "completed",
            "busy",
            "no-answer",
            "failed",
        ],
    )
    d.append(n)
    vr.append(d)
    return str(vr)


@router.post("/twiml/transfer")
async def twiml_transfer(request: Request):
    """
    TwiML endpoint for live transfers. Twilio Calls API will POST here after we update the call URL.
    Expects form data including CallSid; may include ?target_number in the querystring.
    Returns proper text/xml TwiML with callbacks wired.
    """
    form = await request.form()
    call_sid = form.get("CallSid") or request.query_params.get("CallSid") or ""
    target_number = request.query_params.get("target_number") or "+13526659393"

    xml = _build_transfer_twiml(target_number, call_sid).strip()
    # Mark pending so the app can wait on it
    if call_sid:
        set_transfer_pending(call_sid, _clean_e164(target_number))

    return Response(content=xml, media_type="text/xml")


def transfer_call_via_url(call_sid: str, target_number: str) -> None:
    """
    Redirect the active call to our TwiML transfer route (POST).
    """
    to = _clean_e164(target_number)
    qs = urlencode({"target_number": to})
    url = f"{TRANSFER_WEBHOOK_URL}?{qs}"
    # Mark pending immediately (Twilio will then fetch /twiml/transfer and reinforce it)
    set_transfer_pending(call_sid, to)
    client.calls(call_sid).update(url=url, method="POST")


# -------- Twilio callbacks (state updates) --------


@router.post("/twilio/number-status")
async def twilio_number_status(request: Request):
    """
    Receives per-number status events during/after dial.
    Body (form-encoded) includes CallSid and CallStatus, DialCallStatus, etc.
    """
    form = await request.form()
    call_sid = request.query_params.get("call_sid") or form.get("CallSid") or ""
    event = (
        form.get("CallStatus")
        or form.get("DialCallStatus")
        or form.get("CallEvent")
        or ""
    )
    # Normalize a bit
    if event in {"queued", "ringing", "in-progress"}:
        event = event
    elif event in {"busy", "no-answer", "failed", "completed", "answered"}:
        event = event
    set_transfer_status(call_sid, event or "in-progress")
    # Twilio expects 200; no TwiML here
    return Response(content="", media_type="text/plain")


@router.post("/twilio/dial-action")
async def twilio_dial_action(request: Request):
    """
    Called once the <Dial> verb ends. DialCallStatus is authoritative.
    """
    form = await request.form()
    call_sid = request.query_params.get("call_sid") or form.get("CallSid") or ""
    dial_status = (
        form.get("DialCallStatus") or ""
    )  # 'completed','busy','no-answer','failed'

    if dial_status:
        set_transfer_status(call_sid, dial_status)

    # This is a TwiML response point. We can return an empty <Response/> to let the call end,
    # or say something if needed. Keep it minimal:
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="text/xml",
    )
