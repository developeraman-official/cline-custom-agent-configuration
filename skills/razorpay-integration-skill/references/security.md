# Security & compliance

## Secrets
- `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` are **server-only** — never ship them to the
  client, never commit them. Only the **key id** (`rzp_...`) may appear client-side.
- Use **test** keys (`rzp_test_…`) in non-prod; rotate keys if ever exposed.
- Two different HMAC secrets for two different jobs: payment-verify uses the **key secret**;
  webhooks use the **webhook secret**. (See `references/orders.md`, `references/webhooks.md`.)

## Verify everything server-side
- Every payment: HMAC signature check before marking paid.
- Every webhook: timing-safe HMAC over the **raw** body before parsing.
- Re-fetch and assert amount/status from Razorpay for high-value flows; never trust client input.

## Encrypt PII at rest (AES-256-GCM)

If you store PAN or bank numbers (even transiently during onboarding), encrypt them. GCM is
authenticated (tamper-evident). Store `iv:authTag:ciphertext`; keep the 32-byte key in env.

```ts
import crypto from 'crypto'
const KEY = Buffer.from(process.env.ENCRYPTION_KEY!, 'hex')   // 32 bytes

export function encrypt(plain: string): string {
  const iv = crypto.randomBytes(12)
  const cipher = crypto.createCipheriv('aes-256-gcm', KEY, iv)
  const enc = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()])
  const tag = cipher.getAuthTag()
  return `${iv.toString('hex')}:${tag.toString('hex')}:${enc.toString('hex')}`
}
export function decrypt(blob: string): string {
  const [ivH, tagH, dataH] = blob.split(':')
  const decipher = crypto.createDecipheriv('aes-256-gcm', KEY, Buffer.from(ivH, 'hex'))
  decipher.setAuthTag(Buffer.from(tagH, 'hex'))
  return Buffer.concat([decipher.update(Buffer.from(dataH, 'hex')), decipher.final()]).toString('utf8')
}
```

## Data minimization (DPDP Act 2023 mindset)
- Don't retain sensitive data longer than needed. Once Razorpay has the PAN/bank (account
  activated), **clear the plaintext/ciphertext** and keep only **masked** forms for display:
  `pan_masked` (`XXXXX1234F`), `account_last4` (`1234`).
- Do this on the `account.activated` webhook (clear-after-confirm), and make it idempotent.

## Access control for stored PII
- Read/write secrets and PII only from server code with a privileged DB role.
- If your DB has row-level security, note that an RLS bypass (service role) is **independent** of
  table GRANTs — both layers matter. Don't rely on one alone.

## Avoid hardcoding
- No project refs, keys, or account ids hardcoded in source — env vars only. (A hardcoded test key
  in client config or a prod DB ref in a component is a smell to fix.)
