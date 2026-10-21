# English style reference

Read this when writing or revising English social or blog posts or technical documents. Always apply [Common](#common), then the one section that matches the context: [Social and blog posts](#social-and-blog-posts) or [Technical documents](#technical-documents). Interface copy belongs to `awesome-interface`'s `references/writing.md`. A project glossary, house style guide or writer's voice sample overrides this file.

The AI-writing patterns below are edit candidates, not proof of who wrote a text. Fix a **strong** pattern on a single sighting. Fix a **weak** pattern only when another pattern appears in the same paragraph. Leave quotations, proper names, titles and passages that discuss a phrase as they are.

## Common

### Facts and meaning

- Use only facts from the source or the user. Do not add a name, number, date, quote, citation, cause or ranking. When a sentence needs a missing fact, write a simpler sentence and list the gap.
- Before editing, mark protected spans and keep them byte for byte: numbers with units, quotations, code, commands, paths, URLs, product names and identifiers.
- After editing, compare claim by claim with the source: tense and status (planned versus shipped), modality (can, may, will, must), negation, and scope words (only, also, about, at most, at least, all, some, yet).
- Keep the type of each statement: an observation stays an observation, a forecast does not become a commitment, a guideline does not become a requirement.

### Voice

- Technical, reference and interface text is neutral and plain. Blog and personal text keeps the writer's opinions, uncertainty, humor and specific details.
- Address the reader as "you" in instructions. Use active voice when it makes the actor clear; keep the passive when the actor is unknown or irrelevant.
- Use the word that names the thing. Prefer "is" and "has" over "serves as", "boasts", "features" or "offers" when the sentence only states identity or possession.

### AI-writing patterns

| Pattern | Example | Fix | Strength |
| --- | --- | --- | --- |
| Not X but Y | "It's not just a tool, it's a mindset." | State the positive claim. Keep a contrast only when readers actually believe X | Strong |
| One-line closers | "Let that sink in.", "That's the real win." | Delete, or replace with the concrete consequence | Strong |
| Deep-sounding sayings | "At its core, it's about trust." | Write the specific claim the saying hides | Strong |
| Staged run-up | "Here's the thing:", "Let's dive in.", "Honestly?" | Start with the point | Strong |
| Arguing with no one | "This isn't about speed." when no one said it was | Delete the unraised objection | Strong |
| Chatbot residue | "Great question!", "I hope this helps.", "Let me know if..." | Delete | Strong |
| Era opener | "In today's fast-paced landscape," | Delete | Strong |
| Inflated significance | "a pivotal moment", "transformative", "the future is bright" | Keep the fact, drop the claimed importance | Medium |
| Overused AI words | delve, showcase, testament, tapestry, pivotal, underscore, landscape, robust (figurative), leverage, foster, journey, stakeholder alignment, "a culture of" | Use the plain word or the specific fact | Medium |
| Shallow -ing riders | "..., highlighting the team's commitment to quality." | Delete unless the source supports the interpretation | Medium |
| Sales language | "seamless", "game-changing", "supercharge", "unlock" | Say what it does | Medium |
| Borrowed authority | "Experts agree...", "Studies show..." | Name the source or cut the claim | Medium |
| Guessing to fill gaps | "She likely grew up..." | Say the source does not show it, or cut | Medium |
| Decorative formatting | Emoji bullets, emoji or Title Case headings, bold on every label, "**Label:** restatement" | Use sentences or plain lists; sentence-case headings | Medium |
| Heading echoed in first line | "## Performance" then "Performance matters." | Delete the echo | Medium |
| Forced triads | Three items where the content has two | Use as many items as the meaning has | Weak |
| Dash as the default connector | Several em dashes per paragraph | Use a comma, colon, parentheses or a new sentence; keep a deliberate dash | Weak |
| Stacked hedges | "could potentially possibly" | Keep one qualifier the source supports | Weak |
| Writing about the document | "This post explores...", "The table below compares..." | Describe the subject directly | Weak |

Salutations and sign-offs in email and announcements are conventions, not tells.

### Mechanics

- Use sentence case for headings, titles and UI labels. Omit final periods on headings and UI titles.
- Use numerals for technical quantities, measurements, versions and money. In prose, spell out zero through nine when no unit follows. Group thousands with commas (`12,000`).
- Use the serial comma. Use one space after sentence punctuation.
- Use straight or curly quotes as the project already does; do not convert between them.
- Spell out an unfamiliar abbreviation on first use.

## Social and blog posts

- Match the writer's voice sample when one exists: sentence length, word choice, punctuation, openings and dash rate. Without a sample, keep the writer's opinions and specific details, and do not add a tidy lesson at the end.
- Open with what changed or what happened, not with a hook question or "Big news!".
- In launch posts, state limits, supported platforms and unscheduled dates plainly. "Coming in November" without a date stays "planned for November; date not set".
- Combine related source facts into connected sentences in the order readers care about, instead of turning each source bullet into its own sentence.
- Follow writing instructions in the source notes (for example, "pricing is not public yet") without repeating them in the post.
- When the source notes are in another language, write the idiomatic English sentence instead of carrying over their word order or nouns: "The Android app is planned for spring", not "Android is planned for spring".
- One idea per social post. Shorten the idea rather than the spelling. Use hashtags rarely and only ones people search; do not ask for likes or reposts.
- Check each platform's current character limit before posting.
- Blog post structure follows the `post` genre of `writing-for-humans`.

## Technical documents

- Lead with the conclusion or the task. Put conditions before instructions ("To export a project, select...").
- Use numbered lists for sequences and tables for comparisons. Do not split one paragraph's worth of reasoning into bullets.
- Define terms and abbreviations at first use and keep one term per concept.
- Put code, commands, paths and configuration keys in code formatting.
- State status precisely: a prototype, staging environment or estimate is not production or a measured result.

## Review

1. No fact was added or dropped; numbers, names, dates, negation and scope words match the source.
2. No strong pattern remains, and no paragraph has two or more weak patterns.
3. Headings and labels use sentence case; formatting carries meaning.
4. Register and terminology are consistent across the text.
5. Every item in the applied context section holds.

## Sources

- [blader/humanizer](https://github.com/blader/humanizer) (MIT): pattern catalogue and strength levels, mark-then-rewrite and fact-diff procedure; its patterns derive from Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing).
- [Google developer documentation style guide](https://developers.google.com/style/highlights) and [Numbers](https://developers.google.com/style/numbers): conditions before instructions, sentence-case headings, numerals for technical quantities.
- [Microsoft Writing Style Guide: top 10 tips](https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice): front-loaded information, sentence-style capitalization, heading punctuation.
- [Mailchimp Content Style Guide: Writing for social media](https://styleguide.mailchimp.com/writing-for-social-media/) and [Grammar and mechanics](https://styleguide.mailchimp.com/grammar-and-mechanics/): deliberate hashtags, no exclamation marks in failure messages.
