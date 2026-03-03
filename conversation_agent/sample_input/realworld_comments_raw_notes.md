# Slack Thread Dump — Comments Feature
Date: 2026-02-24  
Channel: #conduit-feature-comments  
Note: unedited notes, conflicting statements likely

---

PM: we need comments to feel instant, users should be able to drop a thought under an article and see it right away.

Eng1: backend already supports `GET /articles/{slug}/comments`, `POST /articles/{slug}/comments`, `DELETE /articles/{slug}/comments/{id}`.

QA: do we have rule on max comment length?

PM: not sure, maybe 500 chars? check spec maybe 1k.

Eng2: also who can delete - definitely comment author. maybe article author too? not sure what RealWorld spec says in this impl.

Design: empty state should not look broken when no comments. "No comments yet" copy pending.

QA: if post fails we need error surfaced and not lose typed text.

Eng1: right now comment submit clears box on success only (I think). Need verify.

PM: anonymous users should read comments but posting should require login.

QA: what happens if token expires while submitting comment?

Eng2: likely 401 then redirect/login prompt, but I don't think flow is standardized.

Design: mobile spacing around comment cards is cramped.

PM: sorting newest first? I assumed oldest first for readability.

Eng1: API returns in created order, frontend currently just maps response.

QA: deletion confirmation needed?

PM: prefer lightweight, no modal for now maybe.

Eng2: race condition maybe if two quick submits? haven't tested.

PM: this sprint keep scope tight:
- read comments
- add comment
- delete own comment

QA: need clear rule for permissions and ordering or test plan will be guesswork.

---

Potential requirements from thread (not approved):
- Auth required to add comments
- Unauth users can view comments
- Users can delete their own comments
- Failed submissions keep drafted text
- Comment list rendering works on mobile and desktop

Unknowns:
- max length
- sorting order
- delete confirmation behavior
- behavior on expired token mid-submit
- whether article owner can delete others' comments
