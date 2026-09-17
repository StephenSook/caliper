import { useEffect, useRef, useState } from "react";
import Lenis from "lenis";
import { Audit } from "./screens/Audit";
import { api, type RunResponse } from "./lib/api";
import "./styles/tokens.css";
import "./styles/app.css";

export default function App() {
  const [run, setRun] = useState<RunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [domain, setDomain] = useState("member_experience");
  const lenis = useRef<Lenis | null>(null);

  useEffect(() => {
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
  }, []);

  async function start() {
    setLoading(true);
    setError(null);
    try {
      setRun(await api.createRun());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <header className="masthead">
        <div className="mh-mark">
          <span className="mh-name">CALIPER</span>
          <span className="mh-tag">Before you measure the agent, check the caliper.</span>
        </div>
        {run && <span className="mh-run mono">{run.run_id}</span>}
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
          <button className="cta" onClick={start} disabled={loading}>
            {loading ? "Auditing the instrument" : "Run the audit"}
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
                <div className="big mono">
                  {Object.values(run.redactions).reduce((a, b) => a + b, 0)}
                </div>
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
        </>
      )}
    </main>
  );
}
