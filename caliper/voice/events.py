"""Every Nova 2 Sonic event shape, one builder each.

The bidirectional protocol is a strict sequence and the failure modes are silent,
so the shapes live here rather than being assembled inline at three call sites.

Input sequence:

    sessionStart
      promptStart                    assigns promptName, sets voice and tools
      contentStart(TEXT, SYSTEM) / textInput / contentEnd
      contentStart(AUDIO, USER) / audioInput x N / contentEnd
      [on toolUse] contentStart(TOOL) / toolResult / contentEnd
      promptEnd
    sessionEnd

Audio is 16 kHz in and 24 kHz out, sixteen bit mono LPCM, base64. Sending the
output rate to the input produces audio that is recognisably wrong rather than
obviously broken, which is worse.
"""

from __future__ import annotations

import base64
import json
import uuid

# Confirmed Nova 2 Sonic voices.
VOICES = (
    "matthew",
    "tiffany",
    "amy",
    "olivia",
    "lupe",
    "carlos",
    "ambre",
    "florian",
    "lennart",
    "beatrice",
    "lorenzo",
    "tina",
    "carolina",
    "leo",
    "kiara",
    "arjun",
)

INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000

# HIGH, MEDIUM or LOW. Nova 2 Sonic only. MEDIUM is the documented default.
ENDPOINTING = "MEDIUM"

SCORING_TOOL_NAME = "score_practice_turn"


def new_id() -> str:
    return str(uuid.uuid4())


def session_start(max_tokens: int = 1024, temperature: float = 0.7, top_p: float = 0.9) -> str:
    return json.dumps(
        {
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "maxTokens": max_tokens,
                        "topP": top_p,
                        "temperature": temperature,
                    },
                    "turnDetectionConfiguration": {"endpointingSensitivity": ENDPOINTING},
                }
            }
        }
    )


def scoring_tool_spec(criteria: list[dict]) -> dict:
    """The tool the model calls mid conversation so the form fills in live.

    The contract lives in the JSON schema, not in prose, because a model obeys a
    typed schema and negotiates with a docstring.
    """
    ids = [c["id"] for c in criteria]
    schema = {
        "type": "object",
        "properties": {
            "transcript_window": {
                "type": "string",
                "description": "The representative's most recent turn, verbatim.",
            },
            "criterion_id": {
                "type": "string",
                "enum": ids,
                "description": "Which scored criterion this turn is evidence for.",
            },
            "member_restated": {
                "type": "boolean",
                "description": "True only if the MEMBER restated the amount and reason herself.",
            },
            "restatement_text": {
                "type": "string",
                "description": "The member's own words, if she restated.",
            },
        },
        "required": ["transcript_window", "criterion_id"],
    }
    return {
        "toolSpec": {
            "name": SCORING_TOOL_NAME,
            "description": (
                "Score the representative's most recent turn against the active quality "
                "criteria. Call this after each of the representative's turns."
            ),
            "inputSchema": {"json": json.dumps(schema)},
        }
    }


def prompt_start(prompt_name: str, criteria: list[dict], voice_id: str = "tiffany") -> str:
    if voice_id not in VOICES:
        raise ValueError(f"unknown voice {voice_id!r}; confirmed voices are {VOICES}")
    return json.dumps(
        {
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "textOutputConfiguration": {"mediaType": "text/plain"},
                    "audioOutputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": OUTPUT_SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "voiceId": voice_id,
                        "encoding": "base64",
                        "audioType": "SPEECH",
                    },
                    "toolUseOutputConfiguration": {"mediaType": "application/json"},
                    "toolConfiguration": {
                        "tools": [scoring_tool_spec(criteria)],
                        "toolChoice": {"auto": {}},
                    },
                }
            }
        }
    )


def content_start_system(prompt_name: str, content_name: str) -> str:
    return json.dumps(
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "type": "TEXT",
                    "interactive": False,
                    "role": "SYSTEM",
                    "textInputConfiguration": {"mediaType": "text/plain"},
                }
            }
        }
    )


def text_input(prompt_name: str, content_name: str, content: str) -> str:
    return json.dumps(
        {
            "event": {
                "textInput": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": content,
                }
            }
        }
    )


def content_start_audio(prompt_name: str, content_name: str) -> str:
    return json.dumps(
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": INPUT_SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "audioType": "SPEECH",
                        "encoding": "base64",
                    },
                }
            }
        }
    )


def audio_input(prompt_name: str, content_name: str, pcm: bytes) -> str:
    return json.dumps(
        {
            "event": {
                "audioInput": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": base64.b64encode(pcm).decode("ascii"),
                }
            }
        }
    )


def content_start_tool_result(prompt_name: str, content_name: str, tool_use_id: str) -> str:
    return json.dumps(
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "interactive": False,
                    "type": "TOOL",
                    "role": "TOOL",
                    "toolResultInputConfiguration": {
                        "toolUseId": tool_use_id,
                        "type": "TEXT",
                        "textInputConfiguration": {"mediaType": "text/plain"},
                    },
                }
            }
        }
    )


def tool_result(prompt_name: str, content_name: str, payload: dict) -> str:
    return json.dumps(
        {
            "event": {
                "toolResult": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": json.dumps(payload),
                }
            }
        }
    )


def content_end(prompt_name: str, content_name: str) -> str:
    return json.dumps({"event": {"contentEnd": {"promptName": prompt_name, "contentName": content_name}}})


def prompt_end(prompt_name: str) -> str:
    return json.dumps({"event": {"promptEnd": {"promptName": prompt_name}}})


def session_end() -> str:
    return json.dumps({"event": {"sessionEnd": {}}})


def build_system_prompt(persona: dict) -> str:
    """The member the representative practises against.

    She is confidently wrong about one specific thing, cooperative, and will not
    volunteer the correct number. If she simply agreed, the practice would score
    nothing.
    """
    state = persona["member_state"]
    facts = persona["plan_facts"]
    verification = ", ".join(persona["verification_required"])
    return (
        "You are a health plan member on a call with a member services representative. "
        "You are NOT an assistant and you never offer help.\n\n"
        f"Your situation: {state['believes']} "
        f"You are {state['emotional_register']}. "
        f"You misunderstand one thing specifically: {state['core_misunderstanding']}.\n\n"
        "The true facts of your claim, which you do NOT know and must not recite:\n"
        f"  the provider billed {facts['billed_amount']}, "
        f"the plan allows {facts['allowed_amount']}, "
        f"the plan paid {facts['plan_paid']}, "
        f"you owe {facts['member_responsibility']} "
        f"because your coinsurance is {facts['coinsurance_rate']:.0%} of the allowed amount, "
        "which applies after the deductible is met.\n\n"
        "How to behave:\n"
        f'- Open with something close to: "{state["opening_line"]}"\n'
        f"- Do not reveal plan details until the representative verifies your identity "
        f"({verification}). If they ask, answer.\n"
        "- Push back once if the explanation is vague. Ask what the difference is between "
        "what the hospital charged and what you owe.\n"
        "- When the representative asks you to say the amount back in your own words, do it "
        "in YOUR words, not theirs. If you understood, say the number and the reason. If the "
        "explanation was unclear, say a WRONG number, because that is the honest outcome.\n"
        "- Never lecture. Never explain insurance to the representative. Keep turns short, "
        "one or two sentences, like a real phone call.\n"
    )
