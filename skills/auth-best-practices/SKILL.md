---
name: auth-best-practices
description: Authentication best practices implemented in this Next.js project to prevent privilege escalation and secure user sessions
---

# Auth Best Practices

This skill documents the authentication security improvements made to fix a NextAuth privilege escalation vulnerability and implement defense-in-depth security.

## Vulnerability Fixed

**Issue**: Free users could manipulate session data (via client-side tampering) to gain enterprise/admin access by modifying the `tier` and `accessToken` fields in their JWT session.

**Root Cause**: The NextAuth `update` callback was trusting client-supplied values for `tier` and `accessToken` without re-verifying against the source of truth (Google Sheets database).

## Implemented Fixes

### 1. JWT Callback Hardening (`lib/auth.ts`)

- **Never trust client-supplied tier/accessToken**: In the JWT callback (especially on `update` events), ignore any `tier` or `accessToken` values coming from the client token.
- **Source of truth**: Always fetch the latest user data from the Google Sheets database using the user's email (normalized identifier) to set `tier` and `accessToken` in the JWT.
- **Session exposure**: Removed `accessToken` from the session object returned to the client to prevent leakage.
- **User ID normalization**: For Google provider, use the user's email as the consistent `user.id` instead of the Google sub ID, which can change in edge cases.

```typescript
// In lib/auth.ts - JWT callback
async function jwt({ token, user, account, trigger, session }) {
  // Sign in
  if (account && user) {
    // ... (token setup)
    
    // CRITICAL: Always verify tier from database, never trust client input
    const dbUser = await getUserFromDatabase(user.email?.toLowerCase());
    if (dbUser) {
      token.tier = dbUser.tier;
      token.accessToken = dbUser.accessToken; // Only stored in JWT, not session
    }
    
    return token;
  }
  
  // Update (client-side session modification attempt)
  if (trigger === "update") {
    // IGNORE any client-supplied tier/accessToken - refetch from database
    const dbUser = await getUserFromDatabase(token.email?.toLowerCase());
    if (dbUser) {
      token.tier = dbUser.tier;
      token.accessToken = dbUser.accessToken;
    }
    // Return token with database-verified values only
    return token;
  }
  
  return token;
}
```

### 2. Defense-in-Depth Tier Verification (`lib/auth/require-tier.ts`)

Created a reusable server-side utility that re-verifies a user's tier from the database at authorization boundaries (API routes, server components).

```typescript
// lib/auth/require-tier.ts
import { getUserFromDatabase } from "./google-sheets";

export async function requireTier(userId: string, requiredTier: string[]) {
  const user = await getUserFromDatabase(userId.toLowerCase());
  if (!user) {
    throw new Error("User not found");
  }
  
  if (!requiredTier.includes(user.tier)) {
    throw new Error(`Insufficient tier: ${user.tier}`);
  }
  
  return user;
}
```

**Usage in API routes**:
```typescript
// Example: app/api/max-audit/route.ts
import { requireTier } from "@/lib/auth/require-tier";
import { auth } from "@/auth";

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.email) {
    return new Response("Unauthorized", { status: 401 });
  }
  
  // Defense-in-depth: Verify tier from database
  await requireTier(session.user.email, ["enterprise", "max"]);
  
  // ... proceed with enterprise-only logic
}
```

### 3. Session Token Minimization

- The `accessToken` (for Google Sheets API) is **only** stored in the encrypted JWT cookie, never exposed in the client-side session object.
- Prevents XSS attacks from stealing the backend API token.

## Additional Security Improvements (Auth-Adjacent)

While not strictly authentication, these improvements protect auth-related API routes:

### SSRF Protection (`lib/ssrf-protection.ts`)
- All API routes that fetch external URLs (page speed, keyword research, SEO audit) now validate URLs are public and not pointing to localhost/internal IPs.
- Prevents attackers from using the server as a proxy to access internal services.

### Safe Error Handling (`lib/error-utils.ts`)
- Auth-related API routes now log detailed errors server-side but return generic messages to clients.
- Prevents leakage of stack traces, database structure, or internal URLs.

### Rate Limiting Improvements (`lib/rate-limit.ts`)
- Added proactive cleanup mechanism to prevent memory leaks in the rate limit store.
- Protects auth endpoints from brute-force attacks.

### Security Headers (`middleware.ts`)
- Enhanced Content Security Policy and Strict-Transport-Security headers.
- Protects against XSS and ensures HTTPS-only communication.

## Key Principles Applied

1. **Never trust the client**: Always re-verify critical permissions (tier, access) from the source of truth on the server.
2. **Defense in depth**: Multiple layers of protection (JWT hardening + live verification at API boundaries).
3. **Principle of least privilege**: Sessions contain only what's needed for the UI; sensitive tokens are kept server-side.
4. **Fail closed**: When in doubt, deny access (e.g., user not found in database → unauthorized).

## Files Architecture

- `lib/auth.ts` - JWT callback hardening
- `lib/auth/require-tier.ts` - New defense-in-depth verification utility
- `middleware.ts` - Enhanced security headers
- Various API routes (`app/api/*/route.ts`) - Added tier verification, SSRF protection, safe error handling
- `lib/ssrf-protection.ts` - New SSRF utility
- `lib/error-utils.ts` - New safe error handling utility
- `lib/rate-limit.ts` - Improved rate limiting with cleanup

## Testing Verification

- All changes compile with zero TypeScript errors.
- Manual testing confirmed:
  - Free users cannot access enterprise endpoints even after tampering with session cookies.
  - Enterprise users retain access when their database tier is correct.
  - Error messages do not leak internal details.
  - External URL fetching is blocked for localhost/internal IPs.

This skill encapsulates the auth security hardening implemented to resolve the privilege escalation vulnerability and establish robust authentication practices.