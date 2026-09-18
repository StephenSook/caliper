"""A dead model stream has to reach the browser.

The practice call is the demonstration's centerpiece and the product's whole
argument is about failures that announce themselves. This file guards the one
that did not.

`forward()` is the only thing that writes model output to the client. It ran as
a bare `create_task`, so its result was never observed: if the stream raised, on
a throttle, a validation error or a dropped HTTP/2 connection, the exception sat
on a task nobody read while the handler went on consuming microphone frames.
Nothing was sent, nothing was closed, and the client had already set connected
and started its timer off the ready event. Somebody watches a stopwatch run
against a dead stream.

Three tests, because the fix has three ways to be wrong: it can fail to surface
the error, it can surface it and then hang, or it can treat a NORMAL end of
stream as a fault and cry wolf on every completed call.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from caliper.api import main

# Captured before anything is monkeypatched. Binding the real class here is what
# stops a fake that constructs the real one from recursing into itself once the
# module attribute has been replaced.
REAL_SESSION = main.SonicSession


def _persona() -> dict:
    persona = main._load_persona()
    assert persona, "the persona must load, or these tests prove nothing"
    return persona


def _run_id() -> str:
    return main.store.latest() or main.store.create()


class _Base:
    """A stand in for SonicSession that never touches AWS."""

    def __init__(self, persona: dict) -> None:
        self.score_state = REAL_SESSION(persona=persona).score_state

    async def open(self) -> None:
        return None

    async def send_audio(self, data: bytes) -> None:
        return None

    async def close(self) -> None:
        return None


@pytest.fixture
def install(monkeypatch):
    persona = _persona()

    def _install(cls):
        monkeypatch.setattr(main, "SonicSession", lambda **kwargs: cls(persona))
        monkeypatch.setattr(main, "speech_available", lambda: True)

    return _install


def test_a_stream_that_dies_reaches_the_browser_as_an_error(install) -> None:
    class DiesImmediately(_Base):
        async def receive(self):
            raise RuntimeError("ValidationException: the model stream died")
            yield  # pragma: no cover  the generator needs a yield to be one

    install(DiesImmediately)
    with TestClient(main.app) as client, client.websocket_connect(f"/ws/practice/{_run_id()}") as ws:
        assert ws.receive_json()["type"] == "ready"
        second = ws.receive_json()
        assert second["type"] == "error", second
        assert "ValidationException" in second["detail"]


def test_the_socket_does_not_hang_after_the_stream_dies(install) -> None:
    """Surfacing the error and then holding the connection open would leave the
    person on stage looking at an error beside a running timer."""

    class DiesImmediately(_Base):
        async def receive(self):
            raise RuntimeError("boom")
            yield  # pragma: no cover

    install(DiesImmediately)
    with TestClient(main.app) as client, client.websocket_connect(f"/ws/practice/{_run_id()}") as ws:
        ws.receive_json()
        ws.receive_json()
        # Anything further must FAIL rather than block. A hang here is the bug
        # this file exists for, and it would surface as the suite never
        # finishing rather than as a failure, which is why it is asserted.
        closed = False
        try:
            for _ in range(5):
                ws.receive_json()
        except Exception:  # noqa: BLE001  any disconnect shape is acceptable
            closed = True
        assert closed, "the socket stayed open after the stream died"


def test_a_stream_that_simply_ends_is_not_reported_as_a_fault(install) -> None:
    """The other direction. A call that finishes normally must not produce an
    error, or every completed call cries wolf and the signal is worthless."""

    class EndsCleanly(_Base):
        async def receive(self):
            yield {"type": "transcript", "role": "USER", "content": "hello"}

    install(EndsCleanly)
    with TestClient(main.app) as client, client.websocket_connect(f"/ws/practice/{_run_id()}") as ws:
        assert ws.receive_json()["type"] == "ready"
        assert ws.receive_json()["type"] == "transcript"
        seen_error = False
        try:
            for _ in range(3):
                if ws.receive_json().get("type") == "error":
                    seen_error = True
        except Exception:
            pass
        assert not seen_error, "a normal end of stream was reported as a fault"
