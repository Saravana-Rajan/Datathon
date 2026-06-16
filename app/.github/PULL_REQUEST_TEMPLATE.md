<!--
  Thanks for the PR. Fill this template in — it speeds review by ~10x.
  Anything you delete will be assumed "did not apply".
-->

## Summary

<!-- 1-3 sentences. What does this PR do, and WHY?
     Link the design-doc section or issue this implements. -->

Closes #

## Type of Change

- [ ] `feat` — new user-visible feature
- [ ] `fix` — bug fix
- [ ] `refactor` — no behavior change
- [ ] `perf` — performance
- [ ] `docs` — docs only
- [ ] `test` — tests only
- [ ] `chore` / `ci` — tooling, deps, build
- [ ] **Breaking change** — also explain migration below

## What Changed

<!-- Bullet list of the concrete changes. Be specific.
     Bad: "improved chat"
     Good: "switched ChatPanel.tsx from polling to SSE; added retry/backoff in lib/api.ts" -->

-
-
-

## Screenshots / Recordings

<!-- For frontend changes, paste before/after screenshots.
     For voice changes, attach a 10-second recording.
     For backend-only changes, you can skip this. -->

| Before | After |
|---|---|
|        |       |

## Test Plan

<!-- How did you verify this works? Be specific about commands run,
     URLs hit, queries asked, roles tested. -->

- [ ] Tested locally (`catalyst serve` + `npm run dev`)
- [ ] `ruff check` passes
- [ ] `pytest` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes
- [ ] Tested with both `en` and `kn` language toggles
- [ ] Tested with at least two roles (e.g. `sub_inspector` + `inspector`)
- [ ] Verified audit log row written for the new action

## Design / Decision Impact

- [ ] No impact on locked decisions in `design.md`
- [ ] I appended a new row to `design.md` Section 18 Decision Log
- [ ] I added a Google service and updated `decisions.md` with the Catalyst gap it fills
- [ ] I did **not** add a Google service that has a Catalyst equivalent

## Compliance Checklist

- [ ] No PII leaves India (data residency)
- [ ] No PII appears in LLM prompts unmasked
- [ ] Role-based access checked at the function-entry boundary
- [ ] Audit log row includes `user_id`, `role`, `raw_query`, `tool_calls`, `data_accessed`
- [ ] If this is a predictive feature: no caste / religion / community as input feature

## Breaking Changes

<!-- Only if you ticked "Breaking change" above. Otherwise delete this section.
     Explain: what breaks, who is affected, what they need to do. -->

## Reviewer Notes

<!-- Anything specific you want the reviewer to look at?
     Areas you're unsure about? Trade-offs you considered? -->

---

🤖 *Conventional Commits enforced. Squash-merge by default.*
