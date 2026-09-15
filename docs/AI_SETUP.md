# AI setup

**Optional.** Every reading works fully without it, in English, written from
rules. Follow this only if you want more fluent prose or languages other than
English.

Two providers are supported: **Google Gemini** (via AI Studio) and **Anthropic
Claude**. The running app has a live version of this page at `/setup/ai`, which
checks your actual environment and shows which provider is in use.

---

## What the AI does, and does not do

Every number in a reading is computed by the Vedic engine: planetary longitudes
from the Swiss Ephemeris, houses, divisional charts, Vimshottari dasha, yogas,
doshas and the domain scores. `apps/astro/` imports **no network library at
all** - it cannot call a model even if asked to.

| | |
|---|---|
| **Computed by the engine** | Positions, ascendant, houses, D9 and D10, dasha, yogas, doshas, strength scores, every band and verdict |
| **Written by rules** | The full report prose, in English - always, with no API key |
| **Optionally rewritten by AI** | Wording only, for fluency and other languages |
| **Never touched by AI** | Any placement, score, band or conclusion |

The model receives the findings and the rule-written draft, and is constrained
to narrate only what it is given. If it is unreachable, the report silently
keeps the rule-written text - generation is never blocked on it.

Why the separation matters: astrological calculation has correct answers. A
model asked to compute a chart produces fluent, plausible, *inconsistent*
output - the same person could get different planetary positions on different
days. Users cross-check against other kundli sites, and the engine's
determinism test (`test_identical_input_produces_identical_chart`) passes
byte-for-byte precisely because no model sits in that path.

---

## Option 1 - Google Gemini (AI Studio)

Free tier, no payment card required. The quickest way to start.

### Get a key

1. Go to <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key**. Copy it immediately.

> **Both key formats are valid.** AI Studio issues `AQ....` (current) and
> `AIza...` (legacy). If another tool rejects an `AQ.` key, that tool has a
> hardcoded `AIza` check - it is not a problem with your key. This app accepts
> both, and the SDK sends either on the `x-goog-api-key` header the native
> Gemini endpoint expects.

### Configure

```bash
.venv/bin/python -m pip install google-genai
```

> **Use the venv's Python, not a bare `pip`.** A bare `pip install` resolves
> through PATH and usually finds the system Python, and a virtualenv ignores
> `~/.local/lib` by default - so the package installs "successfully" and stays
> invisible to the server. `/setup/ai` prints the exact command for the
> interpreter it is running on.

Then put the key in `.env` beside `manage.py`:

```
GEMINI_API_KEY=AQ....
GEMINI_MODEL=gemini-2.5-pro      # optional, default gemini-2.5-flash
```

`.env` is preferable to exporting: it survives closing the terminal, and it
avoids shell-syntax differences (`export VAR=` in bash, `$env:VAR =` in
PowerShell, `set VAR=` in CMD).

`GOOGLE_API_KEY` is accepted as an alternative variable name.

---

## Option 2 - Anthropic Claude

Prepaid credit required. A Claude.ai chat subscription does **not** include API
access.

1. Create an account at <https://console.anthropic.com> - the developer console,
   separate from Claude.ai.
2. Add credit under **Billing**, and set a monthly spend limit while you are
   there. Without credit, requests fail with `credit_balance_too_low`.
3. **API Keys** → **Create Key**. Shown only once; begins `sk-ant-`.

```bash
.venv/bin/python -m pip install anthropic
```

Then `ANTHROPIC_API_KEY=sk-ant-...` in `.env`.

Optional: `ANTHROPIC_MODEL` (default `claude-opus-5`).

---

## Choosing a provider

When both are configured, **Gemini is used**. Pin a choice explicitly:

```
AI_PROVIDER=gemini       # or: anthropic, none, auto (default)
```

`none` disables AI narration even when a key is present - useful for comparing
the rule-written output against the AI version.

---

## Then restart

```bash
python demo/manage.py serve
```

Environment variables are read once at process start, so a running server will
not pick up a new key. Reload `/setup/ai` - the provider panel should show the
key detected.

> **Never commit a key.** `.env` is in `.gitignore`. A key pasted into a chat,
> an issue, or a public repository should be treated as compromised and rotated
> immediately - scrapers find them within minutes.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| SDK shows "not installed" but pip said "already satisfied" | pip installed into a different Python. A virtualenv ignores `~/.local/lib`, so a user-site install is invisible to it. Use the command shown in the provider card on `/setup/ai`, which names the running interpreter explicitly. |
| Panel still says "not set" | Variable exported in a different shell from the one running the server, or the server was not restarted. |
| Gemini `401 UNAUTHENTICATED` | Key wrong, revoked, or has stray quotes or whitespace. Create a fresh one in AI Studio. |
| Gemini `429 RESOURCE_EXHAUSTED` | Free-tier rate limit. Wait, or change `GEMINI_MODEL`. |
| Gemini empty response | Usually a safety block or an exhausted output budget; the server log names the finish reason. |
| Claude `authentication_error` | Key wrong or revoked. |
| Claude `credit_balance_too_low` | No credit on the account. |
| Report reads like the rules version | Narration failed and fell back by design. The server console carries an `AI narration unavailable` warning naming the reason. |

## Adding another provider

Drop a module into `apps/reports/providers/` exposing:

```python
NAME = "myprovider"
def model() -> str: ...
def status() -> dict: ...                       # see providers/gemini_api.py
def narrate(payload: dict, language: str) -> dict:   # raises on failure
```

Register it in `narrator_ai.PROVIDERS`. Nothing else in the codebase talks to a
model.
