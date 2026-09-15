# AI setup

**Optional.** Every reading works fully without it, in English, written from
rules. Follow this only if you want more fluent prose or languages other than
English.

The running app has a live version of this page at `/setup/ai`, which checks
your actual environment and tells you what is and is not detected.

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

## Getting a key

1. **Create an account** at <https://console.anthropic.com>.
   This is the developer console, separate from a Claude.ai chat subscription -
   a Claude Pro plan does **not** include API access.

2. **Add credit** under *Billing*. The API is prepaid; a new account needs a
   minimum first purchase. Without credit every request fails with
   `credit_balance_too_low`.

3. **Create the key** under *API Keys* → *Create Key*. Name it something like
   `janmapath-demo`. **Copy it immediately** - the full key is shown only once.
   It begins with `sk-ant-`.

4. **Set a monthly spend limit** in the console. The single most useful
   safeguard against a runaway loop during development.

---

## Configuring the app

### 1. Install the SDK

```bash
pip install anthropic
```

### 2. Provide the key

Either export it:

```bash
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Or put it in a `.env` file beside `manage.py` (copy `.env.example`):

```
ANTHROPIC_API_KEY=sk-ant-...
```

`manage.py` loads `.env` on start. Exported variables always win over the file.

> **Never commit the key.** `.env` is in `.gitignore`. A key pushed to a public
> repository is scraped within minutes - revoke it in the console immediately if
> that happens.

### 3. Restart and verify

```bash
python demo/manage.py runserver
```

Open `/setup/ai`. The status panel should show the SDK installed and the key
detected, and the narration toggle then appears on the reading form.

---

## Cost

The app uses `claude-opus-5`. One reading sends roughly 4,000 input tokens (the
findings plus the draft) and receives about 2,500 output tokens - on the order
of **8 US cents per report**.

At production scale the daily-horoscope pipeline dominates cost, not reports.
Narration there is generated per *signature group* rather than per user and then
cached, which is what makes it affordable. See [`ARCHITECTURE.md`](ARCHITECTURE.md) §8.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Page still says "not set" | The variable was exported in a different shell from the one running the server, or the server was not restarted. Environment variables are read once at process start. |
| `authentication_error` | Key is wrong, revoked, or has stray whitespace or quotes. Create a fresh key; paste it without surrounding quotes. |
| `credit_balance_too_low` | No credit on the account. Add credit under Billing. |
| `rate_limit_error` | Too many requests for the account tier. Wait and retry; limits rise with usage history. |
| Report reads like the rules version | Narration failed and fell back by design. Check the server console for an `AI narration unavailable` warning with the reason. |

## Using a different provider

Replace `apps/reports/narrator_ai.py`. It has one entry point -
`narrate(report, findings, language)` - and returns the report unchanged on any
failure. Nothing else in the codebase talks to a model.
