# Install plan

`mise run plan` shows which links, backups, and conflicts an install would produce, and `mise run install` applies them. A person reads the plan before letting the installer change the machine.

## Sub-features

- `plan-links` lists one `would link skill` line per skill directory for both the shared tree and the Claude Code tree.
- `plan-writes-nothing` leaves the home directory empty.
- `install-skills-only` creates the links and stops before permissions and plugins.
- `install-idempotent` reports no change on a second run.

## How to get to it (user POV)

- Run `mise run plan`, then `mise run install`, in the checkout.
- Run `node scripts/install.ts --skills-only --apply` on a shared workstation.

## Driving it with verify-hstack

Preconditions: the baseline in [README.md](README.md).

- **Plan.** Run `"$V" run "$RUN" -- "$NODE" scripts/install.ts --skills-only`. Exit status is `0`, every `would` line names a path under `$RUN/home`, the last line is `plan only: run \`mise run install\` to apply`, and `ls -A "$RUN/home"` prints nothing.
- **Install.** Add `--apply`. Exit status is `0`, and `readlink -f "$RUN/home/.claude/skills/<skill>"` ends in this checkout's `skills/<skill>`.
- **Second run.** Run the plan again. No line starts with `would`.
- **Proof.** Redirect each run to `$RUN/evidence/install-plan.txt` and `$RUN/evidence/install-apply.txt`.

## Gotchas

- Only `--skills-only` is driven here. The permission and plugin steps call `rulesync`, `claude`, and `agy`; `scripts/install.test.ts` and `scripts/safe-generate.test.ts` cover them with fakes, and a run against the real CLIs is a host change that `docs/agents/authority.md` governs.
- A plan that names a path outside `$RUN` means an agent-home variable leaked into the run. Stop and fix the isolation before applying.
