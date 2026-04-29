"use client";

import clsx from "clsx";

export default function MetricCard({
  title,
  value,
  footer,
  tone = "neutral"
}: {
  title: string;
  value: string;
  footer?: string;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="flex items-center justify-between">
        <div className="text-xs text-zinc-400">{title}</div>
        <div
          className={clsx("h-2 w-2 rounded-full", {
            "bg-emerald-400": tone === "good",
            "bg-amber-400": tone === "warn",
            "bg-rose-400": tone === "bad",
            "bg-zinc-600": tone === "neutral"
          })}
        />
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
        {value}
      </div>
      {footer ? <div className="mt-1 text-xs text-zinc-500">{footer}</div> : null}
    </div>
  );
}
