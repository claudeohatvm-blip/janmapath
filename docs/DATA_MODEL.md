# JanmaPath — Data Model

> Postgres holds identity, money and fulfilment. MongoDB holds astrology
> documents. See [`ARCHITECTURE.md` §5](ARCHITECTURE.md) for the reasoning behind
> the split.

Conventions:
- Primary keys are **UUIDv7** unless stated otherwise (time-sortable, non-enumerable).
- All money is **integer paise**, never float. Column suffix `_paise`.
- All timestamps are `timestamptz`, stored UTC.
- `created_at` / `updated_at` on every table via a `core.TimestampedModel` mixin.

---

## PostgreSQL

### `accounts`

**`users`** — canonical identity, keyed on verified phone.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `phone_e164` | varchar(16) | **unique, not null** · `USERNAME_FIELD` |
| `phone_verified_at` | timestamptz | null until OTP verified |
| `email` | citext | nullable, unique |
| `email_verified_at` | timestamptz | |
| `full_name` | varchar(150) | |
| `password_hash` | varchar(255) | nullable — Google users may have none |
| `preferred_language` | varchar(10) | `en`, `hi`, `ta`, `te`, `ml`, `kn`, `bn`, `mr` |
| `status` | varchar(20) | `active` · `suspended` · `deletion_requested` |
| `is_active` `is_staff` `is_superuser` | bool | Django auth |
| `date_joined` `last_login` | timestamptz | |

**`auth_identities`** — linked third-party credentials.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `user_id` | uuid | FK → users, cascade |
| `provider` | varchar(20) | `google` |
| `provider_sub` | varchar(255) | **unique with `provider`** — match on this, never email |
| `email` | citext | as reported by provider |
| `raw_profile` | jsonb | |

**`otp_requests`** — abuse forensics. *Live challenges are in Redis, not here.*

`id` · `phone_e164` · `purpose` (`register`/`login`/`link_phone`) · `ip` (inet) ·
`user_agent` · `outcome` (`sent`/`rate_limited`/`verified`/`failed`/`expired`) ·
`created_at`

> Index on `(phone_e164, created_at desc)` and `(ip, created_at desc)` for
> rate-limit queries and SMS-pumping detection.

**`refresh_tokens`** — rotating, with family reuse detection.

`id` · `user_id` · `family_id` (uuid) · `token_hash` (sha256, unique) ·
`issued_at` · `expires_at` · `revoked_at` · `replaced_by_id` · `user_agent` · `ip`

> On presentation of an already-revoked token, revoke the entire `family_id` —
> that signals theft.

**`consents`** — DPDP evidence trail.

`id` · `user_id` · `consent_type` (`dpdp_processing`/`terms`/`whatsapp_daily`/
`whatsapp_marketing`) · `version` · `granted_at` · `revoked_at` · `ip` ·
`evidence` (jsonb: page, copy shown, checkbox state)

> Consent is **versioned**. A policy change invalidates prior consent and
> requires re-consent.

---

### `profiles`

**`places`** — geocode cache.

`id` · `query_hash` (unique) · `display_name` · `lat` (numeric 9,6) · `lon` ·
`tz_id` (IANA) · `country` · `admin1` · `provider` · `provider_place_id`

**`birth_profiles`** — the input to every chart.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `user_id` | uuid | FK → users |
| `relation` | varchar(20) | `self` · `partner` · `child` · `other` |
| `full_name` | varchar(150) | |
| `gender` | varchar(20) | |
| `birth_date` | date | |
| `birth_time` | time | nullable when `time_accuracy = 'unknown'` |
| `time_accuracy` | varchar(20) | **`exact` · `approximate` · `unknown`** |
| `place_id` | uuid | FK → places |
| `lat` `lon` `tz_id` | — | **snapshot copied from place at creation** |
| `verified_at` | timestamptz | user confirmed data at first-run check |

> The lat/lon/tz snapshot is deliberate. If a `places` row is later corrected, an
> existing chart's inputs must not silently change beneath it.
>
> A user may hold at most one `relation='self'` profile — partial unique index.

---

### `kundli`

**`charts`** — pointer + immutable identity of a computed chart.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `birth_profile_id` | uuid | FK |
| `engine_version` | varchar(20) | semver of `apps/astro` |
| `ayanamsa` | varchar(20) | `lahiri` |
| `input_checksum` | varchar(64) | **unique with `(engine_version, ayanamsa)`** |
| `mongo_doc_id` | varchar(24) | → `mongo.charts` |
| `status` | varchar(20) | `pending` · `ready` · `failed` |
| `computed_at` | timestamptz | |

> The unique constraint makes recomputation idempotent and free.

**`chart_jobs`** — drives the SSE progress screen.

`id` · `birth_profile_id` · `status` · `stage` · `stage_index` · `error` ·
`started_at` · `finished_at`

**`chart_doshas`** — denormalised for querying and segmentation.

`id` · `chart_id` · `dosha_code` (`mangal`/`kaal_sarp`/`pitru`/`sade_sati`/
`shani_dhaiya`) · `severity` (`low`/`moderate`/`high`) · `is_cancelled` (bool)

> Full explanatory text stays in the Mongo chart document. This table exists so
> "users with high-severity Mangal dosha" is a join, not a collection scan.

---

### `reports`

**`reports`**

`id` · `user_id` · `chart_id` · `report_type` (`life`/`financial`/`marital`/
`remedy`) · `status` · `content_version` · `language` · `mongo_doc_id` ·
`pdf_key` (S3) · `generated_at`

**`report_prints`** — the print-after-pooja-and-post flow.

`id` · `report_id` · `service_booking_id` (nullable — the pooja) · `order_id` ·
`shipment_id` · `status` (`awaiting_pooja`/`queued`/`printed`/`shipped`/`delivered`)

---

### `billing`

**`plans`** — `code` (PK) · `name` · `price_paise` · `duration_days` ·
`features` (jsonb) · `is_active`

**`orders`**

`id` · `user_id` · `kind` (`subscription`/`extra_match`/`pooja`/`prasad`/
`report_print`/`consultation`/`wallet_topup`) · `amount_paise` · `currency` ·
`status` (`created`/`paid`/`failed`/`refunded`) · `metadata` (jsonb) · `created_at`

**`payments`**

`id` · `order_id` · `provider` · `provider_order_id` · `provider_payment_id`
(**unique**) · `amount_paise` · `status` · `method` · `captured_at` · `raw` (jsonb)

**`refunds`** — `id` · `payment_id` · `amount_paise` · `provider_refund_id` ·
`status` · `reason` · `created_at`

**`webhook_events`** — the idempotency guard.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `provider` | varchar(20) | |
| `provider_event_id` | varchar(255) | **UNIQUE with `provider`** ← the whole point |
| `event_type` | varchar(64) | |
| `payload` | jsonb | raw body as received |
| `signature_valid` | bool | |
| `received_at` `processed_at` | timestamptz | |
| `status` | varchar(20) | `received` · `processed` · `failed` · `ignored` |
| `error` | text | |

**`entitlements`** — what the user is actually allowed to do.

`id` · `user_id` · `plan_code` · `source_order_id` · `starts_at` · `ends_at` ·
`status` (`active`/`expired`/`revoked`) · `granted_reason` (`purchase`/`promo`/
`comp`/`refund_reversal`)

> Index `(user_id, status, ends_at)` — this is the hottest read in the app.

**`feature_quotas`**

`id` · `user_id` · `entitlement_id` · `feature` (`guna_matching`) ·
`limit_count` · `used_count` · `period_start` · `period_end`

> **Unique on `(entitlement_id, feature)`.** Increment via
> `F("used_count") + 1` with a conditional `WHERE used_count < limit_count` —
> never read-modify-write.

---

### `matching`

**`match_requests`**

`id` · `user_id` · `profile_a_id` · `profile_b_id` · `total_guna` (numeric 4,1) ·
`max_guna` (36) · `verdict` · `mongo_doc_id` · `was_charged` (bool) ·
`order_id` (nullable) · `quota_id` (nullable) · `created_at`

---

### `services`

**`service_catalog`** — `code` (PK) · `name` · `kind` (`pooja`/`remedy`/
`consultation`) · `base_price_paise` · `is_active` · `metadata` (jsonb)

**`temples`** — `id` · `name` · `deity` · `city` · `state` · `contact_name` ·
`contact_phone` · `is_active`

**`service_bookings`**

`id` · `user_id` · `service_code` · `temple_id` (nullable) · `deity` ·
`dosha_code` (nullable) · `scheduled_for` · `status` (`pending_payment`/
`confirmed`/`scheduled`/`performed`/`cancelled`) · `price_paise` · `order_id` ·
`wants_prasad` (bool) · `performed_at` · `evidence` (jsonb: photos, video URL) ·
`notes`

**`astrologers`**

`id` · `display_name` · `bio` · `languages` (text[]) · `specialities` (text[]) ·
`rate_per_min_paise` · `rating_avg` · `rating_count` · `status`
(`pending`/`verified`/`suspended`) · `verified_at` · `payout_ref`

> GIN index on `languages` — "book an astrologer who speaks Malayalam" is a core
> product promise.

**`astrologer_availability`** — `id` · `astrologer_id` · `weekday` ·
`start_time` · `end_time` · `tz_id`

**`consultations`**

`id` · `user_id` · `astrologer_id` · `channel` (`call`/`chat`/`video`) ·
`scheduled_at` · `started_at` · `ended_at` · `duration_sec` ·
`rate_per_min_paise` · `amount_paise` · `status` · `provider_ref` (Exotel call
SID) · `recording_key` · `user_rating`

**`wallet_accounts`** — `id` · `user_id` (**unique**) · `balance_paise` ·
`updated_at`

**`wallet_ledger`** — **append-only. Never update or delete a row.**

`id` · `wallet_id` · `direction` (`credit`/`debit`) · `amount_paise` ·
`balance_after_paise` · `reason` · `ref_type` · `ref_id` · `created_at`

> Balance on `wallet_accounts` is a cached projection. The ledger is the source
> of truth and must always reconcile. Writes happen inside `transaction.atomic()`
> with `SELECT ... FOR UPDATE` on the wallet row.

---

### `fulfilment`

**`addresses`** — `id` · `user_id` · `name` · `phone` · `line1` · `line2` ·
`city` · `state` · `pincode` · `country` · `is_default`

**`shipments`**

`id` · `user_id` · `kind` (`prasad`/`printed_report`) · `ref_type` · `ref_id` ·
`address_id` · `courier` · `awb` · `status` · `shipping_paise` · `shipped_at` ·
`delivered_at` · `provider_payload` (jsonb)

---

### `messaging`

**`notification_prefs`** — `user_id` (PK) · `whatsapp_daily` (bool) ·
`whatsapp_marketing` (bool) · `sms` · `email` · `send_hour_local` (default 6) ·
`updated_at`

**`whatsapp_messages`**

`id` · `user_id` · `template_name` · `language` · `payload` (jsonb) · `wamid` ·
`status` (`queued`/`sent`/`delivered`/`read`/`failed`) · `sent_at` ·
`delivered_at` · `read_at` · `error_code` · `error_detail`

---

### `core`

**`audit_log`** — `id` · `actor_user_id` (nullable for system) · `action` ·
`object_type` · `object_id` · `before` (jsonb) · `after` (jsonb) · `ip` ·
`created_at`

> Written for every admin mutation of users, orders, entitlements, wallets and
> bookings.

---

## MongoDB

Database: `janmapath`. Replica set **required** — transactions depend on it.

### `charts`

```jsonc
{
  "_id": ObjectId,
  "chart_pg_id": "uuid",              // back-pointer to postgres
  "input": {
    "birth_date": "1996-04-12",
    "birth_time": "14:35:00",
    "time_accuracy": "exact",
    "lat": 8.5241, "lon": 76.9366,
    "tz_id": "Asia/Kolkata",
    "utc_datetime": "1996-04-12T09:05:00Z"   // resolved, historical-aware
  },
  "engine": { "version": "1.0.0", "ayanamsa": "lahiri", "ephemeris": "swisseph" },
  "ascendant": { "sign": "Kanya", "degree": 17.42, "nakshatra": "Hasta", "pada": 2 },
  "planets": [
    { "body": "Sun", "longitude": 358.71, "sign": "Meena", "house": 7,
      "nakshatra": "Revati", "pada": 3, "retrograde": false, "dignity": "debilitated" }
  ],
  "houses": [ { "number": 1, "sign": "Kanya", "lord": "Mercury", "occupants": [] } ],
  "divisional_charts": { "D1": { }, "D9": { }, "D10": { } },
  "panchang": { "tithi": "Shukla Dwitiya", "yoga": "Siddha", "karana": "Bava", "vara": "Friday" },
  "dashas": {
    "vimshottari": {
      "balance_at_birth": { "lord": "Ketu", "years": 3.24 },
      "periods": [ { "lord": "Ketu", "start": "1996-04-12", "end": "1999-07-01",
                     "antar": [ ] } ]
    }
  },
  "analysis": {
    "doshas": [ { "code": "mangal", "severity": "moderate", "is_cancelled": false,
                  "basis": "Mars in 8th from Lagna", "explanation": "..." } ],
    "yogas": [ ],
    "suppressed": []                  // populated when time_accuracy = "unknown"
  },
  "computed_at": ISODate
}
```

> `suppressed` lists output withheld because birth time is unknown. The report
> renderer reads it and says so plainly rather than omitting silently.

### `reports`

```jsonc
{
  "_id": ObjectId,
  "report_pg_id": "uuid",
  "chart_pg_id": "uuid",
  "type": "life",
  "language": "en",
  "content_version": "1.0.0",
  "sections": [
    { "key": "overview", "title": "Your Chart at a Glance",
      "is_free": true,                 // drives the paywall boundary
      "blocks": [ { "type": "paragraph", "text": "..." } ] }
  ],
  "generation": { "model": "claude-opus-5", "finding_signature": "sha256:...",
                  "generated_at": ISODate }
}
```

> `is_free` on each section is what the free-preview / paywall split reads. The
> boundary is content configuration, not hard-coded view logic.

### `narrative_cache`

```jsonc
{
  "_id": "sha256 of (finding-set + language + content_version)",
  "kind": "daily" | "report_section" | "dosha_explanation",
  "language": "hi",
  "content": { },
  "model": "claude-opus-5",
  "hits": 4821,
  "created_at": ISODate
}
```

> The economics of the whole content pipeline live in this collection's hit rate.

### `daily_horoscopes`

```jsonc
{
  "_id": ObjectId,
  "date": "2026-09-15",
  "signature_hash": "sha256:...",     // (moon nakshatra, dasha lord, top-3 transits)
  "language": "en",
  "content": { "headline": "...", "body": "...", "lucky_colour": "...",
               "focus_area": "career" },
  "created_at": ISODate
}
```

> Compound index on `(date, signature_hash, language)`.

### `daily_dispatch`

```jsonc
{
  "_id": ObjectId,
  "date": "2026-09-15",
  "user_pg_id": "uuid",
  "signature_hash": "sha256:...",
  "personalisation": { "name": "Anjali", "chart_line": "..." },
  "status": "queued" | "sent" | "failed"
}
```

> The 02:30 diff writes here; the 05:45 fan-out reads it. TTL index on `date`,
> 30 days.

### `panchang_daily`

`_id` · `date` · `tz_id` · `sunrise` · `sunset` · `moonrise` · `tithi` ·
`nakshatra` · `yoga` · `karana` · `rahu_kalam` · `yamaganda` · `abhijit_muhurta`

### `transits_daily`

`_id` · `date` · `samples[]` (planetary longitudes at fixed intervals) ·
`ingresses[]` (sign changes occurring today) · `retrogrades[]`

### `match_results`

```jsonc
{
  "_id": ObjectId,
  "match_pg_id": "uuid",
  "kootas": [ { "name": "Varna", "max": 1, "scored": 1, "note": "..." },
              { "name": "Nadi",  "max": 8, "scored": 0, "note": "Nadi dosha present" } ],
  "total": 24.5,
  "dosha_compatibility": { "mangal": { "a": true, "b": false, "verdict": "mitigated" } },
  "narrative": { "summary": "...", "recommendation": "..." }
}
```

---

## Index summary

| Store | Index | Why |
|---|---|---|
| PG | `users(phone_e164)` unique | login lookup |
| PG | `auth_identities(provider, provider_sub)` unique | Google linking |
| PG | `otp_requests(phone_e164, created_at desc)` | rate limiting |
| PG | `charts(input_checksum, engine_version, ayanamsa)` unique | idempotent recompute |
| PG | `entitlements(user_id, status, ends_at)` | hottest read in the app |
| PG | `feature_quotas(entitlement_id, feature)` unique | quota enforcement |
| PG | `webhook_events(provider, provider_event_id)` unique | payment idempotency |
| PG | `payments(provider_payment_id)` unique | reconciliation |
| PG | `astrologers` GIN on `languages` | language-based booking |
| PG | `wallet_ledger(wallet_id, created_at)` | balance reconciliation |
| Mongo | `charts.chart_pg_id` | join from Postgres |
| Mongo | `daily_horoscopes(date, signature_hash, language)` | fan-out lookup |
| Mongo | `daily_dispatch(date, status)` + TTL on `date` | send queue |
| Mongo | `narrative_cache._id` | natural key, already indexed |
