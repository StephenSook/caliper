/*
  Phone checks in WebKit.

  Chromium's phone emulation is not a substitute for WebKit here. WKWebView is
  WebKit, so the native shell and every iPhone visitor run this engine, and it
  has behaviours Chromium does not reproduce: it zooms the page when a text field
  under 16px takes focus and never zooms back, and it lays some overflow out
  differently. Both of those shipped in this project and neither was visible in
  Chromium.

  Two targets:

    the native launcher, served from an origin the backend already allows, so
    the submit path is exercised in the same engine the app runs
    the product itself, at phone width, checked for horizontal overflow and for
    any focusable field that would trigger the zoom

  Usage:  node frontend/scripts/webkit-phone-check.mjs <backend-origin>

  It lives under frontend/ because node resolves imports from the script's own
  directory, so playwright has to be reachable from here.
*/

import { webkit } from "playwright";

const BACKEND = (process.argv[2] || "").replace(/\/+$/, "");
if (!BACKEND) {
  console.error("usage: node frontend/scripts/webkit-phone-check.mjs https://<backend-origin>");
  process.exit(2);
}

const IPHONE = { width: 402, height: 874 };
let failures = 0;
const check = (name, ok, detail = "") => {
  console.log(`  ${ok ? "ok  " : "FAIL"}  ${name}${detail ? "  " + detail : ""}`);
  if (!ok) failures += 1;
};

const browser = await webkit.launch();
const context = await browser.newContext({
  viewport: IPHONE,
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
});

// ---------------------------------------------------------------- the product
{
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.goto(`${BACKEND}/practice`, { waitUntil: "networkidle", timeout: 45000 });

  const metrics = await page.evaluate(() => {
    const smallFields = [...document.querySelectorAll("input, textarea, select")]
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        px: parseFloat(getComputedStyle(el).fontSize),
      }))
      .filter((f) => f.px < 16);
    return {
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      smallFields,
      title: document.title,
      text: document.body.innerText.slice(0, 200),
    };
  });

  check("product: no horizontal overflow", metrics.overflow <= 0, `overflow ${metrics.overflow}px`);
  check(
    "product: no field below the 16px zoom threshold",
    metrics.smallFields.length === 0,
    JSON.stringify(metrics.smallFields),
  );
  check("product: rendered something", metrics.text.length > 40, `${metrics.text.length} chars`);
  check("product: no uncaught page error", errors.length === 0, errors.join(" | ").slice(0, 160));
  await page.close();
}

// -------------------------------------------------------------- the launcher
{
  // Served from http://localhost:4173, which the backend's origin allowlist
  // already contains, so the launcher's cross origin health probe is exercised
  // exactly as it is in the app rather than bypassed.
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.goto("http://localhost:4173/index.html", { waitUntil: "load", timeout: 20000 });

  await page.fill("#host", BACKEND);

  const beforeZoom = await page.evaluate(() => visualViewport.scale);
  await page.focus("#host");
  const afterZoom = await page.evaluate(() => visualViewport.scale);
  check("launcher: focusing the field does not zoom", afterZoom === beforeZoom, `${beforeZoom} -> ${afterZoom}`);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  check("launcher: no horizontal overflow with a long address", overflow <= 0, `overflow ${overflow}px`);

  // Submit the way the return key does, which is the path the button shares.
  await page.evaluate(() => document.getElementById("form").requestSubmit());
  await page.waitForURL((u) => u.href.includes("/practice"), { timeout: 30000 }).catch(() => {});

  const url = page.url();
  check("launcher: submit reaches the practice screen", url.includes("/practice"), url);
  check("launcher: no uncaught page error", errors.length === 0, errors.join(" | ").slice(0, 160));
  await page.close();
}

await browser.close();
console.log(failures === 0 ? "\nall phone checks passed" : `\n${failures} phone check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
