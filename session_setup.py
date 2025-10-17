import json

from app_instance import SYSTEM_MESSAGE, VOICE


# =======================
# Realtime session setup
# =======================
async def send_initial_conversation_item(openai_ws):
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Start the conversation with your initial greeting as Sally from Princeton Insurance.",
                }
            ],
        },
    }
    await openai_ws.send(json.dumps(initial_conversation_item))
    await openai_ws.send(json.dumps({"type": "response.create"}))


async def initialize_session(openai_ws):
    session_update = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": "gpt-realtime",
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcmu"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.7,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                    },
                },
                "output": {"format": {"type": "audio/pcmu"}, "voice": VOICE},
            },
            "instructions": SYSTEM_MESSAGE,
            "tools": [
                {
                    "type": "function",
                    "name": "record_call_data",
                    "description": "Record call information to the database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "caller_phone": {
                                "type": "string",
                                "description": "Caller's phone number in E.164 format (e.g., +14155551234)",
                            },
                            "task_type": {
                                "type": "string",
                                "description": "Type of task or request (e.g., 'Policy Question', 'Address Change', 'Payment Inquiry')",
                            },
                            "call_summary": {
                                "type": "string",
                                "description": "Brief summary of the call",
                            },
                            "detail_info": {
                                "type": "string",
                                "description": "Detailed information about the call, customer requests, and outcomes",
                            },
                        },
                        "required": ["caller_phone", "task_type", "call_summary"],
                    },
                },
                {
                    "type": "function",
                    "name": "check_status",
                    "description": "Check availability status of team members' phone lines",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "line_numbers": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "Array of line numbers to check (1, 2, 3)",
                            }
                        },
                        "required": ["line_numbers"],
                    },
                },
                {
                    "type": "function",
                    "name": "transfer_to_human",
                    "description": "Transfer the active call to a live human agent via Twilio",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "line_number": {
                                "type": "integer",
                                "description": "Preferred: 1, 2, or 3. The server maps this to the correct phone number.",
                                "enum": [1, 2, 3],
                            },
                            "target_number": {
                                "type": "string",
                                "description": "Optional: E.164 phone number to transfer to, e.g. +13526659393 (used if line_number not provided).",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Short reason for the transfer (for logging)",
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "name": "end_call",
                    "description": "End the phone call",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Reason for ending the call",
                            }
                        },
                        "required": ["reason"],
                    },
                },
            ],
            "tool_choice": "auto",
        },
    }
    print("Sending Princeton Insurance session update:", json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))
    await send_initial_conversation_item(openai_ws)
