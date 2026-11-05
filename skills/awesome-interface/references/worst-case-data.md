# Worst-case data

Read this from [stress testing](stress-test.md) when choosing fixture values. Each value must be something a real user could produce, or the actual limit from the project's schema, column or API contract. Random filler such as forty repeated letters proves nothing. If no limit exists, report the field as unbounded and use a long but believable value. Use `example.com`, `example.org` or `.test` for emails and URLs.

Pick the rows that match the fields the component renders. Spread different failures across the first visible items, as real data does, instead of stacking them into one row.

## Text and identity

| Value | Tends to break |
| --- | --- |
| Long hyphenated or multi-part name: `Aleksandra Wiśniewska-Kowalczyk`, `María José de la Cruz y Fernández` | Single-line rows, naive first-plus-last initials, sorting by "last name" |
| One- or two-letter name: `J`, `Jo` | Empty-looking columns, single-character initials, tiny link targets |
| Name missing; only an email or ID present | Initials or display-name code that throws or prints `undefined`; the fallback must exist |
| Leading spaces or repeated spaces: `  Sam   Lee ` | Initials from empty words, odd gaps |
| Emoji first or ZWJ sequence: `🦊 Fox`, `👩🏽‍💻 Priya` | `charAt(0)` or `slice` cutting a surrogate pair or sequence |
| CJK or RTL name: `王秀英`, `نور الهدى عبد الرحمن` | Word-based initials, line breaking, icon and punctuation placement without `dir="auto"` |
| Stacked diacritics: `Đặng Thị Ngọc Hân` | Clipping under tight `line-height` with `overflow: hidden` |
| Unbreakable email or URL: `bartholomew.fitzgerald@northwind-industries-holdings.example.com` | Siblings pushed out of the row; end truncation hiding the part that differs |
| Markup-like text: `<EMEA> Sales`, `<b>x</b>`, `&amp;` | Strings inserted as HTML instead of text: lost content and script injection |
| Long translated label: `Benachrichtigungseinstellungen` | Unbreakable labels and badges |
| Empty, whitespace-only, or newline-containing title | Collapsed headings, zero-height rows, doubled row height |

## Numbers, collections and time

| Value | Tends to break |
| --- | --- |
| `0` and `1` | Empty states, "1 members", "1 days ago", division by zero in percentages |
| `1284`, `1000000`, a live change from `99` to `100` | Missing separators, badge width, width jitter without `tabular-nums` |
| `null`, `undefined`, `NaN` | Rendered literally |
| Zero items, one item, page size and page size plus one, an unpaginated realistic maximum | Missing empty state, one-card grids, off-by-one counts, render cost |
| Null or zero timestamp (`1970-01-01`), a future date, now | "20000 days ago", "-3 days ago", "0 seconds ago" |
| A time near midnight in another time zone | A different calendar day than the user expects |

Format numbers and relative time with `Intl` and the project's existing helpers rather than hand-built strings.

## Media and states

| Value | Tends to break |
| --- | --- |
| No image, or an image URL that fails | Broken-image icon instead of the fallback; fallback size parity |
| Very wide or very tall image | Distortion without `object-fit`; card height blowout |
| Every enum status in one list | Badge widths and row alignment |
| Partial data: some optional fields filled, others missing | Misaligned rows, stray separators |
| Loading, API error, no permission | Missing states, raw error text, layout changes when actions disable |

Environment cases (320px container, 200% zoom, dark theme, RTL, touch-only input) remain in the stress-test scenario table.
