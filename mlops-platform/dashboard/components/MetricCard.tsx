"use client";

import clsx from "clsx";
import { TrendingDown, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";

/** Reusable metric card with variants, deltas, tooltips, and skeleton loading. */
export default function MetricCard({
  title,
  value,
  unit,
  delta,
  deltaLabel,
  color = "default",
  icon: Icon,
  loading = false,
  description
}: {
  title: string;
  value: string;
  unit?: string;
  delta?: number;
  deltaLabel?: string;
  color?: "default" | "success" | "warning" | "danger";
  icon?: LucideIcon;
  loading?: boolean;
  description?: string;
}) {
  const deltaTone = delta == null ? "neutral" : delta >= 0 ? "up" : "down";
  const DeltaIcon = deltaTone === "up" ? TrendingUp : TrendingDown;

  return (
    <div
      className={clsx("rounded-lg border bg-zinc-950 p-4", {
        "border-zinc-800": color === "default",
        "border-emerald-700/60": color === "success",
        "border-amber-700/60": color === "warning",
        "border-rose-700/60": color === "danger"
      })}
    >
      <div className="flex items-start justify-between gap-3">
        <Tooltip.Provider delayDuration={150}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <div className="min-w-0">
                <div className="text-xs text-zinc-400">{title}</div>
              </div>
            </Tooltip.Trigger>
            {description ? (
              <Tooltip.Portal>
                <Tooltip.Content
                  className="max-w-[280px] rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 shadow-lg"
                  sideOffset={8}
                >
                  {description}
                  <Tooltip.Arrow className="fill-zinc-800" />
                </Tooltip.Content>
              </Tooltip.Portal>
            ) : null}
          </Tooltip.Root>
        </Tooltip.Provider>

        {Icon ? (
          <div className="rounded-md border border-zinc-800 bg-zinc-950 p-2 text-zinc-200">
            <Icon className="h-4 w-4" />
          </div>
        ) : null}
      </div>

      <div className="mt-3">
        {loading ? (
          <div className="h-7 w-36 animate-pulse rounded bg-zinc-900" />
        ) : (
          <div className="flex items-end gap-2">
            <div className="text-2xl font-semibold tracking-tight text-zinc-50">
              {value}
            </div>
            {unit ? <div className="pb-0.5 text-xs text-zinc-400">{unit}</div> : null}
          </div>
        )}

        {delta != null ? (
          <div className="mt-2 flex items-center gap-2 text-xs">
            <div
              className={clsx("inline-flex items-center gap-1", {
                "text-emerald-300": deltaTone === "up",
                "text-rose-300": deltaTone === "down"
              })}
            >
              <DeltaIcon className="h-3.5 w-3.5" />
              <span>{delta >= 0 ? "+" : ""}{delta.toFixed(3)}</span>
            </div>
            {deltaLabel ? <div className="text-zinc-500">{deltaLabel}</div> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
