# PRD — Authentication Core Flow (Sign Up / Login / Logout)
**Product:** RealWorld Conduit (React + Redux)
**Author:** Product + QA Collaboration Draft
**Status:** Ready for QA planning
**Scope:** Single feature slice — authentication only

---

## 1. Problem Statement

New and returning users need a reliable authentication flow to access personalized features (feed, article publishing, favorites, comments). Current project testing coverage is undefined, increasing release risk around account access and session continuity.

---

## 2. Goal

Deliver a stable, testable authentication experience for:
- User registration
- User login
- User logout
- Session persistence on app reload

Primary success signal: users can create or access accounts without credential loss, token corruption, or broken redirects.

---

## 3. In Scope

- Register via `POST /users`
- Login via `POST /users/login`
- Persist JWT in localStorage key `jwt`
- Send `Authorization: Token {jwt_token}` on authenticated requests
- Restore authenticated state on app load when token exists
- Logout by clearing local token/session state and returning to unauthenticated navigation

---

## 4. Out of Scope

- Password reset and email verification
- Social login / SSO
- MFA
- Account lockout and fraud controls
- Profile editing behavior outside auth entry/exit flow

---

## 5. Requirements

### 5.1 Registration
Unauthenticated users must be able to submit username, email, and password from the Sign Up page. On valid submission, the app must authenticate the user and redirect to the home route.

### 5.2 Login
Unauthenticated users must be able to submit email and password from the Login page. On valid credentials, the app must authenticate and redirect to home.

### 5.3 Error Handling
If registration or login fails, the app must present API error messages in a visible, user-readable format without crashing or clearing user-entered form fields.

### 5.4 Token Persistence
On successful registration or login, JWT token must be saved in localStorage under key `jwt`. On app refresh, existing token must rehydrate authenticated session state.

### 5.5 Auth Header
When token exists, authenticated API requests must include `Authorization` header in format `Token {jwt_token}`.

### 5.6 Logout
Authenticated users must be able to logout. Logout must remove token and return navigation state to unauthenticated mode.

### 5.7 Route Guard Behavior
Unauthenticated users attempting to access authenticated-only actions (for example, publish article) must be redirected to login/register path.

---

## 6. Acceptance Criteria

- New user can sign up and arrive at authenticated home state
- Existing user can log in and arrive at authenticated home state
- Invalid credentials display user-visible errors and preserve form inputs
- JWT token is present after auth success and absent after logout
- App refresh with valid token restores authenticated state
- Authenticated calls include correct token header format
- Unauthenticated publish attempt redirects to auth entry

---

## 7. Dependencies

- Conduit API availability (`/users`, `/users/login`, `/user`)
- Browser localStorage availability
- Existing Redux middleware that sets/removes token in request layer

---

## 8. Open Questions

- None for v1 auth slice. Security hardening requirements are deferred.
