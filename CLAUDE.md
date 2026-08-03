# Bentley Compass 360 — build handoff

## FIRST ACTION, before anything else

Confirm you are on the `sandbox` git branch, not `main`. Run `git branch
--show-current` and state the result. If it is not `sandbox`, switch to it
(`git checkout sandbox`) and confirm again. Do not read further into the task
list, edit any file, or run any code until this is confirmed. All work in this
project happens on `sandbox`; `main` is the live system Mark is testing and must
never be touched except by an explicit human-instructed merge. If you cannot
determine the branch, stop and ask the human rather than guessing.

Once confirmed, read the rest of this file top to bottom before starting work.

---

Read this file first. It carries the full context, guardrails, decisions, and
outstanding work for the Compass 360 feedback platform. It was written at the
end of a long planning conversation so a fresh session can continue safely
without re-deriving everything.

---

## 1. What this project is

A 360-degree leadership feedback platform, built as a Streamlit app backed by a
Turso (libSQL) cloud database, delivered by The Development Catalyst for
Bentley. Leaders complete a self-assessment and nominate raters (line manager,
peers, direct reports, others) who give feedback; the system generates a
detailed Word report per leader.

Key contextual facts that shape design decisions:

- The assessed managers are employed by franchised dealerships, NOT by Bentley.
  Bentley influences but doesn't employ them. This limits what Bentley can
  mandate and matters for how authority and stakes are framed.
- The 360 is ONE input among several in a broader programme assessment. It is
  NOT a standalone pass/fail gate. This reframing removed the need for heavy
  gatekeeping (e.g. no approval gate on rater nomination).
- Mark (Bentley contact) is currently testing the LIVE system.

---

## 2. Environment and the ONE critical safety rule

There are two environments, deliberately walled off:

- LIVE: GitHub `main` branch → the Streamlit app Mark is testing → the original
  Turso database. This is what Mark uses. DO NOT TOUCH IT.
- SANDBOX: GitHub `sandbox` branch → a separate Streamlit app
  (bentley-compass-360-sandbox) → a SEPARATE Turso database. This is where ALL
  work happens.

**THE RULE: Work only on the `sandbox` branch and the sandbox Turso database.
Never commit to `main`, never point at the live database, never redeploy the
live app. Changes reach Mark ONLY when the human explicitly merges `sandbox`
into `main`. That merge is the human's decision, not yours — do not merge to
main without an explicit instruction.**

Everything irreversible (see identity severing below) is safe to build and test
on `sandbox` precisely because it never reaches Mark until that merge.

---

## 3. Environment gotchas already solved (don't reintroduce)

- The repo pins caused build failures. `libsql-experimental` has NO prebuilt
  wheel for Python 3.14 and fails to compile on Streamlit. FIX APPLIED: switched
  requirement to `libsql>=0.1.11` (which has a cp314 wheel) and changed the
  import in `database.py` from `import libsql_experimental as libsql` to
  `import libsql`. The `libsql.connect(database=..., auth_token=...)` call is
  unchanged — the API matches.
- `runtime.txt` pinning Python 3.12 exists but Streamlit's builder honoured it
  inconsistently; the `libsql` swap made the Python version moot.
- `sqlite3` must be imported UNCONDITIONALLY at the top of `database.py` (it was
  only imported inside an `except ImportError`, causing `NameError` when libsql
  imported fine but the code fell back to the SQLite branch). Ensure:
  ```python
  import sqlite3
  try:
      import libsql
      USING_TURSO = True
  except ImportError:
      USING_TURSO = False
  ```
- `_load_turso_credentials` in `database.py` had a bare `except: pass` that
  silently swallowed secrets-read failures. If Turso isn't connecting, make that
  except print the exception to stderr so the real cause shows in logs. Secrets
  are correctly structured as a `[turso]` section with `url` and `token` keys.
- Streamlit Community Cloud throttles CPU after repeated failed builds. Minimise
  rebuilds; make batched, correct edits rather than many small trial commits.

---

## 4. Anonymity design principle (governs report + portal work)

Agreed stance: **minimise easy breaks, don't chase the nth degree.** Perfect
anonymity in small-group 360 is impossible; the realistic goal is that
re-identification takes real effort and the coaching culture discourages it.

Concretely:
- KEEP: identity severing at submission; group-size floor; blind portal nudge;
  total-level portal progress only.
- HARD FLOOR (never violate): never show a group of one, or any count/coverage
  split that resolves to a single person by simple subtraction (e.g. "3 of 4
  responded"). This is a free, accidental break, not the high-effort kind.
- RELAXED (per the human's decision): per-group coverage and per-group comments
  ARE allowed where the group clears the anonymity threshold. Do NOT add the
  stricter MIN_SPLIT suppression or forced comment-pooling that an earlier draft
  contained — the human explicitly relaxed to group-level display above the floor.
- The rater-facing guidance and coach/debrief guidance carry part of the
  protection and must be written as real artefacts (see outstanding work).

---

## 5. Design decisions already made (implement these, don't relitigate)

### Instrument
- Items are PAIRED: each item has a `self` form ("I ...") and an `other` form
  ("They ..."). Same behaviour, only the grammatical subject differs. Served by
  relationship: Self gets `self` form, everyone else gets `other` form.
- Scale is FREQUENCY (1–5: Rarely or never / Occasionally / Sometimes / Often /
  Consistently) plus a "No opportunity to observe" option stored as 0.
- "No opportunity" (0) is EXCLUDED from score averages (never counted as a low
  score) and surfaced separately as "coverage" ("rated by X of Y").
- 9 items were reworded from trait/state language into observable-behaviour
  language so "how often" parses. The other 36 were converted to the "They"
  convention. All 45 done and tested (see `framework items paired.py`).
- The old scored "Overall Effectiveness" items (Q46, Q47) are REMOVED and
  replaced by two OPEN TEXT prompts (not scored):
  - keep: self "What do you want to keep doing?" / other "What should this
    person keep doing?"
  - change: self "What one change would make the biggest difference to your
    leadership?" / other "... to their leadership?"
  These route to the comments/section structure, not ratings.
- Every dimension keeps an optional verbatim comment box (9 total). These plus
  the 2 closing prompts replace the old strengths/development comment boxes.

### Report (target layout = the "Test_360_Report_Mark_Marsh" mockup)
Structure to preserve: cover, About This Report, TOC, Response Summary,
Executive Summary (dimension table self/combined/gap), radar chart, four-quadrant
Strengths & Development analysis (Agreed Strengths / Good News-Hidden Strengths /
Development Areas / Blind Spots), Detailed Feedback by Dimension with a per-item
bar chart for all 45 items + per-dimension comment blocks, then qualitative
feedback, then Next Steps.
Changes from that mockup:
- Frequency-scale item wording (paired, other-form shown as labels).
- The two open prompts FOLDED INTO "Overall Qualitative Feedback" (the human
  chose to drop a separate Overall Effectiveness heading). Report must read the
  new comment section keys (keep/change), not the old strengths/development keys.
- Coverage shown INLINE under each item as a whole-item total ("rated by X of
  Y"), never per-group inline (per-group only in the human's debrief-prep view).
- Comment blocks protected per the anonymity principle above.

### Leader portal (already largely built in `leader_portal.py`)
- Token portal at `?portal=<portal_token>`; rater form at `?t=<rater_token>`.
- Leader nominates raters (name, email, relationship), ongoing access, can add
  any time, can remove ONLY raters who haven't yet responded (guard needed in
  `delete_rater` too, not just the UI).
- Soft warnings on thin groups, no hard block.
- Response progress: TOTAL-LEVEL ONLY, gated behind a threshold so it never
  resolves to a single outstanding person. NO per-group, NO per-person status.
  (The live `render_progress_section` currently shows per-person named status —
  this MUST be reworked to total-only.)
- ONE blind "remind everyone still to respond" button: uniform confirmation, no
  counts, no names, per-rater 48h rate-limit on `reminder_sent_at`.

### Anonymity severing (Model A)
- At FINAL submission, null the rater's name and email on the `raters` row and
  overwrite `email_log.to_email` with a placeholder (that column is NOT NULL, so
  use a placeholder like `[severed]`, cannot use NULL). Token, relationship, and
  all responses are preserved; the response can no longer be resolved to a
  person. Irreversible by design.
- Hook it into the real submission path: `feedback_form.py` calls
  `db.submit_feedback(rater_id, ratings, comments)` which calls
  `mark_rater_complete`. Sever AFTER the completion commit.
- Tested working against the real schema (columns are `name`, `email`,
  `to_email`).

### White-label rename
- Rename the system to "Bentley Compass 360" throughout, FULL white-label:
  remove "Development Catalyst" / "360 Development Catalyst" entirely from
  client-facing surfaces (report masthead/cover/headers/footers in the report
  generator; page/tab titles and screens in app.py, leader_portal.py,
  feedback_form.py; all email subject lines and body copy in email_sender.py).
- Full white-label implies the visual brand shifts to Bentley's identity too —
  confirm Bentley colours/fonts with the human before restyling, or keep neutral.
- Careful find-and-replace with judgement: change the SYSTEM name, don't blindly
  sed (there may be legitimate non-system uses).

---

## 6. Known live bug to fix first

`database.py` imports `ANONYMITY_THRESHOLD` from `framework.py` (in
`get_leader_feedback_data`), but that constant is NOT defined in `framework.py`.
Every report generation will raise ImportError. FIX: add
`ANONYMITY_THRESHOLD = 3` to `framework.py` (the group-size fold-into-Others
floor, distinct from `MIN_RESPONSES_FOR_REPORT = 5`). Confirmed value with human.

---

## 7. Tested code artefacts to fold in

These were written and tested during planning. They target the REAL schema
(`name`, `email`, `to_email`). Treat them as reference implementations to
integrate on the `sandbox` branch, re-testing against the live code:

- `framework items paired.py` — the full paired ITEMS dict (45 items, 9
  reworded), SCALE_FREQUENCY, OPEN_PROMPTS, and get_item_text()/get_prompt_text()
  helpers. Drop-in for the ITEMS block in framework.py. NOTE the caller changes:
  anything reading `ITEMS[n][1]` as a string must call `get_item_text(n,
  relationship)`; loops over `range(1,48)` become 45 items; report overall
  section reads open prompts not Q46/Q47.
- `Portal Anonymity Changes.md` — the four changes (ANONYMITY_THRESHOLD fix;
  severing method + hook; total-only progress + blind nudge rework of
  `render_progress_section`; delete_rater guard). Written against real column
  names. The severing email_log fix uses a `[severed]` placeholder (NOT NULL
  column). NOTE: this doc predates the anonymity RELAXATION in section 4 — where
  it specifies strict MIN_SPLIT coverage suppression, use the relaxed
  group-level rule instead.
- `rater_import.py` — a standalone CSV bulk importer. LOWER PRIORITY: the leader
  portal already has a working CSV uploader against the right schema. This module
  is only needed if the human later wants admin-side bulk upload across MULTIPLE
  leaders at once, and if so it must be re-aligned to `name`/`email` columns
  (it was drafted against wrong column names `rater_name`/`rater_email`).

---

## 8. Outstanding work, in dependency order

1. Fix the ANONYMITY_THRESHOLD bug in framework.py (section 6). Unblocks reports.
2. Fold in the paired frequency-scale item set (`framework items paired.py`) and
   make the caller changes in feedback_form.py and the report generator.
3. Rework the report generator to the target layout with: frequency wording,
   open prompts folded into Qualitative Feedback, inline whole-item coverage,
   relaxed group-level comment protection. Verify output by rendering to PDF and
   looking at it.
4. Rework `render_progress_section` in leader_portal.py to total-only progress +
   blind rate-limited nudge (section 5). Add the delete_rater pre-response guard.
5. Wire identity severing into submit_feedback (section 5). TEST on sandbox.
6. Build the self-identified development priorities flow: at self-assessment the
   leader names and ranks a few development priorities, fed by the self-form
   "change" prompt. (Design agreed, not yet built.)
7. White-label rename to Bentley Compass 360 (section 5).
8. Write the two guidance artefacts (rater-facing: "comment on behaviour and its
   effect, not identifying incidents"; coach/debrief: "do not attempt to
   attribute feedback; discourage the leader from doing so"). These carry part
   of the anonymity protection per the relaxed stance.
9. Housekeeping: add a `.gitignore` (exclude secrets.toml, *.db) so credentials
   can never be committed.

Do NOT merge any of this to `main` until the human explicitly says so, after
they've reviewed it working on the sandbox.

---

## 9. Working style the human prefers

- Name trade-offs explicitly BEFORE building; propose a better way if you see one.
- Don't pre-justify or check in mid-task unless something is genuinely ambiguous.
- British English. Direct, not hedging. No em dashes. Avoid "not just X but Y",
  throat-clearing, reflexive three-item lists.
- The human reviews logic directly and makes architectural calls conversationally.
- On anything irreversible or affecting Mark's live environment: STOP and confirm.
