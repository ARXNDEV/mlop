"use client";

import { Fragment, useMemo, useState } from "react";

import clsx from "clsx";

import type { MlflowRun } from "@/lib/types";

type SortKey = "start_time" | "status" | "accuracy" | "f1_score" | "roc_auc";

function metric(run: MlflowRun, key: string): number {
  const v = run.metrics[key];
  if (v == null) return Number.NEGATIVE_INFINITY;
  return v;
}

export default function ExperimentsTable({ runs }: { runs: MlflowRun[] }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("start_time");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    const s = [...runs];
    s.sort((a, b) => {
      let av = 0;
      let bv = 0;
      if (sortKey === "start_time") {
        av = a.start_time;
        bv = b.start_time;
      } else if (sortKey === "status") {
        av = a.status.localeCompare(b.status);
        bv = 0;
      } else {
        av = metric(a, sortKey);
        bv = metric(b, sortKey);
      }
      const diff = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? diff : -diff;
    });
    return s;
  }, [runs, sortKey, sortDir]);

  const compareRuns = useMemo(() => {
    if (selected.length !== 2) return null;
    const a = runs.find((r) => r.run_id === selected[0]);
    const b = runs.find((r) => r.run_id === selected[1]);
    if (!a || !b) return null;
    return { a, b };
  }, [runs, selected]);

  const onSort = (k: SortKey) => {
    if (k === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(k);
    setSortDir("desc");
  };

  const onToggleSelect = (runId: string) => {
    setSelected((cur) => {
      if (cur.includes(runId)) return cur.filter((x) => x !== runId);
      if (cur.length >= 2) return [cur[1], runId];
      return [...cur, runId];
    });
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-medium text-zinc-100">MLflow runs</div>
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <div>{runs.length} runs</div>
          <button
            type="button"
            className={clsx(
              "rounded-md border px-3 py-2 transition",
              selected.length === 2
                ? "border-zinc-700 bg-zinc-900 text-zinc-100"
                : "border-zinc-800 bg-zinc-950 text-zinc-500"
            )}
            disabled={selected.length !== 2}
            onClick={() => {}}
          >
            Compare (select 2)
          </button>
        </div>
      </div>

      {compareRuns ? (
        <div className="mb-4 rounded-md border border-zinc-800 bg-zinc-900/30 p-3 text-xs">
          <div className="mb-2 font-medium text-zinc-200">Comparison</div>
          <div className="grid gap-2 md:grid-cols-3">
            {(["accuracy", "f1_score", "roc_auc"] as const).map((k) => {
              const av = compareRuns.a.metrics[k];
              const bv = compareRuns.b.metrics[k];
              const delta = (bv ?? 0) - (av ?? 0);
              return (
                <div key={k} className="rounded border border-zinc-800 bg-zinc-950 p-2">
                  <div className="text-zinc-400">{k}</div>
                  <div className="mt-1 flex items-center justify-between">
                    <div className="text-zinc-200">{(av ?? 0).toFixed(4)}</div>
                    <div className="text-zinc-200">{(bv ?? 0).toFixed(4)}</div>
                    <div
                      className={clsx("font-medium", {
                        "text-emerald-300": delta > 0,
                        "text-rose-300": delta < 0,
                        "text-zinc-400": delta === 0
                      })}
                    >
                      {delta >= 0 ? "+" : ""}
                      {delta.toFixed(4)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-xs text-zinc-400">
              <th className="py-2 pr-3 font-medium">Select</th>
              <th className="py-2 pr-3 font-medium">Run ID</th>
              <th className="cursor-pointer py-2 pr-3 font-medium" onClick={() => onSort("start_time")}>
                Start
              </th>
              <th className="cursor-pointer py-2 pr-3 font-medium" onClick={() => onSort("status")}>
                Status
              </th>
              <th className="cursor-pointer py-2 pr-3 font-medium" onClick={() => onSort("accuracy")}>
                Accuracy
              </th>
              <th className="cursor-pointer py-2 pr-3 font-medium" onClick={() => onSort("f1_score")}>
                F1
              </th>
              <th className="cursor-pointer py-2 pr-3 font-medium" onClick={() => onSort("roc_auc")}>
                ROC AUC
              </th>
              <th className="py-2 pr-3 font-medium">Model Version</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const isExpanded = !!expanded[r.run_id];
              const isSelected = selected.includes(r.run_id);
              return (
                <Fragment key={r.run_id}>
                  <tr
                    className={clsx(
                      "border-b border-zinc-900 transition hover:bg-zinc-900/40",
                      isSelected && "bg-zinc-900/30"
                    )}
                    onClick={() => setExpanded((e) => ({ ...e, [r.run_id]: !isExpanded }))}
                  >
                    <td className="py-2 pr-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => onToggleSelect(r.run_id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs text-zinc-300">
                      {r.run_id.slice(0, 12)}
                    </td>
                    <td className="py-2 pr-3 text-zinc-300">
                      {new Date(r.start_time).toLocaleString()}
                    </td>
                    <td className="py-2 pr-3 text-zinc-300">{r.status}</td>
                    <td className="py-2 pr-3 text-zinc-50">{(r.metrics.accuracy ?? 0).toFixed(4)}</td>
                    <td className="py-2 pr-3 text-zinc-50">{(r.metrics.f1_score ?? 0).toFixed(4)}</td>
                    <td className="py-2 pr-3 text-zinc-50">{(r.metrics.roc_auc ?? 0).toFixed(4)}</td>
                    <td className="py-2 pr-3 text-zinc-300">{r.tags.model_version ?? "—"}</td>
                  </tr>
                  {isExpanded ? (
                    <tr className="border-b border-zinc-900">
                      <td colSpan={8} className="bg-zinc-950/60 p-3">
                        <div className="grid gap-3 md:grid-cols-3">
                          <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                            <div className="mb-2 text-xs font-medium text-zinc-200">Params</div>
                            <pre className="max-h-48 overflow-auto text-xs text-zinc-400">
                              {JSON.stringify(r.params, null, 2)}
                            </pre>
                          </div>
                          <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                            <div className="mb-2 text-xs font-medium text-zinc-200">Metrics</div>
                            <pre className="max-h-48 overflow-auto text-xs text-zinc-400">
                              {JSON.stringify(r.metrics, null, 2)}
                            </pre>
                          </div>
                          <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                            <div className="mb-2 text-xs font-medium text-zinc-200">Tags</div>
                            <pre className="max-h-48 overflow-auto text-xs text-zinc-400">
                              {JSON.stringify(r.tags, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
