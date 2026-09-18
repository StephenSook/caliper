# Judge Q and A

Open this on a phone during questions. Every figure in it was regenerated from
the engine, and every claim about the code was checked against the code.

---

## The hardest question. Expect it.

**"Your sample is only 17 evaluations. Isn't your conclusion as underpowered as
the form you are criticising?"**

> We do not claim the form is unreliable. Our verdict is literally
> INDETERMINATE. The system says: with 17 evaluations the 95 percent interval
> runs from at or below zero to 0.776, so this sample cannot establish whether
> the instrument works. That is the finding. You cannot make a defensible
> decision about a person from an instrument whose reliability is
> unestablished, and the fix is one afternoon of double scoring.

That question is a gift. It shows you understood your own limits first.

---

## Statistics

**"Why KR-20 and not Cronbach's alpha?"**

> Same formula. KR-20 is the dichotomous case, which is what a pass or fail
> form is.

**"Why a Feldt interval?"**

> A point estimate hides that 17 evaluations cannot pin it down. Feldt inverts
> the F distribution to give the interval. The interval is the argument.

**"Could a low KR-20 just mean the form is multidimensional?"**

> Yes, that is a real alternative and it is one of the two we log as rejected.
> We reject it because 7 of 10 Compliance items have zero variance. A
> multidimensional instrument still discriminates within its dimensions. This
> one does not discriminate at all.

**"What is your corroboration threshold?"**

> Phi has to clear 0.15. Below that we do not call it corroboration and we say
> so on screen. Two items that both fail on nearly everything co fail without
> being related, which is base rate saturation.

**"How do you know your numbers are right?"**

> Press the button again, it recomputes. The interval is on screen next to
> every point estimate, and we cross check reliability against pingouin.

---

## The AI

**"How do you know the model did not hallucinate a number?"**

> There is one model call in the entire system and it is a synthetic member
> talking. Every number is plain Python. A test fails the build if a second
> module ever imports a model SDK.

**"Why does the model play the member instead of grading?"**

> Because grading is the part that has to be auditable. A model that decides
> whether a criterion was met cannot be checked. A model that plays a difficult
> member, and lets code read the transcript, can.

**"Is the model just told the answer?"**

> Yes, and that is the honest limit. The system prompt hands her the figure, so
> what the code reads is whether she chose to recite it. The rule is
> deterministic, the observation is not. The other two criteria read only what
> the representative said.

**"Where is the AI, really?"**

> Amazon Nova 2 Sonic on Bedrock, bidirectional streaming, us-east-1. One
> module imports it: caliper/voice/sonic_session.py.

---

## Engineering

**"SQLite? At scale?"**

> It is an append only audit trail for the approval gate, not a data store. One
> file, no network, survives a venue with no wifi. Swapping it for Postgres is
> a connection string.

**"Why not boto3 for the voice?"**

> boto3 cannot do duplex. We use aws-sdk-bedrock-runtime over awscrt for
> HTTP/2 bidirectional streaming.

**"What happens if Bedrock is down?"**

> Everything except the call still runs. The audit needs no cloud at all.

**"Can this run in our environment?"**

> The deterministic core has zero AWS dependency. Only the voice needs Bedrock.

**"Why can the public site not take a call?"**

> Deliberate. A public box holding cloud credentials is a liability. It says so
> on screen rather than failing silently.

**"What about the case data?"**

> It never enters a database. It is read from the export at runtime,
> pseudonymised at ingest, and the public instance runs on a de-identified
> matrix. No member identifier, agent name, evaluator comment or call id is
> written to disk.

---

## Business

**"What would it take to actually deploy this?"**

> Double score a set of calls across both evaluators so severity becomes
> separable from ability. That is one afternoon. Everything downstream of that
> already runs.

**"So your AI refuses to do the job?"**

> It declines the one claim the evidence cannot support, and hands over the
> protocol that would fix it instead of going quiet.

**"What does being wrong cost?"**

> One curriculum hour at the sponsor's own fully loaded rates: 870.88 USA,
> 248.95 Mexico, 113.38 Philippines. Double it if it was built on a wrong
> diagnosis. Offshoring cuts the build cost 87 percent and does nothing about
> building the wrong thing.

---

## The stack, in one breath

> Python and FastAPI on the backend, React and TypeScript on the front, Amazon
> Bedrock running Nova 2 Sonic for the voice, SQLite for the audit trail. Every
> statistic is plain Python: numpy, scipy, statsmodels, networkx, cross checked
> against pingouin. Capacitor for the mobile shell. Docker on Render.

---

## Two things never to say

**Do not say Nova 2 Lite.** It is in one preflight script and the product never
calls it. A judge who greps the repo will find that.

**Do not say "it is just a prototype."** It is live, it is public, and a
stranger can regenerate every figure. Say that instead.

---

## Numbers to have cold

- 82 percent is 14 of 17 evaluations, across 8 of 10 agents
- linkage fragility 2 of 10, two evaluators, every comparison passes through
  two agents
- 0 of 17 calls scored by both evaluators
- 7 of 10 Compliance items never distinguished anything
- 13 of 13 golden cases pass, executed live rather than recorded
