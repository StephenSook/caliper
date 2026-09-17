"""A live Nova 2 Sonic practice call.

Three things here will otherwise cost hours, so they are handled explicitly.

1. **boto3 cannot do this.** There is no
   `invoke_model_with_bidirectional_stream` on the synchronous client. The
   operation lives in `aws-sdk-bedrock-runtime`, the request and chunk types live
   in its `.models` module rather than `.client`, and the config must be built
   with the async `resolve` classmethod.

2. **The default transport refuses.** aiohttp raises UnsupportedTransportError
   because duplex event streaming needs HTTP/2, so the AWS Common Runtime
   transport is selected explicitly. Without `awscrt` installed the import fails
   in a way that reads as a missing module rather than a missing capability.

3. **Every toolUse MUST receive a toolResult.** AWS, verbatim: "Nova 2 Sonic
   expects a toolResult event after every toolUse event it sends. If your
   application fails to respond, the model enters a waiting state, causing
   unresponsive behavior." So the tool handler is wrapped such that an exception
   still emits a result. A silent call on stage is the worst outcome available.

Barge in: when the member is interrupted Nova stops generating and marks the
content interrupted. Nova generates faster than real time, so audio already
delivered but not yet played has to be DISCARDED rather than played out. This
module emits an `interrupted` event and the client clears its queue.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from caliper.voice import events as ev
from caliper.voice.scoring_tool import PracticeScore, new_score, safe_score

REGION = os.environ.get("AWS_REGION", "us-east-1")
PROFILE = os.environ.get("AWS_PROFILE")
MODEL_ID = os.environ.get("CALIPER_VOICE_MODEL_ID", "amazon.nova-2-sonic-v1:0")

# The documented connection limit is eight minutes. Transition early enough to
# replay history and keep talking.
SESSION_LIMIT_SECONDS = 480
TRANSITION_AT_SECONDS = 360

# One frame of digital silence, 32 ms at 16 kHz sixteen bit mono.
#
# Endpointing detects the END of a turn by hearing silence. If a caller simply
# STOPS SENDING FRAMES, there is no silence to detect, only an absence of data,
# and the model waits forever: you get userSpeechStart, an ASR transcript, and
# then nothing at all. A real microphone streams ambient room noise so this never
# arises live, but any scripted or recorded path has to pad deliberately.
SILENCE_FRAME = b"\x00" * 1024


@dataclass
class SonicSession:
    """One practice call. Owns the stream, the score, and the tool contract."""

    persona: dict
    on_event: Callable[[dict], None] | None = None
    voice_id: str = "tiffany"

    prompt_name: str = field(default_factory=ev.new_id)
    audio_content_name: str = field(default_factory=ev.new_id)
    score_state: PracticeScore = field(init=False)
    _stream: object | None = field(default=None, init=False, repr=False)
    _client: object | None = field(default=None, init=False, repr=False)
    _active: bool = field(default=False, init=False)
    _rep_turn: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        self.score_state = new_score(self.persona["scored_criteria"])

    # ------------------------------------------------------------------ setup
    async def open(self) -> None:
        from aws_sdk_bedrock_runtime.client import AsyncBedrockRuntimeClient
        from aws_sdk_bedrock_runtime.config import AsyncBedrockRuntimeConfig
        from aws_sdk_bedrock_runtime.models import (
            InvokeModelWithBidirectionalStreamOperationInput,
        )
        from smithy_http.aio.crt import AWSCRTHTTPClient

        config = await AsyncBedrockRuntimeConfig.resolve(profile=PROFILE, region=REGION)
        config.transport = AWSCRTHTTPClient()
        self._client = AsyncBedrockRuntimeClient(config=config)
        self._stream = await self._client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=MODEL_ID)
        )
        self._active = True

        await self._send(ev.session_start())
        await self._send(ev.prompt_start(self.prompt_name, self.persona["scored_criteria"], self.voice_id))

        system_content = ev.new_id()
        await self._send(ev.content_start_system(self.prompt_name, system_content))
        await self._send(
            ev.text_input(self.prompt_name, system_content, ev.build_system_prompt(self.persona))
        )
        await self._send(ev.content_end(self.prompt_name, system_content))

        await self._send(ev.content_start_audio(self.prompt_name, self.audio_content_name))
        self._emit({"type": "ready", "criteria": self.score_state.as_payload()["criteria"]})

    async def _send(self, payload: str) -> None:
        from aws_sdk_bedrock_runtime.models import (
            BidirectionalInputPayloadPart,
            InvokeModelWithBidirectionalStreamInputChunk,
        )

        if not self._stream:
            raise RuntimeError("the session is not open")
        await self._stream.input_stream.send(
            InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=payload.encode())
            )
        )

    def _emit(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    # ------------------------------------------------------------------- audio
    async def send_audio(self, pcm16_16k: bytes) -> None:
        """One frame of microphone audio. 16 kHz, sixteen bit, mono, little endian."""
        if not self._active:
            return
        await self._send(ev.audio_input(self.prompt_name, self.audio_content_name, pcm16_16k))

    async def send_silence(self, seconds: float = 1.5, pace: bool = True) -> None:
        """End a turn deliberately, for any path that is not a live microphone.

        Without this the model never hears the pause, never emits userSpeechEnd,
        and never answers at all.
        """
        for _ in range(max(1, int(seconds / 0.032))):
            await self.send_audio(SILENCE_FRAME)
            if pace:
                await asyncio.sleep(0.03)

    # ------------------------------------------------------------------ receive
    async def receive(self) -> AsyncIterator[dict]:
        """Read the output stream, handling tools, barge in and completion."""
        if not self._stream:
            raise RuntimeError("the session is not open")

        while self._active:
            output = await self._stream.await_output()
            result = await output[1].receive()
            if result is None or result.value is None or result.value.bytes_ is None:
                continue

            try:
                message = json.loads(result.value.bytes_.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

            event = message.get("event", {})

            if "textOutput" in event:
                payload = event["textOutput"]
                content = payload.get("content", "")
                role = payload.get("role", "ASSISTANT")

                if '"interrupted"' in content:
                    self._emit({"type": "interrupted"})
                    yield {"type": "interrupted"}
                    continue

                out = {"type": "transcript", "content": content, "role": role}
                self._emit(out)
                yield out

                # Score from the transcript rather than waiting for the model to
                # call the tool.
                #
                # The persona is a member told never to offer help, which
                # suppresses tool calling, and more importantly a score that
                # depends on the model CHOOSING to score is not deterministic.
                # Reading the transcript keeps the decision entirely in code,
                # which is the rule the audit already follows. The tool stays
                # declared so Nova can volunteer a structured observation, but it
                # corroborates rather than decides.
                for scored in self._score_from_transcript(role, content):
                    yield scored

            elif "audioOutput" in event:
                out = {"type": "audio", "content": event["audioOutput"].get("content", "")}
                self._emit(out)
                yield out

            elif "toolUse" in event:
                async for produced in self._handle_tool(event["toolUse"]):
                    yield produced

            elif "contentEnd" in event:
                stop = event["contentEnd"].get("stopReason")
                if stop == "INTERRUPTED":
                    self._emit({"type": "interrupted"})
                    yield {"type": "interrupted"}

            elif "completionEnd" in event:
                out = {"type": "turn_complete"}
                self._emit(out)
                yield out

    def _score_from_transcript(self, role: str, content: str) -> list[dict]:
        """Apply the criteria to what was actually said, in code.

        USER turns are the representative under practice. ASSISTANT turns are the
        member, and are what the confirmation criterion needs, because that item
        scores whether SHE could say it back rather than whether he said it well.
        """
        if not content.strip():
            return []

        facts = self.persona.get("plan_facts")
        before = {c.id: c.state for c in self.score_state.criteria.values()}

        if role.upper() == "USER":
            # The ASR delivers one turn as several fragments, so scoring each
            # fragment alone can never satisfy a criterion that needs a name plus
            # two identifiers: no single fragment carries all three. Accumulate
            # the turn and score the accumulation.
            self._rep_turn = f"{self._rep_turn} {content}".strip()[-2000:]
            content = self._rep_turn
            for criterion_id in ("VERIFY_IDENTITY", "ALLOWED_VS_BILLED"):
                if criterion_id in self.score_state.criteria:
                    safe_score(
                        self.score_state,
                        {"criterion_id": criterion_id, "transcript_window": content},
                        facts,
                    )
        else:
            asked = any(
                phrase in (self._rep_turn or "").lower()
                for phrase in ("your own words", "say it back", "tell me what", "repeat")
            )
            if asked and "CONFIRM_UNDERSTANDING" in self.score_state.criteria:
                self._rep_turn = ""  # her reply closes his turn
                safe_score(
                    self.score_state,
                    {
                        "criterion_id": "CONFIRM_UNDERSTANDING",
                        "transcript_window": content,
                        "member_restated": True,
                        "restatement_text": content,
                    },
                    facts,
                )

        after = {c.id: c.state for c in self.score_state.criteria.values()}
        if after == before:
            return []
        out = {
            "type": "score",
            "criteria": self.score_state.as_payload()["criteria"],
            "all_passed": self.score_state.all_passed,
            "source": "transcript",
        }
        self._emit(out)
        return [out]

    async def _handle_tool(self, tool_use: dict) -> AsyncIterator[dict]:
        """Score the turn and ALWAYS reply.

        Wrapped so that a parse failure, a bad argument or an unexpected
        exception still produces a toolResult. A path that exits without
        responding leaves Nova waiting and the call goes silent.
        """
        tool_use_id = tool_use.get("toolUseId", "")
        try:
            arguments = json.loads(tool_use.get("content") or "{}")
        except json.JSONDecodeError:
            arguments = {}

        payload = safe_score(self.score_state, arguments, self.persona.get("plan_facts"))

        content_name = ev.new_id()
        try:
            await self._send(ev.content_start_tool_result(self.prompt_name, content_name, tool_use_id))
            await self._send(ev.tool_result(self.prompt_name, content_name, payload))
            await self._send(ev.content_end(self.prompt_name, content_name))
        except Exception as exc:  # noqa: BLE001
            self._emit({"type": "tool_error", "detail": str(exc)})

        out = {
            "type": "score",
            "criteria": payload.get("criteria", []),
            "all_passed": self.score_state.all_passed,
        }
        self._emit(out)
        yield out

    # -------------------------------------------------------------------- close
    async def close(self) -> None:
        if not self._active:
            return
        self._active = False
        try:
            await self._send(ev.content_end(self.prompt_name, self.audio_content_name))
            await self._send(ev.prompt_end(self.prompt_name))
            await self._send(ev.session_end())
            await self._stream.input_stream.close()
        except Exception:  # noqa: BLE001
            # Closing is best effort. A failure here must not mask the transcript
            # and score the caller already has.
            pass


async def run_until_complete(session: SonicSession, timeout: float = SESSION_LIMIT_SECONDS) -> dict:
    """Convenience for a scripted rehearsal, not used by the live WebSocket path."""
    transcript: list[str] = []
    try:
        async with asyncio.timeout(timeout):
            async for event in session.receive():
                if event["type"] == "transcript":
                    transcript.append(event["content"])
    except TimeoutError:
        pass
    finally:
        await session.close()
    return {"transcript": transcript, "score": session.score_state.as_payload()}
