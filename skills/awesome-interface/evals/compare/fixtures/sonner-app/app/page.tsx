"use client";

import { toast, Toaster } from "sonner";
import { SettingsDialog } from "@/components/SettingsDialog";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function Page() {
  return (
    <main className="relative isolate mx-auto max-w-3xl p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">프로젝트</h1>
        <div className="flex gap-2">
          <ThemeToggle />
          <SettingsDialog />
        </div>
      </header>
      <button
        className="mt-6 rounded-lg border px-4 py-2"
        onClick={() => toast.success("프로젝트를 복제했습니다.")}
      >
        복제
      </button>
      <Toaster position="bottom-right" />
    </main>
  );
}
