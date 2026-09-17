# Data handling and confidentiality

Judge facing. Every control below is enforced by a test or a guard that has been
proven to fail, not by a convention.

## What we will not claim

We are not a covered entity and this system holds no protected health
information. We therefore do not claim HIPAA compliance. What we claim is
conservative handling of competition confidential employee data, and we state
below what a production deployment would additionally require.

The practice conversation uses a synthetic member persona over real, public plan
mechanics taken from CMS and HealthCare.gov. No real member record ever reaches
the speech model. That is an architecture choice rather than a mitigation.

## Controls

| Control | Where | How it is proven |
|---|---|---|
| Supplied case package cannot be committed | `.gitignore`, `scripts/check_confidential.py` | Guard asserts on the set git would actually stage, floors the file count so a scan of nothing cannot report clean, and was proven red against a planted identifier |
| Personnel pseudonymized at ingest | `caliper/ingest/pseudonymize.py` | Token does not contain its input; mapping differs across salts |
| Evaluator free text comments never ingested | `caliper/ingest/normalize.py` | Test asserts the column map has no route to that field |
| Dates of service never serialized | `Observation.as_dict` | Test asserts the key is absent and an occasion ordinal is present |
| Identifiers detected in supplied material | `caliper/ingest/pii_scan.py` | Planted violations for all seven patterns; redaction count reported on the intake screen |
| No identifier on any rendered surface | golden test E9 | Runs on a synthetic fixture so it executes in CI, with the real package as an additional assertion |
| No em dash or en dash | `scripts/check_dashes.py` | Builds its forbidden characters from code points so it cannot match itself |
| Gates run before a commit exists | `.githooks/pre-commit` | Proven to block, then proven to allow a clean commit |

## Why the scanner runs over material we did not author

One supplied training workbook carries member format identifiers, group numbers,
dates of service and dollar amounts used as practice examples. We therefore treat
every supplied sheet as potentially carrying identifiers, scan all of them, and
report the count on the intake screen. On the supplied package that count is 18.

Reporting it is the point. Responsible data use demonstrated beats responsible
data use claimed.

## Where the models sit

The Nova 2 Sonic model card marks Guardrails, Knowledge Bases, Agents and Flows
as not supported on the speech runtime. Redaction and retrieval therefore run on
the text path, and the speech model reaches that path through asynchronous tool
calling. The speech model never reads a record.

## What production would additionally require

- Bedrock Guardrails on the text path with PII entities set to BLOCK on input,
  since Bedrock does not apply input checks when the behaviour is MASK, plus a
  custom regex for health plan member identifiers because no built in entity type
  covers them.
- A server side output scrubber between the model and the client. A system prompt
  instructing a model not to emit identifiers is not a control.
- A signed audit trail of every human approval decision, retained to the client's
  schedule.
- A data processing agreement and a defined retention window for run state.
