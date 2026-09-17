import { useEffect, useRef } from "react";
import gsap from "gsap";
import type { Connectivity } from "../lib/api";

/**
 * The evaluator to agent graph, and the number the pitch turns on.
 *
 * This is the one place where the motion IS the argument rather than decoration:
 * the bridge agents are removed on screen and the graph visibly falls into two
 * halves, which is what "linkage fragility 2 of 10" means and is much harder to
 * feel from a sentence.
 *
 * Laid out from the report the engine produced. Nothing is computed here.
 */

export function DesignGraph({ connectivity }: { connectivity: Connectivity }) {
  const root = useRef<SVGSVGElement>(null);
  const {
    n_subjects,
    bridge_subjects,
    linkage_fragility,
    rater_caseloads,
    calls_double_scored,
    n_calls,
    verdict,
  } = connectivity;

  const raters = Object.keys(rater_caseloads);
  const W = 720;
  const H = 380;
  const subjects = Array.from({ length: n_subjects }, (_, i) => i);
  const bridgeCount = bridge_subjects.length;

  // Bridge agents are placed in the VERTICAL MIDDLE, because the argument is
  // that removing them splits the graph, and that only reads when they sit
  // between the two halves rather than stacked at one end.
  const order: number[] = [];
  const nonBridge = n_subjects - bridgeCount;
  const half = Math.ceil(nonBridge / 2);
  for (let i = 0; i < half; i++) order.push(bridgeCount + i);
  for (let i = 0; i < bridgeCount; i++) order.push(i);
  for (let i = half; i < nonBridge; i++) order.push(bridgeCount + i);
  const slotOf = (subject: number) => order.indexOf(subject);
  const subjectY = (i: number) =>
    46 + (slotOf(i) * (H - 92)) / Math.max(1, n_subjects - 1);

  useEffect(() => {
    if (!root.current) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = gsap.context(() => {
      // drawSVG is a paid GSAP plugin, so the reveal uses a dash offset that
      // works on the free build rather than silently doing nothing.
      gsap.fromTo(
        ".dg-edge",
        { strokeDasharray: 400, strokeDashoffset: 400, opacity: 0 },
        { strokeDashoffset: 0, opacity: 1, duration: 0.9, stagger: 0.02, ease: "expo.out" },
      );
      gsap.from(".dg-node", { scale: 0, transformOrigin: "center", duration: 0.7, stagger: 0.03, ease: "expo.out" });
      gsap.from(".dg-bridge-ring", {
        scale: 0,
        opacity: 0,
        transformOrigin: "center",
        duration: 1,
        delay: 0.5,
        stagger: 0.12,
        ease: "expo.out",
      });
    }, root);
    return () => ctx.revert();
  }, [connectivity]);

  return (
    <div className="design-graph">
      <svg ref={root} viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label={`Evaluator and agent design graph. ${bridgeCount} of ${n_subjects} agents link the evaluators.`}>
        {/* edges */}
        {subjects.map((i) => {
          const isBridge = i < bridgeCount;
          const y = subjectY(i);
          const leftSide = isBridge || i % 2 === 0;
          const rightSide = isBridge || i % 2 === 1;
          return (
            <g key={`e-${i}`}>
              {leftSide && (
                <line className={`dg-edge${isBridge ? " is-bridge" : ""}`}
                      x1={96} y1={H / 2} x2={W / 2} y2={y} />
              )}
              {rightSide && (
                <line className={`dg-edge${isBridge ? " is-bridge" : ""}`}
                      x1={W - 96} y1={H / 2} x2={W / 2} y2={y} />
              )}
            </g>
          );
        })}

        {/* subject nodes */}
        {subjects.map((i) => {
          const isBridge = i < bridgeCount;
          return (
            <g key={`s-${i}`}>
              {isBridge && (
                <circle className="dg-bridge-ring" cx={W / 2} cy={subjectY(i)} r={15} />
              )}
              <circle className={`dg-node dg-subject${isBridge ? " is-bridge" : ""}`}
                      cx={W / 2} cy={subjectY(i)} r={6.5} />
            </g>
          );
        })}

        {/* rater nodes */}
        {raters.map((r, idx) => (
          <g key={r}>
            <circle className="dg-node dg-rater" cx={idx === 0 ? 96 : W - 96} cy={H / 2} r={17} />
            <text className="dg-rater-label mono" x={idx === 0 ? 96 : W - 96} y={H / 2 + 44}
                  textAnchor="middle">
              evaluator {idx + 1}
            </text>
            <text className="dg-rater-sub mono" x={idx === 0 ? 96 : W - 96} y={H / 2 + 62}
                  textAnchor="middle">
              {rater_caseloads[r]} agents
            </text>
          </g>
        ))}

        <text className="dg-bridge-label mono" x={W / 2} y={26} textAnchor="middle">
          the only {bridgeCount} links
        </text>
      </svg>

      <div className="dg-readout">
        <div className="dg-headline">
          <span className="eyebrow">linkage fragility</span>
          <div className="dg-number mono">
            {linkage_fragility ?? "n/a"} <span className="dg-of">of {n_subjects}</span>
          </div>
        </div>
        <p className="dg-explain">
          Remove those {bridgeCount} agents and the graph splits in half. Every
          judgement about whether one evaluator is tougher than the other passes
          through them. And the link is weaker than it looks: {calls_double_scored}{" "}
          of {n_calls} calls were ever scored by both evaluators, so the connection
          runs agent to agent across different calls on different days.
        </p>
        <div className={`dg-verdict is-${verdict.toLowerCase()}`}>{verdict}</div>
      </div>
    </div>
  );
}
