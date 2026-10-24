# Council interface design

October 19, 2026. Scope: a new visual system and two presentation views of the same Council. No new inference protocol, provider or billing permission.

## Direction before implementation

**Visual thesis:** a quiet charcoal writing room, warm off-white typography, generous space and a single muted mint accent; the question and answer carry the composition.

**Content plan:** saved conversations at the edge, a clear question composer at the center, a readable answer in the conversation, and process/diagnostic detail in a secondary Explain view. The application opens on the working surface, without a marketing hero or decorative image.

**Interaction thesis:** a quick selected-state transition for the view switch, a restrained entrance for secondary context, and subtle focus/hover feedback. All movement respects reduced-motion preferences; typing and repeated navigation have no decorative delay.

## Research and skill selection

These are complementary tools rather than a defensible universal ranking. Primary sources were inspected; no third-party installer or hook was executed.

| Resource | Useful contribution | Decision for this application |
| --- | --- | --- |
| [Existing frontend skill](C:/Users/CM/.codex/skills/frontend-skill/SKILL.md) | App-specific restraint, hierarchy, spacing, one accent and purposeful motion. | Governing implementation skill. |
| [Impeccable](https://github.com/pbakaus/impeccable) | Explicit simplification, critique, polish and responsive/a11y checks. | Apply a critique-and-refine loop; do not install its runtime/hooks for this change. |
| [Vercel interface guidelines](https://github.com/vercel-labs/web-interface-guidelines) | Keyboard/focus behavior, semantic controls, content overflow and reduced motion. | Use as a review checklist. Preserve existing budget safeguards even where generic form advice differs. |
| [Anthropic frontend design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Intentional visual direction and avoiding generic generated layouts. | Useful composition reference; keep product controls and legibility ahead of decorative novelty. |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Broad palette, typography and interaction guidance. | A reference library, not the authority for this product's behavior or a reason to add a framework. |
| [Emil Kowalski's skills](https://github.com/emilkowalski/skills) and [interaction examples](https://emilkowal.ski/ui/train-your-judgement) | Motion judgment, repetition and interaction craft. | Short, interruptible transitions; no constant ornamental movement. |

[NN/g's progressive disclosure guidance](https://www.nngroup.com/articles/progressive-disclosure/) supports moving advanced controls behind a clearly named entry. [W3C cognitive accessibility guidance](https://www.w3.org/WAI/WCAG2/supplemental/objectives/o5-user-focus/) supports reducing distraction and helping users keep their place. These inform the design; they do not establish usability without user testing.

## Two views

**Simple is the default.** The user sees their question, plain-language status, model replies and the answer. Earlier process messages can be expanded without leaving the chat. Advanced setup is under Customize. Failures, incomplete participation, synthetic-demo status, stale answers and spending/allowance blocks remain visible.

**Explain is for inspection.** It displays the full ordered transcript, phase progression, claims/evidence access, actual model identifiers, role assignments, attempt counts and a bounded execution snapshot. This is public process data, not private chain of thought. It uses the existing API response and makes no extra inference calls.

The Simple/Explain preference is local to the browser and survives reload. Changing it preserves chat ID, draft, selected participants, answer requirements and all saved records. Storage failure falls back gracefully. Keyboard users can operate the switch and every disclosure. Mobile uses the same features with a scrollable diagnostic region instead of a squeezed third column.

## Acceptance checklist

- [x] Default entry is Simple with one clear composer and no engineering-version/mode selector.
- [x] Explain exposes actual process and execution data; it is not a second review algorithm.
- [x] Toggling preserves the draft/chat; the selected view survives reload. Toggling dispatches zero inference calls.
- [x] A visible path expands process messages and opens source/claim inspection.
- [x] Partial, unavailable, blocked, stale and synthetic states stay explicit in both views.
- [x] New/long conversations, math, code, focus, 390/622/desktop widths and reduced motion are checked in the browser.
- [x] Existing interaction and research-workspace scenarios remain covered.

## Validation evidence

The production build passes. The browser scenarios include view/draft preservation, saved conversations, source-link expansion, inspector access, provider/quota errors, math rendering, a 100-conversation history, keyboard use, storage failure and reduced motion. The current [acceptance record](../validation/council-design-status.json) records the final counts and evidence.

A separate [read-only check of the real app](../validation/council-design-ui.json) covers both views at 1440px, 622px and 390px, including the previously partial four-provider chat. It makes zero inference requests and keeps that answer labelled partial. Screenshots were visually inspected. [Integrity checks](../validation/council-design-integrity.json) compare all 39 packaged backend source files and scan the frontend source/build for configured provider keys and the director token: unchanged backend, zero credential matches.

These are software and visual checks. They are not independent usability research or evidence of improved model quality. The prior full-live-review and independent-quality limitations remain unchanged.
