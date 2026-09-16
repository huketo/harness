# Web gestures and motion continuity

Read this reference for web drag, swipe, momentum, snapping or re-grabbing an animated surface. [UI motion](ui.md) owns the purpose, mechanism selection and performance rules; [accessibility](accessibility.md) owns target sizes, keyboard and non-drag alternatives, scrolling, zoom and reduced-motion requirements. Ordinary fades do not need this reference. Native-platform animation APIs require their own project guidance.

## Establish the gesture contract

Inspect the existing component, gesture recognizer and animation library before adding handlers. Reuse their capture, cancellation and settling mechanisms rather than attaching a competing controller. Record the permitted axis, scroll ownership, bounds or snap points, dismiss direction, commit action and cancellation result. Keep committed application state separate from the transient drag position.

A press can show feedback immediately while the action commits through its established activation path. A drag needs enough movement to distinguish it from a tap or page scroll; use the component's existing threshold rather than a universal pixel value. Scope `touch-action` to the surface and permitted axes before the gesture begins, following the accessibility contract. A successful drag must not also trigger the control's click action accidentally.

## Track one pointer without a jump

For a custom Pointer Events implementation:

1. On an eligible pointer-down, record the active pointer ID, pointer position and current rendered position. Preserve where the user grabbed the surface instead of snapping its center to the pointer. Use a consistent coordinate space, accounting for transforms or scrolling in ancestors.
2. Capture that pointer when the gesture takes ownership, so movement continues outside the element. Ignore other pointer IDs during this single-pointer gesture; do not replace the active pointer when another finger lands.
3. During direct manipulation, follow pointer displacement from the recorded grab position without an easing lag. Outside a bound, apply progressive resistance if that is the component's established behavior. Resistance affects the transient display, not the legal resting bounds or stored value.
4. On pointer-up, choose one outcome and enter settling. Clear the active gesture before releasing capture so the resulting `lostpointercapture` cannot undo a completed release.
5. On `pointercancel`, unexpected capture loss, unmount or navigation, use the defined non-committing cancellation path. Release owned capture, listeners and animation resources once. Cancellation must not confirm a dismissal or destructive action, and stale completion callbacks must not overwrite a newer gesture.

Keep frame updates in the existing animation value or a single owned transform writer, not competing React state and imperative style paths. Measure before changing architecture for performance. A motion library's gesture implementation may already provide this lifecycle; verify it instead of duplicating it.

## Release velocity and target selection

Estimate release velocity from a short recent position/time history in a consistent clock and coordinate system, preserving its sign. Whole-drag distance divided by total elapsed time is not release velocity: it loses a late flick, reversal or pause. Require a positive time interval, handle sparse samples, and include or account for a stationary pause at release so stale speed does not launch a stopped surface.

Confirm units at the API boundary. CSS pixels per millisecond and pixels per second differ by a factor of 1000; normalized velocity also depends on distance to the target and needs a zero-distance case. Prefer the existing library's measured velocity when its semantics match the gesture.

Select a legal target using both release position and direction-aware velocity, as the component contract requires. A quick flick can justify dismissal without a long drag; a fast reversal away from the dismiss direction should not be treated like an outward flick merely because its speed is large. For snap points, use the existing inertia/projection model to estimate where movement would settle, then choose an allowed target. Projection constants and thresholds are product-specific starting values, not universal physics requirements. Clamp the final target to the legal range unless the chosen action intentionally dismisses the surface.

Pass release velocity to a settling mechanism that actually consumes it. Check the installed API: a duration/bounce preset is not interchangeable with a physics spring carrying initial velocity. Avoid introducing a spring package when the existing component already owns settling, or when a simple state transition meets the requested behavior.

## Re-grab and redirect

A user should be able to grab a settling surface without waiting for it to finish. Start from its presentation value — the position currently on screen — rather than its logical destination. Read that value through the existing animation mechanism, stop or retarget the old motion without snapping, and establish a new grab offset from that position. Keep one owner of transform composition so a replacement animation does not erase an unrelated scale or rotation.

For an animated retarget, preserve appropriate current velocity through the existing spring API instead of restarting from zero. While the finger directly controls position, keep tracking direct; resume velocity-aware settling on release. Check axes independently when their bounds or velocities differ. Guard old completion handlers so an interrupted close cannot later hide a reopened surface or restore focus to the wrong control.

## Reduced motion and stable outcomes

Use the accessibility reference to choose a reduced/static treatment while preserving the same actions, legal resting states and focus behavior. Direct manipulation must remain understandable; remove decorative overshoot and long settling where appropriate. A global `transform: none` can reveal an off-screen closed drawer or destroy drag positioning, so change the animation treatment rather than erase the component's state geometry. Essential completion must work even when motion finishes immediately or is canceled.

## Verify the interaction

Exercise the actual component, first at normal speed, then slowly where useful. Use a physical touch device for claims about touch feel or browser gesture arbitration; mouse automation alone cannot establish those claims.

| Scenario | Observable result |
| --- | --- |
| Grab near an edge; move outside the element | No initial jump; the owned pointer continues tracking. |
| Add a second finger during a drag | The active gesture does not jump to the new pointer. |
| Drag slowly, flick late, reverse direction, or pause before release | Target choice follows recent signed motion and position, not stale average speed. |
| Cancel the pointer or lose capture unexpectedly | The non-committing state is restored or settled as specified; no action fires twice. |
| Release normally, then receive capture loss | The chosen outcome is retained; cleanup does not roll it back. |
| Re-grab during settling; rapidly close and reopen; navigate away | No snap to the old target, stale hide/focus callback or invisible interaction blocker. |
| Scroll nearby content and use the non-drag control path | Page interaction and the same application action remain reachable. |
| Enable reduced motion and repeat entry, release and cancellation | Correct visible/hidden state and usable controls without waiting on decorative completion. |

Report the component, input route, states and observed result. Mark unexercised device behavior and performance as unverified; source inspection of a spring configuration does not prove continuity or smoothness.
