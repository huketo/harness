# Issue tracker: GitLab

Issues for this repository live in GitLab Issues for `{{REPO_SLUG}}` on `{{GITLAB_HOST}}`. Use the `glab` CLI. In a clone with a remote for this project, `glab` infers the host and project from `git remote -v`; otherwise add `--repo https://{{GITLAB_HOST}}/{{REPO_SLUG}}` to every command, and for `glab api` set `GITLAB_HOST={{GITLAB_HOST}}` and name the project by its URL-encoded path instead of `:id`.

Reading is local work. Creating, editing, labelling, commenting on, or closing an issue is an external write: check [`authority.md`](authority.md) first.

## Read

- One issue with its discussion: `glab issue view <iid> --comments`. Structured: `glab issue view <iid> --output json`.
- Open issues: `glab issue list --output json --per-page 100`, narrowed with `--label`, `--assignee`, or `--search`; add `--page <n>` until a page returns fewer items than requested.
- GitLab numbers issues (`#<n>`) and merge requests (`!<n>`) separately, so each reference names one item.

## Write

- Create: `glab issue create --title "<title>" --description "$(cat <file>)" --yes`.
- Comment: `glab issue note <iid> --message "<text>"`. GitLab calls comments notes.
- Labels: `glab issue update <iid> --label <label>` or `--unlabel <label>`; separate several labels with commas.
- Close: `glab issue close <iid>` takes no comment, so post the explanation with `glab issue note` first.
- Merge requests use the same shape: `glab mr view`, `glab mr note`, `glab mr update`.

## Relationships

- Related issues: `glab issue create --linked-issues <iid> --link-type relates_to`. Read an issue's links with `glab api projects/:id/issues/<iid>/links`.
- Blocking: GitLab's native blocking link, added by posting the quick action `/blocked_by #<blocker>` as a note (`glab issue note <child> --message "/blocked_by #<blocker>"`). Native blocking links need a paid tier; where they are unavailable, put `Blocked by: #<n>, #<n>` on the first line of the description. An issue is unblocked when every blocker is closed.

## What skills expect

- "Fetch the ticket", or an issue reference such as `#123` in a commit message: run `glab issue view <iid> --comments`.
- "File" or "publish to the issue tracker": create a GitLab issue as in **Write**, after the authority check.
- "Blocked by": use the blocking link or the `Blocked by:` line from **Relationships**.
