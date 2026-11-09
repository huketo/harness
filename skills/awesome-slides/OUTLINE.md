# Outline

`outline.md` is the storyboard: the argument the deck makes, slide by slide, before any design. The person approves it before phase 3 starts, because the design is judged on these real slides.

## Shape the argument

Pick the working shape that matches the brief's outcome, then bend it to the evidence:

- **Decision:** context → criteria → options → consequences → recommendation → the requested decision.
- **Technical explanation:** behavior that motivates → system model → mechanism → evidence or demo → limits → practical use.
- **Teaching:** learner goal → prerequisite model → worked example → practice → check → transfer.
- **Research:** question → method and boundaries → observations → interpretation → implications → uncertainty.
- **Status or incident:** expected → observed → impact → contributing conditions → response → current risk and next step.

Titles alone should tell the story: setup, turn, evidence, conclusion. A content slide's title is an assertion its body proves; covers, dividers, exercises, and questions keep functional labels.

## Per-slide record

```markdown
status: draft | approved | assumed

## 3. <assertion title>
- Purpose: the change this slide causes in the audience
- Evidence: source or artifact, with its class — measured | controlled demo | synthetic | unverified
- Visual: comparison | chart | table | code | diagram | image | timeline | text
- Clicks: none | the order in which things appear, and why each step earns a click
- PDF: final | steps — `steps` only when watching the sequence is itself the point
- Notes: what to say first, the explanation, caveats, the transition to the next slide
- Time: approximate share of the duration
```

## Evidence discipline

- Ground technical claims in the code, version, command output, or primary documentation they describe; cite repository paths and symbols, not machine paths.
- A comparison names its candidates, conditions, metric, unit, aggregation, and source. With no reliable measurement, use a qualitative trade-off or a labelled benchmark plan.
- Code views do one teaching job each and come from the real source when it exists.
- Cases keep observation → interpretation → action → verification as separate steps.
- Synthetic values and mock screens carry a visible label. Gaps stay visible as "unverified" rather than filled with plausible detail.
- Revising existing material: map every required claim, figure, qualifier, and note to its new slide, notes, appendix, or an approved omission.

## Gate

Show the person the outline as titles plus one line per slide (purpose and visual), with the full record in `outline.md`. Stop until they approve or change it.

**Done** when every required claim and source has a slide, the titles read as the argument, the time budget fits the duration with a planned cut path, and `status` is `approved` or `assumed`.
