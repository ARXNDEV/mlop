"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import clsx from "clsx";
import { Activity, FlaskConical, GitCompare, Waves } from "lucide-react";

const nav = [
  { href: "/", label: "Overview", icon: Activity },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/ab-test", label: "A/B Test", icon: GitCompare },
  { href: "/drift", label: "Drift", icon: Waves }
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 px-2">
        <div className="text-sm font-semibold tracking-wide text-zinc-100">
          mlops-platform
        </div>
        <div className="text-xs text-zinc-500">Observability</div>
      </div>

      <nav className="flex flex-col gap-1">
        {nav.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-2 rounded-md px-2 py-2 text-sm transition",
                active
                  ? "bg-zinc-900 text-zinc-50"
                  : "text-zinc-300 hover:bg-zinc-900/60 hover:text-zinc-50"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto px-2 pt-6 text-xs text-zinc-600">
        Local dev mode
      </div>
    </div>
  );
}
