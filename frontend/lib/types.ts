/**
 * Wire types, mirroring `backend/app/api/schemas.py`.
 *
 * Note what is *not* here: there is no `notes: string[]` or `warnings: string[]` on the
 * finding. Every caveat is a property of the object it qualifies — `citation.caveat`,
 * `dataset_limitation` — so no component can render a value while leaving its qualification
 * behind. That is a deliberate constraint carried across the wire, not an accident of
 * modelling.
 */

export type EpistemicType = "fact" | "inference" | "assumption" | "recommendation";
export type Confidence = "high" | "medium" | "low";
export type Mode = "extractive" | "generative";

export interface Citation {
  document_id: string;
  document_title: string;
  page_number: number;
  char_start: number;
  char_end: number;
  quote: string;
  is_verbatim: boolean;
  text_was_repaired: boolean;
  raw_quote: string | null;
  page_quality: string | null;
  caveat: string | null;
  reference: string;
}

export interface CriticNote {
  action: string;
  reason: string;
  from: string | null;
  to: string | null;
}

export interface Statement {
  id: string;
  type: EpistemicType;
  text: string;
  agent: string | null;

  citation?: Citation | null;
  dataset_provider?: string | null;
  dataset_retrieved_at?: string | null;
  dataset_limitation?: string | null;
  proxy_for?: string | null;

  derived_from: string[];
  transformation?: string | null;
  confidence?: Confidence | null;
  confidence_basis?: string | null;

  falsified_by?: string | null;
  why_needed?: string | null;
  demoted_from?: string | null;

  responds_to?: string | null;
  priority?: number | null;
  who?: string | null;

  was_weakened: boolean;
  rejected: boolean;
  critic_notes: CriticNote[];
}

export interface Conflict {
  kind: string;
  title: string;
  measured_side: string;
  regulatory_side: string;
  why_it_matters: string;
  resolvability: string;
  blocking_reasons: string[];
  what_would_resolve_it: string[];
  severity: number;
  is_decisive: boolean;
}

export interface BlindSpot {
  page_start: number;
  page_end: number;
  page_count: number;
  descriptor: string;
  following_context: string;
  matched_terms: string[];
  page_image_urls: string[];
}

export interface ChangeMyMind {
  current_position: string;
  would_change_if: string;
  type: string;
}

export interface AgentTrace {
  agent: string;
  duration_ms: number;
  ok: boolean;
  statements_produced: number;
  error: string | null;
  detail: Record<string, unknown>;
}

export interface CriticFinding {
  statement_id: string;
  action: string;
  reason: string;
  check: string;
}

export interface SitePanel {
  key: string;
  title: string;
  available: boolean;
  facts: Statement[];
  limitation: string | null;
  unavailable_reason: string | null;
}

export interface MapFeature {
  osm_type: string;
  osm_id: number;
  category: string;
  label: string;
  latitude: number;
  longitude: number;
  distance_m: number;
  osm_url: string;
  tags: Record<string, string>;
}

export interface GeocodeCandidate {
  display_name: string;
  latitude: number;
  longitude: number;
  place_type: string;
  is_area_centroid: boolean;
  extent_km: number | null;
  precision_note: string;
}

export interface Finding {
  id: string;
  question: string;
  location_query: string;
  created_at: string;
  mode: Mode;
  total_duration_ms: number;

  resolved_name: string | null;
  latitude: number | null;
  longitude: number | null;
  needs_disambiguation: boolean;
  geocode_candidates: GeocodeCandidate[];

  context: Statement[];
  evidence: Statement[];
  conflicts: Conflict[];
  unreadable: BlindSpot[];
  answer: string | null;
  change_my_mind: ChangeMyMind[];
  verify_next: Statement[];
  assumptions: Statement[];

  site_panels: SitePanel[];
  unavailable_sources: string[];
  traces: AgentTrace[];
  critic_findings: CriticFinding[];
  critic_checks_run: string[];
  coverage: Record<string, unknown>;
  map_features: MapFeature[];
}

export interface Corpus {
  title: string;
  sha256: string;
  page_count: number;
  readable_page_count: number;
  unreadable_page_count: number;
  text_coverage: number;
  total_chars: number;
  total_substitutions: number;
  pages_needing_repair: number;
  unreadable_ranges: number[][];
  quality_breakdown: Record<string, number>;
  chunk_count: number;
  risky_tables: { page: number; caption: string; risk: string; explanation: string }[];
  is_draft: boolean;
}

export interface PageDetail {
  page_number: number;
  quality: string;
  is_readable: boolean;
  char_count: number;
  substitutions: number;
  corruption_rate: number;
  caveat: string | null;
  text: string;
  raw_text: string | null;
  has_image: boolean;
  image_url: string | null;
  source_url: string;
}

export interface Health {
  ok: boolean;
  corpus_loaded: boolean;
  ingest_ms: number;
  mode: Mode;
  model: string | null;
  fixtures: {
    count: number;
    providers: string[];
    oldest_days: number | null;
    any_stale: boolean;
  };
}

export interface Metric {
  name: string;
  description: string;
  status: "measured" | "not_measured" | "not_applicable";
  value: number | null;
  unit: string;
  numerator: number | null;
  denominator: number | null;
  display: string;
  reason_not_measured: string | null;
  failure_count: number;
  failures: Record<string, unknown>[];
}

export interface EvalReport {
  run_at: string;
  mode: string;
  corpus: { title: string; sha256: string };
  case_count: number;
  metrics: Metric[];
  cases: {
    id: string;
    kind: string;
    question: string;
    checks: Record<string, boolean | null>;
    passed: boolean;
    latency_ms: number;
    evidence_pages: number[];
    blind_spots: number[][];
    note: string;
  }[];
}
