/*
  Record the practice call, driven by a fake microphone.

  Chrome will answer getUserMedia from a file instead of a device, so the call
  can be driven with nobody in the room:

      --use-fake-ui-for-media-stream        grant the permission without a prompt
      --use-fake-device-for-media-stream    synthesise the device
      --use-file-for-fake-audio-capture=... play this wav into it

  That matters more than it sounds. The audio goes through the REAL browser, the
  REAL AudioWorklet resampler and the REAL socket, and the criteria on screen are
  filled by the REAL scorer. A recording made this way is a recording of the
  product. A script talking to the API would only be a recording of a script.

  The voice is synthesised and that is disclosed wherever the recording is used.
  It is insurance for a live beat, never evidence of one.

      node frontend/scripts/record-call.mjs --base http://127.0.0.1:8000
*/

import { chromium } from "playwright";
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";

// Accepts both --key=value and --key value. The first version only handled the
// equals form, so `--base http://...` set base to boolean true and the URL was
// silently dropped, which failed on the first method call rather than on the
// parse.
const args = {};
{
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i += 1) {
    if (!argv[i].startsWith("--")) continue;
    const body = argv[i].slice(2);
    if (body.includes("=")) {
      const [k, ...v] = body.split("=");
      args[k] = v.join("=");
    } else if (argv[i + 1] && !argv[i + 1].startsWith("--")) {
      args[body] = argv[i + 1];
      i += 1;
    } else {
      args[body] = true;
    }
  }
}

const BASE = (args.base || "http://127.0.0.1:8000").replace(/\/+$/, "");
const WAV = path.resolve(args.audio || "artifacts/call.wav");
const OUT = path.resolve(args.out || "artifacts/recording");
const SECONDS = Number(args.seconds || 95);

if (!existsSync(WAV)) {
  console.error(`no call audio at ${WAV}. Run: python scripts/make_call_audio.py`);
  process.exit(2);
}
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  // The full browser, not chrome-headless-shell. The shell is the default for
  // headless launches and does not carry the media stack, so the fake audio
  // device flags below are accepted and then do nothing, which reads as the
  // model never hearing anything.
  channel: "chromium",
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    `--use-file-for-fake-audio-capture=${WAV}`,
    "--autoplay-policy=no-user-gesture-required",
  ],
});

const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  permissions: ["microphone"],
  recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
});

const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

console.log(`  opening ${BASE}/practice`);
await page.goto(`${BASE}/practice`, { waitUntil: "networkidle", timeout: 60000 });

// Wait for the handset to attach to a run rather than assuming it has.
await page.waitForSelector(".mh-run", { timeout: 60000 }).catch(() => {});

const start = page.locator("button", { hasText: /Start the practice call/i });
await start.waitFor({ state: "visible", timeout: 30000 });
if (await start.isDisabled()) {
  console.error("  the start button is disabled: this host cannot take a live call");
  await context.close();
  await browser.close();
  process.exit(1);
}

console.log("  starting the call");
await start.click();

// Report what the scorer does, as it does it, so the log is a transcript of the
// run rather than a promise that something happened.
let lastPassing = "";
const deadline = Date.now() + SECONDS * 1000;
while (Date.now() < deadline) {
  await page.waitForTimeout(2000);
  const state = await page.evaluate(() => ({
    rows: [...document.querySelectorAll(".pf-row")].map((r) => ({
      label: r.querySelector(".pf-text")?.textContent?.trim() ?? r.textContent.trim().slice(0, 40),
      state: r.querySelector(".pf-state")?.textContent?.trim() ?? "",
    })),
    lines: document.querySelectorAll(".pc-line, .transcript-line").length,
    elapsed: document.querySelector(".pc-timer, .call-timer")?.textContent?.trim() ?? "",
  }));
  const passing = state.rows.filter((r) => /PASS/i.test(r.state)).map((r) => r.label).join(", ");
  if (passing !== lastPassing) {
    console.log(`  ${state.elapsed || "--:--"}  passing: ${passing || "none yet"}  (${state.lines} transcript lines)`);
    lastPassing = passing;
  }
}

const final = await page.evaluate(() => ({
  rows: [...document.querySelectorAll(".pf-row")].map((r) => r.textContent.trim().replace(/\s+/g, " ")),
  transcript: [...document.querySelectorAll(".pc-line, .transcript-line")].map((l) =>
    l.textContent.trim().replace(/\s+/g, " "),
  ),
}));

await context.close(); // flushes the video
await browser.close();

console.log();
console.log(`  transcript lines: ${final.transcript.length}`);
final.transcript.slice(0, 8).forEach((l) => console.log(`    ${l.slice(0, 120)}`));
console.log("  final form:");
final.rows.forEach((r) => console.log(`    ${r.slice(0, 110)}`));
if (errors.length) console.log("  page errors:", errors.slice(0, 3));

const ok = final.transcript.length > 0;
console.log();
console.log(ok ? `  recorded into ${OUT}` : "  FAIL the call produced no transcript");
process.exit(ok ? 0 : 1);
