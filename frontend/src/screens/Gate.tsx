import { useState } from "react";
import type { Diagnosis, Transition } from "../lib/api";

/**
 * Screen four. The human gate.
 *
 * Everything the reviewer needs is on this one screen, because sending them
 * somewhere else to decide is the reprompting the rubric penalises.
 *
 * Four actions rather than two, because "approve or not" is not how a reviewer
 * thinks. And the screen states plainly whether the approver's identity could be
 * PROVEN: a product that refuses to over assert about a workforce has no business
 * over asserting about its own audit trail.
 */

const ACTION_COPY: Record<string, { label: string; detail: string }> = {
  APPROVE: { label: "Approve", detail: "The diagnosis is right. Continue the run." },
  EDIT: { label: "Edit", detail: "Mostly right. Change it, then continue." },
  REJECT: { label: "Reject", detail: "Wrong. Nothing downstream should be built." },
  REQUEST_MORE_EVIDENCE: {
    label: "Request more evidence",
    detail: "Not yet. Send it back for another look.",
  },
};

export function Gate({
  diagnosis,
  actions,
  runId,
  state,
  ledger,
  onDecide,
  pending,
  decision,
}: {
  diagnosis: Diagnosis;
  actions: string[];
  runId: string;
  state: string;
  ledger: Transition[];
  onDecide: (decision: string, actor: string) => void;
  pending: boolean;
  decision: { decided_by: string; decided_by_verified: boolean; note: string } | null;
}) {
  const [actor, setActor] = useState("");

  return (
    <section className="screen screen-gate">
      <header className="screen-head">
        <span className="eyebrow">screen 04 / human validation</span>
        <h2>Nothing is generated until a person signs off.</h2>
        <p className="lede">
          This is a gate in the workflow, not a disclaimer under it. The approved
          decision becomes the run state, so the same run continues from here.
          Nothing is re entered.
        </p>
      </header>

      <div className="gate-card">
        <div className="gate-summary">
          <div className="gs-row">
            <span className="eyebrow">proposed cause</span>
            <strong>{diagnosis.root_cause_primary.replaceAll("_", " ").toLowerCase()}</strong>
          </div>
          <div className="gs-row">
            <span className="eyebrow">confidence</span>
            <strong>{diagnosis.confidence.replaceAll("_", " ").toLowerCase()}</strong>
          </div>
          <div className="gs-row">
            <span className="eyebrow">is training the answer</span>
            <strong>{diagnosis.is_training_intervention ? "partly" : "no"}</strong>
          </div>
          <div className="gs-row">
            <span className="eyebrow">individual diagnosis</span>
            <strong>{diagnosis.individual_attribution.licensed ? "licensed" : "declined"}</strong>
          </div>
          <div className="gs-row">
            <span className="eyebrow">alternatives rejected</span>
            <strong>{diagnosis.alternatives_rejected.length} on the record</strong>
          </div>
        </div>

        {!decision && (
          <>
            <label className="gate-actor">
              <span className="eyebrow">who is deciding</span>
              <input
                value={actor}
                onChange={(e) => setActor(e.target.value)}
                placeholder="name or role"
                aria-label="who is deciding"
              />
            </label>
            <div className="gate-actions">
              {actions.map((a) => (
                <button
                  key={a}
                  className={`gate-btn${a === "APPROVE" ? " is-primary" : ""}`}
                  disabled={pending || !actor.trim()}
                  onClick={() => onDecide(a, actor.trim())}
                >
                  <span className="gb-label">{ACTION_COPY[a]?.label ?? a}</span>
                  <span className="gb-detail">{ACTION_COPY[a]?.detail}</span>
                </button>
              ))}
            </div>
          </>
        )}

        {decision && (
          <div className="gate-decided">
            <div className="gd-headline mono">
              <span>recorded: {decision.decided_by}</span>
              <span className={`gd-verified${decision.decided_by_verified ? " is-verified" : ""}`}>
                {decision.decided_by_verified ? "identity proven" : "identity not proven"}
              </span>
            </div>
            <p className="gd-note">{decision.note}</p>
          </div>
        )}
      </div>

      <div className="ledger">
        <div className="ledger-head">
          <span className="eyebrow">run ledger</span>
          <span className="mono">
            {runId} / {state}
          </span>
        </div>
        <ol className="ledger-list mono">
          {ledger.map((t) => (
            <li key={t.seq}>
              <span className="lg-seq">{String(t.seq).padStart(2, "0")}</span>
              <span className="lg-state">{t.to_state}</span>
              <span className="lg-actor">
                {t.actor}
                {!t.actor_verified && t.actor !== "system" && (
                  <span className="lg-unverified"> unverified</span>
                )}
              </span>
              <span className="lg-at">{t.at.slice(11, 19)}</span>
            </li>
          ))}
        </ol>
        <p className="ledger-note">
          Every transition is written to disk before it is acted on. Kill this
          process and start it again and the run resumes from the approved state.
        </p>
      </div>
    </section>
  );
}
