# Native, editable PowerPoint with officecli

Use this route when the delivered PPTX must contain editable text, shapes, tables, or charts. The web starters are not a native-PPTX conversion engine. Keep the storyboard and selected style recipe, but author native objects rather than inserting an image of each slide.

## Establish the actual tool contract

Read the installed `officecli` skill. Run `officecli --version` and `officecli help pptx shape`, then the schema for each object you will use (`slide`, `table`, `chart`). Property names and rendering capabilities follow that installed version; do not guess a command from another Office library. Installation requires the environment's authority; a missing binary is not permission to run a remote installer.

Start with a title, the densest content slide, and a technical visual if needed. Read the created presentation dimensions before assigning coordinates. Use unit-qualified geometry and a shared margin/column scheme. Translate the selected style's color and typography roles into native shape properties; HTML pixels and PowerPoint points are not interchangeable. Use fonts present in the delivery environment, including the East Asian font slot for Korean.

## A concrete editable-text starting point

These commands use the officecli 1.0.148 DOM syntax. Run them in a new output directory, not over an existing user deck. Set `OFFICECLI_NO_AUTO_RESIDENT=1` for short one-shot commands if background residents are unsuitable; for a long session follow the officecli skill's open/save/close workflow.

```sh
officecli create deck.pptx
officecli add deck.pptx / --type slide --prop background=F7F5EF
officecli add deck.pptx '/slide[1]' --type shape \
  --prop name=Claim --prop text='검색 시간을 줄일 수 있는지 검증합니다' \
  --prop x=1.5cm --prop y=2cm --prop width=21cm --prop height=3cm \
  --prop size=32pt --prop font='Noto Sans CJK KR' \
  --prop color=16243A --prop fill=none --prop line=none --prop autoFit=none
officecli set deck.pptx '/slide[1]' \
  --prop notes='0:30. 합성 예시이며 실제 성과가 아니다. 다음 장에서 측정 조건을 설명한다.'
officecli get deck.pptx '/slide[1]' --depth 2 --json
```

This is an editable example, not a complete design or real performance claim. `add` returns a stable shape ID; use that returned path for subsequent edits instead of assuming positional shape 1. `autoFit=none` exposes text that needs more room: inspect the rendering and fix the composition, rather than silently shrinking every text box. Set visible source/caveat text as another native text object, not only in notes.

## Construct the message with native objects

- **Comparison:** use a native table for editable labels and values. Inspect `officecli help pptx table` for the current rows/columns/data schema. Keep a separate visible caveat beside the comparison; do not embed labels into a background image.
- **Chart:** use native chart data when users must edit the series. Inspect the chart schema and read back the values and units. If a custom diagram cannot remain fully editable, disclose exactly which objects are images.
- **System flow:** use named native shapes and connectors with a shared grid. Verify connector endpoints after moving boxes. Preserve labels as text and group related objects only after they render correctly.
- **Case story:** lay out observation, interpretation, change, and validation as distinct related text groups. Do not invent a measured outcome to complete the template.
- **Notes:** set explanation, transitions, and timing on each speaker-led slide. Put decision conditions and evidence on the visible slide for reading decks.

## Verify the actual file

```sh
officecli validate deck.pptx
officecli view deck.pptx text
officecli view deck.pptx html -o preview.html
```

Flush with `save` or `close` before a non-officecli renderer reads the file if using resident mode. Open the preview and inspect every slide at presentation size; schema validation alone says nothing about wrapping or visual quality. Confirm text/shapes remain editable by inspecting the DOM and changing a copy of a representative object. Query the installed `view` help for screenshot/PDF support; exporters may be separate plugins. A browser HTML preview is not proof of identical PowerPoint rendering. When PowerPoint or another final consumer is available, open the delivered PPTX there and inspect fonts, notes, text boxes, charts, and connectors. Report an unavailable final-consumer check explicitly.

Source: the installed officecli skill and runtime `help pptx shape` / `help pptx slide` schemas. This native-PPTX recipe is an original integration, not a feature supplied by the four web-presentation research repositories.
