# Issue tracker: local Markdown

Issues for this repository live as Markdown files under `.scratch/`. They are ordinary files: writing one is local work, and committing it follows [`authority.md`](authority.md). They are tracked by git unless `.gitignore` lists `.scratch/`.

## Layout

- One directory per feature: `.scratch/<feature>/`.
- The feature's spec: `.scratch/<feature>/spec.md`.
- One file per issue: `.scratch/<feature>/issues/<NN>-<slug>.md`, numbered from `01` in creation order. Never combine several issues in one file.
- The first lines of an issue file hold its state: `Status: open`, `in-progress`, `done`, or `wontfix`, and an optional `Blocked by: <NN>, <NN>` naming issue numbers in the same feature.
- Discussion is appended at the end of the file under a `## Comments` heading, newest last.

## Read

- The person usually names the path or `<feature>` and number. Otherwise search `.scratch/*/issues/` by title or content.
- Open issues: files whose `Status:` is `open` or `in-progress`.

## Write

- New issue: create the next numbered file in the feature's `issues/` directory, creating the directory when needed.
- Comment: append under `## Comments`.
- Close: set `Status: done` or `Status: wontfix` and append the reason under `## Comments`.

## What skills expect

- "Fetch the ticket": read the issue file.
- "File" or "publish to the issue tracker": create the next numbered issue file.
- "Blocked by": the `Blocked by:` line. An issue is unblocked when every file it lists has `Status: done`.
