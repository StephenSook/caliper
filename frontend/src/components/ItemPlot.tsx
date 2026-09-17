import { useEffect, useRef } from "react";
import gsap from "gsap";
import type { ItemStat } from "../lib/api";

/**
 * Every item on the form, plotted at the proportion of calls that passed it.
 *
 * The shaded band is the usable range. A question almost everyone passes, or
 * almost everyone fails, cannot separate a strong performer from a weak one, so
 * the band is the whole argument and it is drawn first.
 *
 * No statistic is computed here. Positions come from figures the engine produced.
 */

const FLOOR = 0.25;
const CEILING = 0.85;

export function ItemPlot({ items, animate = true }: { items: ItemStat[]; animate?: boolean }) {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!animate || !root.current) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const ctx = gsap.context(() => {
      gsap.from(".ip-row", {
        opacity: 0,
        x: -18,
        duration: 0.62,
        stagger: 0.045,
        ease: "expo.out",
      });
      gsap.from(".ip-dot", {
        scale: 0,
        transformOrigin: "center",
        duration: 0.7,
        stagger: 0.045,
        delay: 0.12,
        ease: "expo.out",
      });
    }, root);
    return () => ctx.revert();
  }, [animate, items]);

  const sorted = [...items].sort((a, b) => a.difficulty_p - b.difficulty_p);

  return (
    <div className="item-plot" ref={root}>
      <div className="ip-scale" aria-hidden="true">
        <span className="mono">too hard</span>
        <span className="mono">{FLOOR}</span>
        <span className="ip-scale-mid mono">usable range</span>
        <span className="mono">{CEILING}</span>
        <span className="mono">too easy</span>
      </div>

      <div className="ip-rows">
        {sorted.map((item) => {
          const outside = item.difficulty_p < FLOOR || item.difficulty_p > CEILING;
          const dead = item.verdict === "DEAD";
          return (
            <div className="ip-row" key={item.item_id}>
              <div className="ip-label" title={item.item_text}>
                {item.item_text}
              </div>
              <div className="ip-track">
                <div
                  className="ip-band"
                  style={{ left: `${FLOOR * 100}%`, width: `${(CEILING - FLOOR) * 100}%` }}
                />
                <div
                  className={`ip-dot${outside ? " is-outside" : ""}${dead ? " is-dead" : ""}`}
                  style={{ left: `${item.difficulty_p * 100}%` }}
                />
              </div>
              <div className="ip-value mono">
                {item.difficulty_p.toFixed(3)}
                <span className="ip-rpb">
                  {item.discrimination_rpb === null
                    ? "no variance"
                    : `r ${item.discrimination_rpb.toFixed(3)}`}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="ip-caption">
        Horizontal position is the proportion of calls that passed each question.
        A question almost everyone passes, or almost everyone fails, carries no
        information about who is good at this job.
      </p>
    </div>
  );
}
