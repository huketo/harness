# Marketing context

How to create or update a project's marketing context: the document every marketing task reads first so the product, audience, and claim limits do not have to be rediscovered each time.

## What the context is for

A marketing context routes and constrains. It points to the sources that own each fact and records the limits on what marketing may say. It restates a fact only when the restatement is the rule itself (for example, "describe the free beta as having no platform payments"), and then links the owning source beside it. Duplicated facts drift; links do not.

## Placement

Put the context where the project's documentation conventions place agent-facing guidance or product knowledge, and register it in the project's documentation index if one exists. Follow the project's rules for metadata, status, dates, and change history rather than inventing a parallel scheme. With no convention, propose a location, explain the choice, and name it in the deliverable. Point to it from the project's agent instructions with one line, so later tasks reach it.

## Procedure

1. **Check for an existing context.** If one exists, read it, verify that its links still resolve, and ask which sections need updating. Change only those sections.
2. **Draft from sources.** Read the project's documentation index, approved product or domain context, current requirements and roadmap, decisions, published policies, and the shipped product (routes, UI copy, configuration). Draft every section below from what you find, with a link for each statement.
3. **Separate the three kinds of content.**
   - Facts confirmed by code, decisions, or policy.
   - Positions and plans from strategy or GTM drafts, with their status.
   - Unknowns: questions only the owner can answer.
4. **Find conflicts.** Compare strategy and marketing drafts against requirements, decisions, policy, and code. Each conflict becomes a claim limit with both sources cited.
5. **Review with the owner.** Present the draft with its unknowns and conflicts first. Record answers in the owning source when the project has one; the context links to it.

The draft is complete when every section is filled, linked, or listed as an unknown, and every conflict found has a claim-limit row.

## Sections

### Product

- One line: what it is and for whom.
- Category: the shelf customers search on.
- Product type and business model, as they apply to the release being marketed. Distinguish the current release from planned stages.
- Current stage: pre-launch, beta, generally available, with the dated source.

### Audience

- Primary and secondary segments, and who is not a fit.
- For each segment: the job they hire the product for, the trigger that sends them looking, and the alternative they use today.
- Personas only when several roles influence adoption (buyer and user differ, or creators and fans play distinct parts).

### Positioning

- Competitive alternatives, including doing nothing and general-purpose tools, each with where it falls short.
- Differentiators that the shipped product delivers, each linked to its evidence.
- Switching forces: push away from the current option, pull toward this one, habit that holds them, anxiety about switching.

### Claim limits

The rules that keep marketing truthful. One row per sensitive topic:

| Topic | Say | Do not say | Source |
| --- | --- | --- | --- |

Cover at least: release state and dates, pricing and fees, money handling and guarantees, data ownership and portability, security, safety, or protection features, AI-related claims, content and age rules, integrations with other platforms, and anything the drafts overstate.

### Voice and language

- Market and language of the audience; register (for example, one Korean speech level per surface).
- Tone and personality in a few adjectives, with an example sentence that fits and one that does not.
- Product vocabulary: link the project glossary rather than copying it; add marketing-only terms and words to avoid.
- Visual and asset rules that constrain campaigns (logo use, mascot policy, generated-imagery policy), linked to their decision.

### Customer language

Verbatim phrases from research, reviews, community threads, or interviews, each with source and date. Mark the section empty rather than paraphrasing hypothetical customers.

### Proof

Metrics, testimonials, press, partners, or awards the owner can show, each with its evidence. Before launch this section is usually empty; say so.

### Channels and goals

- Owned, earned, and paid channels that exist today (official accounts, sites, communities), each with its URL or "none yet".
- The conversion action marketing drives and the metric it is measured by, with how it can be measured now.
- Approved goals and budgets, distinguished from proposals.

### Sources

The index of owning documents the sections link to, with their status. This lets later tasks reload the truth instead of trusting the context's summary.
