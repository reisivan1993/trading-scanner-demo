export interface SetupData {
  entry: string;
  stop: string;
  target_1: string;
  target_2: string | null;
  rr_ratio: number;
  shares: number;
  dollar_risk: string;
  dollar_pnl_t1: string;
}

export interface ScoreData {
  total: number;
  confluence: number;
  invalidation: number;
  rr: number;
  momentum: number;
  volume: number;
  pattern: number;
  cleanliness: number;
  web_intel_modifier: number;
}

export interface PatternData {
  name: string;
  direction: string;
  confidence: number;
}

export interface ChecklistItem {
  criterion: string;
  passed: boolean;
  value: string | null;
  notes: string;
}

export interface SetupResult {
  rank: number;
  symbol: string;
  direction: "long" | "short";
  setup: SetupData;
  score: ScoreData;
  patterns: PatternData[];
  checklist: ChecklistItem[];
  web_intel_notes: string[];
  current_price: string | null;
  basis: string;
}

export interface ScanMeta {
  run_id: string;
  started_at: string;
  completed_at: string | null;
  tickers_scanned: number;
  setups_found: number;
  setups_passed_risk: number;
}

export interface ScanResponse {
  meta: ScanMeta;
  cash_is_position: boolean;
  banner_message: string;
  results: SetupResult[];
  report_markdown: string;
}
