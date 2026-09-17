/**
 * Screen five. What we build, and the chain proving every piece traces back.
 *
 * Twenty percent of the score is whether the training is traceable to the
 * diagnosed root cause rather than merely on topic, so the ID chain is drawn
 * rather than described and the coverage number is live.
 *
 * The most important check in the system is that the practice simulation scores
 * the SAME item the diagnosis produced. That is the failure ResultsCX names in
 * their own process document: a technically excellent simulation that scores the
 * wrong behaviour, where nobody finds out until the quality data looks identical.
 */

interface Bundle {
  rewritten_item: {
    item_id: string;
    old_text: string;
    new_text: string;
    scoring: string;
    why_the_old_item_failed: string[];
    provenance: Record<string, unknown>;
  };
  objectives: {
    objective_id: string;
    condition: string;
    behavior: string;
    criterion: string;
    bloom_level: string;
  }[];
  activities: {
    activity_id: string;
    title: string;
    activity_type: string;
    duration_minutes: number;
    learner_instructions: string;
    debrief_questions: string[];
  }[];
  simulations: { simulation_id: string; scored_item_id: string; call_driver: string }[];
  metrics: {
    metric_id: string;
    baseline_rate: number;
    target_rate: number;
    required_n_per_arm: number;
    method: string;
    regression_to_mean: Record<string, string>;
    design: string;
  }[];
  outcome_claim: { verdict: string; statement: string };
}

interface Alignment {
  passed: boolean;
  coverage: number;
  total_elements: number;
  failures: { code: string; element_id: string; detail: string }[];
  checks_run: string[];
  kc_gate: { passed: number; total: number; coverage: number; checks: string[] };
}

export function Intervention({
  bundle,
  alignment,
  diagnosisId,
}: {
  bundle: Bundle;
  alignment: Alignment;
  diagnosisId: string;
}) {
  const item = bundle.rewritten_item;
  const obj = bundle.objectives[0];
  const act = bundle.activities[0];
  const sim = bundle.simulations[0];
  const metric = bundle.metrics[0];

  const chain = [
    { id: diagnosisId, label: "diagnosis" },
    { id: obj?.objective_id, label: "objective" },
    { id: act?.activity_id, label: "activity" },
    { id: sim?.simulation_id, label: "practice" },
    { id: metric?.metric_id, label: "measure" },
  ].filter((n) => n.id);

  return (
    <section className="screen screen-intervention">
      <header className="screen-head">
        <span className="eyebrow">screen 05 / intervention</span>
        <h2>The fix, and the chain that proves every piece traces back.</h2>
      </header>

      <div className="panel rewrite">
        <span className="eyebrow">the question, rewritten</span>
        <div className="rewrite-grid">
          <div className="rw-old">
            <span className="rw-tag mono">before</span>
            <p>{item.old_text}</p>
            <span className="rw-judgement">scored on reviewer judgement</span>
          </div>
          <div className="rw-arrow" aria-hidden="true">
            &rarr;
          </div>
          <div className="rw-new">
            <span className="rw-tag mono">after</span>
            <p>{item.new_text}</p>
            <span className="rw-judgement is-observable">{item.scoring}</span>
          </div>
        </div>
        <details className="rw-why">
          <summary>Why the old question could not work</summary>
          <ul>
            {item.why_the_old_item_failed.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
          <p className="rw-provenance">
            {item.provenance.honesty_note as string}
          </p>
        </details>
      </div>

      {obj && (
        <div className="panel objective">
          <span className="eyebrow">the objective, in three parts</span>
          <dl className="obj-parts">
            <div>
              <dt>condition</dt>
              <dd>{obj.condition}</dd>
            </div>
            <div>
              <dt>behaviour</dt>
              <dd>{obj.behavior}</dd>
            </div>
            <div>
              <dt>criterion</dt>
              <dd>{obj.criterion}</dd>
            </div>
          </dl>
          <p className="obj-note mono">
            observable / {obj.bloom_level.toLowerCase()} / the defect we diagnosed was an
            item with no criterion, so generating one without a criterion would repeat it
          </p>
        </div>
      )}

      <div className="panel alignment">
        <div className="panel-head">
          <h3>Alignment</h3>
          <div className={`align-coverage mono${alignment.passed ? " is-pass" : " is-fail"}`}>
            coverage {(alignment.coverage * 100).toFixed(0)}%
            <span className="ac-sub">
              {alignment.total_elements} elements / {alignment.checks_run.length} checks
            </span>
          </div>
        </div>

        <div className="chain">
          {chain.map((n, i) => (
            <div className="chain-node" key={n.id}>
              <span className="cn-id mono">{n.id}</span>
              <span className="cn-label">{n.label}</span>
              {i < chain.length - 1 && <span className="cn-link" aria-hidden="true" />}
            </div>
          ))}
        </div>

        {alignment.failures.length > 0 ? (
          <ul className="align-failures">
            {alignment.failures.map((f, i) => (
              <li key={i}>
                <span className="af-code mono">{f.code}</span> {f.detail}
              </li>
            ))}
          </ul>
        ) : (
          <p className="align-ok">
            Every objective, activity, practice scenario and measure traces to the
            approved diagnosis. The practice call is scored on{" "}
            <code className="mono">{sim?.scored_item_id}</code>, which is the item the
            diagnosis produced.
          </p>
        )}

        <div className="kc-gate">
          <span className="eyebrow">
            the sponsor's own knowledge check gate, run as code
          </span>
          <div className="kc-row mono">
            {alignment.kc_gate.passed} of {alignment.kc_gate.total} pass all{" "}
            {alignment.kc_gate.checks.length} checks
          </div>
          <div className="kc-checks">
            {alignment.kc_gate.checks.map((c) => (
              <span className="kc-check mono" key={c}>
                {c.replaceAll("_", " ")}
              </span>
            ))}
          </div>
        </div>
      </div>

      {act && (
        <div className="panel drill">
          <span className="eyebrow">the drill</span>
          <h3>{act.title}</h3>
          <p className="drill-meta mono">
            {act.activity_type} / {act.duration_minutes} minutes
          </p>
          <p>{act.learner_instructions}</p>
          <ul className="drill-debrief">
            {act.debrief_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      {metric && (
        <div className="panel outcome">
          <span className="eyebrow">how we would know it worked</span>
          <div className="outcome-numbers mono">
            <div>
              <span className="on-label">baseline</span>
              <strong>{(metric.baseline_rate * 100).toFixed(1)}%</strong>
            </div>
            <div>
              <span className="on-label">target</span>
              <strong>{(metric.target_rate * 100).toFixed(0)}%</strong>
            </div>
            <div>
              <span className="on-label">calls per arm needed</span>
              <strong>{metric.required_n_per_arm}</strong>
            </div>
          </div>
          <p className="outcome-method mono">{metric.method}</p>
          <div className={`outcome-claim is-${bundle.outcome_claim.verdict.toLowerCase()}`}>
            {bundle.outcome_claim.statement}
          </div>
          <p className="outcome-rtm">
            <strong>Regression to the mean, {metric.regression_to_mean.risk}.</strong>{" "}
            {metric.regression_to_mean.explanation} {metric.regression_to_mean.required_design}
          </p>
        </div>
      )}
    </section>
  );
}
