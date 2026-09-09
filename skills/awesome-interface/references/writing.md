# Interface writing

Write copy that lets someone understand the current state and take the right next action. Clear and brief beats clever; consistent terminology beats variety. Preserve an intentional product voice unless it obscures meaning, conflicts with the stakes or becomes inconsistent.

This domain owns product terminology, voice, labels, instructions and state messages, for generation as well as revision and review. Label associations, error markup and announcements belong to [accessibility.md](accessibility.md); room for translated content and state placement to [layout.md](layout.md); text rendering, truncation and punctuation mechanics to [typography.md](typography.md). Review ranking and reporting belong to [review.md](review.md).

## Establish meaning before wording

Read nearby copy, the actual action or validation behavior, the content style guide and localization conventions. Identify the audience, its current task, the state that triggers the message and what the product can truthfully do next. Build a small working vocabulary from existing nouns and verbs: if the menu says “Archive,” the confirmation should not call the same operation “Move to storage.”

When generating new copy, determine the action and consequence from the specification or implementation. When revising, compare the visible promise with the actual behavior before shortening it. Do not invent retry support, data retention, security guarantees, timing, eligibility rules or validation restrictions to make a sentence sound helpful. If a needed fact is missing, identify it and draft only the parts supported by evidence.

A local request is not permission to rename product concepts or rewrite the whole voice. Prefer the smallest edit that removes ambiguity, inconsistency or a blocked next step. Review requests propose replacements without applying them unless implementation was requested.

## Draft the complete interaction

For the requested surface, write the copy people encounter before, during and after the action, rather than treating a button as an isolated phrase:

1. Name the object or task in the heading or field label.
2. Put necessary prerequisites and format hints before commitment, close to the relevant control.
3. Label the action by what it does.
4. Describe pending, success, empty and failure states that the flow actually has.
5. State recovery or a next step that the interface supports.
6. Check every string against the same vocabulary and product behavior.

Stop when the requested states have usable copy, not when an arbitrary set of alternatives exists. If the user asks for final wording, deliver one coherent recommendation. Generate stylistic variants only when requested, and keep their underlying facts and consequences identical.

## One voice, tone matched to stakes

| Context | Tone |
| --- | --- |
| Onboarding, first-use empty, ordinary success | Warm and orienting; restrained personality can fit the product |
| Routine actions and settings | Neutral, direct and economical |
| Errors and destructive confirmations | Calm, specific and free of jokes |
| Security, data loss or irreversible effects | Explicit about scope and consequence |

Address the reader as “you” in instructions rather than “the user.” Use possessives only when they distinguish ownership; “Favorites” often needs no “Your.” Keep perspective consistent across the flow. An established first-person brand voice can remain where it is clear, but vague “we're having trouble” language should not displace the actual state or recovery.

Use plain words a tired reader can understand on the first pass. Remove filler, not information needed for a safe decision. Avoid idioms, unnecessary gender and jokes that fail in translation. Use device-neutral verbs such as “select” when pointer, touch and keyboard are all possible; name a gesture only when the instruction genuinely requires it.

Use sentence case as a safe default when no policy exists. Otherwise preserve the project's capitalization by element type, including product names and proper nouns. Authored capitalization belongs here; CSS transformations and typographic rendering belong to [typography.md](typography.md).

## Labels that predict the outcome

### Actions and confirmations

Use a specific verb and, where needed, its object: “Save draft,” “Send invitation,” “Delete project.” Prefer labels whose consequence remains clear when read apart from the surrounding paragraph. Avoid generic “OK,” celebratory filler or bare “Yes”/“No” for consequential actions.

A confirmation should name what is affected and whether the action is reversible. Its action repeats the consequence, while the escape action is unambiguous. Only state permanent deletion or recoverability when the product actually guarantees it.

| Intent | Example copy | Required fact |
| --- | --- | --- |
| Save an unfinished item | “Save draft” | Saving does not publish it |
| Delete a project permanently | “Delete project?” / “This permanently deletes the project and its files.” / “Delete project” / “Cancel” | Both project and files really are deleted and the operation cannot be undone |
| Remove a filter | “Clear filters” | The action clears the filters, not the underlying data |

Keep one progression vocabulary within a multi-step flow: choose “Continue” or “Next” consistently, and distinguish the final committing action from navigation. “Done” fits a finish or dismissal only when no hidden submission consequence needs naming.

### Links and navigation

Describe the destination or purpose: “Read the billing guide,” not “Click here.” Repeated “Learn more” links need distinguishing subject matter, especially in a link list. Keep navigation labels stable across entry points. If a setting is referenced and a deep link exists, link directly to it rather than writing a brittle path through several menus.

### Settings and fields

Name a toggle's enabled state: “Send read receipts” makes on/off understandable; “Don't send read receipts” creates a double negative. Check that toggling on actually produces the named state. Distinguish a setting that changes immediately from one that requires saving.

Field labels name the requested information; hints state useful constraints or examples. Placeholders may illustrate the expected format but should not carry essential instructions that vanish during entry. Persistent labels and their programmatic association are specified in [accessibility.md](accessibility.md).

Use examples accepted by the actual field and locale. An ambiguous date placeholder is not a substitute for stating the accepted date format. Do not suggest narrow personal-name rules, password lengths or character restrictions unless the real contract requires them.

## Errors are recovery instructions

Explain what could not happen, then what can be done. Include a known cause when it helps; distinguish a verified cause from a guess. A network failure does not prove that the person's connection is at fault, and a generic server error does not justify telling them to change their input.

| Weak copy | Better direction |
| --- | --- |
| “Invalid email” | “Enter a valid email address.” |
| “Password too short” | State the actual minimum from the validation contract, not a guessed policy |
| “Oops! Something went wrong!” | Name the failed action and an available next step: “Unable to save. Try again.” only if retry is supported |
| “Invalid name” | State a genuine requirement; do not invent a letters-only rule |
| “Session error” | Explain whether sign-in is needed and whether entered work remains, using only verified behavior |

Use positive instructions where useful, without blame or playful punctuation. Give known constraints as hints before an avoidable error. Keep field-specific messages specific to that field; form-level failures should explain the overall outcome. Placement and announcement wiring are owned by [accessibility.md](accessibility.md).

Be precise about partial success. “Saved” is false if only some items were saved; identify the completed scope and what remains actionable. Do not promise “Nothing was lost” without evidence. When the user cannot fix the failure, say what remains available rather than issuing a fake instruction.

Repeated errors may indicate an interaction problem rather than a wording problem. Name the underlying issue and propose prevention when within scope; do not silently redesign the validation or behavior during a copy-only task.

## State messages that move the task forward

### Empty and no-result states

A first-use empty state explains what belongs here, why it is useful when not obvious and one clear way to begin. For example, a project list may use “No projects yet,” “Projects keep tasks and files together,” and “Create project” if that action exists. Avoid filler descriptions when the heading and action already orient the reader.

A search/filter empty state distinguishes absence from failure: identify the relevant query or active constraint and offer a supported way to revise it. “No results for ‘quarterly’” with “Clear filters” is appropriate only if filters are involved; otherwise point to changing the search. Do not imply the entire collection is empty when only the current filter matches nothing.

Use [layout.md](layout.md) to place guidance that must remain available after the empty state ends.

### Pending and success

Pending copy names what is happening without claiming completion. Distinguish “Saving…” from “Saved.” Keep the action understandable during progress, and avoid fabricated time estimates. If the operation can be canceled, name what cancellation affects; otherwise do not suggest that option.

Success copy confirms the actual result with enough context to resolve uncertainty: “Draft saved” is more useful than “Success!” Avoid redundant celebration on every routine action. Mention a next step only when it helps the current task. State persistence and announcement behavior are owned by [accessibility.md](accessibility.md).

### Destructive, unavailable and permission states

Explain why an action is unavailable when that reason is useful and known. Identify the required condition or permission and a real route to resolve it, without exposing unnecessary sensitive detail. Use [accessibility.md](accessibility.md) for the explanation's reachability.

Keep warnings proportional to consequence. State the affected object, scope and reversibility rather than relying on alarming adjectives. Distinguish removing access, archiving and deleting: similar-looking controls must not conceal different outcomes.

## Localization-ready copy

Use the existing localization mechanism and stable message keys. Translate complete messages with named parameters and proper pluralization rather than concatenating fragments around a variable. Different languages reorder words and have more than singular/plural cases; a count is not an English suffix rule.

Give translators enough context to distinguish an action from a noun, a heading from a sentence and the meaning of substituted values. Keep one concept consistent without forcing the same source string into contexts that require different grammar. Preserve brand names, identifiers and code tokens intentionally using the project's translation convention, not by globally preventing translation.

Check zero, one and multiple-item wording and the actual formatted values used by the application. Preserve locale-aware number/date formatting. Space for expansion belongs to [layout.md](layout.md); bidirectional rendering and punctuation belong to [typography.md](typography.md).

## Verification evidence

For new copy, provide the final strings mapped to their controls or states. For fixes or review findings, provide the exact location, current wording, replacement and the ambiguity or task failure it resolves. Group a repeated terminology problem by its root cause rather than presenting every occurrence as a different writing rule.

Source inspection is sufficient to check wording, vocabulary, localization structure and the label's agreement with the action only where the behavior is available to inspect. Trace errors to their actual triggering conditions and recovery paths. Check every requested state, not merely the default labels. Record unknown behavioral facts rather than smoothing them over with plausible copy.

A copy-only proposal does not need a browser to establish semantic improvements. Once text is integrated, wrapping, clipping, visible placement, focus and announcements require their corresponding rendered checks; source review does not verify those outcomes. Report which kind of evidence was obtained and which remains unverified.
