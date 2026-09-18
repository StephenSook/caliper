# CALIPER: the live demo

Dan's run sheet. KSU Coles x ResultsCX, Friday September 18, 1:00pm.

You are running the demo. The whole argument lands in one sentence, so say it
before you touch anything:

> **"Everybody else grades the workers. We grade the test."**

A quality form decides who gets coached, who goes on a performance plan, and
sometimes who keeps a job. Nobody had checked whether that form can measure
anything. That is the entire product.

---

## Before the room, five minutes

1. Laptop on `https://caliper-77ma.onrender.com`, sitting on screen 01.
   **Do not press Run the audit yet.** The first press is the demo.
2. The page can take about 30 seconds to wake the first time. Load it early so
   the room never watches it boot.
3. Phone: CALIPER on the home screen, screen timeout set to never.
4. For the live call, Stephen runs `scripts/demo_phone.sh` and hands you a URL.
   Type it into the app's **Connect** screen. Do this before you walk up, not on
   stage.

---

## The demo, click by click

### Screen 01, intake

Say the one sentence. Then:

> **CLICK "Run the audit"**

It computes live, in front of them. A run id appears top right, like
`RUN-AF91F4C3`, and next to it the state `AWAITING_APPROVAL`. Point at it. That
id is the thread through the whole rest of the demo.

### Screen 02, instrument audit

Three tabs, one per form.

| Form | KR-20 | 95% interval | Unusable items |
|---|---|---|---|
| Member Experience | 0.4661 | -0.019 to 0.776 | 5 of 9 |
| Business Process | 0.4155 | -0.223 to 0.764 | 2 of 4 |
| Compliance | 0.3101 | -0.309 to 0.709 | 10 of 10 |

> "All three forms have a 95 percent confidence interval whose lower bound sits
> at or below zero. Not one of them can be shown to work on this sample."

**Compliance is the punch. Land it slowly.** Seven of ten questions have never
once distinguished any two calls, and that includes the item recording HIPAA
verification.

> "A question everybody passes is not a control. It is a habit."

### Screen 03, diagnosis

The defect: **"Explained Options/Resolution in a Clear, Organized and
Appropriate Manner."** Fails 14 of 17 evaluations across 8 of 10 agents. That is
the 82 percent.

Two things to point at, because they are what a technical judge checks:

- **Corroboration is scanned, not assumed.** The phi coefficient sits next to
  the co-failure count, and a pairing below the floor is not called
  corroboration.
- **Two alternatives rejected, on the record.** Not hidden.

### Screen 04, human validation. This is your moment.

Before you click anything, show them the four buttons are **greyed out**.

> **TYPE your name in "who is deciding"**

The buttons light up only now. Say why:

> "Four actions, not two, because approve or not is not how a reviewer actually
> thinks. Approve, edit, reject, request more evidence. Nothing downstream can
> run until a person moves this, and every transition goes in a ledger with who
> decided."

> **CLICK "Approve"**

The state flips to `INTERVENTION_GENERATED` and screens 05, 06 and 07 appear.
Then say the line that separates this from a disclaimer:

> "The decision became the run state. Kill the process and restart it and the
> run resumes from approved. No re-prompt has happened anywhere in this."

### Screen 05, intervention

The rewritten question, before and after. The old one was scored on reviewer
judgement. The new one is scored on an observation: did the member restate, in
their own words, what they owe.

The chain is drawn, not described: `DIAG-001` to `OBJ-001` to `ACT-001` to
`SIM-001` to `METRIC-001`.

> **CLICK "Download the design workbook" and OPEN it**

Six tabs, in ResultsCX's own schema and their own order, from this one run.

> "Your own template workbook has a purple box on six tabs. The legend says:
> copy this prompt, fill in the brackets, attach the files, send. That is six
> manual re-prompts across six tabs. This is the same six artifacts, from one
> run, without anyone pasting anything."

### Screen 06, practice and proof

**On the public website this screen says it cannot take a live call. That is on
purpose and you should say so out loud, not apologise for it.**

> "This public instance deliberately holds no cloud credentials, because a
> public box with credentials is a liability. Everything else on this screen is
> real. The call runs against our own backend."

Then run the call on the laptop, or on the phone if Stephen has the tunnel up.
The member is synthetic and **you say that every single time**. Her plan
mechanics are real and public. The criteria fill in during the conversation,
scored by code, not by a model.

### Screen 07, what being wrong costs

| One curriculum hour at 17.47 designer hours | USA | Mexico | Philippines |
|---|---|---|---|
| Build cost | $870.88 | $248.95 | $113.38 |
| Built on a wrong diagnosis, so built twice | $1,741.76 | $497.90 | $226.76 |

> "Offshoring cuts the build cost by 87 percent and does nothing about building
> the wrong thing. Offshoring without fixing the instrument means being wrong
> more cheaply."

---

## If something breaks

| What happened | What you do |
|---|---|
| The call will not connect | Say it in one sentence, play the recording, narrate over it, keep going. Do not debug on stage. |
| The tunnel is down | The laptop demo needs no tunnel. Skip the phone beat entirely. |
| The laptop dies | Open `caliper-77ma.onrender.com/judge` on a phone. Everything but the call is there. |
| A number looks wrong | Read what is on the screen, not what you memorised. The screen is computed live and it is right. |
| You are running long | Cut the workbook download and screen 07. **Never cut the audit or the gate.** Those are 50 percent of the rubric. |
| Page looks stuck loading | The free host sleeps. Reload once. It wakes in about 30 seconds. |

---

## Questions you will get

**"So your AI just refuses to do the job?"**

> "It declines the one claim the evidence cannot support, and it hands over the
> protocol that would fix it instead of going quiet. Double score a set of calls
> across both evaluators and evaluator severity becomes separable from agent
> ability. That is one afternoon of work, and it is on the screen."

**"Where is the AI?"**

> "One model call in the entire system, and it is the synthetic member speaking
> on the practice call. Every number, every sentence, the objectives and the
> whole workbook are plain Python. There is a test that fails the build if a
> second model call ever appears."

**"Is this real data?"**

> "The evaluations are the supplied export. The member on the practice call is
> synthetic and we say so every time. No agent or member identifier appears on
> any surface."

**"How do we know the numbers are right?"**

> "Press the button again, it recomputes. The interval is on screen next to
> every point estimate, and we cross check the reliability against pingouin."

---

## Numbers to have cold

- **82 percent** is 14 of 17 evaluations, across 8 of 10 agents.
- **2 of 10** linkage fragility. Two evaluators, and every comparison passes
  through two agents.
- **0 of 17** calls were scored by both evaluators. Zero.
- **7 of 10** Compliance items never distinguished anything.
- **13 of 13** golden tests pass, and they run live, not from a recording.

If anything on this sheet does not match what the screen says, the screen is
right. Message Stephen before 1:00pm rather than during.
