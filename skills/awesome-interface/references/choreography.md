# Choreography: several elements moving together

Read this when two or more elements move in response to the same event: a hero or page entrance, a staggered list, a view swap inside a container, a multi-step flow, an item leaving while its siblings close the gap, or a component with several moving parts. It owns order, overlap, timing relationships and stillness across elements. [UI motion](ui.md) owns whether a single element animates, its mechanism, curve and duration tokens; [accessibility](accessibility.md) owns the reduced-motion contract; [web gestures](gestures.md) owns motion the pointer drives.

Good choreography is mostly subtraction: cut moving parts, run the remaining ones in parallel, and sequence only when order carries meaning. A sequence that works reads as one gesture, a wave; one that does not reads as a queue the user waits through.

## Cast the elements

List every element that moves on the event, with its source location, and give each a role before choosing any timing:

| Role | What it is | Treatment |
| --- | --- | --- |
| Lead | The one thing the user must notice: the title, the new view, the item acted on | Moves first, travels furthest |
| Support | Secondary content that follows the lead: subtitle, actions, the rest of a list | Shorter, smaller motion after or alongside the lead |
| Decoration | Pills, badges, background accents, dividers | Opacity only, or nothing |
| Static | Everything else, including containers whose content moves | Does not animate |

Most groups shrink here. A side panel with eight menu items becomes one move: the panel slides and its items are already inside it. If two elements both need to be the lead, report the hierarchy problem; motion cannot settle it.

## Relate each pair

Choose one relationship for every pair of moving elements and record why:

```
Do both belong to the same visual object or the same moment?
├── Yes → Together: same start, same timing family.
└── No → Does the order carry meaning (reading order, cause and effect, one arrives before the other)?
         ├── No → Together. Order without meaning is only delay.
         └── Yes → Would both visible at once look broken (overlap, passing through, two dense views fighting)?
                   ├── Yes → Sequence: the second starts as the first ends, or just before.
                   └── No → Overlap: a stagger; the second starts while the first still moves.
```

**Carry** is the fifth option when a child's own path cannot be controlled, such as a shared-layout animation: move the parent and let the children travel with it.

### Together, by default

- One entrance per container. When a panel or card enters, its content is already inside it; do not also stagger its children.
- An element that leaves stops taking space when the removal starts, so its siblings close the gap while it fades. Use the presence mechanism's pop-out mode where the project's library has one (`AnimatePresence mode="popLayout"` in Motion). Without one, fix the exiting node at its current offset with `position: absolute` inside a positioned parent, then animate it out and let siblings reflow or FLIP. Removing it from focus and the accessibility tree at the same moment is covered in [UI motion](ui.md#entrances-exits-and-icon-swaps).
- A view swap inside one container is a crossfade: the old view exits while the new one enters, rather than both stacking until the exit finishes.
- Sub-animations of one component share one timing family so it reads as one object: a drawer that opens over one duration and resizes over another reads as two. Inner content may use a lighter curve from the same family. Set the family once through the project's motion tokens or the library's shared configuration.

### Overlap: the stagger

- Vary the gaps. Equal delay, distance and duration on every item moves like a metronome; gaps that shrink as the group continues, or delays shaped by an easing curve, read as one wave.
- Order follows importance, which usually but not always matches DOM order. Elements that read as one unit, such as a title and its first paragraph, share a beat.
- Vary treatment with role: the lead travels furthest, support less, decoration fades in place.
- For product UI, start from small steps (about `30`–`80ms`) with the whole group finishing near the project's short-transition budget; a one-time marketing or first-run entrance can take longer steps. These are starting points beneath the project's tokens. For a long list, stagger the first few items and let the rest arrive with the last of them.
- Direction follows reading order for content, and runs outward from the point of interaction for something the user triggered.
- Every element is usable as soon as it is visible; a delayed decoration never holds back an action the user is reaching for. Surfaces opened many times a session appear together, per the frequency rule in [UI motion](ui.md#decide-before-animating).

### Sequence: when to wait

Sequence only when overlap would look wrong: two dense views in a container that changes width and height, an element that would visibly pass through another (time the covering element's appearance to the landing instead), or a drawing whose second stroke depends on the first. Start the second move slightly before the first ends; that small overlap turns a queue into one gesture. Keyframed sequences that must hold their end state need an appropriate `animation-fill-mode`.

## Sync secondary motion to its moment

Hook each supporting animation to a specific moment of the lead (its start, impact or settle) instead of a delay that merely looks right.

- Sync to the cause: in hover-then-click, an emphasis pulse belongs to the click, not the hover.
- Land accents with the lead: lines or sparkles around an icon finish as the main shape settles, as a short burst late in its timeline, with the most important accent first.
- A repeated action skips the buildup: keep internal proportions and move the whole timeline earlier.

## Adapt timing to the size of the change

- When a container resizes between views, derive duration from the distance and clamp it; a large jump and a tiny one with the same fade look like a smear and a flicker respectively.
- Smaller elements may need more bounce to read as alive; the same bounce on a large surface settles slowly and reads heavy. Tune per state where the mechanism allows.
- With a handful of states, hand-tune each transition rather than deriving a formula; reach for a formula only when there are too many states to tune.

## Direction and exits

- Forward moves content toward the start edge (new content enters from the end edge); back reverses it. Under RTL, follow the [layout](layout.md) direction. Content switching between sibling menus enters from the side of the newly selected trigger.
- An exit reads its direction when it starts. Pass the current direction to exiting children through the library's mechanism (Motion's `custom` on both `AnimatePresence` and the child), or the leaving view animates with a stale direction.
- Exits happen together, shorter and quieter than entrances, as [UI motion](ui.md#entrances-exits-and-icon-swaps) describes. Do not reverse-stagger a group out; the user has already decided to leave. Leave toward the side the element entered from.

## Interruption

A sequence has more states than one animation. Exercise each:

- Retrigger mid-sequence: hover out halfway, press Next twice quickly, switch menus while one is opening. Each run stops in-flight animations before starting new ones; sequences never stack.
- An idle loop resumes only after every reset animation has finished; with differing durations, await all of them.
- Rapid view switching with a presence mechanism can leave two children mounted. Check it, and give each child a stable unique key.

## Attention loops and reduced motion

An idle animation that invites interaction waits a few seconds before its first run, repeats rarely, stops while the user interacts, and follows the pause/stop requirements in [accessibility](accessibility.md#motion-timing-and-reflow) when it runs long.

Under reduced motion, collapse the choreography: drop delays and movement, keep any opacity change, and let the group appear together. When the sequence itself explains something step by step, jump between its frames instead of animating between them.

## Implementation

Use the lightest mechanism that expresses the relationships, checking the installed library's API before using its examples:

- CSS: a per-item delay custom property with shrinking values on one keyframe, with `animation-fill-mode: both` so delayed items do not flash their final state first. Changing an inherited custom property on a parent recalculates styles for its descendants; that is acceptable for a one-shot entrance, not for per-frame values.
- A declarative library: parent-level stagger options (Motion's `stagger()` accepts `from` and `ease`) for groups that enter and exit with component state.
- Imperative orchestration only when several elements coordinate across several events and must await completion. Keep a handle on every running animation so a new run can stop the old one.

## Plan, then verify

Before coding, write a timeline with one row per moving element in start order: element, role, start, duration, motion and relationship. Then list the elements deliberately left still and why. The plan is complete when every inventoried element has a row.

After implementing, record the interaction and step through it frame by frame: a wave and a queue look alike at full speed in one's head and different on a recording. Run the interruption checks, then judge the fiftieth use of the day; motion the user would skip by then is cut. State what source cannot prove, such as whether a stagger reads as one wave, and name the moment to scrub.

Adapted selectively from Emil Kowalski's `choreograph` skill; see `../LICENSE.emilkowalski` and the repository's adopted-skills provenance record.
