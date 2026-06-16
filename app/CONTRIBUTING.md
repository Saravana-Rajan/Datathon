# Contributing to KSP Saathi

Thanks for picking up an issue. This guide gets you from a clean clone to a merged PR in as few steps as possible.

> If you're a teammate during Datathon 2026, the locked design lives in [`../design.md`](../design.md). Read Section 18 (Decision Log) before proposing anything that changes architecture — append, don't rewrite.

---

## Quick Setup

```bash
git clone https://github.com/ksp-saathi/datathon-2026.git
cd datathon-2026/app
cp .env.example .env       # then fill in credentials
```

See the [README Quick Start](README.md#quick-start-5-steps-to-local-dev) for the full local-dev loop.

---

## Adding a New Catalyst Function

Catalyst Functions live in `backend/functions/<function-name>/`. Each function is a self-contained Python package with its own `requirements.txt`.

1. **Scaffold the function**

   ```bash
   cd backend
   catalyst functions:new --type advancedio --stack python3.11 my-new-function
   ```

   That creates `backend/functions/my-new-function/` with `main.py`, `catalyst-config.json`, and `requirements.txt`.

2. **Implement the handler**

   ```python
   # backend/functions/my-new-function/main.py
   from shared.gemini import gemini_client
   from shared.audit import audit_log

   def handler(context, basic_io):
       payload = basic_io.get_argument("payload")
       # ... your logic ...
       audit_log(context, action="my_new_function", payload=payload)
       basic_io.write({"status": "ok"})
   ```

3. **Wire it into a Circuit**

   Add the function as a step in `backend/circuits/main-query-flow.yaml`. If it runs in parallel with siblings, put it under the same `parallel:` block.

4. **Add a test**

   ```bash
   touch backend/functions/my-new-function/test_main.py
   ```

   Tests run automatically in CI via `pytest`. Cover at minimum: happy path, missing input, and one failure mode.

5. **Deploy and verify**

   ```bash
   catalyst deploy --only functions/my-new-function
   curl -X POST "$CATALYST_API_BASE/baas/v1/project/$CATALYST_PROJECT_ID/function/my-new-function/execute" \
        -H "Authorization: Zoho-oauthtoken $CATALYST_AUTH_TOKEN" \
        -d '{"payload": "test"}'
   ```

---

## Adding a New Frontend Component

Frontend components live in `frontend/src/components/`. We use shadcn/ui primitives, Tailwind, and the Vercel AI SDK for streaming UIs.

1. **Create the file**

   ```bash
   touch frontend/src/components/MyNewPanel.tsx
   ```

2. **Use the house pattern** — typed props, named export, no default exports:

   ```tsx
   // frontend/src/components/MyNewPanel.tsx
   import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

   export interface MyNewPanelProps {
     title: string;
     data: ReadonlyArray<{ id: string; label: string }>;
   }

   export function MyNewPanel({ title, data }: MyNewPanelProps) {
     return (
       <Card>
         <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
         <CardContent>
           <ul>{data.map((d) => <li key={d.id}>{d.label}</li>)}</ul>
         </CardContent>
       </Card>
     );
   }
   ```

3. **Wire into a page** — import from `frontend/src/app/<route>/page.tsx`.

4. **If it consumes the backend** — use the typed API client in `frontend/src/lib/api.ts`. Do not call `fetch` directly from components.

5. **Bilingual strings** — every user-facing string must have an English and Kannada variant. Use the `useT()` hook (see `frontend/src/lib/i18n.ts`).

---

## Code Style

| Language | Standard | Tool | Command |
|---|---|---|---|
| Python | PEP 8 + type hints on all public funcs | `ruff` (lint) + `ruff format` | `ruff check . && ruff format --check .` |
| TypeScript / TSX | Prettier defaults + ESLint Next.js config | `prettier` + `eslint` | `npm run lint && npm run format:check` |
| YAML (Circuits, CI) | 2-space indent, no tabs | `yamllint` | `yamllint .` |
| Markdown | One sentence per line in long docs | — | — |

**Auto-fixes locally before committing:**

```bash
# Python
ruff check --fix backend/ && ruff format backend/

# TypeScript
cd frontend && npm run lint:fix && npm run format
```

CI rejects PRs that don't pass `ruff check`, `pytest`, `npm run typecheck`, and `npm run build`.

---

## Commit Format — Conventional Commits

Every commit message must follow [Conventional Commits 1.0](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<optional body>

<optional footer>
```

**Types we use:**

| Type | When |
|---|---|
| `feat` | New user-visible feature |
| `fix` | Bug fix |
| `refactor` | Code change with no behavior change |
| `perf` | Performance improvement |
| `docs` | Docs only |
| `test` | Tests only |
| `chore` | Build, deps, tooling |
| `ci` | CI config |

**Scope examples:** `frontend`, `backend`, `circuits`, `voice`, `auth`, `audit`, `pdf`, `maps`, `graph`, `data`.

**Examples:**

```
feat(voice): route Kannada audio to Gemini Live API
fix(audit): include role claim in immutable log row
docs(deploy): add custom domain SSL provisioning notes
refactor(synthesizer): extract shared prompt template
```

Breaking changes get a `!` after the scope and a `BREAKING CHANGE:` footer:

```
feat(auth)!: switch JWT signing from HS256 to RS256

BREAKING CHANGE: every deployed function must re-fetch the public key.
```

---

## Pull Request Checklist

When you open a PR, the [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) auto-fills with a checklist. The short version:

- [ ] Commits follow Conventional Commits
- [ ] `ruff check`, `pytest`, `npm run typecheck`, `npm run build` all pass locally
- [ ] New code has tests (unit for pure logic, integration for Circuits)
- [ ] Audit log entries cover any new user-facing action
- [ ] Bilingual strings present for any new UI copy (en + kn)
- [ ] If you added a Google service, you updated [`../decisions.md`](../decisions.md) with the Catalyst gap it fills
- [ ] If you changed a locked decision, you appended to [`../design.md`](../design.md) Section 18

PRs need at least one review approval before merging. Squash-merge to `main` is the default; rebase if you need to preserve commit boundaries.

---

## Reporting Issues

Open a GitHub Issue with:

1. **What happened** vs **what you expected**
2. **Repro steps** (be specific — "the chat broke" is not actionable)
3. **Environment** — local / staging / production, browser, language, role
4. **Audit log ID** if available (every chat turn produces one — see the Audit Drawer)

For security issues, do not open a public issue. Email `saravanarajan.b@techjays.com` directly.

---

## Questions?

Ping the team in the Datathon 2026 channel, or check the design docs first:

- [`../design.md`](../design.md) — the locked design doc
- [`../decisions.md`](../decisions.md) — why we use each Google service
- [`../CLAUDE.md`](../CLAUDE.md) — working norms and project context
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — Catalyst deployment runbook

Welcome aboard.
