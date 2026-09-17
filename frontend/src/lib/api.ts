/**
 * Typed client for the CALIPER backend.
 *
 * Every field rendered by this app comes from here. Nothing in the interface
 * holds a literal statistic, because a number typed into a component is a number
 * that can drift from the one the engine computes, and the whole product is an
 * argument about not asserting figures you cannot regenerate.
 */

/**
 * Empty means "same origin", which is what the single origin deployment uses:
 * the backend serves this bundle, so /api and /ws are relative and there is no
 * cross origin story to get wrong. A separate value is only for `vite dev`,
 * where the interface and the API run on different ports.
 */
const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

/** WebSocket origin. A relative BASE has to become an absolute ws or wss URL. */
export function wsBase(): string {
  if (BASE) return BASE.replace(/^http/, "ws");
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}`;
}

export interface ItemStat {
  item_id: string;
  item_text: string;
  difficulty_p: number;
  discrimination_rpb: number | null;
  variance: number;
  n_pass: number;
  n_total: number;
  flags: string[];
  verdict: "FUNCTIONING" | "IMPAIRED" | "DEAD";
}

export interface Reliability {
  statistic: string;
  point_estimate: number;
  ci_method: string;
  ci_low: number;
  ci_high: number;
  df1: number;
  df2: number;
  n_evaluations: number;
  n_items: number;
  verdict: string;
  verdict_reason: string;
  thresholds: Record<string, number>;
  /** Quantiles of the sampling distribution, computed by the engine. */
  quantiles: number[];
}

export interface DomainAudit {
  instrument_id: string;
  domain: string;
  n_evaluations: number;
  n_items: number;
  reliability: Reliability;
  items: ItemStat[];
  summary: {
    items_outside_difficulty_band: number;
    items_with_zero_variance: number;
    items_with_negative_discrimination: number;
    items_impaired_or_dead: number;
  };
  sufficiency: {
    mean_evaluations_per_subject: number;
    subjects_with_single_evaluation: number;
    n_subjects: number;
    industry_standard_per_month: string;
    individual_diagnosis_licensed: boolean;
    reason: string;
  };
  regenerate: string;
}

export interface Connectivity {
  n_raters: number;
  n_subjects: number;
  n_components: number;
  bridge_subjects: string[];
  linkage_fragility: number | null;
  minimum_removal_set: string[];
  calls_double_scored: number;
  n_calls: number;
  link_type: string;
  verdict: "CONNECTED" | "FRAGILE" | "DISCONNECTED";
  rater_caseloads: Record<string, number>;
  remedy: { action: string; citation: string; minimum_linking_calls: number };
}

export interface Audit {
  domains: Record<string, DomainAudit>;
  connectivity: Connectivity;
  cross_instrument: {
    n_domains: number;
    reliability_ci_lower_bounds: Record<string, number>;
    all_lower_bounds_at_or_below_zero: boolean;
    statement: string;
  };
  redactions: Record<string, number>;
}

export interface Diagnosis {
  diagnosis_id: string;
  scope: string;
  domain: string;
  item_id: string;
  behavior: string;
  observed: {
    fails: number;
    denominator: number;
    rate: number;
    breadth_subjects: number;
    breadth_denominator: number;
    difficulty_p: number;
    discrimination_rpb: number | null;
    item_flags: string[];
  };
  corroboration: Record<string, unknown> | null;
  existing_curriculum_coverage: { covered: boolean; source: string };
  root_cause_primary: string;
  root_cause_secondary: string | null;
  evidence_for: { claim: string; basis: string; tag: string; regenerate: string | null }[];
  alternatives_rejected: { cause: string; reason: string }[];
  confidence: string;
  individual_attribution: {
    licensed: boolean;
    reason: string;
    remedy: { action: string; citation: string; minimum_linking_calls: number };
    statement: string;
  };
  recommended_intervention_class: string;
  is_training_intervention: boolean;
  human_decision: string | null;
}

export interface RunResponse {
  run_id: string;
  state: string;
  redactions: Record<string, number>;
  audit: Audit;
  diagnosis: Diagnosis;
  gate: { actions: string[] } & Record<string, unknown>;
}

export interface Transition {
  seq: number;
  from_state: string | null;
  to_state: string;
  at: string;
  actor: string;
  note: string;
  actor_verified: boolean;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("caliper_operator_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* the body was not json; the status line is all we have */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<Record<string, unknown>>("/api/health"),
  evidence: () => call<Record<string, unknown>>("/api/evidence"),
  createRun: () => call<RunResponse>("/api/runs", { method: "POST", body: "{}" }),
  getRun: (id: string) => call<Record<string, unknown>>(`/api/runs/${id}`),
  ledger: (id: string) => call<{ transitions: Transition[] }>(`/api/runs/${id}/ledger`),
  decide: (id: string, decision: string, actor: string, note = "") =>
    call<{ state: string; decided_by: string; decided_by_verified: boolean; note: string }>(
      `/api/runs/${id}/decision`,
      { method: "POST", body: JSON.stringify({ decision, actor, note }) },
    ),
  generate: (id: string) =>
    call<{ state: string; bundle: Record<string, unknown>; alignment: Record<string, unknown> }>(
      `/api/runs/${id}/generate`,
      { method: "POST", body: "{}" },
    ),
};

export const BASE_URL = BASE;

/** The sponsor's six tab design workbook for a run, as a download URL. */
export const workbookUrl = (runId: string) => `${BASE}/api/runs/${runId}/workbook`;
