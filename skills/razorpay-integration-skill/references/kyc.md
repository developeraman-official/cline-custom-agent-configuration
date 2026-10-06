# Linked-account KYC onboarding

Before a payee (seller) can receive Route transfers, their linked account must be **activated**.
A clean UX is a **2-step** flow; activation then happens automatically.

```
Step 1 — Identity:  business type + PAN (+ name)  →  address
Step 2 — Bank:      account no + IFSC + holder name  →  auto-trigger activation
                    (create account → stakeholder → request product → PATCH settlement + TnC)
```

## Step 1 — identity

Collect **business type** first; it changes where the PAN goes:

| business_type | PAN goes on | `legal_business_name` |
|---------------|-------------|------------------------|
| `individual` | the **stakeholder** (`kyc.pan`) | the person's name |
| `proprietorship` | the **stakeholder** (`kyc.pan`) | the business name (≠ PAN name) |
| company / partnership / etc. | the **account** (`legal_info.pan`) | the registered entity name |

> **Gotcha:** for individual & proprietorship, sending the personal PAN as the account's
> `legal_info.pan` causes a name mismatch and `needs_clarification`. Put it on the
> **stakeholder** instead. For proprietorship, the *business* name and the *PAN* name are
> different — keep them decoupled (`legal_business_name` vs the stakeholder's `name`).

Validate before sending:
- PAN: `^[A-Z]{5}[0-9]{4}[A-Z]$`
- IFSC: `^[A-Z]{4}0[A-Z0-9]{6}$`

## Step 2 — bank + auto-activate

When the seller submits bank details, run the whole activation chain server-side:

```ts
// 1. create the linked account (see references/route.md §1)
const { accountId } = await createLinkedAccount({ email, phone, legalBusinessName, businessType, panNumber, bankAccount, address })

// 2. stakeholder (individual/proprietor PAN lives here)
await createStakeholder(accountId, { name: panName, phone, email, panNumber })

// 3. request the route product
const { productId } = await requestProductConfiguration(accountId)

// 4. configure settlement + accept T&C → moves account toward activation
await updateProductConfiguration(accountId, productId, {
  settlements: { accountNumber, ifscCode, beneficiaryName },
  tncAccepted: true,
})
// store accountId + status; the rest of the lifecycle arrives via webhooks
```

The account then transitions `created → under_review → activated` (track via webhooks —
`references/webhooks.md`). Sometimes it short-circuits to `instantly_activated`.

## Status polling (complement to webhooks)

A "refresh status" button or cron can `GET /v2/accounts/:id`, but **must not downgrade** a newer
status from a stale read — use the `isStatusDowngrade()` guard (`references/route.md` §status).

## Clarification & resubmit

If the account hits `needs_clarification`, parse the reasons and let the seller fix only the
affected step, then PATCH only the requested fields — full procedure + reason-code map in
`references/recovery-playbook.md` §2.

## Data minimization (do this once activated)

Once Razorpay holds the PAN and bank details, you don't need the plaintext. On `account.activated`,
**clear the raw PII** and keep only masked forms (`pan_masked`, `account_last4`). See
`references/security.md`.

## Gotchas recap
- business_type decides PAN placement (stakeholder vs `legal_info.pan`).
- proprietor: business name ≠ PAN name — keep separate.
- the `route` product needs **both** the POST (request) and the PATCH (configure) to activate.
- don't send `requested_at` to the products endpoint.
