# Sarvik (ksp-saathi) — Integration Test Suite

End-to-end tests for the Sarvik conversational AI: orchestrator flow,
voice loop, data integrity, RBAC, and bilingual Kannada/English coverage.

Per-function unit tests still live next to each Catalyst Function (see
`app/backend/functions/<name>/test_<name>.py`). This directory holds
the **cross-function**, **data-quality**, and **integration-vs-deployed**
suites.

---

## Quick start

```bash
# from repo root
pip install -r app/tests/requirements-test.txt

# fast hermetic suite — no network, no Catalyst, no Gemini (CI default)
pytest app/tests -m unit

# language-coverage sweep over the 30-query golden set
pytest app/tests -m bilingual

# data-quality sweep over data/firs_sample.jsonl
pytest app/tests -m data_quality

# live integration suite — requires a deployed orchestrator
export CATALYST_API_BASE=https://sarvik-XXXXXX.catalystserverless.in
export CATALYST_AUTH_TOKEN=<bearer>     # optional
pytest app/tests -m integration

# voice loop — requires audio fixtures + live deployment
# (drop sample wavs into tests/fixtures/audio/ first; see README there)
pytest app/tests -m voice
```

---

## Markers

| Marker | What it gates | When it runs |
|---|---|---|
| `unit` | Hermetic — fakes for Catalyst/Gemini/Neo4j | **always** in CI |
| `data_quality` | Read-only assertions on `data/firs_sample.jsonl` | always in CI |
| `bilingual` | Kannada + English language preservation | always in CI |
| `rbac` | Role-based access control + PII masking | always in CI |
| `integration` | Hits a deployed orchestrator (SSE) | only on `deploy` branch |
| `voice` | Voice ingress with sample wavs | only on `deploy` branch + when fixtures exist |
| `slow` | Anything > 2 s | run with `-m slow` if needed |

Combos that come up often:

```bash
pytest app/tests -m "unit or data_quality or bilingual or rbac"   # CI default
pytest app/tests -m "not integration and not voice"                # local dev loop
pytest app/tests -m "integration and bilingual"                    # live Kannada QA
```

---

## File layout

```
app/tests/
├── conftest.py                ← shared fixtures (mock clients, token factory, sample data)
├── pytest.ini                 ← marker registry + asyncio config
├── requirements-test.txt
├── README.md
│
├── test_e2e_query_flow.py     ← @integration — orchestrator happy paths
├── test_e2e_voice_flow.py     ← @integration @voice — voice STT/TTS loop
├── test_data_integrity.py     ← @unit @data_quality — synthetic FIR schema + distribution
├── test_rbac.py               ← @unit @rbac — PSI/SHO/DCP scope + masked PII
├── test_bilingual.py          ← @unit @bilingual — 30-query EN+KN sweep
│
└── fixtures/
    ├── audio/
    │   └── README.md          ← how to populate wav files
    └── queries/
        └── golden.json        ← 30 representative queries (15 EN + 15 KN)
```

---

## Required environment variables

| Var | Used by | Required? |
|---|---|---|
| `CATALYST_API_BASE` | `test_e2e_query_flow.py`, `test_e2e_voice_flow.py` | only for `-m integration` |
| `CATALYST_AUTH_TOKEN` | live tests | optional |
| `CATALYST_VOICE_PATH` | `test_e2e_voice_flow.py` | optional (default `/server/voice-ingress`) |

Unit-marked tests use **none** of these. A fresh checkout passes
`pytest -m "unit or data_quality or bilingual or rbac"` without any
setup beyond `pip install -r requirements-test.txt`.

---

## CI matrix

Recommended GitHub Actions matrix:

```yaml
strategy:
  matrix:
    suite:
      - {marker: "unit or data_quality or bilingual or rbac", needs_deploy: false}
      - {marker: "integration", needs_deploy: true}    # only on deploy branch
      - {marker: "voice",       needs_deploy: true}    # only on deploy branch
```

Gate logic:

```yaml
- name: Unit + quality + bilingual + RBAC
  if: matrix.suite.needs_deploy == false
  run: pytest app/tests -m "${{ matrix.suite.marker }}"

- name: Integration / voice (deploy branch only)
  if: matrix.suite.needs_deploy == true && github.ref == 'refs/heads/deploy'
  env:
    CATALYST_API_BASE: ${{ secrets.CATALYST_API_BASE }}
    CATALYST_AUTH_TOKEN: ${{ secrets.CATALYST_AUTH_TOKEN }}
  run: pytest app/tests -m "${{ matrix.suite.marker }}"
```

---

## Adding new tests

1. **Per-function tests** stay next to the function:
   `app/backend/functions/<name>/test_<name>.py` — mock heavily, no
   network. The orchestrator test (`test_orchestrator.py`) is the
   canonical reference.

2. **Cross-function tests** go here. Tag every test with at least one of
   the markers above; `pytest --strict-markers` will fail unmarked tests.

3. **Live integration tests** must pull the `integration_base_url`
   fixture so they auto-skip when `CATALYST_API_BASE` is unset.

4. **New languages?** Extend `_CANNED_ANSWERS` in `test_bilingual.py`
   and `ROLE_SCOPES` in `conftest.py`. The Kannada/English split is
   designed to be extended (Hindi is the obvious next addition once
   Catalyst Zia Hindi voice is wired up).

---

## Troubleshooting

**`ModuleNotFoundError: conftest`** in test files using
`from conftest import has_kannada_chars`: run pytest from the repo root
(`pytest app/tests`) or from `app/tests/` — never from a deeper
subdirectory, because `conftest.py` sits next to the test files.

**Kannada literals look like `ಕಲ` in test output**: that's
pytest's repr — the actual string is fine. Add `-s` and `print()` if
you want to see rendered Kannada.

**`pytest.skip` on every integration test**: `CATALYST_API_BASE` is
unset — expected outside the deploy branch. Set it to your live
deployment URL to run them.

**`h3` import fails in `test_data_integrity.py::test_h3_indexing_*`**:
`pip install h3>=4.0` (optional dep; the test auto-skips otherwise).
