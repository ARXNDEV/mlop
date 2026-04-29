"use client";

import { useTheme } from "next-themes";

import { Moon, Sun } from "lucide-react";

export default function Navbar() {
  const { theme, setTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <div className="flex h-14 items-center justify-between px-6">
      <div className="text-sm font-medium text-zinc-100">MLOps Platform</div>
      <button
        type="button"
        onClick={() => setTheme(isDark ? "light" : "dark")}
        className="inline-flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 transition hover:bg-zinc-900"
      >
        {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        <span>{isDark ? "Light" : "Dark"}</span>
      </button>
    </div>
  );
}
