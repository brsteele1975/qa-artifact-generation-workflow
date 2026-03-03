# NovaBudget — Product Requirements Document

**Version:** 1.0
**Date:** 2026-02-01
**Author:** NovaBudget Product Team
**Status:** Ready for QA planning

---

## 1. Overview

NovaBudget is a web-based personal finance tracker that enables individual users to record
income and expenses, set monthly spending budgets per category, and generate downloadable
spending reports. All data is scoped to the authenticated user's account.

---

## 2. Actors

- **End User**: A registered individual who manages their personal finances through NovaBudget.
- **System**: The NovaBudget backend service responsible for business logic and data persistence.
- **Email Service**: Third-party transactional email provider (SendGrid) used for account notifications.

---

## 3. Functional Requirements

### REQ-001: User Registration

The System shall allow a visitor to register an End User account by providing a valid, unique
email address and a password that meets the following policy: minimum 10 characters, at least
one uppercase letter, one digit, and one special character from the set `!@#$%^&*`.

**Acceptance Criteria:**
- Given a valid, unique email and a policy-compliant password, when the visitor submits the
  registration form, then the System creates an account and returns HTTP 201 with the new
  account UUID. The Email Service sends a verification email within 60 seconds.
- Given a duplicate email, when the visitor submits, then the System returns HTTP 409 with
  the message "An account with this email already exists."
- Given a password that fails any policy rule, when the visitor submits, then the System
  returns HTTP 400 with a message identifying the specific failing rule (e.g., "Password must
  contain at least one special character.").

---

### REQ-002: Transaction Entry

The System shall allow an authenticated End User to create a financial transaction with the
following required fields: amount (decimal, positive for income or negative for expense),
category (selected from a predefined list of 12 standard categories), date (ISO 8601, no future
dates allowed), and an optional description (maximum 200 characters).

**Acceptance Criteria:**
- Given valid transaction data, when the End User submits the form, then the System persists
  the transaction, associates it with the End User's account, and returns HTTP 201 within 2
  seconds.
- Given a date in the future, when the End User submits, then the System returns HTTP 400
  with "Transaction date cannot be in the future."
- Given a description exceeding 200 characters, when the End User submits, then the System
  returns HTTP 400 with "Description must not exceed 200 characters."
- Given an amount of zero, when the End User submits, then the System returns HTTP 400 with
  "Amount must be non-zero."

---

### REQ-003: Budget Goal Setting

The System shall allow an authenticated End User to set a monthly spending budget for any
category in the predefined list. The budget value must be a positive decimal number (minimum
$0.01). Only one active budget per category per calendar month is permitted.

**Acceptance Criteria:**
- Given a valid budget amount for a valid category, when the End User saves the budget,
  then the System stores it, returns HTTP 200, and the budget progress indicator reflects
  current-month spending against the new goal within 1 second.
- Given a budget amount of zero or negative, when the End User submits, then the System
  returns HTTP 400 with "Budget amount must be greater than zero."
- Given a duplicate budget for the same category and month, when the End User submits, then
  the System overwrites the existing budget and returns HTTP 200.

---

### REQ-004: Monthly Spending Report

The System shall allow an authenticated End User to generate a monthly spending report for
any calendar month from the account creation date through the current month. The report must
be compiled and available for download as a PDF within 10 seconds of the request.

**Acceptance Criteria:**
- Given a valid month selection with existing transactions, when the End User requests the
  report, then the System generates a PDF containing all transactions for that month (amount,
  category, date, description) and a category-level spending summary. The PDF download link
  is available within 10 seconds.
- Given a valid month selection with no transactions, when the End User requests the report,
  then the System returns a PDF containing only a "No transactions found for this period."
  message.
- Given a month before the account creation date, when the End User requests the report,
  then the System returns HTTP 400 with "Selected month predates account creation."

---

### REQ-005: Session Security

The System shall enforce session expiration after 30 minutes of End User inactivity. An
inactivity timer resets on any authenticated HTTP request. Upon session expiration, the
System must invalidate the session token server-side and redirect the End User to the login
page with the message "Your session has expired. Please log in again."

**Acceptance Criteria:**
- Given an authenticated session with no HTTP activity for 30 minutes, when the inactivity
  period elapses, then the System invalidates the session token and the End User's next
  request returns HTTP 401. The client redirects to the login page with the expiration message.
- Given an authenticated session with activity within the 30-minute window, when the End User
  makes a request, then the inactivity timer resets and the session remains valid.

---

## 4. Out of Scope

- Password reset and account recovery
- Multi-currency support
- Mobile native applications (web only for v1)
- Data export formats other than PDF
- Shared accounts or household budgeting
