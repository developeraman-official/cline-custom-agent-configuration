# Authentication Security Checklists

Use case-based checklists for verifying authentication security implementation and testing.

## Checklist 1: User Login & Session Creation

### Pre-Conditions

- [ ] User has valid Google account
- [ ] User record exists in Google Sheets database with correct tier
- [ ] NextAuth provider configured correctly
- [ ] JWT secret properly set

### During Login

- [ ] OAuth flow completes successfully
- [ ] JWT callback executes
- [ ] Database queried for user by email (lowercase)
- [ ] JWT token set with database-derived `tier` and `accessToken`
- [ ] `accessToken` **NOT** present in client-session object
- [ ] Session object contains only: email, name, image, tier
- [ ] Encrypted cookie set with proper HttpOnly, Secure, SameSite flags

### Post-Login Verification

- [ ] User can access public pages
- [ ] User redirected appropriately after login
- [ ] Browser devtools: Application > Cookies shows encrypted NextAuth cookie
- [ ] Session data visible via `getSession()` contains expected non-sensitive fields
- [ ] Attempt to view cookie value shows encrypted string (not JSON)

## Checklist 2: Session Integrity & Tampering Resistance

### Pre-Conditions

- [ ] User logged in with known tier (e.g., "free")
- [ ] Valid session cookie present

### Tampering Attempt Tests

- [ ] Attempt to modify cookie value directly → login required on next request
- [ ] Attempt to decode and modify JWT payload → invalid signature detected
- [ ] Attempt to change `tier` in decoded JWT → on next request, tier reverts to database value
- [ ] Attempt to add `accessToken` to session via client-side JS → not reflected in actual session
- [ ] Attempt to elevate privileges by modifying session storage → no effect on server auth

### Verification After Tampering

- [ ] API calls requiring higher tier return 401/403
- [ ] User interface may show incorrect tier temporarily (until refresh)
- [ ] Page refresh restores correct tier from database
- [ ] No error messages leak database details or internal state

## Checklist 3: Protected Route Access (Defense-in-Depth)

### For Each Protected Endpoint (e.g., /api/max-audit)

#### Pre-Conditions

- [ ] Endpoint requires specific tier(s) (e.g., ["enterprise", "max"])
- [ ] `requireTier()` utility imported and used

#### Authentication Test

- [ ] No session → returns 401 Unauthorized
- [ ] Invalid session → returns 401 Unauthorized
- [ ] Valid session, insufficient tier → returns 403 Forbidden
- [ ] Valid session, sufficient tier → proceeds to logic

#### Defense-in-Depth Verification

- [ ] Endpoint calls `auth()` to get session
- [ ] Endpoint validates `session?.user?.email` exists
- [ ] Endpoint calls `requireTier(email, requiredTiers)`
- [ ] `requireTier()` queries database for user by email
- [ ] `requireTier()` verifies `user.tier` is in `requiredTiers` array
- [ ] If user not found in database → throws error → 401/403
- [ ] If tier mismatch → throws error → 403 Forbidden

#### Error Handling

- [ ] Errors from `requireTier()` logged server-side with details
- [ ] Client receives generic message: "Unauthorized" or "Forbidden"
- [ ] No stack traces, database queries, or internal URLs in response

## Checklist 4: API Route Security (Adjacent Protections)

### SSRF Protection

- [ ] All external URL fetching uses `fetchWithBrowserHeaders` from `lib/ssrf-protection.ts`
- [ ] URL validation blocks:
  - localhost, 127.0.0.1, ::1
  - Private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  - Internal hostnames (localhost, internal, .local)
  - Cloud metadata URLs (169.254.169.254)
- [ ] Valid URLs: public http/https domains only

### Rate Limiting

- [ ] Auth-sensitive endpoints use rate limiting from `lib/rate-limit.ts`
- [ ] Limit appropriate to endpoint (e.g., 5/min for login, 30/min for searches)
- [ ] Cleanup mechanism prevents memory leak in rate limit store
- [ ] Distinct limits per IP/user where appropriate

### Error Handling

- [ ] All API routes use `handleApiError` from `lib/error-utils.ts`
- [ ] Try/catch wraps all async logic
- [ ] Errors logged server-side with full details
- [ ] Client receives: `{ error: "Generic message" }` with appropriate status
- [ ] No leakage of: database errors, file paths, stack traces, internal URLs

## Checklist 5: Security Headers & Transport

### Middleware Protections

- [ ] `middleware.ts` sets Content Security Policy
- [ ] `middleware.ts` sets Strict-Transport-Security (HSTS)
- [ ] X-Frame-Options: DENY or SAMEORIGIN
- [ ] X-Content-Type-Options: nosniff
- [ ] Referrer-Policy: strict-origin-when-cross-origin
- [ ] Permissions-Policy: restrictive defaults

### HTTPS Enforcement

- [ ] In production, all traffic redirected to HTTPS
- [ ] Session cookies set with Secure flag
- [ ] No mixed content warnings on auth pages

## Checklist 6: Token & Session Management

### JWT Configuration

- [ ] JWT encryption secret strong and rotated periodically
- [ ] JWT expiration configured appropriately (e.g., 30 days)
- [ ] JWT contains only essential claims: email, name, image, tier, accessToken
- [ ] accessToken encrypted in JWT (not visible to client)

### Session Configuration

- [ ] Session strategy: "jwt" (NextAuth default)
- [ ] Session max age configured
- [ ] Update age configured for balancing security/performance
- [ ] Session cookie: HttpOnly, Secure, SameSite=Strict/Lax

### Logout & Session Invalidation

- [ ] Logout endpoint clears session cookie
- [ ] After login attempt, session rotated (prevents fixation)
- [ ] Invalid/malformed cookies cleared automatically

## Checklist 7: Database & Data Protection

### User Data Storage

- [ ] Email stored lowercase for case-insensitive lookup
- [ ] AccessToken encrypted at rest in database
- [ ] No plaintext passwords or tokens stored
- [ ] PII (email) access logged/audited if required
- [ ] Database service account has least-privilege access

### Data Access Patterns

- [ ] All user lookups by email (normalized)
- [ ] No direct database access from client-side code
- [ ] Database queries parameterized to prevent injection
- [ ] Connection pooling/reuse where applicable
- [ ] Read replicas considered for scaling if needed

## Checklist 8: Testing & Verification

### Automated Tests

- [ ] Unit tests for `requireTier()` function
- [ ] Integration tests for login flow
- [ ] API route tests for tier verification
- [ ] SSRF protection test cases (valid/invalid URLs)
- [ ] Error handling tests (generic messages returned)

### Manual Testing

- [ ] Test with free user attempting to access enterprise endpoints
- [ ] Test session tampering via browser devtools
- [ ] Test error messages don't leak internal info
- [ ] Test rate limiting blocks excessive requests
- [ ] Test security headers present via curl/devtools
- [ ] Test logout properly clears session

### Penetration Testing Areas

- [ ] JWT token manipulation attempts
- [ ] Session fixation/cookie tossing attacks
- [ ] Privilege escalation via parameter tampering
- [ ] Information leakage through error messages
- [ ] SSRF via URL parameters in API routes
- [ ] Brute force protection on auth endpoints

## Checklist 9: Maintenance & Monitoring

### Regular Checks

- [ ] Review NextAuth version for security updates
- [ ] Audit Google Sheets access logs periodically
- [ ] Check rate limit counters for anomalies
- [ ] Review error logs for authentication failures
- [ ] Verify JWT secret rotation schedule
- [ ] Test backup/restore of database access credentials

### Incident Response

- [ ] Procedure for suspected token theft: force logout all sessions
- [ ] Procedure for database breach: rotate access tokens, notify users
- [ ] Procedure for privilege escalation incident: investigate, patch, notify
- [ ] Logging sufficient to reconstruct authentication events

## Checklist 10: Deployment & Configuration

### Environment Variables

- [ ] `NEXTAUTH_SECRET` set to strong random value
- [ ] `NEXTAUTH_URL` set correctly for environment
- [ ] Google OAuth credentials configured
- [ ] Google Service Account credentials for Sheets access
- [ ] All secrets stored securely (not in repo)

### Pre-Deployment Verification

- [ ] Build succeeds with no TypeScript errors
- [ ] ESLint/Prettier passes
- [ ] Auth flow tested in staging environment
- [ ] Security headers verified
- [ ] Error handling tested
- [ ] Rate limiting tested

### Post-Deployment Checks

- [ ] Smoke test login/logout
- [ ] Verify protected routes inaccessible without proper tier
- [ ] Check cookie flags in production
- [ ] Monitor error rates for auth-related 4xx/5xx
- [ ] Verify security headers present in responses
