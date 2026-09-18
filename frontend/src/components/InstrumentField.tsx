import { useEffect, useRef } from "react";
import type * as THREENS from "three";

/**
 * The background, carrying the finding.
 *
 * A decorative canvas would have been easier and would have said nothing. This
 * one draws one point per observation in the supplied export, 391 of them, laid
 * out as the lattice a working instrument would produce: every agent scored on
 * every question, in order, in rows.
 *
 * Then it applies the measured coherence. The displacement of each point is
 * scaled by (1 - reliability), so the field is exactly as disordered as the
 * instrument is. On load it is a clean grid, which is what everybody assumes a
 * quality form is. When the audit finishes, the coherence animates from 1 to the
 * computed KR-20 and the grid visibly comes apart. The act of measuring the
 * instrument is what breaks the picture of order.
 *
 * Nothing here is invented: `coherence` is the reliability the engine computed,
 * passed in as a number.
 *
 * FOUR GATES, because a decorative layer must never be able to take the demo
 * down, and the plan locked these before a line was written:
 *
 *   1. It is mounted independently and reads nothing. Delete this component and
 *      every screen renders and every number is still legible.
 *   2. No runtime fetch. three is bundled; there is no texture, font or CDN call
 *      that could hang on a conference network.
 *   3. A frame rate floor. If the rolling average falls below the floor it sheds
 *      points, and if it stays below it removes itself entirely rather than
 *      dragging the interface down with it.
 *   4. prefers-reduced-motion and ?still=1 both render nothing at all, and a
 *      lost WebGL context unmounts silently instead of throwing.
 */

const OBSERVATIONS = 391; // one point per scored item in the supplied export
const FPS_FLOOR = 46;
const FPS_SAMPLE_MS = 1500;

export function InstrumentField({ coherence }: { coherence: number }) {
  const host = useRef<HTMLDivElement>(null);
  const target = useRef(1);

  // The value the shader eases toward. Kept in a ref so a prop change animates
  // rather than restarting the scene.
  target.current = Number.isFinite(coherence) ? Math.max(0, Math.min(1, coherence)) : 1;

  useEffect(() => {
    const node = host.current;
    if (!node) return;
    if (new URLSearchParams(window.location.search).has("still")) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let teardown: (() => void) | null = null;
    let cancelled = false;

    /*
      three is imported dynamically, and that is a decision rather than a habit.

      Bundled statically it added about 600 kilobytes to the main chunk, which
      every visitor downloads and parses before the first paint, for a layer
      that is by definition optional. Split out, the product renders and becomes
      usable and the scenery arrives afterwards. A backdrop that delays the thing
      it sits behind has its priorities backwards.
    */
    import("three")
      .then((THREE) => {
        if (cancelled || !host.current) return;
        teardown = build(THREE, node);
      })
      .catch(() => {
        // The chunk did not load. There is nothing to tell anyone: the product
        // is complete without it.
      });

    return () => {
      cancelled = true;
      if (teardown) teardown();
    };
  }, []);

  function build(THREE: typeof THREENS, node: HTMLDivElement): () => void {
    let renderer: THREENS.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: "low-power" });
    } catch {
      // No WebGL. The product does not need it, so say nothing and render nothing.
      return () => {};
    }

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.z = 15;

    // The lattice a working instrument would produce: every agent scored on
    // every question, in order.
    const cols = 23;
    const rows = Math.ceil(OBSERVATIONS / cols);
    const home = new Float32Array(OBSERVATIONS * 3);
    const drift = new Float32Array(OBSERVATIONS * 3);
    const seed = new Float32Array(OBSERVATIONS);

    for (let i = 0; i < OBSERVATIONS; i++) {
      const c = i % cols;
      const r = Math.floor(i / cols);
      home[i * 3] = (c / (cols - 1) - 0.5) * 26;
      home[i * 3 + 1] = (r / (rows - 1) - 0.5) * 14;
      home[i * 3 + 2] = 0;
      // A fixed pseudo random direction per point, so the disorder is stable
      // rather than shimmering: the same instrument is wrong the same way twice.
      const a = Math.sin(i * 12.9898) * 43758.5453;
      const b = Math.sin(i * 78.233) * 12345.6789;
      const cc = Math.sin(i * 39.425) * 24634.6345;
      drift[i * 3] = (a - Math.floor(a) - 0.5) * 6.2;
      drift[i * 3 + 1] = (b - Math.floor(b) - 0.5) * 4.4;
      drift[i * 3 + 2] = (cc - Math.floor(cc) - 0.5) * 5.0;
      seed[i] = i / OBSERVATIONS;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(home.slice(), 3));
    geometry.setAttribute("aHome", new THREE.BufferAttribute(home, 3));
    geometry.setAttribute("aDrift", new THREE.BufferAttribute(drift, 3));
    geometry.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));

    const uniforms = {
      uTime: { value: 0 },
      uCoherence: { value: 1 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
    };

    const material = new THREE.ShaderMaterial({
      uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        attribute vec3 aHome;
        attribute vec3 aDrift;
        attribute float aSeed;
        uniform float uTime;
        uniform float uCoherence;
        uniform float uPixelRatio;
        varying float vFade;

        void main() {
          // Disorder is the complement of reliability. At coherence 1 every
          // point sits exactly on the lattice; at the measured 0.47 it does not.
          float disorder = 1.0 - uCoherence;
          vec3 wander = aDrift * disorder;
          // A slow breath, so the field is alive without drawing attention.
          wander += vec3(
            sin(uTime * 0.16 + aSeed * 31.0),
            cos(uTime * 0.13 + aSeed * 27.0),
            sin(uTime * 0.11 + aSeed * 19.0)
          ) * (0.22 + disorder * 0.5);

          vec3 pos = aHome + wander;
          vec4 mv = modelViewMatrix * vec4(pos, 1.0);
          gl_Position = projectionMatrix * mv;
          // The divisor is view depth, so this has to be scaled to the camera
          // distance. A first pass used 18 and produced points about one pixel
          // across: a live WebGL context drawing something invisible, which
          // looks exactly like a broken shader and is not one.
          gl_PointSize = (150.0 * uPixelRatio) / -mv.z;
          // Points that have wandered furthest from where they belong are the
          // ones the eye should catch.
          vFade = clamp(length(wander) * 0.30, 0.0, 1.0);
        }
      `,
      fragmentShader: `
        precision mediump float;
        varying float vFade;
        void main() {
          // A soft round point. discard rather than draw a square.
          vec2 d = gl_PointCoord - vec2(0.5);
          float r = dot(d, d);
          if (r > 0.25) discard;
          float falloff = smoothstep(0.25, 0.0, r);
          vec3 settled = vec3(0.29, 0.33, 0.40);
          vec3 strayed = vec3(0.29, 0.87, 0.60);
          // Deliberately restrained. The disordered state has to be LEGIBLE as
          // disorder without competing with the numbers, and the first tuning
          // pass was bright enough to pull the eye off the type, which by the
          // plan's own rule means the backdrop had failed at its job.
          gl_FragColor = vec4(mix(settled, strayed, vFade * 0.55), falloff * (0.16 + vFade * 0.22));
        }
      `,
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);
    node.appendChild(renderer.domElement);

    const resize = () => {
      const w = node.clientWidth || window.innerWidth;
      const h = node.clientHeight || window.innerHeight;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    window.addEventListener("resize", resize);

    let raf = 0;
    let disposed = false;
    let frames = 0;
    let windowStart = performance.now();
    let degraded = false;
    const start = performance.now();

    const onLost = (e: Event) => {
      e.preventDefault();
      stop();
    };
    renderer.domElement.addEventListener("webglcontextlost", onLost);

    const tick = (now: number) => {
      if (disposed) return;
      raf = requestAnimationFrame(tick);
      uniforms.uTime.value = (now - start) / 1000;
      // Ease toward the measured coherence rather than snapping, so the grid is
      // seen coming apart.
      uniforms.uCoherence.value += (target.current - uniforms.uCoherence.value) * 0.012;
      renderer.render(scene, camera);

      frames += 1;
      if (now - windowStart >= FPS_SAMPLE_MS) {
        const fps = (frames * 1000) / (now - windowStart);
        frames = 0;
        windowStart = now;
        if (fps < FPS_FLOOR) {
          if (!degraded) {
            // Shed half the points once before giving up on the effect.
            degraded = true;
            geometry.setDrawRange(0, Math.floor(OBSERVATIONS / 2));
          } else {
            // Still slow after shedding. A backdrop is not worth a stuttering
            // interface on a projector, so it removes itself.
            stop();
          }
        }
      }
    };

    function stop() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      renderer.domElement.removeEventListener("webglcontextlost", onLost);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === node) node.removeChild(renderer.domElement);
    }

    raf = requestAnimationFrame(tick);
    return stop;
  }

  return <div className="instrument-field" ref={host} aria-hidden="true" />;
}
