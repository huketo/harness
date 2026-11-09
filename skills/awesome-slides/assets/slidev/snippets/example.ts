// ⟨Replace with code imported from the real source the talk explains.⟩
export function retryDelay(attempt: number) {
  const capped = Math.min(attempt, 6)
  return 100 * 2 ** capped
}
