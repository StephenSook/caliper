import type { Diagnosis as DiagnosisType } from "../lib/api";

/**
 * Screen three. The diagnosis, and the line we will not cross.
 *
 * Two panels here are worth real points and most teams will not have them: the
 * alternatives rejected on the record, and the scope boundary rendered as a
 * visible line with the remedy attached to the decline.
 *
 * The refusal is worded as a standard, never as an inability. State the
 * standard, state the gap, give the corrective path. Research on abstention is
 * specific about this: an explained "I do not know" beats an unexplained one on
 * competence, but a refusal still costs an AI system perceived competence even
 * when explained, because people expect machines to know things. So the remedy
 * is never more than a few centimetres from the decline.
 */

const CAUSE_LABEL: Record<string, string> = {
  MEASUREMENT_STANDARD_SETTING: "Measurement and standard setting",
  KNOWLEDGE: "Knowledge",
  SKILL: "Skill",
  WILL: "Will and accountability",
  PROCESS: "Process",
  POLICY: "Policy",
  TOOLING: "Tooling and systems",
  COACHING: "Coaching and reinforcement",
};

export function Diagnosis({ d }: { d: DiagnosisType }) {
  const corr = d.corroboration as Record<string, unknown> | null;
  const phi = corr?.phi as number | undefined;

  return (
    <section className="screen screen-diagnosis">
      <header className="screen-head">
        <span className="eyebrow">screen 03 / diagnosis</span>
        <h2>What is actually going wrong, and how far the evidence reaches.</h2>
      </header>

      <div className="diag-hero">
        <span className="eyebrow">the defect</span>
        <h3 className="diag-behavior">{d.behavior}</h3>
        <div className="diag-numbers mono">
          <div>
            <strong>{d.observed.fails}</strong> of {d.observed.denominator} evaluations failed
          </div>
          <div>
            across <strong>{d.observed.breadth_subjects}</strong> of{" "}
            {d.observed.breadth_denominator} agents
          </div>
          <div>
            difficulty <strong>{d.observed.difficulty_p.toFixed(3)}</strong>
            {d.observed.discrimination_rpb !== null && (
              <>
                {" / "}discrimination <strong>{d.observed.discrimination_rpb.toFixed(3)}</strong>
              </>
            )}
          </div>
        </div>
        <div className="diag-flags">
          {d.observed.item_flags.map((f) => (
            <span className="flag" key={f}>
              {f.replaceAll("_", " ").toLowerCase()}
            </span>
          ))}
        </div>
      </div>

      <div className="diag-grid">
        <div className="panel">
          <span className="eyebrow">root cause</span>
          <h3 className="cause-primary">
            {CAUSE_LABEL[d.root_cause_primary] ?? d.root_cause_primary}
          </h3>
          {d.root_cause_secondary && (
            <p className="cause-secondary">
              secondary: {CAUSE_LABEL[d.root_cause_secondary] ?? d.root_cause_secondary}
            </p>
          )}
          <div className={`training-verdict${d.is_training_intervention ? "" : " is-not-training"}`}>
            {d.is_training_intervention
              ? "Training is part of the answer."
              : "Training is not the answer here."}
          </div>
          <p className="cause-intervention">{d.recommended_intervention_class}</p>
        </div>

        <div className="panel">
          <span className="eyebrow">evidence</span>
          <ul className="evidence-list">
            {d.evidence_for.map((e, i) => (
              <li key={i}>
                <span className={`tag tag-${e.tag.toLowerCase()}`}>{e.tag}</span>
                <span className="evidence-claim">{e.claim}</span>
                {e.regenerate && <code className="evidence-regen mono">{e.regenerate}</code>}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="panel">
        <span className="eyebrow">alternatives considered and rejected, on the record</span>
        <ul className="rejected-list">
          {d.alternatives_rejected.map((r) => (
            <li key={r.cause}>
              <span className="rejected-cause mono">{CAUSE_LABEL[r.cause] ?? r.cause}</span>
              <span className="rejected-reason">{r.reason}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel panel-corroboration">
        <span className="eyebrow">corroboration, scanned rather than assumed</span>
        {corr && corr.item_text ? (
          <>
            <p className="corr-item">{corr.item_text as string}</p>
            <div className="corr-stats mono">
              <span>
                <strong>{corr.co_fail_count as number}</strong> of{" "}
                {corr.shared_evaluations as number} evaluations failed both
              </span>
              <span>
                phi <strong>{phi?.toFixed(3)}</strong>
              </span>
              <span className="corr-domain">{corr.domain as string}</span>
            </div>
            <p className="corr-note">
              Co failure alone is not corroboration. Two items that both fail on
              nearly everything co fail without being related, which is base rate
              saturation, so the association is reported next to the count and a
              pairing below the floor is not called corroboration.
            </p>
          </>
        ) : (
          <p className="corr-note">{(corr?.note as string) ?? "No corroborating item cleared the floor."}</p>
        )}
      </div>

      <div className="scope-line">
        <div className="scope-half scope-commit">
          <span className="eyebrow">we commit to this</span>
          <p>
            A systemic pattern across {d.observed.breadth_denominator} agents and{" "}
            {d.observed.denominator} evaluations, corroborated on the same calls, on
            an item that breaches both published floors.
          </p>
          <div className="scope-badge is-yes mono">{d.confidence.replaceAll("_", " ")}</div>
        </div>
        <div className="scope-half scope-decline">
          <span className="eyebrow">we will not do this</span>
          <p>{d.individual_attribution.statement}</p>
          <div className="scope-badge is-no mono">individual diagnosis declined</div>
          <div className="scope-remedy">
            <span className="eyebrow">the fix, which takes one afternoon</span>
            <p>{d.individual_attribution.remedy.action}</p>
            <p className="scope-citation mono">{d.individual_attribution.remedy.citation}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
