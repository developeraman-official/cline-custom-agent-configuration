/**
 * Razorpay webhook handler. Mirrors references/webhooks.md. Generic — adapt `db`
 * and the HTTP shape (this uses a Web `Request`/`Response`, like a Next.js route).
 *
 * Covers: raw-body signature verification, the acc_ prefix lookup, idempotency,
 * always-2xx, and event dispatch (payments, refunds, route accounts).
 */
import crypto from 'crypto'

// --- placeholder data layer ---
declare const db: {
  sellers: {
    findByRazorpayAccountId(accId: string): Promise<{ id: string; razorpay_account_status: string } | null>
    update(id: string, patch: Record<string, any>): Promise<void>
  }
  events: { insert(row: Record<string, any>): Promise<void> } // append-only audit
  payments: { markCaptured(paymentId: string): Promise<void> }
  refunds: { setStatusByRazorpayId(refundId: string, status: string): Promise<void> }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

function verify(rawBody: string, signature: string, secret: string): boolean {
  const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex')
  const a = Buffer.from(expected, 'hex')
  const b = Buffer.from(signature, 'hex')
  return a.length === b.length && crypto.timingSafeEqual(a, b)
}

const ACCOUNT_EVENT_STATUS: Record<string, string> = {
  'account.under_review': 'under_review',
  'account.activated': 'activated',
  'account.instantly_activated': 'activated',
  'account.activated_kyc_pending': 'activated',
  'account.needs_clarification': 'needs_clarification',
  'account.suspended': 'suspended',
  'account.rejected': 'rejected',
}

export async function POST(request: Request): Promise<Response> {
  // 1) Verify on the RAW body BEFORE parsing.
  const rawBody = await request.text()
  const signature = request.headers.get('x-razorpay-signature') ?? ''
  const secret = process.env.RAZORPAY_WEBHOOK_SECRET
  if (!secret) return json({ error: 'Webhook not configured' }, 500)
  if (!verify(rawBody, signature, secret)) return json({ error: 'Invalid signature' }, 400)

  const event = JSON.parse(rawBody)
  const type: string = event.event

  try {
    // 2) Payments
    if (type === 'payment.captured') {
      await db.payments.markCaptured(event.payload.payment.entity.id) // idempotent upsert
      return json({ received: true })
    }

    // 3) Refunds
    if (type === 'refund.processed' || type === 'refund.failed') {
      const refund = event.payload.refund.entity
      await db.refunds.setStatusByRazorpayId(refund.id, refund.status) // idempotent
      return json({ received: true })
    }

    // 4) Route account events
    const newStatus = ACCOUNT_EVENT_STATUS[type]
    if (newStatus) {
      const entity = event.payload?.account?.entity
      // THE GOTCHA: event.account_id has the acc_ prefix; entity.id does not.
      const accountId = event.account_id ?? (entity?.id ? `acc_${entity.id}` : null)
      if (!accountId) return json({ received: true }) // ack; investigate via logs

      const seller = await db.sellers.findByRazorpayAccountId(accountId)
      if (!seller) return json({ received: true }) // ack; not found is not retryable

      await db.sellers.update(seller.id, {
        razorpay_account_status: newStatus, // webhooks are authoritative (no downgrade guard)
        ...(newStatus === 'activated' && {
          razorpay_activated_at: entity?.activated_at
            ? new Date(entity.activated_at * 1000).toISOString()
            : new Date().toISOString(),
        }),
      })
      await db.events.insert({
        seller_id: seller.id,
        razorpay_account_id: accountId,
        event_type: type,
        payload: { previous_status: seller.razorpay_account_status, new_status: newStatus },
      })
      return json({ received: true })
    }

    // 5) Unhandled type — acknowledge so Razorpay stops retrying.
    return json({ received: true })
  } catch (err) {
    // Returning 200 prevents infinite retries on parse/programming errors.
    // Return non-2xx ONLY for transient failures you actually want retried.
    console.error('Webhook processing error:', err)
    return json({ received: true, error: 'processing_failed' })
  }
}
