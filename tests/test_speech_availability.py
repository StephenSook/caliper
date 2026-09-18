"""An instance that cannot take a call must say so, before anyone tries.

The deterministic half of CALIPER needs no credentials at all, which is exactly
what lets the audit, the diagnosis, the workbook and the golden cases run on a
public host holding nothing worth leaking. A spoken call needs a speech model and
therefore credentials, so that same host cannot take one.

Without the refusal these tests protect, the observed behaviour on the deployed
instance was: the socket opened, the call screen reported connected, the timer
started, and nothing ever arrived. No audio, no transcript, no error, no close.
Someone watches a stopwatch until they give up.

A silence is the only failure mode that carries no diagnosis with it, which is
what makes it worth a test rather than a comment.
"""

from __future__ import annotations

import pytest

from caliper.api import main


def test_health_reports_whether_a_call_is_possible(monkeypatch: pytest.MonkeyPatch) -> None:
    """The interface reads this to decide whether to offer the button at all."""
    monkeypatch.setattr(main, "speech_available", lambda: False)
    assert main.health()["speech_available"] is False

    monkeypatch.setattr(main, "speech_available", lambda: True)
    assert main.health()["speech_available"] is True


def test_speech_is_unavailable_when_the_chain_resolves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No credentials means no call, and the check says so rather than guessing."""
    import boto3

    class NoCredentials:
        def get_credentials(self):
            return None

    monkeypatch.setattr(boto3, "Session", lambda *a, **k: NoCredentials())
    assert main.speech_available() is False


def test_speech_is_available_when_the_chain_resolves_something(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import boto3

    class SomeCredentials:
        def get_credentials(self):
            return object()

    monkeypatch.setattr(boto3, "Session", lambda *a, **k: SomeCredentials())
    assert main.speech_available() is True


def test_a_broken_sdk_reads_as_unavailable_rather_than_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From the point of view of the person holding the phone, a broken SDK and
    absent credentials are the same fact: no call. Raising here would replace a
    clear sentence with a stack trace."""
    import boto3

    def explode(*a, **k):
        raise RuntimeError("botocore is unhappy")

    monkeypatch.setattr(boto3, "Session", explode)
    assert main.speech_available() is False


def test_the_refusal_names_a_reason_a_reader_can_act_on() -> None:
    """Guards the copy, not just the branch.

    The refusal is the only thing the person sees, so it has to say which half of
    the product is missing and what to do. A bare "unavailable" would be a
    shorter silence.
    """
    import inspect

    source = inspect.getsource(main.practice)
    assert '"type": "unavailable"' in source
    assert '"reason": "no_speech_credentials"' in source

    # The branch must come BEFORE the session is opened, or the silence happens
    # anyway and the message arrives after it.
    assert source.index("no_speech_credentials") < source.index("SonicSession(")
