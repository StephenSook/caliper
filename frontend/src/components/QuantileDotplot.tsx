import { useEffect, useRef } from "react";
import gsap from "gsap";
import type { Reliability } from "../lib/api";

/**
 * The reliability estimate drawn as fifty outcomes rather than a whisker.
 *
 * A non expert reads twenty dots below a line as a probability. They read an
 * error bar as a boundary, which is the wrong intuition and the reason this is
 * not an error bar (Fernandes, Walls, Munson, Hullman and Kay, CHI 2018).
 *
 * The dots arrive from the engine. Nothing here computes a quantile.
 */

// Range chosen so the dots use the full width rather than huddling in the
// middle, and so zero is visible: an interval that reaches zero is the finding.
const LO = -0.2;
const HI = 0.95;
const COLUMNS = 19; // fifty dots over nineteen bins stack about three high
const pos = (v: number) => ((v - LO) / (HI - LO)) * 100;

export function QuantileDotplot({ reliability }: { reliability: Reliability }) {
  const root = useRef<HTMLDivElement>(null);
  const { quantiles, thresholds, point_estimate, ci_low, ci_high } = reliability;

  useEffect(() => {
    if (!root.current) return;
    if (new URLSearchParams(window.location.search).has("still")) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = gsap.context(() => {
      gsap.from(".qd-dot", {
        y: -14,
        opacity: 0,
        duration: 0.8,
        stagger: 0.012,
        ease: "expo.out",
      });
    }, root);
    return () => ctx.revert();
  }, [quantiles]);

  // Stack dots into columns so the SHAPE of the distribution is visible. A row
  // of evenly spread dots is just an error bar with extra steps.
  const buckets: number[][] = Array.from({ length: COLUMNS }, () => []);
  quantiles.forEach((q) => {
    const idx = Math.min(COLUMNS - 1, Math.max(0, Math.floor(((q - LO) / (HI - LO)) * COLUMNS)));
    buckets[idx].push(q);
  });
  const research = thresholds.research ?? 0.7;
  const belowResearch = quantiles.filter((q) => q < research).length;

  return (
    <div className="qdp" ref={root}>
      <div className="qdp-plot">
        {[
          { v: 0, label: "zero" },
          { v: thresholds.cms_star_floor ?? 0.6, label: "CMS floor 0.60" },
          { v: research, label: "research 0.70" },
          { v: thresholds.applied ?? 0.8, label: "applied 0.80" },
          { v: thresholds.individual_decisions ?? 0.9, label: "decisions about people 0.90" },
        ].map((t, i) => {
          // A label past the midpoint grows to the LEFT of its tick. Anchoring
          // everything on the left pushes the rightmost labels off the viewport,
          // which on a phone makes the whole page scroll sideways and is
          // structurally invisible on a desktop.
          const at = pos(t.v);
          const flip = at > 58;
          return (
            <div className="qdp-threshold" key={t.label} style={{ left: `${at}%` }}>
              <span
                className={`qdp-threshold-label mono${flip ? " is-flipped" : ""}`}
                style={{ top: `${-8 + (i % 2) * 15}px` }}
              >
                {t.label}
              </span>
            </div>
          );
        })}

        <div className="qdp-ci" style={{ left: `${pos(ci_low)}%`, width: `${pos(ci_high) - pos(ci_low)}%` }} />

        <div className="qdp-dots">
          {buckets.map((bucket, i) => (
            <div
              className="qdp-col"
              key={i}
              style={{ left: `${((i + 0.5) / COLUMNS) * 100}%`, width: `${100 / COLUMNS}%` }}
            >
              {bucket.map((q, j) => (
                <span className={`qd-dot${q < research ? " is-short" : ""}`} key={j} title={q.toFixed(3)} />
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="qdp-readout">
        <div>
          <span className="eyebrow">{reliability.statistic}</span>
          <div className="qdp-point mono">{point_estimate.toFixed(3)}</div>
        </div>
        <div>
          <span className="eyebrow">honest range</span>
          <div className="qdp-range mono">
            {ci_low.toFixed(3)} to {ci_high.toFixed(3)}
          </div>
        </div>
        <div>
          <span className="eyebrow">of fifty outcomes</span>
          <div className="qdp-count mono">
            <strong>{belowResearch}</strong> fall short
          </div>
        </div>
      </div>

      <p className="qdp-caption">{reliability.verdict_reason}</p>
    </div>
  );
}
