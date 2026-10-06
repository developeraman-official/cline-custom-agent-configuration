# Razorpay Route — marketplace payment splitting

Route lets one customer payment be **split** across multiple payees: the platform keeps a fee,
each seller gets their share. Payees are **Linked Accounts** that must be created and KYC-verified
(see `references/kyc.md`) before they can receive transfers.

This is the most under-documented corner of Razorpay. The flow:

```
1. Create Linked Account            POST /v2/accounts
2. Create Stakeholder               POST /v2/accounts/:id/stakeholders   (individual/proprietor PAN here)
3. Request product config (route)   POST /v2/accounts/:id/products
4. Update product config (bank+TnC) PATCH /v2/accounts/:id/products/:productId
   → account moves: created → under_review → activated   (track via webhooks)
5. Split at payment time            transfers on the Order/Payment
6. Hold → release after delivery    PATCH /v1/transfers/:id { on_hold: 0 }
7. Reverse on refund                POST /v1/transfers/:id/reversals
```

> The Node SDK has no typed methods for v2 Route endpoints. Call the raw HTTP client:
> `(razorpay as any).api.post({ version: 'v2', url: '/accounts', data })`. Pass `version`
> separately — the SDK prepends `/{version}` to the url. v1 endpoints (transfers) omit `version`.

## Account status lifecycle

```
not_started → created → under_review → activated
                  └→ needs_clarification ⇄ (resubmit) → under_review → activated
activated → suspended | rejected   (terminal-ish; Razorpay-initiated)
```

Map Razorpay's status to yours and derive status from webhook event names:

```ts
export type AccountStatus =
  | 'not_started' | 'created' | 'needs_clarification'
  | 'under_review' | 'activated' | 'suspended' | 'rejected'

export function extractStatusFromEvent(eventType: string): AccountStatus | null {
  return ({
    'account.under_review': 'under_review',
    'account.activated': 'activated',
    'account.instantly_activated': 'activated',
    'account.activated_kyc_pending': 'activated',
    'account.needs_clarification': 'needs_clarification',
    'account.suspended': 'suspended',
    'account.rejected': 'rejected',
  } as Record<string, AccountStatus>)[eventType] ?? null
}
```

## ⚠️ The status-downgrade race (must-fix)

You'll poll the account status (a "sync now" button, or a cron) to complement webhooks. But a
Razorpay **read-after-write can be stale** — you submit a resubmission, the account moves to
`needs_clarification`, and a poll 1 second later returns the *old* `created`, overwriting the
newer status. Real accounts get **stuck** this way.

Fix: a status-priority guard. **Webhooks are authoritative** (they bypass it); **polling** must
never downgrade.

```ts
const STATUS_PRIORITY: Record<string, number> = {
  not_started: 0, created: 1, under_review: 2,
  needs_clarification: 3, activated: 4, suspended: 5, rejected: 5,
}

export function isStatusDowngrade(current: string, next: string): boolean {
  // These can legitimately arrive from any state — never treat as a downgrade:
  if (next === 'needs_clarification' || next === 'suspended'
      || next === 'rejected' || next === 'activated') return false
  return (STATUS_PRIORITY[next] ?? 0) < (STATUS_PRIORITY[current] ?? 0)
}

// in the polling endpoint:
if (!isStatusDowngrade(seller.razorpay_account_status, fetched.status)) {
  await db.sellers.update(seller.id, { razorpay_account_status: fetched.status })
}
```

## 1. Create the Linked Account

```ts
const payload: Record<string, any> = {
  email, phone,
  type: 'route',
  legal_business_name: legalBusinessName,
  business_type: businessType,                 // 'individual' | 'proprietorship' | ...
  contact_name: legalBusinessName,
  profile: {
    category: 'ecommerce', subcategory: 'ecommerce_marketplace',
    addresses: { registered: {
      street1, street2, city, state, postal_code: postalCode, country: 'IN',
    } },
  },
}
// company PAN ONLY here. For individual/proprietor, PAN goes on the stakeholder (see kyc.md):
if (!['individual', 'proprietorship'].includes(businessType) && panNumber) {
  payload.legal_info = { pan: panNumber }
}
const res = await (razorpay as any).api.post({ version: 'v2', url: '/accounts', data: payload })
// res.id === 'acc_...'  → store this; it's your lookup key everywhere
```

## 2. Product configuration (the "enable Route" handshake)

After the stakeholder, request the `route` product, then PATCH settlement (bank) details + accept
T&C. The response carries `activation_status` and a `requirements[]` array describing anything
still missing (feeds the clarification parser — see `references/kyc.md`).

```ts
// request
const prod = await (razorpay as any).api.post({
  version: 'v2', url: `/accounts/${accountId}/products`,
  data: { product_name: 'route' },             // do NOT send requested_at — Razorpay rejects it
})
// configure settlement + accept T&C
await (razorpay as any).api.patch({
  version: 'v2', url: `/accounts/${accountId}/products/${prod.id}`,
  data: {
    settlements: { account_number, ifsc_code, beneficiary_name },
    tnc_accepted: true,
  },
})
```

## 3. Splitting a payment (transfers)

Create transfers as part of the Order, or directly on the captured payment. Each transfer routes
an amount (paise) to a linked account; `on_hold` lets you delay settlement until delivery.

```ts
// Example: split via order creation
const order = await razorpay.orders.create({
  amount: totalPaise, currency: 'INR',
  transfers: [{
    account: sellerAccountId,                  // 'acc_...'
    amount: sellerSharePaise,                   // total - platform fee
    currency: 'INR',
    on_hold: 1,                                 // hold until you release post-delivery
    notes: { order_id: yourOrderId },
  }],
})
// after payment, fetch the transfer ids to store them:
const { transfers } = await fetchPaymentTransfers(paymentId) // GET /payments/:id/transfers → items[]
```

The **platform fee** is simply what you *don't* transfer: `platformFee = total - Σ transfers`.
Keep fee logic in your own code; Route just moves the amounts you tell it to.

## 4. Hold → release → reverse

```ts
// release a held transfer (e.g. 7 days after delivery)
await (razorpay as any).api.patch({ url: `/transfers/${transferId}`, data: { on_hold: 0 } })

// reverse a transfer on refund/cancellation (Razorpay auto-refunds the buyer)
await (razorpay as any).api.post({
  url: `/transfers/${transferId}/reversals`, data: { amount: amountInPaise },
})
```

## 5. Data model you'll need (adapt to your DB)

- `sellers.razorpay_account_id` (`acc_...`), `razorpay_account_status`, `razorpay_activated_at`
- an append-only `razorpay_account_events` audit table (`seller_id`, `account_id`, `event_type`, `payload`, `created_at`)
- per-order transfer ids + on_hold/released/reversed state

## Gotchas recap
- Store and look up by the **`acc_` id**; webhooks deliver it as `event.account_id` (see `references/webhooks.md`).
- **Individual/proprietor PAN → stakeholder**, not `legal_info.pan`.
- **Don't send `requested_at`** to the products endpoint.
- **Guard polling against downgrades**; webhooks win.
- All amounts **paise**, integers.
- See `references/recovery-playbook.md` for `needs_clarification`, duplicate-email, and suspended-account recovery.
