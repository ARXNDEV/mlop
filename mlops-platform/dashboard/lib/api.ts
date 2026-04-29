import type { ABHistory, ABTestSummary, ABWinner, MetricsSummary } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export function fetchMetricsSummary(): Promise<MetricsSummary> {
  return getJson<MetricsSummary>("/metrics/summary");
}

export async function fetchABSummary(): Promise<{ v1: ABTestSummary; v2: ABTestSummary }> {
  const res = await getJson<ABTestSummary[]>("/ab-test/summary");
  const v1 = res.find((s) => s.version === "v1") ?? null;
  const v2 = res.find((s) => s.version === "v2") ?? null;
  if (!v1 || !v2) {
    throw new Error("Missing AB summaries");
  }
  return { v1, v2 };
}

export function fetchABWinner(): Promise<ABWinner> {
  return getJson<ABWinner>("/ab-test/winner");
}

export function fetchABHistory(): Promise<ABHistory> {
  return getJson<ABHistory>("/ab-test/history");
}
