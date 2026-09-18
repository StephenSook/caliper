import { useCallback, useEffect, useRef, useState } from "react";
import gsap from "gsap";
import type { Connectivity } from "../lib/api";

/**
 * The evaluator to agent graph, and the number the whole pitch turns on.
 *
 * This is the one place where the motion IS the argument rather than decoration.
 * "Linkage fragility 2 of 10" is a sentence somebody nods at. Watching the two
 * agents that hold the design together get removed, and the graph fall into two
 * pieces that no longer touch, is a thing a room reacts to.
 *
 * So the split is performed, not described. Press the control and the bridge
 * edges retract, the bridge agents disappear, the two halves drift apart, and
 * the gap between them is labelled with what it means: no comparison between the
 * two evaluators survives.
 *
 * Every number is from the engine. The only thing computed here is where to put
 * a circle.
 */

export function DesignGraph({ connectivity }: { connectivity: Connectivity }) {
  const root = useRef<SVGSVGElement>(null);
  const [split, setSplit] = useState(false);
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
  // How far each half moves when the design comes apart. Used by the animation
  // and by the viewBox, so the two cannot disagree.
  const SPLIT_TRAVEL = 74;
  const H = 380;
  const subjects = Array.from({ length: n_subjects }, (_, i) => i);
  const bridgeCount = bridge_subjects.length;

  // Bridge agents sit in the VERTICAL MIDDLE. Removing them only reads as a
  // split when they are between the two halves rather than stacked at one end.
  const order: number[] = [];
  const nonBridge = n_subjects - bridgeCount;
  const half = Math.ceil(nonBridge / 2);
  for (let i = 0; i < half; i++) order.push(bridgeCount + i);
  for (let i = 0; i < bridgeCount; i++) order.push(i);
  for (let i = half; i < nonBridge; i++) order.push(bridgeCount + i);
  const slotOf = (subject: number) => order.indexOf(subject);
  const subjectY = (i: number) => 46 + (slotOf(i) * (H - 92)) / Math.max(1, n_subjects - 1);

  const isBridge = (i: number) => i < bridgeCount;
  // A non bridge agent was only ever scored by one evaluator. That is the whole
  // problem, and it is what lets each one travel with its own side.
  const side = (i: number) => (i % 2 === 0 ? "left" : "right");

  const stillMode = () =>
    typeof window !== "undefined" && new URLSearchParams(window.location.search).has("still");
  const reducedMotion = () =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (!root.current || stillMode() || reducedMotion()) return;
    const ctx = gsap.context(() => {
      // drawSVG is a paid GSAP plugin, so the reveal uses a dash offset that
      // works on the free build rather than silently doing nothing.
      gsap.fromTo(
        ".dg-edge",
        { strokeDasharray: 400, strokeDashoffset: 400, opacity: 0 },
        { strokeDashoffset: 0, opacity: 1, duration: 0.9, stagger: 0.02, ease: "expo.out" },
      );
      gsap.from(".dg-node", {
        scale: 0,
        transformOrigin: "center",
        duration: 0.7,
        stagger: 0.03,
        ease: "expo.out",
      });
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

  const cut = useCallback(() => {
    setSplit(true);
    if (!root.current || reducedMotion()) return;
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: "expo.inOut" } });
      // 1. The links go first, and they RETRACT rather than fade, so the eye
      //    follows them leaving rather than noticing they are gone.
      tl.to(".dg-edge.is-bridge", { strokeDashoffset: 400, opacity: 0, duration: 0.7 })
        .to(".dg-bridge-ring, .dg-subject.is-bridge", { scale: 0, opacity: 0, duration: 0.5 }, "<0.1")
        // 2. Then the halves come apart. Nothing else on the screen moves, so
        //    the separation is the only thing happening.
        .to(".dg-side-left", { x: -SPLIT_TRAVEL, duration: 1.1 }, ">-0.1")
        .to(".dg-side-right", { x: SPLIT_TRAVEL, duration: 1.1 }, "<")
        .to(".dg-chasm", { opacity: 1, duration: 0.6 }, "<0.35")
        .fromTo(
          ".dg-chasm-label",
          { opacity: 0, y: 8 },
          { opacity: 1, y: 0, duration: 0.6 },
          "<0.1",
        );
    }, root);
    return () => ctx.revert();
  }, []);

  const restore = useCallback(() => {
    setSplit(false);
    if (!root.current || reducedMotion()) return;
    gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: "expo.out" } });
      tl.to(".dg-chasm, .dg-chasm-label", { opacity: 0, duration: 0.3 })
        .to(".dg-side-left, .dg-side-right", { x: 0, duration: 0.9 }, "<")
        .to(".dg-bridge-ring, .dg-subject.is-bridge", { scale: 1, opacity: 1, duration: 0.5 }, "<0.3")
        .to(".dg-edge.is-bridge", { strokeDashoffset: 0, opacity: 1, duration: 0.7 }, "<");
    }, root);
  }, []);

  const raterX = (idx: number) => (idx === 0 ? 96 : W - 96);

  return (
    <div className="design-graph">
      <svg
        ref={root}
        // The viewBox is wider than the layout on purpose. The halves travel
        // outward when the graph splits, and at the original width that pushed
        // the evaluator labels past the edge and clipped them mid word. The
        // extra margin is exactly the travel plus room for the label, so the
        // split has somewhere to go.
        viewBox={`${-SPLIT_TRAVEL - 26} 0 ${W + (SPLIT_TRAVEL + 26) * 2} ${H}`}
        role="img"
        aria-label={
          split
            ? `The design graph with the ${bridgeCount} bridge agents removed. It is now in two disconnected halves, so no comparison between the two evaluators is possible.`
            : `Evaluator and agent design graph. ${bridgeCount} of ${n_subjects} agents link the two evaluators.`
        }
      >
        {/* The gap the split opens, drawn first so everything sits over it. */}
        <g className="dg-chasm">
          <line x1={W / 2} y1={34} x2={W / 2} y2={H - 34} />
        </g>

        {/* LEFT HALF. Evaluator one, and the agents only it ever scored. */}
        <g className="dg-side-left">
          {subjects
            .filter((i) => !isBridge(i) && side(i) === "left")
            .map((i) => (
              <line key={`el-${i}`} className="dg-edge" x1={raterX(0)} y1={H / 2} x2={W / 2} y2={subjectY(i)} />
            ))}
          <circle className="dg-node dg-rater" cx={raterX(0)} cy={H / 2} r={17} />
          <text className="dg-rater-label mono" x={raterX(0)} y={H / 2 + 44} textAnchor="middle">
            evaluator 1
          </text>
          <text className="dg-rater-sub mono" x={raterX(0)} y={H / 2 + 62} textAnchor="middle">
            {rater_caseloads[raters[0]]} agents
          </text>
          {subjects
            .filter((i) => !isBridge(i) && side(i) === "left")
            .map((i) => (
              <circle key={`sl-${i}`} className="dg-node dg-subject" cx={W / 2} cy={subjectY(i)} r={6.5} />
            ))}
        </g>

        {/* RIGHT HALF. */}
        <g className="dg-side-right">
          {subjects
            .filter((i) => !isBridge(i) && side(i) === "right")
            .map((i) => (
              <line key={`er-${i}`} className="dg-edge" x1={raterX(1)} y1={H / 2} x2={W / 2} y2={subjectY(i)} />
            ))}
          <circle className="dg-node dg-rater" cx={raterX(1)} cy={H / 2} r={17} />
          <text className="dg-rater-label mono" x={raterX(1)} y={H / 2 + 44} textAnchor="middle">
            evaluator 2
          </text>
          <text className="dg-rater-sub mono" x={raterX(1)} y={H / 2 + 62} textAnchor="middle">
            {rater_caseloads[raters[1]]} agents
          </text>
          {subjects
            .filter((i) => !isBridge(i) && side(i) === "right")
            .map((i) => (
              <circle key={`sr-${i}`} className="dg-node dg-subject" cx={W / 2} cy={subjectY(i)} r={6.5} />
            ))}
        </g>

        {/* THE BRIDGES. Everything that holds the design together. */}
        <g className="dg-bridges">
          {subjects
            .filter(isBridge)
            .map((i) => (
              <g key={`b-${i}`}>
                <line className="dg-edge is-bridge" x1={raterX(0)} y1={H / 2} x2={W / 2} y2={subjectY(i)} />
                <line className="dg-edge is-bridge" x1={raterX(1)} y1={H / 2} x2={W / 2} y2={subjectY(i)} />
              </g>
            ))}
          {subjects.filter(isBridge).map((i) => (
            <g key={`bn-${i}`}>
              <circle className="dg-bridge-ring" cx={W / 2} cy={subjectY(i)} r={15} />
              <circle className="dg-node dg-subject is-bridge" cx={W / 2} cy={subjectY(i)} r={6.5} />
            </g>
          ))}
        </g>

        <text className="dg-bridge-label mono" x={W / 2} y={26} textAnchor="middle">
          {split ? "removed" : `the only ${bridgeCount} links`}
        </text>
        <text className="dg-chasm-label mono" x={W / 2} y={H - 14} textAnchor="middle">
          no comparison crosses this gap
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
          {split ? (
            <>
              The design is now in two pieces that do not touch. Every judgement
              about whether one evaluator is tougher than the other ran through
              the {bridgeCount} agents that just disappeared. Nothing in this data
              can separate a harsh evaluator from a weak agent any more, and
              nothing in it could before either, because those {bridgeCount}{" "}
              agents were carrying the entire comparison.
            </>
          ) : (
            <>
              Remove those {bridgeCount} agents and the graph splits in half. Every
              judgement about whether one evaluator is tougher than the other passes
              through them. And the link is weaker than it looks: {calls_double_scored}{" "}
              of {n_calls} calls were ever scored by both evaluators, so the connection
              runs agent to agent across different calls on different days.
            </>
          )}
        </p>
        <button className="dg-cut" type="button" onClick={split ? restore : cut}>
          {split ? "Put them back" : `Remove the ${bridgeCount} bridge agents`}
        </button>
        <div className={`dg-verdict is-${verdict.toLowerCase()}`}>{verdict}</div>
      </div>
    </div>
  );
}
