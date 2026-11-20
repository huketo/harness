# Worst-case data

Read this from [stress testing](stress-test.md) when choosing fixture values, and from [change review](change-review.md#swapped-controls-and-changed-writes) when a change swaps or edits an input control. Each value must be something a real user could produce, or the actual limit from the project's schema, column or API contract. Random filler such as forty repeated letters proves nothing. If you find no limit, report the field as "no limit found": the search did not show that none exists. Then use a long but believable value. Use `example.com`, `example.org` or `.test` for emails and URLs.

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

Format numbers and relative time with `Intl` and the project's existing helpers rather than hand-built strings.

## Media and states

| Value | Tends to break |
| --- | --- |
| No image, or an image URL that fails | Broken-image icon instead of the fallback; fallback size parity |
| Very wide or very tall image | Distortion without `object-fit`; card height blowout |
| Every enum status in one list | Badge widths and row alignment |
| Partial data: some optional fields filled, others missing | Misaligned rows, stray separators |
| Loading, API error, no permission | Missing states, raw error text, layout changes when actions disable |

## Input equivalence classes

Run the class for every control of that kind the task reaches, typing and pasting each value. Record three results per row: what the control shows, what it commits or sends (the form value or request body), and whether submit is enabled. For a swapped control, run the same rows on the old and new control and compare them row by row. Count requests with `guard.log` or the network log, and use `--bodies` when the sent value matters (see [capture and compare](review.md#capture-and-compare)).

**Numbers and amounts.** A rejected value keeps its text in the box and submit disabled; it never submits the last good value.

| Value | Tends to break |
| --- | --- |
| `2.5`, `.5`, `5.`, `12.50`, `0.123456789` | Integer parsing that commits `25` for `2.5`; an amount sent as `12.5`; lost precision |
| `-3`, `-0`, `+3`, a Unicode minus `−3` | A digit filter that commits `3` for `-3`; the Unicode minus rejected or misread |
| `1e3`, a 20-digit number | Exponent read as digits (`13`); values past `Number.MAX_SAFE_INTEGER` silently rounded |
| `1,234.56`, `1 000`, `  42 `, `007` | Group separators and spaces misread for the locale; leading zeros dropped or kept inconsistently |
| Empty, `abc`, `12abc`, `1.2.3` | A prefix parse that commits `12` for `12abc`; submit enabled while the text does not parse |

**Uploads.** The `accept` attribute filters only the file picker; a dropped or pasted file reaches the validation code directly.

| File | Tends to break |
| --- | --- |
| Allowed MIME type, no extension | A check by extension refuses it |
| Allowed extension, generic MIME type (`application/octet-stream`) | A check by MIME type refuses it |
| Upper-case extension: `SCAN.PDF` | A case-sensitive extension match |
| Allowed extension, wrong MIME type | Accepted on its name alone |
| A type the control must refuse | Silently dropped, or accepted with no error |

**Enter and Space.** Count writes after each press; expect none from the press that opens a surface and one per intended submit.

| Press | Tends to break |
| --- | --- |
| Enter, then Space, immediately after a menu, picker or dialog opens, at 0 ms and 300 ms | The opening keypress also selects the first option and writes |
| Enter pressed twice quickly, or held, on a submit | Two submissions before the first response returns |

**Dates.** Run every date surface under `America/Los_Angeles`, west of UTC, and `Asia/Tokyo` and `Asia/Seoul`, east of it, through the browser context's time zone (Playwright `timezoneId`) or the host browser tool. Compare the value sent, not the label: `2025-03-15` entered comes back as `2025-03-15` in every zone. Keep a date-only value a string or a UTC date.

| Value | Tends to break |
| --- | --- |
| `2025-03-15` parsed with `new Date("2025-03-15")` | UTC midnight, shown as March 14 west of UTC |
| A local-midnight `Date` sent through `toISOString()` | `2025-03-14T15:00:00.000Z` east of UTC: the previous day reaches the server |
| A moment near midnight shown in another zone | A different calendar day than the user expects |

A shift the old code already had is still a defect: report it as such, never keep it for parity, and fix it as its own named change.

Environment cases (320px container, 200% zoom, dark theme, RTL, touch-only input) remain in the stress-test scenario table.
