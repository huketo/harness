# Releasing the hstack plugin

[Documentation](../index.md) · [Installation](installation.md) · [Agent configuration](../AGENT-CONFIG.md)

This guide owns three things: which changes need a changeset, how a release is cut, and how a release reaches Claude Code. [`../AGENT-CONFIG.md`](../AGENT-CONFIG.md) owns what the plugin ships, [`installation.md`](installation.md) owns the installer's host effects, and [`../agents/authority.md`](../agents/authority.md) owns the approval a release needs.

## How a release reaches Claude Code

The repository root is the `hstack` plugin marketplace. `.claude-plugin/marketplace.json` lists [`plugin/`](../../plugin/) as the `hstack` plugin, so the shipped `agents/` and `hooks/` files are the source itself. Only `plugin/.claude-plugin/plugin.json` and `plugin/hooks/hooks.json` are generated, and they are tracked in git; `mise run check` fails when they no longer match their sources.

The plugin version has one source: the `version` in the root `package.json`, which changesets bumps. `node plugin/build.mjs --host claude` copies it into `plugin.json`. Claude Code takes the plugin version from `plugin.json`, so **a merged change reaches Claude Code only when a release bumps the version**. A marketplace with auto-update on is refreshed after the first message of a session, and the new version loads in the next session or at `/reload-plugins`.

`mise run install` registers the marketplace from GitHub, installs the plugin at user scope, and turns auto-update on for it, because Claude Code leaves auto-update off for every marketplace except the official ones. The Antigravity CLI copy has no marketplace: `mise run install` refreshes it from the checkout.

## Add a changeset

A change needs a changeset when it changes what the plugin ships: `plugin/agents/`, `plugin/hooks/merge-guard.mjs`, `plugin/rules/`, or the generated `plugin/.claude-plugin/plugin.json` and `plugin/hooks/hooks.json`, whether edited directly or through `manifest.json` or `build.mjs`. A change that leaves every shipped file identical, such as a test, a skill, the installer, or `.rulesync/`, needs none; skills and permissions reach a host through `mise run install`, not through a plugin version.

1. Run `mise run setup` once per checkout. The step is complete when `node_modules/.bin/changeset` exists.
2. Run `npx changeset`, or write `.changeset/<short-name>.md` by hand:

   ```markdown
   ---
   "hstack": patch
   ---

   Deny a merge whose API URL names another host.
   ```

   The summary states the behavior a user of the guard or reviewer will observe. Choose `patch` for a fix, `minor` for a new capability or rule, and `major` when an existing allow or deny decision flips.
3. Commit the changeset file in the same change. The step is complete when `git diff main --name-only` lists the changeset beside the `plugin/` files it describes.

## Cut a release

A release publishes to every machine that auto-updates the marketplace, so it needs an explicit request that names the release ([`authority.md`](../agents/authority.md#separate-decision-every-time)). Merging the release pull request is the publication.

[`.github/workflows/release.yml`](../../.github/workflows/release.yml) prepares the release. On every push to `main` with pending changesets, it runs `npm run version-packages` and keeps one pull request titled `chore(release): version hstack` up to date. When a push leaves no pending changesets, as the merge of that pull request does, the workflow runs `npm run tag-release` (`changeset git-tag`). Because `privatePackages.tag` is `true`, that tags the current version as `v<version>`, and the action pushes the tag and creates a GitHub release from that version's `CHANGELOG.md` entry. A version that already has a tag is skipped, so other pushes to `main` create nothing. Nothing is published to npm: the package is private.

1. Read the open `chore(release): version hstack` pull request. The step is complete when its diff bumps `package.json` and `plugin/.claude-plugin/plugin.json` to the same version, adds the `CHANGELOG.md` entry, and deletes the consumed changeset files.
2. Land it only under the explicit release request.
3. Afterwards, the Release workflow run on `main` tags `v<version>` and creates its GitHub release. The step is complete when `gh release view v<version>` shows the `CHANGELOG.md` entry. To check a machine sooner, run `claude plugin marketplace update hstack` and `claude plugin update hstack@hstack`; the step is complete when `claude plugin list --json` reports the new version for `hstack@hstack`.

The workflow opens its pull request with the repository's `GITHUB_TOKEN`, which needs **Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests**. Without it the run fails at the pull-request step; after enabling it, rerun the workflow from the Actions tab (`workflow_dispatch`).

When Actions is unavailable, cut the same release by hand: on a branch from `main`, run `GITHUB_TOKEN=$(gh auth token) npm run version-packages`, run `mise run check`, and raise the result as `chore(release): version hstack`. After it lands, create the tag and release the workflow would have made: `gh release create v<version> --target <commit> --title v<version> --notes-file <file>`, where the file holds that version's `CHANGELOG.md` entry.
