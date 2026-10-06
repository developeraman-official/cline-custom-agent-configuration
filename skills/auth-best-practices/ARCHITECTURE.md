# Authentication Architecture

## Overview

This document describes the authentication architecture implemented in this Next.js application using NextAuth.js v5, with security enhancements to prevent privilege escalation and ensure robust session management.

## Core Components

### 1. NextAuth Configuration (`lib/auth.ts`)

The central authentication configuration that handles:

- Provider configuration (Google OAuth)
- JWT token creation and validation
- Session creation and serialization
- Security callbacks (especially critical JWT update handling)

### 2. Database Layer (Google Sheets or relational db)

User data is stored in Google Sheets with the following schema:

- Email (primary key, normalized to lowercase)
- Tier (free, pro, enterprise, max)
- AccessToken (encrypted Google Sheets API token)
- CreatedAt, UpdatedAt timestamps

### 3. Defense-in-Depth Verification (`lib/auth/require-tier.ts`)

A reusable utility that re-verifies user tier from the database at authorization boundaries.

### 4. API Route Protection Pattern

All protected API routes follow this pattern:

```typescript
// 1. Get session from NextAuth
const session = await auth();
// 2. Verify user is authenticated
if (!session?.user?.email) return unauthorized();
// 3. DEFENSE-IN-DEPTH: Verify tier from database
await requireTier(session.user.email, ["required", "tiers"]);
// 4. Proceed with protected logic
```

## Data Flow

### Sign-In Flow

1. User authenticates via Google OAuth
2. NextAuth creates initial JWT token
3. **JWT Callback**: Fetches user from database using email
4. Sets `tier` and `accessToken` in JWT from database (never from user object)
5. Returns JWT token (encrypted cookie)
6. Session object created (contains only non-sensitive data: email, name, image, tier)

### Session Update Flow (Client-Side Tampering Attempt)

1. User attempts to modify session (e.g., change tier to "enterprise")
2. NextAuth triggers JWT callback with `trigger === "update"`
3. **JWT Callback**: IGNORES client-supplied tier/accessToken
4. Refetches user from database using email from token
5. Resets token values to database-verified values
6. Returns corrected JWT token
7. Client receives secure session with correct tier

### API Access Flow

1. Request includes encrypted JWT cookie
2. NextAuth validates and decrypts JWT
3. API route handler:
   - Calls `auth()` to get session
   - Validates session exists
   - Calls `requireTier()` with email and required tiers
   - Database verification occurs here (second source of truth check)
   - Proceeds if verification passes

## Security Boundaries

### Trust Boundaries

- **Client Side**: Completely untrusted - can send any data
- **JWT Cookie**: Trusted only if properly signed and encrypted by server
- **Session Object**: Trusted only for UI display (name, email, etc.) - **never** for authorization decisions
- **Database**: Sole source of truth for authorization data (tier, accessToken)

### Critical Security Enforcements

1. **JWT Callback Hardening**: Never uses client-supplied values for tier/accessToken on update
2. **Database Re-verification**: All authorization checks hit the database
3. **Token Minimization**: accessToken never appears in client-session object
4. **Error Genericization**: Internal details never leaked in error responses

## Trust Diagram

```
[Client Browser]
     │
     ▼ (HTTPS + Encrypted Cookie)
[NextAuth JWT Validation] ←─── Trust boundary: Cookie integrity
     │
     ▼
[Session Object] ←─── Trust boundary: UI-only data (email, name, etc.)
     │
     ▼ (Never used for auth decisions)
[API Route Handler]
     │
     ├─► auth() → [Session]
     │
     ├─► requireTier() → [Database Query] ←─── Trust boundary: Source of truth
     │
     ▼
[Protected Resource Access]
```

## Key Architectural Decisions

### 1. Email as Primary Identifier

- Uses normalized email (lowercase) as consistent user ID across providers
- Avoids issues with Google sub ID changes in edge cases
- Enables reliable database lookups

### 2. Dual Source of Truth Verification

- JWT tier set from database at sign-in
- API authorization re-verifies tier from database
- Provides defense-in-depth against token theft or manipulation

### 3. Strict Session Minimization

- Session contains: email, name, image, tier (for UI)
- JWT contains: email, name, image, tier, accessToken (encrypted)
- Client-side JavaScript **cannot** access accessToken
- Reduces XSS attack surface

### 4. Fail-Closed Authorization

- If user not found in database → access denied
- If tier verification fails → access denied
- If database unavailable → access denied (prevents false positives)

## Integration Points

### With SSRF Protection

- All external URL fetching (in SEO tools, page speed, etc.) uses `lib/ssrf-protection.ts`
- Prevents authenticated server from being used as proxy to internal services

### With Rate Limiting

- Auth endpoints and sensitive API routes use enhanced rate limiting
- Prevents brute-force attacks on authentication and authorization

### With Error Handling

- All auth-related errors use `lib/error-utils.ts`
- Logs details server-side, returns generic messages to client
- Prevents information leakage through error messages

### With Security Headers

- `middleware.ts` applies CSP and HSTS headers
- Protects auth pages from XSS and ensures HTTPS

## Deployment Considerations

### Environment Variables

- `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS`: For Google Sheets API access
- `NEXTAUTH_SECRET`: For JWT encryption
- `NEXTAUTH_URL`: For callback URLs
- `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`: For OAuth

### Database Requirements

- Google Sheet with columns: email, tier, accessToken, createdAt, updatedAt
- Service account with access to the sheet
- Email column must be indexed for fast lookups

### Scaling Notes

- Database reads occur on every sign-in and API authorization
- Consider caching tier lookups with short TTL (e.g., 5 minutes) if database becomes bottleneck
- JWT size remains small (only essential claims)
