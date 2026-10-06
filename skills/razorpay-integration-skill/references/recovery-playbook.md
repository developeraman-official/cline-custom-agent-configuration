# Recovery playbook — known Razorpay errors → the fix

The procedures Razorpay's docs don't give you. When a linked account gets stuck during
onboarding, work top-down: **always start by reading the account's event history** (your audit
table + a live `GET /v2/accounts/:id`) so you know the real current state before acting.

## Quick lookup

| Symptom / error | Likely cause | Go to |
|-----------------|--------------|-------|
| `BAD_REQUEST_DUPLICATE_ACCOUNT_EMAIL` ("Merchant email already exists for account - acc_…") | The email is already attached to another Razorpay account | [§1 Duplicate email](#1-duplicate-email--alias-workaround) |
| Account `needs_clarification`, seller doesn't know why | Razorpay flagged specific fields | [§2 Clarification + resubmit](#2-needs_clarification--parse-reasons--resubmit) |
| `"Only fields requested for needs clarification are allowed for update"` | Trying to PATCH a field Razorpay didn't ask for | [§3 Locked fields](#3-locked-fields-error) |
| Status keeps reverting (e.g. `needs_clarification` → `created`) | Polling overwrote with a stale read | [§4 Status downgrade](#4-status-downgrade-race) |
| Razorpay **suspended** the account (their side) | Risk/compliance action by Razorpay | [§5 Suspended account](#5-suspended-account-email-locked-recovery) |
| Everything looks fine but seller still can't receive money | Product config (route) not activated | [§6 Activation didn't finish](#6-activation-didnt-finish) |

---

## 1. Duplicate email — alias workaround

**Error:** `BAD_REQUEST_DUPLICATE_ACCOUNT_EMAIL`. Razorpay enforces one account per email. Common
when a seller previously started onboarding, or used the same email elsewhere.

**Fix:** register the linked account under a **plus-alias** of the same inbox. Most providers
(Gmail, Outlook/Microsoft 365, iCloud, Fastmail, Proton) route `name+tag@domain.com` to
`name@domain.com`, so the seller still gets all Razorpay mail, but Razorpay sees a distinct email.

```ts
// e.g. seller@example.com + 'pay' → seller+pay@example.com
function generateAliasEmail(email: string, suffix: string): string {
  const [local, domain] = email.split('@')
  return `${local}+${suffix}@${domain}`
}

const PLUS_ALIAS_DOMAINS = new Set([
  'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com',
  'icloud.com', 'me.com', 'fastmail.com', 'protonmail.com', 'proton.me',
])
function supportsPlusAliasing(email: string): boolean {
  return PLUS_ALIAS_DOMAINS.has(email.split('@')[1]?.toLowerCase())
}
```

Procedure:
1. Confirm the domain supports plus-aliasing (custom domains usually do too, but verify).
2. Create the linked account with the alias email; keep the seller's *login* email unchanged in your app.
3. Store the alias you used (`razorpay_account_email`) so support can trace it later.
4. Tell the seller (one email): "we registered your payments under `seller+pay@…`; it still reaches your inbox."

Guardrails worth adding: feature-flag it, rate-limit it, validate the suffix, and handle
`ALIAS_ALSO_TAKEN` (try a different suffix).

---

## 2. `needs_clarification` → parse reasons → resubmit

Razorpay puts an account in `needs_clarification` and attaches a `requirements[]` array (and/or
`bank_details_verification_status`, `legal_info.pan_verification_status`) describing what's wrong.
Map those reason codes to human messages and let the seller fix only the affected step.

```ts
const REASON_MESSAGES: Record<string, { message: string; step: 1 | 2 }> = {
  bank_details_not_matching:    { message: 'Account holder name doesn’t match your PAN.', step: 2 },
  invalid_ifsc:                 { message: 'IFSC is invalid or wrong branch.',            step: 2 },
  beneficiary_name_not_matching:{ message: 'Beneficiary name doesn’t match bank records.', step: 2 },
  pan_verification_failed:      { message: 'PAN could not be verified.',                  step: 1 },
  invalid_pan:                  { message: 'PAN is invalid.',                             step: 1 },
  address_proof_mismatch:       { message: 'Address doesn’t match records.',             step: 1 },
  // ...extend as you encounter new codes
}
```

Resubmit by PATCHing **only** the requested fields:
- Bank/settlement issues → `PATCH /v2/accounts/:id/products/:productId` with new `settlements`.
- PAN/identity/address → `PATCH /v2/accounts/:id` (and/or the stakeholder).

After a successful resubmit the account returns to `under_review`. Then **don't let polling
downgrade it** (§4).

---

## 3. Locked-fields error

**Error:** `"Only fields requested for needs clarification are allowed for update"`. You tried to
PATCH a field Razorpay didn't flag.

**Fix:** PATCH *only* the exact fields in the `requirements[]`/clarification reasons. If the seller
needs to change something Razorpay didn't ask about (e.g. switching business type), you generally
can't — you must **reset and recreate** the linked account (§3a).

### 3a. Reset & recreate (admin recovery)
When an account is wedged (wrong business type submitted, locked fields), the clean path is to
unlink and start over:
1. **Block if unsafe:** never reset an `activated` account that has payment history.
2. Clear your stored `razorpay_account_id` / status / account_email (keep an audit row).
3. Have the seller re-run onboarding from step 1 with correct data.
4. Require a reason + rate-limit the action; it's destructive to onboarding state.

---

## 4. Status-downgrade race

**Symptom:** an account's status flips back to an earlier state on its own. **Cause:** your polling
endpoint read a stale status from Razorpay and overwrote a newer one. **Fix:** the
`isStatusDowngrade()` guard in `references/route.md` — polling never downgrades; webhooks are
authoritative.

---

## 5. Suspended account (email-locked recovery)

When Razorpay **suspends** an account on their side, the merchant email is often locked to the
suspended account, so you can't simply re-onboard with it.

Procedure (coordinate with Razorpay support — open a ticket first):
1. Verify state via `GET /v2/accounts/:id` and your event log; confirm it's a Razorpay-side suspension.
2. Open a support ticket referencing the `acc_…` id; ask for the path to re-activate or release the email.
3. Per their guidance, re-onboard using a distinct email — the **`+1` / plus-alias** trick (§1) is
   the usual unblock (`seller+1@example.com`).
4. Seller resubmits bank/identity; watch the webhooks back to `activated`.
5. Revert any temporary email change once activated; record the whole sequence in your audit log.

Keep an internal history table (account id, dates, ticket #, action) — these cases recur and the
trail saves hours.

---

## 6. Activation didn't finish

Account shows `created`/`under_review` forever, or is `activated` but transfers fail:
- Did you **request *and* configure** the `route` product (both the POST and the PATCH)? Missing the
  PATCH (settlement + `tnc_accepted`) leaves it un-activated.
- Re-fetch `GET /v2/accounts/:id/products/:productId` and inspect `activation_status` + `requirements[]`.
- Confirm the webhook that should have flipped your DB actually arrived (check the audit table) — if
  not, your signature check or the `acc_` lookup (`references/webhooks.md`) is the suspect.

---

## Diagnostic checklist (run before any fix)
1. `GET /v2/accounts/:id` — what does Razorpay *actually* say right now?
2. Your `razorpay_account_events` audit table — what transitions happened, and when?
3. Compare the two — a divergence usually means a missed webhook or a downgrade overwrite.
4. Only then choose a procedure above. Never guess-and-PATCH a live account.
