# Webhooks

Webhooks are the **source of truth**. Client-side callbacks (the `handler` in `checkout.js`)
get lost — the user closes the tab, the network drops, the redirect fails. Every payment,
subscription, refund, and account-status change should be reconciled from a webhook.

## 1. Verify the signature on the RAW body

Razorpay signs the request body with your `RAZORPAY_WEBHOOK_SECRET` (set per-webhook in the
Razorpay Dashboard — **not** your API key secret). Verify **before** parsing JSON, and use a
timing-safe compare.

```ts
import crypto from 'crypto'

function verifyWebhookSignature(rawBody: string, signature: string, secret: string): boolean {
  const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex')
  const a = Buffer.from(expected, 'hex')
  const b = Buffer.from(signature, 'hex')
  if (a.length !== b.length) return false
  return crypto.timingSafeEqual(a, b)   // constant-time; prevents timing attacks
}

export async function POST(request: Request) {
  const rawBody = await request.text()                 // RAW string, not parsed JSON
  const signature = request.headers.get('x-razorpay-signature') ?? ''
  const secret = process.env.RAZORPAY_WEBHOOK_SECRET
  if (!secret) return json({ error: 'Webhook not configured' }, 500)

  if (!verifyWebhookSignature(rawBody, signature, secret)) {
    return json({ error: 'Invalid signature' }, 400)
  }
  const event = JSON.parse(rawBody)                     // safe to parse now
  // ... handle event.event ...
}
```

> ⚠️ If your framework auto-parses the body to JSON, re-serializing it will **not** match the
> signature (key order / whitespace differ). You must read the untouched raw bytes. In Next.js
> App Router, `await request.text()` gives you the raw body.

## 2. THE `acc_` prefix gotcha (Route account events)

For **account** events (`account.activated`, `account.needs_clarification`, etc.) the account
id appears in two places with **different formats**:

- `event.account_id` → **has** the `acc_` prefix (e.g. `acc_EXAMPLE123`)
- `payload.account.entity.id` → **no** prefix (e.g. `EXAMPLE123`)

If you store linked-account ids as `acc_...` (you should — that's what the create call returns),
look them up using `event.account_id`. Using `entity.id` silently finds nothing and the seller
never gets activated.

```ts
const account = event.payload?.account?.entity
const accountId =
  event.account_id ??                                  // preferred — already has acc_
  (account?.id ? `acc_${account.id}` : null)           // fallback — re-add the prefix
```

## 3. Idempotency

Razorpay **retries** any webhook that doesn't return `2xx`, and may deliver duplicates even on
success. Handlers must be safe to run twice:

- Use **upsert** keyed on the Razorpay entity id (`payment_id`, `subscription_id`, `refund_id`),
  not blind `insert`.
- Make state transitions conditional (`if already activated, no-op`).
- Log every event to an append-only audit table for debugging/replay.

## 4. Always return 2xx (even when you ignore an event)

Return `200` for events you don't handle and even for "record not found" — otherwise Razorpay
retries forever. Only return non-2xx when you genuinely want a retry (e.g. a transient DB error
you expect to recover).

```ts
const status = extractStatusFromEvent(event.event)
if (!status) return json({ received: true })           // unhandled type → ack, don't retry
// ...
if (!seller) return json({ received: true })           // not found → ack, investigate via logs
```

## 5. `await` your async work (serverless killer)

On serverless platforms (Vercel, Lambda) the runtime **freezes/kills the function the moment you
return the response**. Any promise you didn't await — a push notification, a cleanup job, a
secondary write — is silently dropped.

```ts
// ❌ dropped on serverless — function returns before this runs
sendPushNotification(sellerId)
return json({ received: true })

// ✅ await it (or use the platform's waitUntil / after())
await sendPushNotification(sellerId)
return json({ received: true })
```

Exception: genuinely fire-and-forget cleanup *can* be left un-awaited **only** if you accept it
may not run. Anything the user depends on must be awaited.

## 6. Events worth handling

| Domain | Events |
|--------|--------|
| Payments | `payment.captured`, `payment.failed` |
| Subscriptions | `subscription.activated`, `subscription.charged`, `subscription.halted`, `subscription.cancelled` |
| Refunds | `refund.processed`, `refund.failed` |
| Route accounts | `account.under_review`, `account.activated`, `account.instantly_activated`, `account.activated_kyc_pending`, `account.needs_clarification`, `account.suspended`, `account.rejected` |
| Route transfers | `transfer.processed`, `transfer.failed` |

You can point **multiple event types at one webhook URL** and branch on `event.event`, or use
separate URLs per domain (e.g. one for payments/subscriptions, one for Route). Each URL has its
**own** secret.

## 7. Reference handler skeleton (Route account events)

```ts
export async function POST(request: Request) {
  const rawBody = await request.text()
  const signature = request.headers.get('x-razorpay-signature') ?? ''
  if (!verifyWebhookSignature(rawBody, signature, process.env.RAZORPAY_WEBHOOK_SECRET!)) {
    return json({ error: 'Invalid signature' }, 400)
  }
  const event = JSON.parse(rawBody)

  const newStatus = extractStatusFromEvent(event.event)     // see references/route.md
  if (!newStatus) return json({ received: true })           // ack & ignore

  const account = event.payload?.account?.entity
  const accountId = event.account_id ?? (account?.id ? `acc_${account.id}` : null)
  if (!accountId) return json({ received: true })

  const seller = await db.sellers.findByRazorpayAccountId(accountId)
  if (!seller) return json({ received: true })              // ack; investigate via logs

  await db.sellers.update(seller.id, {
    razorpay_account_status: newStatus,
    ...(newStatus === 'activated' && {
      razorpay_activated_at: account.activated_at
        ? new Date(account.activated_at * 1000).toISOString()
        : new Date().toISOString(),
    }),
  })

  await db.razorpayAccountEvents.insert({                    // audit trail
    seller_id: seller.id, razorpay_account_id: accountId,
    event_type: event.event,
    payload: { previous_status: seller.razorpay_account_status, new_status: newStatus },
  })

  return json({ received: true })
}
```

> Webhooks are **authoritative**: a webhook may bypass the status-downgrade guard that polling
> uses (see `references/route.md` §status-downgrade), because Razorpay is telling you the truth.
