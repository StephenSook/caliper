/**
 * Screen seven. What being wrong costs, in the sponsor's own numbers.
 *
 * The case study asks for savings on labor and cost, USA against Mexico or the
 * Philippines. The obvious way to answer that is one large annual figure, and
 * the obvious way is wrong here for the same reason the whole product exists:
 * the number that makes the slide is the one nobody checked.
 *
 * So this screen is built around the thing that determines the answer rather
 * than around the answer. The baseline is a control, not a footnote. Change it
 * and every figure moves, which is the point: a savings number that does not say
 * which baseline it used is not a savings number.
 *
 * Nothing here is typed into the component. Every value arrives from
 * /api/impact, which is computed from constants transcribed out of the report
 * and asserted in tests against figures the report itself prints.
 */

import { useCallback, useEffect, useState } from "react";
import { api, type ImpactReport } from "../lib/api";

const PROVENANCE_LABEL: Record<string, string> = {
  MEASURED: "measured",
  TEAM_ESTIMATE: "team estimate",
  INDUSTRY_BENCHMARK: "industry benchmark",
  NOT_VERIFIED: "not verified",
};

const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

export function Impact() {
  const [hours, setHours] = useState(2);
  const [baseline, setBaseline] = useState("weighted_actual");
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .impact(hours, baseline)
      .then((r) => {
        setReport(r);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [hours, baseline]);

  useEffect(load, [load]);

  if (error) return <p className="error">{error}</p>;
  if (!report) return null;

  const spread = report.baseline_choice_matters;

  return (
    <section className="screen screen-impact">
      <span className="eyebrow">screen 07 / what being wrong costs</span>
      <h2 className="hero-sm">
        The savings number depends entirely on a choice nobody was making out
        loud.
      </h2>
      <p className="lede">
        The supplied labor report gives two build ratios that differ by{" "}
        <b>{spread.ratio} times</b>. They are not contradictory. They answer
        different questions, and a savings figure that does not say which one it
        used is not a savings figure. So it is a control here, not a footnote.
      </p>

      <div className="impact-controls">
        <label>
          <span className="eyebrow">baseline</span>
          <select value={baseline} onChange={(e) => setBaseline(e.target.value)}>
            {report.baselines_available.map((b) => (
              <option key={b.key} value={b.key}>
                {b.label} ({b.hours_per_curriculum_hour} hrs, {PROVENANCE_LABEL[b.provenance] ?? b.provenance})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="eyebrow">hours of finished curriculum</span>
          <input
            type="number"
            min={0.25}
            max={40}
            step={0.25}
            value={hours}
            onChange={(e) => setHours(Math.max(0.25, Number(e.target.value) || 0.25))}
          />
        </label>
      </div>

      <p className="impact-scope mono">
        {report.baseline.label}: {report.baseline.hours_per_curriculum_hour} build hours per
        curriculum hour, {report.baseline.scope}.{" "}
        <span className={`prov prov-${report.baseline.provenance.toLowerCase()}`}>
          {PROVENANCE_LABEL[report.baseline.provenance] ?? report.baseline.provenance}
        </span>
      </p>
      {report.baseline.caveat && <p className="impact-caveat">{report.baseline.caveat}</p>}

      <table className="impact-table">
        <thead>
          <tr>
            <th>Geography</th>
            <th>Fully loaded hourly</th>
            <th>Per curriculum hour</th>
            <th>This intervention</th>
            <th>One avoided rework cycle</th>
          </tr>
        </thead>
        <tbody>
          {report.rows.map((r) => (
            <tr key={r.key} className={r.key === "usa" ? "is-usa" : undefined}>
              <td>
                {r.geography}
                <span className="dim"> {r.statutory_note}</span>
              </td>
              <td className="mono">{money(r.fully_loaded_hourly)}</td>
              <td className="mono">{money(r.cost_per_curriculum_hour)}</td>
              <td className="mono">{money(r.cost_for_this_intervention)}</td>
              <td className="mono impact-headline">{money(r.rework_cycle_cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="impact-note">
        USA labor runs{" "}
        <b>{report.usa_multiple_of.philippines} times</b> the Philippines and{" "}
        <b>{report.usa_multiple_of.mexico} times</b> Mexico, fully loaded, for the
        same instructional design role.
      </p>

      <div className="impact-headline-card">
        <span className="eyebrow">the figure we can stand behind</span>
        <p>{report.rework_baseline.why}</p>
        <p className="dim">
          Priced at {report.rework_baseline.hours_per_curriculum_hour} build hours per curriculum
          hour, from the team's own tracked revision time rather than from a benchmark.
        </p>
      </div>

      <div className="impact-refusal">
        <span className="eyebrow">what we will not claim</span>
        <p>{report.annual_savings_claim.reason}</p>
      </div>

      <p className="impact-caveat">{report.rate_caveat}</p>
    </section>
  );
}
