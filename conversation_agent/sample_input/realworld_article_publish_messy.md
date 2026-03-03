# Product Notes — Article Publish / Edit (Needs Cleanup)
Owner: PM (draft), QA comments inline, Eng not fully aligned yet  
Status: PRE-PRD / Incomplete  
Feature Slice: editor + publish only (not full article lifecycle)

---

## Why this matters
People need to publish articles easily or the app has no content.
Right now there are reports that users get confused with tags and sometimes lose edits if they navigate away.
We need this cleaned up in this sprint if possible.

---

## Goals (rough)
- users can create article
- users can edit their own article
- publish should work reliably
- maybe autosave later (not sure if this sprint)

Metric idea: improve successful publish completion rate from editor page.

---

## In scope (probably)
- `/editor` route form with title, description, body, tags
- publish action to `POST /articles`
- edit action via `PUT /articles/{slug}`
- redirect to article detail after publish (or maybe after edit too? assumed yes)
- validation errors shown when API rejects payload

---

## maybe out of scope
- markdown preview pane (nice to have, no commit)
- rich text editor (definitely not now)
- collaborative editing
- draft autosave (TBD; conflict in meeting notes)

---

## Requirements / Notes

### Editor fields
Title, description, and body are required... I think tags are optional.
Need explicit max lengths from design/content team (missing).

### Tag entry
Current behavior is "type tag and press Enter".  
Open issue: duplicate tags appearing sometimes.  
Not sure if duplicates should be blocked client-side, server-side, or both.

### Publish
Clicking Publish sends create request and on success navigates to article page.
Question: should button disable while request in-flight? likely yes, not yet confirmed.

### Edit existing article
Only author should edit.
We rely on API permission checks, but UI should also hide/disable edit affordance for non-author views.
Unclear if deep-link to `/editor/:slug` by non-author should show 403 state or redirect.

### Error handling
Need user-readable errors from API.
Known gap: some failures only show generic message.
Do not clear form data on failure.

### Unsaved change warning
QA requested warning modal on navigate-away with dirty form.
PM said "nice to have" but not committed.
Keep as open ambiguity for now.

---

## Acceptance criteria (not final)
- Authenticated user can publish article with valid required fields
- On success user lands on created article detail
- API validation errors are displayed and form state is preserved
- Authenticated author can edit own article and save updates
- Non-author cannot edit article from UI paths
- Duplicate tags behavior is defined and consistently enforced

---

## Open questions / missing context
- Required max lengths for title/description/body?
- Exact UX for non-author deep-link edit attempt?
- Is unsaved-changes warning in or out for this slice?
- Should publish/edit enforce optimistic UI states?
- What analytics event names define "publish success rate"?
