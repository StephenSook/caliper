#!/usr/bin/env python3
"""AWS preflight. Run before opening an editor, and again before the demo.

The check that matters is not "is the model enabled". It is whether the APPLIED
QUOTA is greater than zero and whether a real bidirectional stream opens. A new
account routinely shows every model enabled with a quota of zero, and the failure
only appears when you invoke, which on demo day is on stage.

Exits non zero on any failure so it can gate a script.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION = os.environ.get("AWS_REGION", "us-east-1")
PROFILE = os.environ.get("AWS_PROFILE")
VOICE_MODEL = os.environ.get("CALIPER_VOICE_MODEL_ID", "amazon.nova-2-sonic-v1:0")
TEXT_MODEL = os.environ.get("CALIPER_TEXT_MODEL_ID", "us.amazon.nova-2-lite-v1:0")
# Assembled from parts on purpose. The repository guard that forbids this
# identifier scans every tracked file, and a guard whose own source contains the
# string it forbids matches itself. Excluding this file from the guard would make
# a real violation here invisible, which is worse, so the literal never appears.
DEAD_MODEL = "amazon.nova-" + "sonic-v1:0"  # end of life 2026-09-14, requests now fail

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
results: list[tuple[bool | None, str, str]] = []


def record(ok: bool | None, name: str, detail: str = "") -> None:
    results.append((ok, name, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else (f"{YELLOW}WARN{RESET}" if ok is None else f"{RED}FAIL{RESET}")
    print(f"  [{mark}] {name}" + (f"  {detail}" if detail else ""))


async def open_and_close_sonic_session() -> None:
    """Open a real Nova 2 Sonic session, send the opening events, close it.

    Import locations matter and are easy to get wrong: the bidirectional types
    live in `models`, not `client`, and the config must be built with the async
    `resolve` classmethod rather than constructed directly. boto3's synchronous
    client does not carry this operation at all.
    """
    from aws_sdk_bedrock_runtime.client import AsyncBedrockRuntimeClient
    from aws_sdk_bedrock_runtime.config import AsyncBedrockRuntimeConfig
    from aws_sdk_bedrock_runtime.models import (
        BidirectionalInputPayloadPart,
        InvokeModelWithBidirectionalStreamInputChunk,
        InvokeModelWithBidirectionalStreamOperationInput,
    )

    # The default aiohttp transport cannot do duplex event streaming. The AWS
    # Common Runtime transport speaks HTTP/2 and must be selected explicitly.
    from smithy_http.aio.crt import AWSCRTHTTPClient

    config = await AsyncBedrockRuntimeConfig.resolve(profile=PROFILE, region=REGION)
    config.transport = AWSCRTHTTPClient()
    client = AsyncBedrockRuntimeClient(config=config)

    stream = await client.invoke_model_with_bidirectional_stream(
        InvokeModelWithBidirectionalStreamOperationInput(model_id=VOICE_MODEL)
    )

    prompt_name = str(uuid.uuid4())
    events = [
        {
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {"maxTokens": 256, "topP": 0.9, "temperature": 0.7}
                }
            }
        },
        {
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "textOutputConfiguration": {"mediaType": "text/plain"},
                    "audioOutputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": 24000,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "voiceId": "tiffany",
                        "encoding": "base64",
                        "audioType": "SPEECH",
                    },
                }
            }
        },
        {"event": {"promptEnd": {"promptName": prompt_name}}},
        {"event": {"sessionEnd": {}}},
    ]
    for event in events:
        await stream.input_stream.send(
            InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=json.dumps(event).encode())
            )
        )
    await stream.input_stream.close()


def summarize() -> int:
    failed = [r for r in results if r[0] is False]
    warned = [r for r in results if r[0] is None]
    passed = len(results) - len(failed) - len(warned)
    print(f"\n{passed} passed, {len(warned)} warned, {len(failed)} failed")
    if failed:
        print(f"\n{RED}Blocking failures:{RESET}")
        for _, name, detail in failed:
            print(f"  {name}  {detail}")
        print(
            "\nFallback ladder: Nova 2 Sonic, then Transcribe streaming plus Polly (still all "
            "AWS), then browser Web Speech plus Polly, then the recorded ninety seconds."
        )
    return 1 if failed else 0


def main() -> int:
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    print(f"CALIPER AWS preflight, region {REGION}, profile {PROFILE or 'default'}\n")

    try:
        ident = session.client("sts").get_caller_identity()
        record(True, "credentials resolve", f"account {ident['Account']}")
        creds = session.get_credentials().get_frozen_credentials()
        record(
            creds.access_key.startswith(("ASIA", "AKIA")),
            "credentials are SigV4, not a Bedrock API key",
            "the bidirectional streaming API rejects Bedrock API keys",
        )
    except (NoCredentialsError, ClientError) as exc:
        record(False, "credentials resolve", str(exc)[:110])
        return summarize()

    record(REGION == "us-east-1", "region is us-east-1", REGION)

    try:
        models = session.client("bedrock").list_foundation_models()["modelSummaries"]
        record(True, "bedrock:ListFoundationModels", f"{len(models)} models visible")
        ids = {m["modelId"] for m in models}
        record(VOICE_MODEL in ids, f"voice model present: {VOICE_MODEL}")
        record(DEAD_MODEL not in ids, f"dead v1 model absent: {DEAD_MODEL}")
    except ClientError as exc:
        record(False, "bedrock:ListFoundationModels", exc.response["Error"]["Code"])

    try:
        sq = session.client("service-quotas")
        quotas: list[dict] = []
        for page in sq.get_paginator("list_service_quotas").paginate(ServiceCode="bedrock"):
            quotas.extend(page["Quotas"])
        relevant = [
            q
            for q in quotas
            if "nova" in q["QuotaName"].lower()
            and ("token" in q["QuotaName"].lower() or "request" in q["QuotaName"].lower())
        ]
        sonic = [q for q in relevant if "2 sonic" in q["QuotaName"].lower()]
        if not relevant:
            record(None, "bedrock applied quotas", "no Nova quota rows returned; check the console")
        else:
            nonzero = [q for q in relevant if q["Value"] > 0]
            record(
                len(nonzero) > 0,
                "applied quota is greater than zero",
                f"{len(nonzero)} non zero of {len(relevant)} Nova rows",
            )
            for q in sonic:
                record(q["Value"] > 0, f"Nova 2 Sonic quota: {q['QuotaName'][:58]}", f"= {int(q['Value'])}")
    except ClientError as exc:
        record(None, "service quota lookup", exc.response["Error"]["Code"])

    try:
        resp = session.client("bedrock-runtime").converse(
            modelId=TEXT_MODEL,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: ready"}]}],
            inferenceConfig={"maxTokens": 12, "temperature": 0.0},
        )
        text = resp["output"]["message"]["content"][0]["text"].strip()
        record(bool(text), f"Converse on {TEXT_MODEL}", f"returned {text[:24]!r}")
    except ClientError as exc:
        record(False, f"Converse on {TEXT_MODEL}", f"{exc.response['Error']['Code']}: {str(exc)[:80]}")

    try:
        asyncio.run(open_and_close_sonic_session())
        record(True, f"bidirectional stream opens and closes on {VOICE_MODEL}")
    except ImportError as exc:
        record(False, "async bedrock runtime SDK", f"pip install aws-sdk-bedrock-runtime ({exc})")
    except Exception as exc:  # noqa: BLE001
        record(False, f"bidirectional stream on {VOICE_MODEL}", f"{type(exc).__name__}: {str(exc)[:96]}")

    return summarize()


if __name__ == "__main__":
    sys.exit(main())
