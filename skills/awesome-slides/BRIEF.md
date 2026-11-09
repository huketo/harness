# Brief

`brief.md` is the contract the rest of the deck answers to. Facts come from the request, supplied files, and the environment; decisions come from the person.

## Fields

```markdown
status: draft | approved | assumed

- Audience: who reads or hears it, and what they already know
- Outcome: what they should understand, decide, approve, or do afterward
- Mode: presentation | reading | both
- Deliverables: deck.html (presentation, both) · deck.pdf (reading, both, or requested)
- Duration and setting: minutes, room or solo reading, projector or screen
- Language
- Evidence: every supplied file, repository, dataset, and source, with what each establishes
- Design input: supplied references or DESIGN.md, brand rules — or none
- Constraints: privacy, deadlines, fixed content, required wording
- Run style: gated (default) | finish without questions
- Assumed: each field decided without the person, with the reason
```

**Mode** is an editorial contract:

- **presentation** — the speaker carries explanation in notes; slides carry the focal message and the evidence the room needs. Ships `deck.html`.
- **reading** — the slide alone carries context, definitions, figures, caveats, sources, and conclusion. Ships `deck.pdf`; notes hold authoring remarks only.
- **both** — one source; `deck.html` for the talk and `deck.pdf` for readers. Material meant only for readers goes into visible slide text that the speaker can skip, not into a second copy of the deck.

## Interview

1. Read everything supplied and inspect anything the request points at. Fill every field the material already answers.
2. Gated run: ask the person one question at a time about each remaining field that is genuinely theirs: the outcome, mode, audience, run style. Give a recommended answer with its reason so a plain "yes" settles it. Look facts up yourself instead of asking for them.
3. Finish-without-questions or unattended run: ask nothing; decide each open field from the material and list it under `Assumed` with the reason.
4. A missing design input is a valid answer ("none"); phase 3 handles it.

The brief has no approval stop. Its status is `approved` when every field came from the request, the supplied material, or the person's answers, and `assumed` when any field is in `Assumed`.

**Done** when every field holds a value or an explicit "unknown — affects X", and the status is `approved` or `assumed`.
