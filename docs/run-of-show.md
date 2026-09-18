# Run of show

Fifteen minutes, including set up. That is the whole budget, so the target below
is thirteen and a half of content and ninety seconds of slack, because a live
demo that runs long is a live demo that gets cut off mid sentence.

Owners are from the team briefing: **Stephen** data and statistics, AWS and
orchestration. **Ryann** interface. **Dan** learning design outputs. **Deem**
business case and pitch.

Rehearse this out loud twice with a timer. Not reading it, saying it.

---

## Before the room

Ten minutes before, in this order:

```
python scripts/preflight_demo.py --local http://127.0.0.1:8000
python scripts/smoke_voice.py             # exercises the call itself, no headset needed
python scripts/reset_demo.py              # clean slate between run throughs
```

The first exits 0 or names what is broken, across the deployed instance, the
laptop, the published binary, every judge facing figure and CI. The second
synthesises a three turn call through the real socket and tells you whether the
model answered. Neither needs a person to speak.

The third clears rehearsal runs. **Rehearse as often as you like:** the smoke
test marks its run as a rehearsal, so the phone will never attach to it and the
screen on stage cannot end up showing a rehearsal's transcript. Real runs are
never deleted by that script, because a run a human approved is evidence.

Then:

1. Laptop plugged in. Screen mirroring tested on the actual projector.
2. Browser at `http://127.0.0.1:8000`, one tab, no others. Notifications off.
3. Phone unlocked, CALIPER open, screen timeout set to never.
4. The tunnel running, and the phone pointed at it, so the call works.
5. Headset on, not the open room microphone.
6. The backup recording open in a second window, one keypress from playing.
   Regenerate it any time with:

   ```
   python scripts/make_call_audio.py
   node frontend/scripts/record-call.mjs --base=http://127.0.0.1:8000
   ```

   It drives the REAL browser through a fake microphone, so the criteria on
   screen are filled by the real scorer. **It has no sound**, deliberately: the
   recorder captures the screen and not the room, so narrate over it. The
   representative's voice in it is synthesised, which is fine for insurance and
   is never presented as a person.
7. `https://caliper-77ma.onrender.com/judge` open on a spare device in case a
   judge wants to hold something.

**Do not start the run before you present.** The audit computing live is a beat,
and a pre warmed screen looks like a screenshot.

---

## The fifteen minutes

### 0:00 to 1:00  Set up, and the sentence

**Deem**, while Stephen plugs in.

> Everybody else grades the workers. We grade the test.
>
> You gave us seventeen quality evaluations and asked us to find out why agents
> are struggling. We are going to do that. But first we checked whether the form
> you are grading them with can measure anything at all, because every diagnosis
> downstream of it inherits whatever that form gets wrong.

No slide needed. Say it while the laptop wakes up.

### 1:00 to 2:30  Why this is the right first question

**Deem.**

The case study's own words: an error during needs analysis misidentifies the root
problem, and errors during course design produce polished training that addresses
the wrong behaviour. Both create substantial downstream rework.

The point to land: **every one of those failures is downstream of an instrument
nobody has audited.** If the form cannot separate two agents, then a diagnosis
built on it cannot either, however good the analysis is.

Hand to Stephen with: *"So we measured the form."*

### 2:30 to 5:30  The finding. This is the 25 percent

**Stephen.** Click **Run the audit**. Let it compute on screen.

Three things, in this order, and do not rush the second one:

1. **All three forms have a 95 percent confidence interval whose lower bound sits
   at or below zero.** Member Experience is 0.4661, interval -0.019 to 0.776.
   Not one of the three can be shown to work on this sample. Point at the
   quantile plot: that is not a bar, it is the distribution of where the true
   value could be, and it crosses zero.

2. **On the Compliance form, seven of ten questions have never once distinguished
   any two calls.** One of them records whether HIPAA verification was performed.
   Everyone passes it, every time. A question everyone passes is not measuring
   anything, and in a healthcare contact centre that is the question you would
   least like to be decorative.

3. **Linkage fragility, two of ten.** Two evaluators, zero calls scored by both,
   and every comparison between them runs through two agents. Remove those two
   and the design splits in half. You cannot tell a harsh evaluator from a weak
   agent, and nothing in the data can settle it.

If a judge interrupts here, let them. This is the part worth the time.

Then the honest beat, said out loud rather than buried:

> We expected a higher number. Our own build spec said 0.505. We recomputed it,
> found the spec had mixed two variance conventions, and the correct figure is
> 0.4661 with an interval that includes zero. We corrected our own spec. That is
> the same thing we are asking you to do with the form.

### 5:30 to 7:30  The diagnosis, and the human. This is the other 25 percent

**Stephen** walks the diagnosis. **Dan** takes the gate.

- The defect, its frequency and its breadth, its corroborating item **and the phi
  coefficient**, the alternatives considered and why each was rejected.
- The scope boundary: this is a **systemic** finding. We decline to diagnose an
  individual from this instrument, and we hand over the protocol that would make
  it possible rather than going quiet.

**Dan approves the diagnosis on screen.** Say what the gate is:

> Four actions, not two, because approve or not is not how a reviewer thinks.
> Approve, edit, reject, request more evidence. Nothing downstream can run until
> a person moves this, and every transition is in a ledger with who decided and
> whether their name was authenticated.

**Then kill the process and restart it.** The run resumes from the approved
state. That is the difference between a state machine and a disclaimer.

No re prompt has happened. Say so.

### 7:30 to 10:00  The design, in one flow. 20 percent plus 10 percent

**Dan**, with **Ryann** on the interface.

- The rewritten quality item, and why the old one failed, in its own words.
- Objectives, activity, drill, each with an id and a parent, so the chain is
  drawn rather than described. Alignment coverage is a live number.
- **Download the workbook.** Open it. Six tabs, in their own schema, in their own
  order, from one run.

The line that lands:

> Your own template workbook has a purple box on six tabs. The legend says: copy
> this prompt, fill in the brackets, attach the files, send. That is six manual
> re prompts across six tabs. This is the same six artifacts, from one run,
> without anyone pasting anything.

### 10:00 to 12:30  The practice call, live

**Stephen** on the laptop, **Ryann** on the phone, or hand the phone to a judge.

Set it up in one sentence before starting:

> The member is synthetic and we will say that every time. Her plan mechanics are
> real and public: an explanation of benefits, a billed amount, an allowed amount,
> coinsurance on the allowed amount after the deductible.

Then take the call. Ninety seconds. While it runs, the laptop shows **the
rewritten form filling in, criterion by criterion**.

The point, said while it is happening:

> The question the audit rewrote is the question this call is scored on. Same
> instrument for the diagnosis, the practice and the proof. And the scoring is
> code reading the transcript, not the speech model deciding whether it liked the
> answer.

**If the call fails:** say so in one sentence, play the recording, keep moving.
Do not debug in front of the room. The recording is one keypress away and it is
the same call.

### 12:30 to 13:30  What being wrong costs

**Deem**, on screen seven.

> You asked for savings on labor and cost, USA against Mexico or the Philippines.
> Fully loaded, USA runs 7.7 times the Philippines and 3.5 times Mexico for the
> same instructional design role. One hour of finished curriculum costs about
> eighteen dollars to build on Philippines labor, thirty nine on Mexico, one
> hundred thirty eight on USA.
>
> The number we can stand behind is the one on the right: what one wrong
> diagnosis costs. A misdiagnosis produces training that addresses the wrong
> behaviour, which gets found downstream and fixed by revising it, and your own
> report prices a revision at 3.60 build hours per curriculum hour from tracked
> time.

Then change the baseline dropdown on screen and let the numbers move.

> Your report gives two build ratios that differ by 6.3 times. They are not
> contradictory, they answer different questions. We are not going to pick one
> for you and call it a saving.
>
> And we will not multiply it by a rate of misdiagnosis, because nobody has
> measured how often a needs analysis lands on the wrong cause. A real cost times
> a guessed frequency is a big number with nothing underneath it. That is the
> same discipline we applied to your form.

### 13:30 to 15:00  Close, and questions

**Deem.**

> Six steps, one run, one human decision point that actually gates the work, and
> an instrument audit nobody was doing.
>
> The honest version of what we found is that we cannot yet tell you which agent
> needs coaching, because seventeen evaluations from two evaluators who never
> scored the same call cannot support that. What we can tell you is exactly what
> it would take: the protocol is on screen, and the number of evaluations is
> computed, not guessed.

If time remains, open `/judge` and let them read it themselves.

---

## Questions you will get, and the answers

**"So your AI refuses to do the job?"**
> It refuses one thing: naming an individual from an instrument that cannot
> separate individuals. It does the rest in one run. Refusing that is the job.
> An agent that answers anyway is the failure your own case study names.

**"How do we know the model did not hallucinate these numbers?"**
> There is exactly one model call in the entire system and it is the synthetic
> member speaking. Every number, verdict and dollar figure is ordinary Python,
> and a test fails the build if a second module ever imports a model SDK.

**"You are saying our form is broken. The client wrote that form."**
> We are saying seventeen evaluations cannot establish that it works, which is a
> statement about the sample as much as the instrument. That is a solvable
> problem and the fix is cheap: double score a subset so the two evaluators
> overlap. This gives the client a defensible number instead of an argument.

**"Why should we believe your reliability figure?"**
> Recompute it. `/api/evidence` recomputes from source on every request, and the
> interval is on screen with it. We also cross check against pingouin, which is
> the standard implementation, and we corrected our own spec when it disagreed.

**"What is the ROI?"**
> Per avoided rework cycle, priced from your report: one hundred seventy nine
> dollars on USA labor per curriculum hour. Multiply by however often you think
> a needs analysis lands on the wrong cause. We will not supply that number
> because nobody has measured it, and we would be making it up.

**"Is this HIPAA compliant?"**
> We do not claim compliance. We do identifier scanning at ingest with a
> redaction count on screen, pseudonymise every person before anything is
> computed, and the public instance holds no case data at all. Compliance is a
> programme, not a feature, and claiming it would be the kind of statement this
> product exists to refuse.

**"How is this different from using Claude with our template?"**
> Your template is six prompts across six tabs, pasted by hand, and none of them
> checks whether the data underneath can support the conclusion. This is one run
> with one human gate, and it starts by auditing the instrument, which no prompt
> in that workbook does.

**"Could a designer actually use this?"**
> The output is your workbook, in your schema, in your tab order. Nobody has to
> learn anything. And the parts that need judgement stop and ask.

---

## If something breaks

| What | Do this |
|---|---|
| The call will not connect | Say it in one sentence, play the recording, narrate over it, continue. |
| The tunnel is down | The laptop demo needs no tunnel. Skip the phone beat. |
| The laptop dies | `https://caliper-77ma.onrender.com/judge` on a phone. Everything but the call is there. |
| A number looks wrong on screen | Read what is on screen, not what you remember. The screen is computed. |
| You are running long | Cut the workbook download and the baseline dropdown. Never cut the audit or the gate. |

**Never** debug in front of the room, and never say the demo worked earlier.
