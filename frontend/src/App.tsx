import { useCallback, useEffect, useRef, useState } from "react";
import Lenis from "lenis";
import { Audit } from "./screens/Audit";
import { Diagnosis } from "./screens/Diagnosis";
import { Gate } from "./screens/Gate";
import { Intervention } from "./screens/Intervention";
import { Practice } from "./screens/Practice";
import { api, workbookUrl, type RunResponse, type Transition } from "./lib/api";
import "./styles/tokens.css";
import "./styles/app.css";

type DecisionResult = { decided_by: string; decided_by_verified: boolean; note: string };

export default function App() {
  const [run, setRun] = useState<RunResponse | null>(null);
  const [state, setState] = useState<string>("");
  const [ledger, setLedger] = useState<Transition[]>([]);
  const [decision, setDecision] = useState<DecisionResult | null>(null);
  const [bundle, setBundle] = useState<Record<string, unknown> | null>(null);
  const [alignment, setAlignment] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [domain, setDomain] = useState("member_experience");
  const lenis = useRef<Lenis | null>(null);

  const still = new URLSearchParams(window.location.search).has("still");

  /*
    Handset mode.

    A practice call is a headset activity in real life, so the phone is the
    correct form factor for it rather than a second copy of the product. Reached
    by /practice or /?screen=practice, this renders the call and nothing else,
    and attaches itself to whatever run the laptop already started so nobody has
    to type a run id at a judging table.

    The run id is resolved from the server, never guessed, and when there is no
    run the screen says so plainly instead of opening a socket that cannot work.
  */
  const params = new URLSearchParams(window.location.search);
  const handset =
    params.get("screen") === "practice" || window.location.pathname === "/practice";
  const [handsetRun, setHandsetRun] = useState<string | null>(params.get("run"));
  const [handsetError, setHandsetError] = useState<string | null>(null);

  useEffect(() => {
    if (!handset || handsetRun) return;
    let cancelled = false;
    let timer = 0;

    /*
      Keep looking rather than failing once.

      The intended shape of the demo is two devices on one run: the laptop runs
      the audit and a human approves the diagnosis, and the phone is the handset
      that takes the drill. So the phone polls, and the moment a run exists on
      this host it attaches to it with nobody touching the phone. An empty state
      that needs a reload is an empty state somebody is looking at when it
      matters.
    */
    const look = () => {
      api
        .latestRun()
        .then((r) => {
          if (cancelled) return;
          if (r.latest_run_id) {
            setHandsetRun(r.latest_run_id);
            return;
          }
          setHandsetError("");
          timer = window.setTimeout(look, 3000);
        })
        .catch((e) => {
          if (cancelled) return;
          setHandsetError(String(e));
          timer = window.setTimeout(look, 5000);
        });
    };
    look();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [handset, handsetRun]);

  const startFromHandset = useCallback(async () => {
    setBusy(true);
    setHandsetError(null);
    try {
      const r = await api.createRun();
      setHandsetRun(r.run_id);
    } catch (e) {
      setHandsetError(String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (still) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const l = new Lenis({ duration: 1.1, easing: (t) => 1 - Math.pow(1 - t, 4) });
    lenis.current = l;
    let id = 0;
    const raf = (time: number) => {
      l.raf(time);
      id = requestAnimationFrame(raf);
    };
    id = requestAnimationFrame(raf);
    return () => {
      cancelAnimationFrame(id);
      l.destroy();
    };
  }, [still]);

  const refreshLedger = useCallback(async (id: string) => {
    try {
      setLedger((await api.ledger(id)).transitions);
    } catch {
      /* the ledger is a display, never a gate; a failure here must not stop the run */
    }
  }, []);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.createRun();
      setRun(r);
      setState(r.state);
      await refreshLedger(r.run_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function decide(action: string, actor: string) {
    if (!run) return;
    setBusy(true);
    setError(null);
    try {
      const d = await api.decide(run.run_id, action, actor);
      setState(d.state);
      setDecision({
        decided_by: d.decided_by,
        decided_by_verified: d.decided_by_verified,
        note: d.note,
      });
      await refreshLedger(run.run_id);
      if (action === "APPROVE" || action === "EDIT") {
        const g = await api.generate(run.run_id);
        setState(g.state);
        setBundle(g.bundle);
        setAlignment(g.alignment);
        await refreshLedger(run.run_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const redacted = run ? Object.values(run.redactions).reduce((a, b) => a + b, 0) : 0;

  if (handset) {
    return (
      <main className="app is-handset">
        <header className="masthead">
          <div className="mh-mark">
            <span className="mh-name">CALIPER</span>
            <span className="mh-tag">Practice call</span>
          </div>
          {handsetRun && <span className="mh-run mono">{handsetRun}</span>}
        </header>
        {handsetRun ? (
          <Practice runId={handsetRun} />
        ) : (
          <section className="screen">
            <span className="eyebrow">waiting for a run</span>
            <p className="lede">
              This phone is the handset. It takes the drill on whatever run this
              host is working on, so the laptop and the phone are one run, one
              instrument and one audit trail.
            </p>
            <p className="intake-note">
              Nothing to do here. Start the audit on the laptop and this screen
              picks it up on its own, usually within a few seconds.
            </p>
            <button className="cta" onClick={startFromHandset} disabled={busy}>
              {busy ? "Auditing the instrument" : "Or start the audit from this phone"}
            </button>
            {handsetError ? <p className="error">{handsetError}</p> : null}
          </section>
        )}
      </main>
    );
  }

  return (
    <main className="app">
      <header className="masthead">
        <div className="mh-mark">
          <span className="mh-name">CALIPER</span>
          <span className="mh-tag">Before you measure the agent, check the caliper.</span>
        </div>
        {run && (
          <span className="mh-run mono">
            {run.run_id} <span className="mh-state">{state}</span>
          </span>
        )}
      </header>

      {!run && (
        <section className="screen screen-intake">
          <span className="eyebrow">screen 01 / intake</span>
          <h1 className="hero">
            Everybody else grades the workers.
            <em> We grade the test.</em>
          </h1>
          <p className="lede">
            A quality form decides who gets coached, who goes on a performance
            plan, and sometimes who keeps a job. Nobody has checked whether that
            form can measure anything. We are going to, before we diagnose a
            single person from it.
          </p>
          <button className="cta" onClick={start} disabled={busy}>
            {busy ? "Auditing the instrument" : "Run the audit"}
          </button>
          {error && <p className="error">{error}</p>}
          <p className="intake-note mono">
            Plain arithmetic runs first, in code, before any model is called.
          </p>
        </section>
      )}

      {run && (
        <>
          <section className="screen screen-redaction">
            <span className="eyebrow">screen 01 / intake complete</span>
            <div className="redaction-grid">
              <div>
                <div className="big mono">{redacted}</div>
                <p>
                  identifiers found and redacted from the supplied material before
                  anything was analysed
                </p>
              </div>
              <div>
                <div className="big mono">0</div>
                <p>models called so far. Every number on the next screen is arithmetic.</p>
              </div>
            </div>
          </section>

          <Audit audit={run.audit} domain={domain} onDomain={setDomain} />
          <Diagnosis d={run.diagnosis} />
          <Gate
            diagnosis={run.diagnosis}
            actions={(run.gate.actions as string[]) ?? []}
            runId={run.run_id}
            state={state}
            ledger={ledger}
            onDecide={decide}
            pending={busy}
            decision={decision}
          />
          {error && <p className="error screen-error">{error}</p>}
          {bundle && alignment && (
            <Intervention
              bundle={bundle as never}
              alignment={alignment as never}
              diagnosisId={run.diagnosis.diagnosis_id}
              workbookHref={workbookUrl(run.run_id)}
            />
          )}
          {bundle && (
            <Practice
              runId={run.run_id}
              scoredItemId={
                (bundle.rewritten_item as { item_id?: string } | undefined)?.item_id
              }
            />
          )}
        </>
      )}
    </main>
  );
}
