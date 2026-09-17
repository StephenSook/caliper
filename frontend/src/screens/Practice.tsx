import { useCallback, useEffect, useRef, useState } from "react";
import { AudioPlayer, MicCapture, microphoneBlockedReason } from "../lib/audio";
import { wsBase } from "../lib/api";

/**
 * Screen six. The practice call, and the proof.
 *
 * Live transcript on the left, the rewritten quality form on the right, filling
 * in as the conversation happens. Same instrument for the diagnosis, the
 * practice and the proof, which is the whole product in one screen.
 *
 * The form is scored server side from the transcript, in code. Nothing on this
 * screen decides anything; it renders what the engine returned.
 */

type Criterion = { id: string; state: "PASS" | "FAIL" | "PENDING"; evidence: string };
type Line = { role: string; text: string };

const LABEL: Record<string, string> = {
  VERIFY_IDENTITY: "Identity and authority verified before any plan detail",
  ALLOWED_VS_BILLED: "Billed amount versus allowed amount distinguished",
  CONFIRM_UNDERSTANDING: "Member restated what she owes, in her own words",
};

export function Practice({ runId, scoredItemId }: { runId: string; scoredItemId?: string }) {
  const [connected, setConnected] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [muted, setMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const ws = useRef<WebSocket | null>(null);
  const mic = useRef<MicCapture | null>(null);
  const player = useRef<AudioPlayer | null>(null);
  const transcriptEnd = useRef<HTMLDivElement>(null);

  const blocked = microphoneBlockedReason();

  useEffect(() => {
    if (!connected) return;
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [connected]);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "end" });
  }, [lines]);

  const stop = useCallback(async () => {
    try {
      ws.current?.send(JSON.stringify({ action: "stop" }));
    } catch {
      /* the socket may already be gone */
    }
    ws.current?.close();
    ws.current = null;
    await mic.current?.stop();
    mic.current = null;
    await player.current?.stop();
    player.current = null;
    setConnected(false);
  }, []);

  useEffect(() => () => void stop(), [stop]);

  async function start() {
    setError(null);
    setStarting(true);
    setLines([]);
    setElapsed(0);
    try {
      const token = localStorage.getItem("caliper_operator_token");
      const url =
        wsBase() +
        `/ws/practice/${runId}` +
        (token ? `?token=${encodeURIComponent(token)}` : "");

      const socket = new WebSocket(url);
      socket.binaryType = "arraybuffer";
      ws.current = socket;
      player.current = new AudioPlayer();

      socket.onmessage = (e) => {
        const event = JSON.parse(e.data as string);
        if (event.type === "transcript" && event.content?.trim()) {
          setLines((l) => [...l, { role: event.role, text: event.content }]);
        } else if (event.type === "audio") {
          void player.current?.play(event.content);
        } else if (event.type === "interrupted") {
          // Nova runs ahead of real time. Anything queued but unheard is stale.
          player.current?.clear();
        } else if (event.type === "score") {
          setCriteria(event.criteria);
        } else if (event.type === "ready") {
          setCriteria(event.criteria);
        } else if (event.type === "error") {
          setError(event.detail);
        }
      };
      socket.onerror = () => setError("The practice socket could not be opened.");
      socket.onclose = () => setConnected(false);

      await new Promise<void>((resolve, reject) => {
        socket.onopen = () => resolve();
        setTimeout(() => reject(new Error("timed out opening the practice socket")), 12000);
      });

      const capture = new MicCapture();
      await capture.start((pcm) => {
        if (socket.readyState === WebSocket.OPEN) socket.send(pcm);
      });
      mic.current = capture;
      setConnected(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      await stop();
    } finally {
      setStarting(false);
    }
  }

  const mmss = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
  const passed = criteria.filter((c) => c.state === "PASS").length;

  return (
    <section className="screen screen-practice">
      <header className="screen-head">
        <span className="eyebrow">screen 06 / practice and proof</span>
        <h2>Now talk to the member, and watch the same form fill in.</h2>
        <p className="lede">
          The question the audit rewrote is the question this call is scored on.
          Same instrument for the diagnosis, the practice and the proof. The
          member is synthetic; her plan mechanics are real and public.
        </p>
      </header>

      {blocked && (
        <div className="mic-blocked">
          <strong>Microphone unavailable.</strong> {blocked}
        </div>
      )}

      <div className="practice-grid">
        <div className="panel practice-call">
          <div className="pc-head">
            <div className="pc-who">
              <span className="pc-avatar" aria-hidden="true" />
              <div>
                <div className="pc-name">Member, synthetic</div>
                <div className="pc-driver mono">explanation of benefits dispute</div>
              </div>
            </div>
            <div className={`pc-timer mono${connected ? " is-live" : ""}`}>{mmss}</div>
          </div>

          <div className="pc-transcript">
            {lines.length === 0 && !connected && (
              <p className="pc-empty">
                Press start, verify who she is, explain the difference between what
                the hospital billed and what the plan allows, then ask her to say
                it back in her own words.
              </p>
            )}
            {lines.map((l, i) => (
              <div className={`pc-line is-${l.role.toLowerCase()}`} key={i}>
                <span className="pc-role mono">
                  {l.role === "USER" ? "you" : "member"}
                </span>
                <span className="pc-text">{l.text}</span>
              </div>
            ))}
            <div ref={transcriptEnd} />
          </div>

          <div className="pc-controls">
            {!connected ? (
              <button className="cta" onClick={start} disabled={starting || !!blocked}>
                {starting ? "Connecting" : "Start the practice call"}
              </button>
            ) : (
              <>
                <button
                  className="pc-btn"
                  onClick={() => {
                    const next = !muted;
                    setMuted(next);
                    mic.current?.setMuted(next);
                  }}
                >
                  {muted ? "Unmute" : "Mute"}
                </button>
                <button className="pc-btn is-end" onClick={stop}>
                  End call
                </button>
              </>
            )}
          </div>
          {error && <p className="error">{error}</p>}
        </div>

        <div className="panel practice-form">
          <div className="pf-head">
            <span className="eyebrow">the rewritten quality form</span>
            <span className="pf-count mono">
              {passed} of {criteria.length || 3}
            </span>
          </div>
          <ul className="pf-list">
            {(criteria.length
              ? criteria
              : Object.keys(LABEL).map((id) => ({ id, state: "PENDING", evidence: "" }) as Criterion)
            ).map((c) => (
              <li className={`pf-row is-${c.state.toLowerCase()}`} key={c.id}>
                <span className="pf-text">{LABEL[c.id] ?? c.id}</span>
                <span className="pf-state mono">{c.state}</span>
                {c.evidence && <span className="pf-evidence">{c.evidence}</span>}
              </li>
            ))}
          </ul>
          {scoredItemId && (
            <p className="pf-scored mono">
              scored on <code>{scoredItemId}</code>, the item the diagnosis produced
            </p>
          )}
          <p className="pf-note">
            Scored in code from the transcript, not by the speech model. The model
            plays the member and never decides whether a criterion was met.
          </p>
        </div>
      </div>
    </section>
  );
}
