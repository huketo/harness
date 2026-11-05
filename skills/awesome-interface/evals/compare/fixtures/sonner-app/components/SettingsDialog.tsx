"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { toast, Toaster } from "sonner";

async function saveSettings() {
  const res = await fetch("/api/settings", { method: "POST" });
  if (!res.ok) throw new Error("save failed");
}

export function SettingsDialog() {
  return (
    <Dialog.Root>
      <Dialog.Trigger className="rounded-lg border px-3 py-2">설정</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[100] bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[101] w-[min(420px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-[var(--bg)] p-6">
          <Dialog.Title className="text-lg font-semibold">설정</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm opacity-70">
            알림과 공유 기본값을 바꿉니다.
          </Dialog.Description>
          <button
            className="mt-6 rounded-lg bg-blue-600 px-4 py-2 text-white"
            onClick={() =>
              toast.promise(saveSettings(), {
                loading: "저장 중…",
                success: "설정을 저장했습니다.",
                error: "저장하지 못했습니다. 다시 시도해 주세요.",
              })
            }
          >
            저장
          </button>
          <Toaster position="top-center" />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
