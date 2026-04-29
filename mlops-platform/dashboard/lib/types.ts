export type MetricsSummary = {
  model_accuracy: Record<string, number>;
  model_drift_score: Record<string, number>;
  p95_latency_ms: number;
  ab_split_percent: number;
  active_model_version: Record<string, string>;
};

export type ABTestSummary = {
  version: "v1" | "v2";
  n_requests: number;
  avg_latency_ms: number;
  avg_confidence: number;
  accuracy: number | null;
  p_value: number | null;
};

export type ABWinner = { winner: string; p_value: number | null };

export type ABHistoryPoint = { hour: string; count: number };

export type ABHistory = { v1: ABHistoryPoint[]; v2: ABHistoryPoint[] };

export type DriftPoint = { time: string; drift_score: number };

export type MlflowRun = {
  run_id: string;
  start_time: number;
  status: string;
  metrics: Record<string, number>;
  params: Record<string, string>;
  tags: Record<string, string>;
};
