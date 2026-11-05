# Issue tracker: GitHub

Issues for this repository live in GitHub Issues for `{{REPO_SLUG}}`. Use the `gh` CLI. In a clone with a remote for this repository, `gh` infers it from `git remote -v`; otherwise set `GH_REPO={{REPO_SLUG}}` for every command, including `gh api` paths that use `{owner}/{repo}`.

Reading is local work. Creating, editing, labelling, commenting on, or closing an issue is an external write: check [`authority.md`](authority.md) first.

## Read

- One issue with its discussion: `gh issue view <number> --json number,title,body,state,labels,comments`. Do not read an issue with `gh issue view <number> --comments`: when its output is captured it prints only the comments, without the title and body.
- Open issues: `gh issue list --state open --json number,title,labels`, narrowed with `--label`, `--assignee`, or `--search`.
- Issues and pull requests share one number space, so a bare `#<n>` may be either: try `gh issue view <n>` and fall back to `gh pr view <n>`.

## Write

- Before the first write of a session, confirm the target with `gh repo view --json nameWithOwner`. In a fork, `gh` can default to the upstream parent.
- Create: write the body to a file, then `gh issue create --title "<title>" --body-file <file>`.
- Comment: `gh issue comment <number> --body-file <file>`.
- Labels: `gh issue edit <number> --add-label <label>` or `--remove-label <label>`.
- Close: post the explanation with `gh issue comment` first, then `gh issue close <number>`. On an issue that is already closed, `gh issue close --comment` drops the comment and still exits 0.

## Relationships

- Parent and child: a GitHub sub-issue. With `gh` 2.94 or later use `gh issue create --parent <parent>` or `gh issue edit <parent> --add-sub-issue <child>`; older `gh` uses `gh api --method POST repos/{owner}/{repo}/issues/<parent>/sub_issues -F sub_issue_id=<child-database-id>`. Without sub-issues, put `Part of #<parent>` on the first line of the child's body.
- Blocking: a GitHub issue dependency. With `gh` 2.94 or later use `gh issue edit <child> --add-blocked-by <blocker>`; older `gh` uses `gh api --method POST repos/{owner}/{repo}/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-database-id>`. The database id comes from `gh api repos/{owner}/{repo}/issues/<n> --jq .id`, not from `#<n>`. Without dependencies, put `Blocked by: #<n>, #<n>` on the first line of the body.
- Open blockers: `gh api repos/{owner}/{repo}/issues/<n> --jq .issue_dependencies_summary.blocked_by`; `0` means the issue can start. An issue is unblocked when every blocker is closed.

## What skills expect

- "Fetch the ticket", or an issue reference such as `#123` in a commit message: read it as in **Read**.
- "File" or "publish to the issue tracker": create a GitHub issue as in **Write**, after the authority check.
- "Blocked by": use the dependency or the `Blocked by:` line from **Relationships**.
