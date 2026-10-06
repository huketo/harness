---
name: marketing
description: "Plan, write, and review product marketing: positioning, launches, PR, community and creator growth, marketing copy, social posts, SEO, signup and onboarding conversion, marketing measurement. Not for UI implementation, image generation, slide decks, or general research."
license: MIT
---

# Marketing

Produce marketing work that is true to the product as it ships. Every deliverable rests on the project's own sources, traced through a claim ledger; persuasion never outruns the evidence. This is one skill with internal references, not a dispatcher: read only the references the request needs.

## 1. Bound the task and its authority

Name the deliverable, its audience, the channel or surface, the market, and the language. Use the audience's language for the deliverable and the user's language for discussion with the user.

Drafting is the default scope. Publishing, posting, sending, scheduling, submitting to directories, contacting people (creators, press, partners), spending on ads, and changing live tracking, sites, or production data are external effects: prepare the draft, checklist, or spec, and execute only with explicit authorization that names the action. A request that names the action still leaves the account, recipients, final content, and timing for the owner to confirm. Deliver the drafts first, then request that confirmation, so the work is usable whether or not approval arrives; when the `herdr-hitl` skill is installed, use it for the request. A scheduled or otherwise unattended run stages its output and records blockers instead of asking or executing.

## 2. Load the product truth

1. Follow the project's agent instructions (`AGENTS.md`, `CLAUDE.md`, the documentation index they name) to its marketing context. When one exists, read it first; it names the sources and the claim limits that bind every deliverable.
2. Read the primary sources the deliverable depends on, in this authority order:
   1. Shipped behavior: source code, configuration, the running product.
   2. Accepted decisions and published policies (terms, privacy, content rules).
   3. Current requirements and roadmap for the release in question.
   4. Strategy, GTM plans, research, and brand drafts.
   5. Older or archived documents.

   Record each source's path, status (draft, review, approved, archived, or the project's equivalent), and date. A lower-rank source never overrides a higher one; a strategy document's description of a feature is a hypothesis until code or a decision confirms it.
3. When the project has no marketing context, build this deliverable's ledger from the sources above and recommend creating one. Create it only when the user asks for it: then read [context](references/context.md) and place it where the project's documentation conventions assign. With no convention, choose a location, propose it, and name it in the deliverable.

The step is complete when every product statement the deliverable will make has a row in the claim ledger.

## 3. Keep a claim ledger

The **claim ledger** is the evidence table behind the deliverable:

| Claim | Verdict | Evidence |
| --- | --- | --- |
| Statement as the deliverable will phrase it | supported, conditional, unsupported, or contradicted | `path:line` or URL, source status, date |

- Use supported claims as written. Use conditional claims only with their condition stated in the copy (scope, release, eligibility, opt-in).
- Rewrite or drop unsupported claims, or list them as open questions for the owner.
- A contradicted claim exposes a conflict between sources: report both quotations, follow the higher-ranked source, and flag the lower one for correction. Keep the conflict visible.
- Launch state, prices, fees, guarantees, protection or security properties, legal and age rules, and anything about money handling carry the highest risk: confirm each against code, decisions, or policy before use.
- Market facts (competitors, channels, audience size, benchmarks, platform specs) need a dated source from the project's research or a fresh cited lookup. Figures inside these references are illustrations, never facts about the user's market.
- Proof elements (metrics, testimonials, user counts, logos, awards, press) come only from evidence the owner can show. Write placeholders such as `[verified quote needed]` instead of inventing them.

Deliver the ledger with the work, or a summary of the claims used and their sources when the user wants only the copy.

## 4. Route to the needed references

| Request | Read |
| --- | --- |
| Create or update the project's marketing context | [context](references/context.md) |
| Marketing plan, positioning, channel and idea selection, persuasion principles, offer design | [strategy](references/strategy.md) |
| Audience or customer research, competitor profiles, comparison or alternative pages | [research](references/research.md) |
| Launches, announcements, PR and press, events and contests, directory or listing submissions | [launch](references/launch.md) |
| Community building, creator or influencer programs, partnerships, referral or invite programs | [community](references/community.md) |
| Writing or editing marketing copy for pages, announcements, or emails | [copy](references/copy.md) |
| Social posts, content calendars, platform adaptation | [social](references/social.md) |
| SEO audit, site architecture, structured data, programmatic pages, AI search, content strategy | [seo](references/seo.md) |
| Landing-page conversion, signup flows, onboarding and activation | [activation](references/activation.md) |
| Tracking plans, experiments, attribution | [measurement](references/measurement.md) |
| A recurring marketing check, review, or monitoring loop | [loops](references/loops.md) |

Add a second reference only when the request reaches it; a single social post does not need a marketing plan.

## 5. Hand off adjacent deliverables

These skills own neighboring outputs. Use them when installed; otherwise stop at a written brief or spec for that output.

| Output | Owner |
| --- | --- |
| UI implementation of a page, flow, or component | `awesome-interface` |
| Images, visual concepts, brand boards | `imagegen`, following the project's brand and asset rules |
| Slide decks | `awesome-slides` |
| Diagrams of funnels, loops, or journeys | `diagram-design` |
| Open-ended investigation beyond the product's own sources | `research` |
| Reports and long-form documents for internal readers | `writing-for-humans` |
| Scheduling a recurring run | `herdr-cron` |
| A contested, costly strategic choice | `herdr-quorum` |

## 6. Deliver

Return the deliverable in the format its reference specifies, plus:

- the claim ledger or its summary;
- assumptions and open questions for the owner, each with what would settle it;
- every external effect the work implies, listed as a pending action with its owner;
- files written and their locations.

Separate facts from proposals: label plans, budgets, targets, and channel bets as proposals unless an owner approved them.
