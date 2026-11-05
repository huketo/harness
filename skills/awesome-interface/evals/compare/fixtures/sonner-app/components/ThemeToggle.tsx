"use client";

import { useTheme } from "next-themes";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const next = resolvedTheme === "dark" ? "light" : "dark";
  return (
    <button className="rounded-lg border px-3 py-2" onClick={() => setTheme(next)}>
      {resolvedTheme === "dark" ? "밝은 화면" : "어두운 화면"}
    </button>
  );
}
