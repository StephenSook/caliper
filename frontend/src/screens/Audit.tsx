import { DesignGraph } from "../components/DesignGraph";
import { ItemPlot } from "../components/ItemPlot";
import { QuantileDotplot } from "../components/QuantileDotplot";
import type { Audit as AuditType } from "../lib/api";

/**
 * Screen two. The screen nobody else has.
 *
 * Three panels, each with a plain language caption, because ten percent of the
 * score is whether a non technical learning designer can read this and act on it
 * without knowing what a p value is.
 */
export function Audit({ audit, domain, onDomain }: {
  audit: AuditType;
  domain: string;
  onDomain: (d: string) => void;
}) {
  const d = audit.domains[domain];
  const names: Record<string, string> = {
    member_experience: "Member Experience",
    business_process: "Business Process",
    compliance: "Compliance",
  };

  return (
    <section className="screen screen-audit">
      <header className="screen-head">
        <span className="eyebrow">screen 02 / instrument audit</span>
        <h2>We checked whether the questions can measure anything.</h2>
        <p className="lede">
          Treat the quality form the way you would treat an exam. A question
          almost everyone passes, or almost everyone fails, cannot tell a strong
          performer from a weak one. There is a published rule for this and it is
          about a century old.
        </p>
      </header>

      <nav className="domain-tabs" aria-label="quality form">
        {Object.keys(audit.domains).map((key) => {
          const dd = audit.domains[key];
          const bad = dd.summary.items_outside_difficulty_band;
          return (
            <button
              key={key}
              className={`domain-tab${key === domain ? " is-active" : ""}`}
              onClick={() => onDomain(key)}
            >
              <span className="dt-name">{names[key] ?? key}</span>
              <span className="dt-stat mono">
                {bad} of {dd.n_items} unusable
              </span>
            </button>
          );
        })}
      </nav>

      <div className="panel">
        <div className="panel-head">
          <h3>Every question, plotted against the usable range</h3>
          <div className="panel-stat mono">
            <strong>{d.summary.items_outside_difficulty_band}</strong> of {d.n_items} outside it
            {d.summary.items_with_zero_variance > 0 && (
              <>
                {" / "}
                <strong>{d.summary.items_with_zero_variance}</strong> have never
                distinguished anyone
              </>
            )}
          </div>
        </div>
        <ItemPlot items={d.items} />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>How reliable the form is, shown honestly</h3>
          <div className="panel-stat mono">
            computed from {d.n_evaluations} evaluations
          </div>
        </div>
        <QuantileDotplot reliability={d.reliability} />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>Can we tell a harsh evaluator from a weak agent?</h3>
          <div className="panel-stat mono">{audit.connectivity.verdict}</div>
        </div>
        <DesignGraph connectivity={audit.connectivity} />
      </div>

      <aside className="cross-instrument">
        <span className="eyebrow">across all three forms</span>
        <p>{audit.cross_instrument.statement}</p>
        <div className="ci-grid mono">
          {Object.entries(audit.cross_instrument.reliability_ci_lower_bounds).map(([k, v]) => (
            <div key={k} className="ci-cell">
              <span className="ci-name">{names[k] ?? k}</span>
              <span className={`ci-value${v <= 0 ? " is-bad" : ""}`}>
                lower bound {v.toFixed(3)}
              </span>
            </div>
          ))}
        </div>
      </aside>

      <p className="field-note">
        The field behind this page is not decoration. It is one point per scored
        item in the supplied export, laid out as the lattice a working instrument
        would produce, and displaced by exactly the amount this one is
        unreliable. It was a clean grid until the audit ran.
      </p>

      <footer className="regen mono">
        Regenerate every figure on this screen: <code>{d.regenerate}</code>
      </footer>
    </section>
  );
}
