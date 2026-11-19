# hstack

## 0.2.0

### Minor Changes

- [#8](https://github.com/huketo/harness/pull/8) [`fc925e1`](https://github.com/huketo/harness/commit/fc925e1230b2ace8230ca99f5f297519ed3c39d4) Thanks [@huketo](https://github.com/huketo)! - Ship the common working rules (`rules/common.md`) to Claude Code through a SessionStart hook and to Antigravity CLI as an always-on rule; they defer to each repository's `AGENTS.md` and `docs/agents/`. The Antigravity rules drop their verification section, which the common rules now carry.

## 0.1.0

### Minor Changes

- [#1](https://github.com/huketo/harness/pull/1) [`5fd802f`](https://github.com/huketo/harness/commit/5fd802fcd10e0443056e5cfb931ccccc3860fb53) Thanks [@huketo](https://github.com/huketo)! - First release of the `hstack` plugin marketplace: the merge guard and read-only reviewer for Claude Code and the merge guard and rules for Antigravity CLI ship as the `hstack` plugin, Claude Code updates it from this repository, and `mise run install` links the skills and applies the credential denies without dropping an existing setting.
