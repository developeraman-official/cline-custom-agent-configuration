# Razorpay Integration — a Claude Code Skill

A reusable [Claude Code](https://docs.claude.com/en/docs/claude-code) **skill** that teaches Claude
how to implement and debug **Razorpay** correctly — including the parts the official docs gloss
over: **Razorpay Route** (marketplace payment splitting), **linked-account KYC onboarding**, the
full **webhook** surface (with the infamous `acc_` prefix bug), **refunds with retry**, **GST
invoices**, **PII encryption**, and a **known-errors recovery playbook**.

Distilled from a production Indian marketplace. **Patterns + reference code, not a drop-in
library** — adapt to your stack. India-focused (PAN, IFSC, GST). MIT-licensed.

> **Unofficial & independent.** This is a community project, **not affiliated with, authorized by,
> or endorsed by Razorpay.** "Razorpay®" is a trademark of Razorpay Software Private Limited, used
> here only nominatively to describe the service these patterns integrate with. No Razorpay source
> code or documentation text is reproduced — the prose and examples are original. Always verify
> against the [official Razorpay docs](https://razorpay.com/docs/).

## What's inside

```
razorpay-integration/
├── SKILL.md                       # entry: decision tree + checklist + gotchas (Claude reads this first)
├── .claude-plugin/                # makes it installable as a Claude Code plugin
│   ├── plugin.json
│   └── marketplace.json
├── references/
│   ├── orders.md                  # one-time payments (create → checkout → verify signature)
│   ├── subscriptions.md           # recurring billing + invoice reconciliation
│   ├── route.md            ⭐     # marketplace splitting: linked accounts, transfers, status race
│   ├── kyc.md                     # 2-step onboarding, clarification parsing, resubmit
│   ├── webhooks.md         ⭐     # signature verification, the acc_ bug, idempotency, serverless await
│   ├── refunds.md                 # create + retry, reversal-vs-refund
│   ├── invoices-gst.md            # India GST (CGST/SGST vs IGST)
│   ├── security.md                # AES-256-GCM PII encryption, data minimization
│   └── recovery-playbook.md ⭐    # known Razorpay errors → the exact fix
└── examples/                      # complete, copy-adaptable reference code
    ├── orders-create-verify.ts
    ├── route-onboarding.ts
    └── webhook-handler.ts
```

⭐ = the genuinely hard-to-find knowledge.

## Install & use (Claude Code)

Pick one:

**A. Personal skill (just you, all your projects)**
```bash
git clone https://github.com/<you>/razorpay-integration \
  ~/.claude/skills/razorpay-integration
```
Claude Code auto-discovers skills in `~/.claude/skills/`. Next time you ask Claude to "add Razorpay
Route" or "debug this Razorpay webhook", it loads this skill automatically (the `description` in
`SKILL.md` controls when it triggers).

**B. Project skill (commit it to a repo, share with your team)**
```bash
git clone https://github.com/<you>/razorpay-integration \
  <your-project>/.claude/skills/razorpay-integration
```

**C. As a plugin via a marketplace (one-command install for others)**
This repo already ships `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`, so once
it's on GitHub, users run (inside Claude Code):
```
/plugin marketplace add <you>/razorpay-integration
/plugin install razorpay-integration@razorpay-integration
```
(The `@razorpay-integration` suffix is the marketplace name — same as the plugin name here.)

> Tip: confirm the current plugin commands in your Claude Code with `/help` — the marketplace
> tooling evolves.

## How to publish this open-source (so anyone can use it)

1. Create a **public GitHub repo** (e.g. `razorpay-integration`) and push this folder to it.
2. Keep `README.md` + `LICENSE` (MIT) at the root.
3. **Before pushing, scan for secrets:** `gitleaks detect` (or `trufflehog filesystem .`). This
   skill ships **no** secrets, real account IDs, names, or emails by design — keep it that way.
4. The `.claude-plugin/` manifests are already included, so plugin install (method C) works out
   of the box. Optionally set `homepage`/`repository` in `plugin.json` to your repo URL.
5. Share the repo. Done — anyone can install via A, B, or C.

This works across Claude surfaces that support the Agent Skills format (Claude Code today; the
SKILL.md + references structure is the portable unit).

## Scope & disclaimers

- **Not affiliated with Razorpay.** "Razorpay" is a trademark of its owner. This is independent,
  community documentation of integration patterns.
- **India-specific** in places (Route, KYC, GST, PAN/IFSC) — flagged where it matters.
- **Patterns, not a library.** Examples use generic TypeScript and a `db`/`razorpay` placeholder;
  port them to your framework and data layer.
- **Verify against the current** [Razorpay API docs](https://razorpay.com/docs/api/) — APIs change.
- No warranty; see `LICENSE`.

## License

MIT (no `LICENSE` file is bundled in this repo copy; add one if you redistribute this skill). The license covers **this skill's documentation and example
code only**. It does **not** grant any rights to Razorpay's API, service, or trademarks (those
belong to Razorpay), and it doesn't need to — using a public API and naming it truthfully needs
no license. The examples are original; nothing here is copied from Razorpay's official docs.

## Contributing

PRs welcome — especially new `needs_clarification` reason codes, additional recovery procedures,
and non-India notes. Never include real account IDs, merchant names, emails, keys, or customer data
in examples or fixtures.
