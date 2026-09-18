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


@pytest.fixture(autouse=True)
def _clear_the_probe_cache():
    """The probe caches for five minutes, which is right for a polled health
    endpoint and wrong for a test: a monkeypatched session would never be
    consulted because the real answer is already held. Clearing it before and
    after keeps the cache honest in production and inert here."""
    main._SPEECH_CACHE.update({"at": 0.0, "result": None})
    yield
    main._SPEECH_CACHE.update({"at": 0.0, "result": None})


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
    assert "no credentials" in main._speech_probe()["reason"]


def test_speech_is_available_when_the_chain_resolves_something(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import boto3

    class Frozen:
        access_key = "AKIAEXAMPLE"

    class Creds:
        def get_frozen_credentials(self):
            return Frozen()

    class Sts:
        def get_caller_identity(self):
            return {"Account": "000000000000"}

    class Live:
        def get_credentials(self):
            return Creds()

        def client(self, *a, **k):
            return Sts()

    monkeypatch.setattr(boto3, "Session", lambda *a, **k: Live())
    assert main.speech_available() is True
    assert main._speech_probe()["account"] == "000000000000"


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


def test_the_voice_layer_names_a_profile_rather_than_taking_the_default() -> None:
    """The bug this prevents broke the centerpiece and was completely silent.

    PROFILE defaulted to None, so boto3 resolved the DEFAULT profile. On the
    build machine that profile is an `aws login` session whose credentials are
    present and EXPIRED. Every other part of the product was fine. The practice
    call failed, nothing said which profile had been tried, and the health check
    said speech was available because it had asked whether credentials existed
    rather than whether they worked.
    """
    import os

    from caliper.voice import sonic_session

    assert sonic_session.PROFILE, "a profile must be named, or the dead default is used"
    if not os.environ.get("AWS_PROFILE"):
        assert sonic_session.PROFILE == "caliper"


def test_availability_asks_whether_credentials_WORK_not_whether_they_exist() -> None:
    """Presence is not a check.

    On an expired login session `get_credentials()` returns an object and
    `get_frozen_credentials()` raises. Only the second question distinguishes a
    usable credential from a dead one, and the first version of this code asked
    the first.
    """
    import inspect

    source = inspect.getsource(main._speech_probe)
    assert "get_frozen_credentials" in source, (
        "the probe must freeze the credentials, which is what fails on an expired session"
    )
    assert "get_caller_identity" in source, (
        "the probe must ask STS who the credentials belong to, so a dead one cannot read as live"
    )
    # And it must resolve the SAME profile the voice layer will use, or it is
    # answering a question about a different account.
    assert "PROFILE" in source


def test_the_probe_reports_which_profile_and_account_it_used() -> None:
    """A boolean is not diagnosable. When this says no, it has to say why."""
    probe = main._speech_probe()
    assert set(probe) >= {"available", "profile", "account", "reason"}
    assert probe["reason"], "a probe result with no reason cannot be acted on"
