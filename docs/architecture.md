# How CALIPER is built, and where a human decides

Two diagrams. The first is the agent. The second is the run state machine, which
is where the human sits.

Every module named below exists in the tree, and the claim that only one of them
talks to a language model is enforced by `tests/test_no_model_in_the_core.py`
rather than described here and hoped for.

## The agent

```mermaid
flowchart TB
    subgraph SRC["Supplied case package, never leaves the operator's machine"]
        X1["Member Experience export"]
        X2["Business Process export"]
        X3["Compliance export"]
        X4["Labor and curriculum build report"]
        X5["RCX design template workbook"]
    end

    subgraph ING["ingest, deterministic"]
        N["normalize<br/>resolve columns by header name"]
        P["pseudonymize<br/>salted blake2s, salt never recorded"]
        S["pii_scan<br/>seven identifier patterns, counted"]
    end

    subgraph INS["instrument, deterministic. NO MODEL"]
        C["ctt<br/>KR-20, Feldt interval, item analysis"]
        K["connectivity<br/>rater by subject graph, linkage fragility"]
        W["power<br/>Cohen h, evaluations per arm"]
    end

    subgraph DIA["diagnose, deterministic. NO MODEL"]
        T["taxonomy<br/>skill, will, process, measurement"]
        R["corroborate<br/>phi across all candidate items"]
        E["engine<br/>ranking, evidence for, alternatives rejected"]
    end

    GATE{{"HUMAN APPROVAL GATE<br/>approve, edit, reject, request more evidence"}}

    subgraph INT["intervene, deterministic. NO MODEL"]
        IR["item_rewrite<br/>the defective question, replaced"]
        OB["objectives<br/>Mager three part, id and parent"]
        DR["drill<br/>the practice script"]
        AL["align<br/>every element traces to the approved diagnosis"]
    end

    subgraph OUT["outputs"]
        WB["export/rcx_workbook<br/>the sponsor's six tabs, one run"]
        IM["impact/labor<br/>three geographies, baseline stated"]
        JD["api/judge<br/>credential free evidence"]
    end

    VOICE["voice/sonic_session<br/>THE ONLY MODEL CALL<br/>plays the member"]
    SCORE["voice/scoring_tool<br/>deterministic. Scores the turn"]
    HUMAN2(["A person takes the call"])

    X1 & X2 & X3 --> N --> P --> S
    X4 --> IM
    X5 -.->|"schema only"| WB
    S --> C & K & W
    C & K & W --> T --> R --> E
    E --> GATE
    GATE -->|approved| IR --> OB --> DR --> AL
    AL --> WB & JD
    IM --> JD
    DR --> VOICE
    HUMAN2 <-->|"speech"| VOICE
    VOICE -->|transcript| SCORE
    SCORE -->|"same rewritten item"| JD

    classDef nomodel fill:#0f1a14,stroke:#4ade9a,color:#e8e8e4
    classDef model fill:#1a1410,stroke:#f5b74f,color:#e8e8e4
    classDef human fill:#101820,stroke:#7aa7ff,color:#e8e8e4
    class INS,DIA,INT,ING nomodel
    class VOICE model
    class GATE,HUMAN2 human
```

The shape of that picture is the argument. Everything that produces a number, a
verdict, a dollar figure or a piece of training content is in a green box. The
single amber box is a synthetic member talking. Nothing flows from amber back
into a number.

## Where a human decides

```mermaid
stateDiagram-v2
    [*] --> INTAKE
    INTAKE --> INSTRUMENT_AUDITED: three forms audited
    INSTRUMENT_AUDITED --> DIAGNOSED: defect ranked, corroborated, scoped
    DIAGNOSED --> AWAITING_APPROVAL: gate opened

    AWAITING_APPROVAL --> APPROVED: human approves or edits
    AWAITING_APPROVAL --> REJECTED: human rejects
    AWAITING_APPROVAL --> AWAITING_APPROVAL: human requests more evidence

    APPROVED --> INTERVENTION_GENERATED: design generated against the approved diagnosis
    INTERVENTION_GENERATED --> PRACTICE_SCORED: the call is scored on the rewritten item
    PRACTICE_SCORED --> COMPLETE
    REJECTED --> [*]
```

**The gate is not a disclaimer, it is a state.** Nothing downstream of it can run
until a human has moved the run out of `AWAITING_APPROVAL`, and the alignment
validator fails any generated element that does not trace back to a diagnosis in
`APPROVED`. Kill the process at the gate and restart it: the run resumes from the
approved state, because the decision is in the store and not in a variable.

Four actions rather than two, because approve or not is not how a reviewer
actually thinks:

| Action | What it means | What happens |
|---|---|---|
| `APPROVE` | the diagnosis is right | design generation unlocks |
| `EDIT` | right defect, wrong wording or scope | unlocks, with the edit recorded |
| `REJECT` | wrong diagnosis | the run ends, and nothing is generated |
| `REQUEST_MORE_EVIDENCE` | not enough to decide | the gate stays shut |

Every transition is appended to a ledger with the actor, the note, and
`actor_verified`, which records whether the name attached to the decision was
authenticated or merely typed. A run where nobody was authenticated is still a
valid run; it just says so.

## The second human interaction

The practice call. A person speaks, the model plays the member, and the turn is
scored **in code** against the rewritten quality item the audit produced, not by
the speech model. The same instrument that produced the diagnosis scores the
practice, which is what makes the loop closed rather than merely sequential.

## What the diagram deliberately does not show

There is no arrow from a model into a number, because there is no such path. The
diagnosis narrative, the training objectives, the activity, the drill script, the
six workbook tabs and every dollar figure are templates filled from computed
values. An earlier version of the README claimed a model narrated evidence into
prose and drafted intervention content. Neither was ever built, the package that
would have held them was empty and imported nowhere, and the claim has been
corrected to what ships.
