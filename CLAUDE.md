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

## 1a. THE PROGRAMME TIMELINE (confirmed by the human 2026-08-04)

This is TWO STAGES with a gap, not one continuous process. It drives a lot of
copy and sequencing, and getting it wrong makes documents factually misleading:

1. Leaders are invited onto the programme.
2. They receive the SELF-ASSESSMENT link and complete it BEFORE Module 1.
3. At MODULE 1 they are handed their Self-Assessment report and have their FIRST
   COACHING CONVERSATION from it. No feedback from others exists yet.
4. Between Modules 1 and 2 they are primed, then invited, to NOMINATE RATERS.
5. Raters respond.
6. At MODULE 2 they receive the FULL 360 report.

Consequences already built for:
- The Self-Assessment report's "What Happens Next" must put the coaching
  conversation FIRST and nomination SECOND. An earlier version described feedback
  collection as already under way and put coaching after the full report, which
  told the reader at Module 1 that they had missed a step. Fixed 2026-08-04.
- Portal copy can assume the leader has already self-assessed AND been coached,
  because the portal email is admin-triggered (see below), so it only ever lands
  after Module 1.
- NO PHASE GATE IS NEEDED IN CODE. `get_leaders_needing_portal_email` only builds
  a "ready" list; nothing sends until the human clicks in the Leader Portals tab.
  Holding portal access until after Module 1 is therefore an operational choice
  the human already controls. Do not build a gate for this.
- Reports are LIVE WORKING DOCUMENTS, not read-only outputs (the human's call):
  ruled writing lines under each Reflection Question, a writing block in the Full
  360's Next Steps, and an "Adding to Your Priorities" capture table in both.
- Coaching ADDS to the leader's priorities rather than replacing them. So the
  stored `development_priorities` are never overwritten after submission: they are
  the pre-feedback baseline the Full 360 comparison depends on. Additions are
  captured in the DOCUMENT, which is why no second storage slot or coach-facing
  UI was built. If the human later wants additions in the system so Module 2 can
  render them, that is a new column plus a capture surface.

## 1b. Other contextual facts that shape design decisions:

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
- LOCAL DEV STREAMLIT VERSION MUST MATCH `requirements.txt` (currently
  `streamlit==1.60.0`), not whatever happens to be on the machine already.
  Found 2026-08-14: a whole session's CSS work had been tested exclusively
  against a local install of 1.53.1, and one fix (the leader portal's
  Relationship dropdown background) silently didn't apply on the deployed
  sandbox, because Streamlit swapped `st.selectbox`'s internal implementation
  between those versions - 1.53.1 renders it via BaseWeb
  (`[data-baseweb="select"]`), 1.60.0 via React Aria (`.react-aria-ComboBox`,
  `[role="group"]`), completely different DOM. A CSS selector written and
  verified against the wrong version can look perfectly correct locally and
  do nothing at all once deployed, with no error anywhere to surface it.
  Confirmed by loading the actual deployed Render sandbox directly and
  inspecting its DOM, then reproducing the same gap locally in an isolated
  venv pinned to 1.60.0 (`.venv_test_1_60/`, gitignored, built from
  `requirements.txt` minus `libsql` - Turso isn't needed for CSS/layout
  verification, and `libsql` needs `cmake` to build from source on this Mac,
  which isn't installed; the sqlite3 fallback already documented above
  covers this fine). DELIBERATELY NOT applied to the system-wide Python
  install - that's shared with whatever else runs on this Mac, so it stays
  isolated in this project-local venv. Use it (`source
  .venv_test_1_60/bin/activate`) for any future widget-adjacent CSS work,
  not the system Python's 1.53.1, and when in doubt about whether a fix
  actually applies, check the deployed sandbox directly rather than
  trusting local-only verification.

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

### The thin-'Others' hole, and the fold cascade that now resolves it
Raised by the human: if only one or two people are nominated as 'Others' they are
identifiable, because no other group folds into them. It was worse than that — the
code was PUBLISHING A GROUP OF ONE, breaking the hard floor above.

- Cause: sub-threshold Peers and DRs fold into Others, which is safe because
  merging hides the split. 'Others' had nothing to fold into, and it was
  whitelisted as always-visible in THREE places (`response_counts` seeded from raw
  Others, `g == 'Others'` in the Combined loop, and `'Others'` in the
  by_dimension allow-list). The `hidden_groups` marking for Others had no effect.
- First fix (2026-08-04): if Others was still below ANONYMITY_THRESHOLD after
  absorbing folded groups, it was SUPPRESSED entirely — dropped from
  response_counts, scores, Combined, and comments. This closed the hard-floor
  breach but threw the feedback away.
- SUPERSEDED THE NEXT DAY (2026-08-05, commit `1737e2d`) by a proper two-tier
  cascade in `get_leader_feedback_data`, refined by `f4d8cac` (corrected
  portal/Guidelines copy that still described the old "left out entirely"
  behaviour) and `b021cf7` (extended the at-risk nudge to Peers/DRs). This is
  the CURRENT behaviour:
  - **Tier 1**: Peers/DRs below `ANONYMITY_THRESHOLD` fold into Others.
  - **Tier 2**: if Others is still thin after absorbing tier 1, it folds the
    other way — into whichever of Peers/DRs is still standing on its own
    (Peers preferred, DRs as fallback). This is what actually recovers the
    feedback that used to be suppressed.
  - **Suppression** (the 2026-08-04 fix) remains in the code as a defensive
    fallback for the case where tier 2 finds nowhere to fold into — i.e.
    neither Peers nor DRs survives on its own. The code comment above it notes
    this is mathematically unreachable today, given `MIN_RESPONSES_FOR_REPORT`
    (5) and Boss's 2-person cap guaranteeing at least 3 non-Boss responses
    always exist by report time. Kept as insurance, not as the expected path.
  - Whichever tier fires, it MUST come out of Combined too, not just the
    per-group display — Combined is the mean of the group means, so a folded
    or suppressed group's contribution has to be genuinely merged in (tier 1/2)
    or genuinely removed (suppression), never left in a state where it's
    recoverable by subtraction.
  - Comments from a suppressed group are held back too (tier 1/2 folding
    already carries comments into the target group's pool, so this only
    applies to the dormant suppression path). Showing them even unlabelled
    would tell the leader they came from those two or three people, since
    every other comment carries its group label.
  - Verified 2026-08-08 with two constructed scenarios: Peers, DRs, and Others
    all individually below threshold but summing to clear it (tier 1 folds all
    three into a single Others bucket, as expected — tier 2 and suppression do
    not fire); and Others thin alone with Peers/DRs both healthy (tier 2 fires,
    folding Others into Peers — this is the case `hidden_groups` alone doesn't
    flag, which is why `data['anonymity_applied']` now also checks
    `others_fold_target`, not just `hidden_groups`/`suppressed_groups`).
- Report-facing disclosure: `add_fold_transparency_note` in
  `report_generator.py` (added 2026-08-08) prints a single generic sentence
  between the Response Summary table and the Executive Summary whenever
  `data['anonymity_applied']` is true, for either tier. Deliberately reveals no
  counts and names no groups (per the human's instruction — the alternative
  is the older per-group notes still inside `add_response_summary`, which DO
  name the specific groups folded; that naming has not been removed but now
  sits alongside the generic note, which is worth revisiting for consistency).
- PREVENTION, which is the better fix: `RATER_REQUIREMENTS['Others']` gained
  `min_if_any: ANONYMITY_THRESHOLD`. Others is all-or-nothing — nominate none, or
  nominate at least 3. Nominating 1-2 warns in the portal (soft warning, no hard
  block, consistent with the rest of the portal) and the Guidelines tab explains
  why Others is the special case.
- ALSO NOTE: the threshold applies to RESPONSES, not nominations. Nominating
  exactly 3 Others is fragile, because one non-response tips it under. The portal
  shows an info note at exactly the threshold suggesting one or two more as cover.
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
- ITEM WORDING DIFFERS BY REPORT TYPE (bug found by the human 2026-08-04, fixed):
  the Self-Assessment report must render the I-form, because its only rater was
  the leader and that is what they answered. The Full 360 keeps the They-form,
  because that is how the item was put to the raters, and showing the I-form
  beside a Peers or Direct Reports bar would misrepresent what those people were
  asked. `add_dimension_section` resolves this from its `is_self_only` flag.
  THE TRAP: `get_leader_feedback_data` bakes the They-form into
  `by_item[n]['text']` unconditionally, and the old code preferred that baked
  value, so the self report silently showed "They ...". Never fall back to
  `item_scores['text']` for item wording. The PAPU-NANU tables legitimately use
  the They-form, since that section only appears in the Full 360.

### Leader portal (already largely built in `leader_portal.py`)
- Token portal at `?portal=<portal_token>`; rater form at `?t=<rater_token>`.
- Leader nominates raters (name, email, relationship), ongoing access, can add
  any time.
- NO self-serve rater removal in the portal (decided 2026-08-03, superseding an
  earlier draft that allowed removing non-responders). Rationale: removing a
  non-responder changes no score, no group count and no report, since every
  count derives from `completed_at IS NOT NULL`. Its only real effects were to
  stop further reminders and to shrink the progress denominator, and offering it
  leaked per-person response status (the row visibly disappears). Removal for
  genuine reasons (someone has left the business, an address bounces) is an
  ADMIN action, already available in `admin_dashboard.py`.
- Instead the portal offers corrections to a nominee's EMAIL ADDRESS and the
  RELATIONSHIP they were nominated under (relationship added 2026-08-04 after the
  human asked what happens if someone is added as a second Boss when they should
  be a peer or direct report; previously the only fix was an admin delete and
  re-add). Both are non-destructive and reveal nothing about response status. The
  edit control is shown uniformly for everyone so its presence cannot be used to
  infer who has responded.
- Handled by `_apply_nomination_correction` + `_validate_nomination_change` in
  leader_portal.py, backed by `database.update_nomination_entry`. The ROSTER is
  always updated so the visible outcome is identical for everyone. The RATERS row
  is only updated when `get_unsevered_rater_by_email` finds it, which by
  definition means they have not submitted.
- WHY RELATIONSHIP MUST NOT CHANGE AFTER SOMEONE RESPONDS, on substance and not
  just for privacy: they answered in the context of the relationship they were
  invited under, so their answers belong in that group, and recategorising them
  afterwards would misrepresent their input. It would also let someone move a
  response between groups and watch which group average shifts, which identifies
  whose response it is. `update_rater` now accepts `relationship`, so its
  docstring carries this warning for any future caller.
- Moves are validated against `RATER_REQUIREMENTS[...]['max']` (Boss is capped at
  2), so a leader cannot create a third line manager by moving someone.

### CSV import — RELATIONSHIP PARSING (fixed 2026-08-04)
- The human's bulk upload failed because they typed "others" rather than "Others".
  Both importers were case-sensitive and compared against the INTERNAL codes
  ('Boss', 'DRs'), which are jargon nobody would naturally type. Expecting an
  exact match, capitalisation included, from someone filling in a spreadsheet is a
  trap, so the fix is in the parser, not the instructions.
- `framework.normalise_relationship(value)` is now the single source of truth.
  Tolerant of case, surrounding whitespace, and hyphens/underscores/dots/slashes
  as separators, and accepts plain-English wording as well as the internal codes
  (see `RELATIONSHIP_SYNONYMS`). BOTH import paths go through it — leader portal
  and admin dashboard — so they cannot diverge again.
- 'Self' IS recognised, so the admin importer can use it, but the leader portal
  rejects it with its own message: a leader's self-assessment row is created with
  their assessment, never bulk-uploaded beside their raters.
- Templates in both places now use the plain-English labels and include one row
  per relationship, so all four accepted values are visible instead of guessable.
  `RELATIONSHIP_INPUT_HELP` supplies the wording shown in captions and errors.
- `_parse_rater_csv` in leader_portal.py reports problems PER SPREADSHEET ROW
  (numbered from 2, since row 1 is the header) naming the person and the offending
  value, instead of one generic "invalid relationship values" for the whole file.
  It also catches missing names, malformed emails, duplicates of people already on
  the list, and imports that would breach a category maximum.
- IT IMPORTS NOTHING IF THERE ARE ANY PROBLEMS. A partially imported nominee list
  is worse than none, because the leader cannot easily tell what landed.
- The admin importer previously did NOT add imported raters to
  `leaders.nomination_roster`, so anyone added that way never appeared in the
  leader's portal list. Fixed at the same time.
- Re-invitation fires only when the EMAIL actually changed. A relationship tweak
  does not alter the invitation copy, so re-sending would just be noise.
- The `delete_rater` guard (refuses to delete a rater with a non-NULL
  `completed_at`) IS still implemented and still required: it protects the admin
  path from destroying an already-severed anonymous response.
- Soft warnings on thin groups, no hard block.
- Response progress: TOTAL-LEVEL ONLY. NO per-group, NO per-person status - that
  part still holds and is the real protection. CORRECTED 2026-08-27 (see
  "Correction: Remove the Your Progress Gating Entirely"): the "gated behind a
  threshold" clause below has been removed from the actual system - a bare
  total-level count doesn't name anyone or break down by category, so it was
  never actually anonymity-sensitive, and gating it (at any threshold) was
  applying this pattern somewhere its threat model doesn't reach. The stats
  strip/status card/reminder text now always show real numbers, at any
  outstanding count including 1.
  (The live `render_progress_section` currently shows per-person named status —
  this MUST be reworked to total-only.)
- ONE blind "remind everyone still to respond" button: uniform confirmation, no
  counts, no names, per-rater 48h rate-limit on `reminder_sent_at`.

### Anonymity severing (Model A) — IMPLEMENTED 2026-08-04
- At FINAL submission, null the rater's name AND email on the `raters` row and
  overwrite `email_log.to_email` with `[severed]` (that column is NOT NULL, so it
  cannot be set to NULL). Token, relationship, and all responses are preserved;
  the response can no longer be resolved to a person. Irreversible by design.
- BOTH identifiers must go. Nulling only the email severs nothing meaningful,
  because the name is the stronger identifier (`rater_id → name → person`). This
  was considered and rejected on 2026-08-04.
- Implemented as `database.sever_rater_identity(rater_id)`, called from
  `submit_feedback` AFTER `mark_rater_complete` commits, so a mid-way failure
  can never leave a severed rater with no recorded response. Applies to Self
  too; display code falls back to a group label where a name is missing.
- THE ROSTER COLLISION AND ITS FIX: severing destroys the identity that the
  portal's "People You've Nominated" list used to render, which would both wipe
  the leader's own record and leak per-person response status (blank rows =
  the people who responded). Resolved by storing the leader's nomination roster
  as a JSON list on `leaders.nomination_roster` (added via `_safe_add_column`),
  holding `{name, email, relationship}` per nominee. It lives on the LEADER, not
  on `raters`, so severing cannot touch it. `get_nomination_roster` backfills
  from `raters` for leaders who nominated before the column existed, and
  `add_to_nomination_roster` dedupes on email (or name+relationship when there is
  no email) because callers add the rater row first, so the backfill would
  otherwise double-count the nominee being appended.
- The only link from roster back to a rater row is the email address, so severing
  removes it as a side effect. `_apply_email_correction` in leader_portal.py
  relies on this: it looks the rater up by the OLD address via
  `get_unsevered_rater_by_email`, finds nothing once severed, and therefore never
  writes an address back onto an anonymous response. Writing one back would
  re-identify it. The leader sees the same confirmation either way.
- Verified end-to-end on 2026-08-04 by submitting through the real form UI (not
  just direct DB calls): name/email nulled, `email_log.to_email` = `[severed]`,
  token/relationship/ratings/comments all intact, roster still showing all 7
  nominees with addresses, scores and reports generating correctly, and email
  correction proven not to re-identify a severed row.

### Report page geometry — DONE 2026-08-04
- REPORTS ARE A4 (human's instruction). python-docx's default template is US
  LETTER, which would shift the margins when UK readers print, so
  `apply_page_geometry` overrides page size and margins on EVERY section. Called
  from `generate_report` before anything is laid out. Note the second section
  (created for the page-number footer) copies its geometry from the first, so
  setting section 0 propagates, but `apply_page_geometry` loops all sections
  anyway so it stays correct if that changes.
- ALL geometry derives from constants at the top of report_generator.py:
  `PAGE_WIDTH_IN` / `PAGE_HEIGHT_IN` / `MARGIN_IN` (8.27 x 11.69, 1in margins),
  giving `CONTENT_WIDTH_IN = 6.27` and `CONTENT_HEIGHT_IN = 9.69`.
  DO NOT hard-code inch values for full-width elements. Use
  `content_columns(*relative_widths)`, which returns column widths summing
  exactly to the content width from proportions, so tables stay aligned with each
  other and with the charts if the page ever changes again. Every full-width table
  now goes through it, verified as all totalling 6.27in.
- The tables were previously 6.1in against a 6.0in Letter text column, i.e. wider
  than the column they sat in. That is why "as wide as the table above it" needed
  the tables fixed first, not just the chart widened.
- Radar charts are full width (were 3.74in). In the SELF-ASSESSMENT the radar
  shares its page with the score table: heading plus a ten-row table plus a
  ~4.96in radar is about 8.1in against 9.69in usable, so it fits. In the FULL 360
  it does NOT fit, because that page already carries the Response Summary and
  Executive Summary tables, so the radar gets a deliberate page break under a
  "Your Profile at a Glance" heading. Breaking on purpose beats letting Word push
  it over and leave a ragged half page.
- WATCH HEIGHTS IF YOU CHANGE THINGS: usable height is 9.69in. At full width the
  self-only radar is ~4.96in tall and the two-series one ~5.29in (the legend adds
  height). Adding rows to the self-assessment score table could push its radar off
  the page.

### AI theme synthesis — FIXED 2026-08-04
The "Key Themes in Your Feedback" section calls the Anthropic API from
`synthesise_feedback_themes`. It needs BOTH of these to appear, and it fails
SILENTLY if either is missing:
1. An API key, read by `_get_api_key()` from `st.secrets["anthropic"]["api_key"]`
   or the `ANTHROPIC_API_KEY` env var. NOT in the repo (correctly — .gitignore
   excludes secrets). Must be set in each deployment's Streamlit secrets.
2. A current model ID.
- THE MODEL WAS BROKEN. It was pinned to `claude-sonnet-4-20250514`, which is
  deprecated with a retirement date of 2026-06-15 — already past. A retired ID
  returns 404, and the function swallowed that into `return None`, so the section
  would have quietly vanished from every report even with a valid key set. Now
  `SYNTHESIS_MODEL = 'claude-opus-5'` as a named constant at the top of
  report_generator.py. Swap to `claude-sonnet-5` if cost per report matters more
  than synthesis quality.
- TWO THINGS THE CURRENT MODEL CHANGES, both handled:
  - Thinking is ON BY DEFAULT and `max_tokens` caps thinking PLUS response text
    together. The old 2000 was sized for a non-thinking model and would now
    truncate the JSON mid-object. Raised to 8000; timeout raised 30s -> 120s.
  - Sampling parameters (`temperature`, `top_p`, `top_k`) are REJECTED with a 400
    on this model family. Do not add them.
- JSON parsing now uses structured outputs (`output_config.format` with a
  json_schema) instead of stripping ``` fences off the response and hoping
  `json.loads` succeeds. The schema roots at an object with a `themes` array, so
  the parse is `json.loads(text)['themes']`.
- A refusal returns HTTP 200 with no usable content, so `stop_reason == 'refusal'`
  is checked BEFORE reading `content[0]`.
- Failures now print a loud, specific message to STDERR (visible in Streamlit
  logs) naming the HTTP status and saying the section will be missing. A silent
  skip means a real leader's report loses a whole section with no warning.
- ALREADY DONE, CLAUDE.md previously said otherwise: failures ARE surfaced in
  the admin UI, not just the logs - `st.warning(f"Key Themes section could not
  be generated: {theme_warning}")` in admin_dashboard.py (both the single-leader
  report tab and the bulk-generation one). The whole function is wrapped in a
  broad `except Exception as e: return None, f"theme synthesis raised an
  exception: {e}"`, which is exactly what caught the bug below rather than
  crashing the report generation entirely.
- FOUND 2026-08-17 (first real end-to-end run against the live API in this
  environment - never caught locally, since local testing had no API key to
  exercise a real call): `content[0]` is NOT reliably the text block.
  `max_tokens` caps thinking PLUS response text together (see above) because
  thinking is on by default - and a thinking response puts a `{"type":
  "thinking", ...}` block FIRST in `content`, with no `"text"` key at all.
  Indexing `result['content'][0]['text']` directly raised `KeyError: 'text'`
  in production, surfaced to the admin as "theme synthesis raised an
  exception: 'text'" via the broad except above. Fixed by finding the actual
  `{"type": "text"}` block in `content` instead of assuming its position -
  correct whether thinking produced 0, 1, or several blocks before it, and
  falls back to a clear warning (not a crash) in the edge case where thinking
  exhausts the token budget and no text block exists at all. Verified against
  simulated thinking-then-text, text-only, and thinking-only response shapes.

### Typography and charts — DONE 2026-08-04
- RADAR LABELS were cutting into the plot (the human spotted it). Cause: labels
  were horizontally centred on their spoke, so a long name like "Building
  High-Performing Teams" ran back across the chart. Fixed in
  `create_radar_chart` by (a) wrapping labels at 16 chars with textwrap, (b)
  setting per-label horizontal alignment from the label's SCREEN angle so text
  grows outwards (right half left-aligned, left half right-aligned, top and
  bottom centred), and (c) replacing `tight_layout` with explicit
  `subplots_adjust`, because tight_layout fights polar axes with long outward
  labels. NOTE the angle maths: `set_theta_offset(pi/2)` plus
  `set_theta_direction(-1)` means a data angle d appears at screen angle
  (90 - d) % 360. `set_rlabel_position(20)` puts the 1-5 scale in the gap
  between the first two spokes instead of on top of a label.
- BENTLEY TYPEFACE is now applied. `REPORT_FONT` and `CHART_FONT_PREFERENCE` in
  framework.py; `apply_document_font` and `resolve_chart_font` in
  report_generator.py. TWO MECHANISMS THAT FAIL DIFFERENTLY:
  - Document text: a .docx stores only the font NAME, resolved by Word on open.
    Set on the Normal, Title, Heading 1-3 and List styles, including the
    `w:eastAsia` attribute, which Word needs or it silently keeps its own default
    for some runs. Works regardless of where the report was generated.
  - Chart images: rasterised by matplotlib AT GENERATION TIME, so the font must
    be installed on the generating machine. It is on the human's Mac. It is NOT
    on Streamlit Cloud, so reports generated there get chart text in the fallback
    while document text still says Bentley. GENERATE CLIENT-FACING REPORTS
    LOCALLY to keep them consistent. `resolve_chart_font` degrades gracefully
    (returns None and leaves matplotlib's default) rather than crashing.
  - DO NOT commit the Bentley font files to fix the cloud case. The font metadata
    reads "All rights reserved. BENTLEY TYPE is a trademark of BENTLEY", so that
    is a licensing decision for the human, not a code change.

### White-label rename — DONE 2026-08-04
- The system name is "Bentley Compass 360" everywhere. Per the human's
  instruction: "The 360 Development Catalyst" must NEVER be seen by Bentley
  staff, programme attendees, or raters. Zero occurrences remain in any .py file
  (verified by grep), including internal docstrings, which were renamed too for
  coherence.
- Surfaces changed: report cover masthead (`create_cover_page`); `page_title` and
  landing screen in app.py; headers in feedback_form.py, leader_portal.py and
  admin_dashboard.py (the admin header too, since Mark is Bentley staff and may
  have the admin code); all six email body templates plus the default
  `sender_name` in email_sender.py and the setup example in admin_dashboard.py.
- The landing subtitle changed from "Bentley Compass Leadership Programme" to
  "360-Degree Leadership Feedback" so the screen doesn't read "Bentley Compass"
  twice. Elsewhere "Bentley Compass Leadership Programme" is left alone: it is
  the PROGRAMME name, not the system name, and is correct as-is.
- Verified in-browser on all four surfaces (landing, rater form, leader portal,
  admin dashboard): tab title is "Bentley Compass 360" and no surface contains
  the old name. All six email templates rendered and scanned. Both report types
  generated and scanned across body, tables, headers and footers.
- The visual brand was deliberately NOT changed. It stays on the existing Bentley
  green palette (`COLOURS` in framework.py), which already reads as Bentley. If
  the human wants true Bentley brand assets (typeface, logo, exact hex values),
  that is a separate piece of work needing those assets.
- STILL OUTSTANDING, needs the human: the deployed app URL still contains
  "catalyst-360" (`catalyst-360-arbncruhflmazjemep8uzh.streamlit.app`), which
  raters see in the invitation link and their address bar. Fixing it means
  renaming the Streamlit app or putting a custom domain in front, which is
  infrastructure, not code.
  In the meantime the code no longer hardcodes it in four places. `base_url` now
  comes from `email_sender.get_app_base_url()`, which reads `[app] base_url` from
  that deployment's own secrets and falls back to `DEFAULT_BASE_URL` (still the
  live URL) only when unset. SET THIS IN THE SANDBOX SECRETS: without it the
  sandbox portal generates invitation links pointing at the LIVE app, because
  `portal_base_url` is never assigned in session state anywhere. That was a
  pre-existing cross-environment bug, found while doing the rename.

### Button contrast — DONE 2026-08-04
- The old CSS in app.py applied a blanket `color: white` to
  `stFormSubmitButton` and `stBaseButton-secondary` without setting a
  background. Streamlit renders those variants on a light background, so labels
  were white-on-white and invisible ("Save & Continue Later" showed only its
  emoji; so did "Add Rater", every "✏️" edit button, and "Browse files").
- Rewritten so every rule sets colour and background TOGETHER. Never set one
  without the other in this block. Selectors now hook the `data-testid` on the
  button element itself, because Streamlit nests a div between the `.stButton`
  wrapper and the button, which silently broke the old `>` direct-child rules.
- The system: primary (`stBaseButton-primary`, `stBaseButton-primaryFormSubmit`)
  is filled Bentley green with a white label; secondary (`stBaseButton-secondary`,
  `stBaseButton-secondaryFormSubmit`) is white with a green label and green
  border; download buttons stay neutral grey to distinguish them from actions;
  disabled is grey-on-grey but still legible.
- This also removed Streamlit's default red on the primary Submit button, which
  was off-brand.
- Verified by computing WCAG contrast ratios on every rendered button across the
  landing page, rater form, leader portal and admin dashboard: 46 buttons, worst
  ratio 5.04:1, none below the 4.5:1 AA threshold, most at 10.78:1.

### Feedback form is paginated, not single-scroll (`feedback_form.py`)
Both the Full 360 rater form and the Self-Assessment render one page at a time,
built by `_build_pages(is_self)`: one page per dimension (5 items + its comment
box), then Overall Feedback, then Development Priorities (self-assessment
only), then a final Review page. Review is always last — the edit-jump-back
logic below relies on that.

- Each dimension page validates all 5 items are rated before its "Continue"
  will advance, blocking with a message naming the missing question numbers.
  Overall Feedback and Development Priorities' keep/change and actions text
  have their own validation (priorities: minimum count, no duplicate
  dimension, actions text required whenever a dimension is chosen — see the
  development-priorities subsection above, unchanged by pagination).
- The Review page lists every section with an **Edit** button that jumps back
  to that page (`st.session_state['return_to_review']` + `form_page_idx`);
  clicking Continue from an edited page returns to Review instead of
  continuing forward, via `_advance_from`.
- The progress bar shows a **percentage** of the 45 items answered, not
  "X of 45" — chosen specifically so it reads without needing to translate
  "of" (see the i18n subsection below).
- Save-and-resume lands on the first INCOMPLETE dimension (`_resume_page_index`),
  or the first trailing page if every dimension is done — not necessarily
  page 1. Purely derived from the saved draft, so a same-session rerun and a
  genuine browser-close-and-reopen days later behave identically.
- GOTCHA, ALREADY FIXED, DON'T REINTRODUCE: `st.session_state` does not
  reliably retain a widget's value once that widget stops being
  re-instantiated on a later page — each dimension page only creates its own
  5 `rating_N`/`comment_X` widgets, not every dimension's. `_collect_current_answers`
  therefore takes `base_ratings`/`base_comments` (the draft already loaded
  once at the top of `render_feedback_form`) and merges the CURRENT page's
  fresh session_state on top, rather than trusting session_state alone to
  have accumulated everything from every page visited so far. Every call site
  (Save, Continue, and the Review page's own display) passes these through.
  Confirmed empirically by checking the actual saved draft in the database
  after several page transitions, not assumed.
- Every button-creating call in the file (`st.button`/`st.form_submit_button`)
  is wired through `_t()`/`get_translation()` with one deliberate exception:
  the locale picker's own "Continue", which has no locale yet to translate
  into at the point it renders. Re-audited 2026-08-14 against the paginated
  structure specifically (11 button calls total across dimension/overall/
  priorities/review pages) — no oversights found.

### Survey pages are Heritage White, matching the report (`app.py`, `feedback_form.py`)
The rater form and self-assessment now read as part of the same document
family as the Word report, not a generic Streamlit form:

- Each page's outer card fills with Heritage White — `framework.py`'s
  `COLOURS['heritage_white']`, `#DCD8C0`. This is the SAME confirmed brand
  value already used across the report (radar chart fill, item bar charts,
  the Development Areas PAPU-NANU header), reused as-is, not a separate tint
  chosen for the survey. Scoped via `st.container(key="compass_survey_form")`
  wrapping each `st.form("feedback_form_page")` call, and the leader portal's
  own `portal_add_rater_form`/`portal_upload_raters` containers use the SAME
  white-card CSS pattern under their own separate keys — deliberately scoped
  per-container (rather than a bare `div[data-testid="stForm"]` rule) because
  an unscoped rule would silently reach every other `st.form` in the app,
  including admin_dashboard.py's add-leader/add-rater/quick-add forms, which
  were never meant to change.
- Individual question boxes (`st.container(key=f"item_box_{item_num}")`),
  text areas, the instructions box, the language-picker box, and the
  "Welcome back" resume banner are white cards sitting on top of that fill —
  the same white-card-with-green-left-accent language throughout, including
  the resume banner, which was recoloured off Streamlit's default blue.
- Body text sitting directly on the Heritage White background (not inside a
  white sub-box) was deliberately darkened from the values used on plain
  white/pale-grey backgrounds elsewhere (`#666`→`#4D4D4D`, `#999`→`#595959`)
  to hold WCAG AA contrast against the tan. If you add new text directly on
  the survey-form background, check contrast against `#DCD8C0`, not against
  white.
- The rating scale's last option is split by relationship: the Full 360 rater
  form keeps "No opportunity to observe" (`ui_rating_no_opportunity_other`);
  the self-assessment reads "No opportunity to demonstrate"
  (`ui_rating_no_opportunity_self`) — a leader rating themselves has
  opportunity to demonstrate a behaviour, not to observe it. The other five
  scale words are unaffected, since they read the same either way.

### i18n foundation — scaffold only, ZERO live translations (`database.py`, `framework.py`, `feedback_form.py`, `email_sender.py`)
Built for the round-two (October cohort) rater nomination work. Ships with no
real translation content — every string still renders in English today, by
design, until the item set and rating scale are finalised.

- `translations` table (`string_key`, `locale`, `string_value`); `raters.locale`
  column. `get_translation()`/`_t()` short-circuits to the hardcoded English
  fallback whenever `locale` is `None` or `'en'` — the expected path for every
  rater until translations are actually commissioned, at zero DB cost.
- A locale picker (`render_locale_picker`) is shown once, on a rater's first
  visit, before any survey content — `raters.locale` being set is what skips
  it on every later visit, including a same-session resume, since
  `get_rater_by_token()` re-fetches `rater_info` fresh on every page load.
- Arabic (`RTL_LOCALES`) gets a full RTL layout scoped to the form only
  (`_render_rtl_css`): `direction: rtl` on `div[data-testid="stForm"]`.
  Numbers, Q-numbering, and the 1-5 rating scale are deliberately forced back
  to LTR within that RTL layout — mirroring a two-digit question number would
  misread as a different number, not just flip direction. Because every page
  type (dimension, Review) wraps its content in the same `st.form`, this
  selector always has something to match regardless of which page is showing.
  THREE separate selectors currently do this LTR-forcing, one per page's
  actual Q-number markup — check all three if the item/review markup ever
  changes again:
  - `.item-container span:first-child` — the `.item-container` CSS class
    (app.py) is currently unused by any live markup (both the dimension page
    and the Review page have since moved off it, see below); kept in the
    selector list defensively rather than removed, in case something starts
    using that class again.
  - `.review-item-question span:first-child` — the Review page's item rows.
  - `div[class*="st-key-item_box_"] span:first-child` — the LIVE dimension
    page's item rows. ADDED 2026-08-14: the dimension page's per-item markup
    moved from a `.item-container` div to the `st.container(key=f"item_box_{n}")`
    wrapper during the Heritage-White pass above, and the RTL selector was
    never updated to follow it — so the Q-number silently stopped being
    forced LTR on that specific page type (confirmed via computed style on a
    live Arabic-locale dimension page: `direction` was `rtl` before this fix).
    The lesson: this selector list is keyed to specific CSS classes/keys in
    the item markup, not to a stable concept — if that markup is restructured
    again, re-check this list against actual computed style on every page
    type, don't assume it still applies just because the RTL mechanism itself
    is unchanged.
  - The rating scale (`st.segmented_control`, via `[data-testid="stButtonGroup"]`)
    is forced LTR the same way and was NOT affected by the item-markup change,
    since it's matched by widget testid, not by the item wrapper's class.
- Locale persists correctly through a mid-flow save-and-resume, including
  landing on a partially-completed dimension mid-way through (not page 1),
  with the resumed page already in the correct RTL layout — verified
  2026-08-14 with a real interactive test (not synthetic draft injection):
  Arabic selected, dimension 1 and 2 completed and dimension 3 left
  partially answered, tab closed and reopened via a fresh session. No flash
  of English/LTR is reachable in principle either, since locale is read from
  the rater's row synchronously at the top of `render_feedback_form`, before
  any page content (including the RTL `<style>` block itself) is generated —
  unlike a client-side language switch, there is no separately-rendered
  English pass to flash before Arabic corrects it.
- EVERY `<p>` AND `<textarea>` NEEDS `unicode-bidi: plaintext` inside the RTL
  form, found the same day a human actually looked at a rendered Arabic-locale
  page rather than just checking computed styles: with zero real translations
  shipped, every paragraph and every comment-box placeholder is still plain
  English, and a forced `direction: rtl` on the ancestor visually relocates
  TRAILING PUNCTUATION to the start of the line - "Check everything below
  before submitting. You can still change anything." rendered as ".Check
  everything...anything" (period moved to the front, none at the end). The
  underlying text was never wrong; only its bidi-resolved visual order was.
  `unicode-bidi: plaintext` makes the browser derive each element's own base
  direction from its actual first strong character rather than inheriting the
  forced one, so English fallback text lays out correctly today AND a real
  Arabic paragraph will correctly switch to RTL on its own once dropped in
  later, with no further change needed either way. THE PLACEHOLDER NEEDED ITS
  OWN separate rule (`textarea::placeholder`) - `::placeholder` does not
  inherit `unicode-bidi` from the textarea it belongs to
  (`getComputedStyle(textarea, '::placeholder')` showed `isolate`, not
  `plaintext`, even after the textarea itself was fixed), so the placeholder
  kept the bug on its own until given the identical rule directly.
- LOCAL DEV STREAMLIT VERSION MUST MATCH `requirements.txt` for ANY CSS
  targeting a specific widget's internal markup (item boxes, form
  containers, the survey's Heritage White fill, and especially
  `st.selectbox` are all in this category) — see the environment gotchas
  in section 3 for the full story and the isolated venv this now has to be
  tested against.

### Leader portal: sending an invitation is a separate, deliberate action from adding a rater (`leader_portal.py`, `database.py`, `email_sender.py`)
Adding a rater — the single "Add a Rater" form or a CSV import — only writes
the record. It does NOT send that person's invitation email at the same time.

- The "People You've Nominated" list shows a nudge whenever anyone is waiting
  to be invited ("N people are ready to be invited, check names/emails/
  relationships below carefully — once you send, invitations go out
  immediately and can't be recalled"), and a single **"Send Invitations"**
  button that fires every pending one in one action. This button surfaces the
  same way regardless of whether raters arrived one at a time or via CSV —
  it's driven by `database.get_raters_pending_invitation(leader_id)`, a query
  against `email_log` (anyone without a logged successful `'invitation'` send),
  not by which form was used to add them.
- WHY: a typo in a name, email, or relationship entered a moment earlier used
  to be mailed out immediately and irreversibly. Decoupling adding from
  sending gives a genuine review window — and a natural place to use the
  existing email/relationship correction tools — before anything goes out.
- A row whose invitation attempt genuinely FAILED (an address rejected at
  send time, not merely not-yet-sent) gets a small warning icon next to its
  Edit button, driven by `database.get_failed_invitation_emails(leader_id)`.
  This is deliberately narrower than a full sent/pending status per row —
  showing status for every row would duplicate the aggregate banner in the
  common all-succeeded case, and edges toward the same "response status per
  person" territory the roster was built to avoid (this is invitation status,
  not response status, so it doesn't actually conflict with that principle,
  but the roster's design bar for showing anything per-row is deliberately
  high). It exists specifically because a bulk send can partially fail, and
  without it there's no way to tell WHICH of several pending people needs a
  fixed address versus just a resend.
- The leader is also emailed directly the moment a send fails outright
  (`email_sender.send_invitation_failure_notice`), so they find out even if
  they close the portal tab before seeing the in-app warning. This ONLY
  covers failures the app detects synchronously (an address rejected during
  the SMTP transaction itself, via `_send_email`'s `SMTPRecipientsRefused`
  handling). A message accepted at send time that bounces LATER is invisible
  to the app entirely — that bounce is a separate email sent by the
  recipient's mail server straight back to the sending mailbox, with no hook
  into this application at all. Closing that gap needs a bounce-aware
  transactional email provider (Postmark/SendGrid/SES, via a webhook), which
  is flagged as deliberate future work, not attempted.
- The "Relationship to you" dropdown on the Add a Rater form has NO default —
  it starts blank (`index=None`, a placeholder), and submitting without a
  choice is blocked with "Please select a relationship". A prior real mistake
  was adding too many Bosses via a leftover selection from adding the
  previous rater; forcing a deliberate choice every time is cheaper than
  relying on someone to notice and change it.
- TWO BUGS FOUND AND FIXED WHILE BUILDING THIS, both worth knowing about if
  similar symptoms reappear:
  - `get_raters_pending_invitation` must filter `email IS NOT NULL`. Without
    it, legacy rater rows with no email at all (which can never be sent, and
    don't even appear in the leader's visible roster, since
    `get_nomination_roster`'s own backfill requires a name or email) inflated
    the pending count with something the leader had no way to see or resolve.
  - `delete_rater` (admin dashboard → Links & Tracking tab) must clear
    `email_log` before deleting the `raters` row. `email_log.rater_id` carries
    a `FOREIGN KEY` to `raters(id)` with no cascade, so anyone who'd ever had
    even one email logged against them — an invitation attempt, a reminder,
    success or failure — could not be deleted; Turso raised `FOREIGN KEY
    constraint failed`. Reproduced against a real row with foreign keys
    enforced before confirming the fix.
- `delete_rater`'s existing guard (refuses to delete anyone with a non-NULL
  `completed_at`, returning `False` rather than deleting) was re-verified
  2026-08-14 specifically against a completed-and-SEVERED rater (name/email
  already nulled, `email_log.to_email` already `[severed]`): the guard still
  holds — the row, its ratings, and its comments are left completely
  untouched. This is intentional, not incidental: once someone has responded,
  their ratings/comments are folded into the leader's aggregate group scores,
  so silently allowing a delete here would quietly shrink a response count
  and shift reported averages after the fact — exactly the kind of change
  that must never happen invisibly. KNOWN GAP, NOT YET FIXED: the admin
  dashboard's delete button (`admin_dashboard.py`, Links & Tracking tab)
  renders unconditionally for every rater and never checks `delete_rater`'s
  return value — clicking delete on a completed/severed rater currently just
  reruns the page with no error and no indication anything was refused. The
  DB-level protection holds either way, but an admin has no feedback that the
  click did nothing. Left as-is pending a decision on the intended UI
  behaviour, per the same "don't quietly change the one part of the system
  built around irreversible protection" caution as the guard itself.

### Data-protection consent gates and comment guidance — DONE 2026-08-21
Agreed at a Bentley progress meeting ahead of the next pilot cohort: consent
needs to be explicit and captured, not implied by proceeding, and comments
need to visibly read as optional and focused on highlights, since verbatim
length was a driver of "process feels long" feedback on the test cohort.

- `raters`/`leaders` both gained `consent_given`/`consent_given_at`
  (`_safe_add_column`, same pattern as `raters.locale`), plus
  `set_rater_consent(rater_id)`/`set_leader_consent(leader_id)`. Checked from
  the database on every visit, never session state, so the gate shows once
  and never again once given — same durability discipline as the locale
  picker.
- THREE DISTINCT CONSENT SCREENS, not one shared version, because what a
  person is consenting to genuinely differs:
  - Rater (`render_consent_gate` in `feedback_form.py`, shown to Boss/Peers/
    DRs/Others): scores only ever shown combined with others; comments shown
    to the leader grouped by category, name/email scrubbed on submit; an
    explicit "comments aren't protected by the anonymity threshold the way
    scores are" warning; who else can see the feedback beyond the leader.
  - Self (same function, `relationship == 'Self'` branch): genuinely
    different copy, not a reworded rater version — nothing is anonymised for
    your own reflection, there's no threshold, and no one to hide from but
    the leader themself. The FIRST version of this shipped with the SAME
    copy for Self and raters, which read as if scores/anonymity applied to a
    self-assessment too — corrected the same day once caught.
  - Leader (`render_leader_consent_gate` in `leader_portal.py`, shown once on
    first portal visit): covers their own Self-Assessment/Full 360 data,
    responsibility for nominating raters appropriately, and the rater
    name/email-scrubbing disclosure, since the leader is consenting to their
    raters' data being handled too, not just their own.
  - All three: Continue is FORM-DISABLED until the checkbox is ticked
    (`st.button(..., disabled=not consented)`), not just discouraged by
    copy — verified via the button's actual `disabled` attribute, not just
    how it looks.
- Every string routed through `_t()`/`get_translation()` (leaders have no
  locale column, so their gate always passes `locale=None`, which
  `get_translation` already short-circuits to fallback text) — zero real
  translation rows, ready for the six-language commissioning with no further
  code change.
- Rater and portal invitation emails (`email_sender.py`) each carry a short
  advance-notice paragraph ahead of the in-app checkbox — HTML email can't
  submit a checked box back to the system, so this is notice only, not
  capture. The rater invitation's note is a genuinely separate message for
  Self vs everyone else (not one template with a swapped clause), matching
  how `intro`/`cta_text` already split in that same function. The leader
  portal invitation also gained a line encouraging leaders to tell raters
  verbally that their name/email get scrubbed on submit.
- Every optional comment box (dimension comments, the keep/change prompts)
  gained a PERSISTENT guidance line below the box (`_render_comment_guidance`),
  not placeholder text — placeholder text disappears the moment someone
  starts typing, which is exactly when the reminder matters most. No
  character limit was added; the guidance text does the work of encouraging
  brevity, not a hard cap that would read as suppressing feedback.
- The one genuinely required field (Development Priorities, self-assessment
  only) already had a red-asterisk convention from the earlier priorities
  work; combined with the new "Optional." comment guidance, the two are now
  visibly distinguished from each other with no further styling needed.
- WORDING CONSISTENCY FIX: the survey's pre-existing instruction box claimed
  comments "will be anonymised to the group title you respond from" —
  overclaiming, since only the LABEL is anonymised (group name instead of a
  person's name), never the CONTENT of what's written. Read next to the new
  consent copy's "comments aren't protected the way scores are... may be
  recognisable" warning, the old wording read as a flat contradiction rather
  than the same fact stated twice. Reworded to "labelled with the group you
  respond from, not your name" (`ui_instructions_other_4`,
  `feedback_form.py`) so the two no longer conflict.
- STILL OUTSTANDING, needs the human: `ui_consent_retention` renders a
  literal placeholder — `"[Retention statement to be confirmed]"` — on all
  three consent screens, deliberately visible rather than silently missing.
  Do not invent a retention period. Pending a decision informed by the
  actual DPA arrangement with Bentley, and in tension with the fact that
  `historical_scores` already exists for year-on-year comparison, which
  pulls against early deletion. This is a DIFFERENT open item from section
  8's "guidance artefacts" (rater-facing "comment on behaviour, not
  incidents"; coach-facing "don't attempt to attribute feedback") — the new
  comment-guidance line partially serves the same spirit but does not
  replace that outstanding work.

### Email header encoding — non-ASCII display names — FIXED 2026-08-21
Real bug hit in the sandbox: an invitation to "Seher Başar Turgut"
(sbasar@dogusotomotiv.com.tr) bounced from O365 with `InvalidRecipientsException`
showing the name silently corrupted to "Seher Baar Turgut" — the "ş" dropped
entirely, not garbled. The sending account also started showing as throttled
for "continuous invalid recipients errors" (plural), which is what raised
the possibility of it being systemic rather than one bad address.

- DIAGNOSED, NOT A DATA BUG: `raters`/`leaders.name` was confirmed intact at
  rest for this rater, and every write path (the single-add form and CSV
  import in `leader_portal.py`, `add_rater`/`add_to_nomination_roster` and
  the connection layer in `database.py`) was audited clean — parameterised
  binds throughout, no `.encode`/`.decode`/`unicodedata`/ASCII-only regex
  touching name data anywhere in the repo.
- ROOT CAUSE: `_send_email` in `email_sender.py` built both `msg['From']`
  and `msg['To']` as raw `f"{name} <{email}>"` strings. When `name` has
  non-ASCII characters, Python's email library wraps the WHOLE string — name
  AND address together — in one RFC 2047 encoded-word, which is invalid:
  encoded-words must only ever cover the display-name portion, never
  straddle into the addr-spec. Reproduced locally: this exact code turns
  into `=?utf-8?q?Seher_Ba=C5=9Far_Turgut_=3Csbasar=40...?=` (address baked
  into the blob), and `'Seher Başar Turgut'.encode('ascii', errors='ignore')`
  reproduces the bounce's corrupted name byte-for-byte, consistent with
  whatever downstream system (Exchange's own recipient-resolution/NDR path)
  had to decode and re-parse that malformed compound header.
  `_send_email` is the single shared function every send in the file funnels
  through (7 call sites), so this was one defect with a wide blast radius,
  not seven scattered ones.
- FIX: both header assignments now go through `email.utils.formataddr()`,
  which RFC-2047-encodes only the display name when needed and leaves the
  address as plain, untouched ASCII. Verified: `formataddr()` now produces a
  correctly separated encoded-word-plus-plain-address pair, and round-trips
  correctly through `parseaddr()`/`decode_header()`. Grepped the file for
  the same pattern elsewhere (CC/BCC/Reply-To) — none found; `Reply-To` is a
  bare address with no display name, never exposed.
- NOT DONE, needs the human (no O365 admin access or live deployment from
  this environment): confirm the O365 throttle has actually cleared before
  retrying — if it was account-wide, retrying too soon risks failing again
  for the throttle itself and being mistaken for the fix not working — then
  resend the invitation to Seher's real row and confirm it sends clean.
  Seher was confirmed as the only non-ASCII name among the current ten
  leader rows at diagnosis time; no other resends were identified as needed.

### Email greetings, sender display name — DONE 2026-08-21, then PARTLY REVERTED
Two rounds, because the first change caused a real delivery failure.

- GREETINGS: every email template now opens with "Dear {name}," using the
  actual recipient's name (`email_greeting` translation key, `_translated()`).
  `_get_rater_invitation_html` and `_get_reminder_html` had NO greeting at
  all and needed the rater's own name threaded through as a new parameter
  from `send_rater_invitation`/`send_rater_reminder` - the other four
  templates already had one. `_get_admin_notification_html` deliberately
  excluded: it's a system alert about a leader, not addressed to a named
  person. Caught and fixed in the same pass: `admin_dashboard.py`'s
  test-email preview still called the old 3-argument signature - would
  have thrown a `TypeError` on the next "Send Test Email" click.
- SENDER DISPLAY NAME - DO NOT CHANGE THIS AGAIN WITHOUT RE-READING THIS
  ENTRY. First set to the brand ("Bentley Compass 360") via a hardcoded
  `SENDER_DISPLAY_NAME` constant in `email_sender.py`, removing the
  `sender_name` config field entirely (that field was the exact mechanism
  that had let a live send display "Ian Moreton-Thickett" instead of the
  system). That seemed like the right white-labelling call - until two of
  three real corporate recipients (Doğuş Otomotiv, Samaco) silently never
  received their invitation after the change, no bounce, `email_log` showed
  success on our side both times. Diagnosis: enterprise mail security
  treating a recognisable third-party brand name paired with an unrelated
  sending domain as a phishing/brand-impersonation signal - exactly the
  pattern those systems are built to catch, and something that gets WORSE,
  not better, at the scale this eventually sends across many independent
  corporate mail environments. `SENDER_DISPLAY_NAME` was reverted to
  `"Ian Moreton-Thickett"` and this is now the PERMANENT configuration, not
  a temporary experiment - the display name and the sending domain need to
  actually match. The no-override discipline stays: still one hardcoded
  constant, still no `sender_name` env var/secrets path. If white-labelling
  the sender identity comes up again, the actual fix is a Bentley-owned
  sending domain, not a display-name change on an unrelated domain - and
  that wasn't judged practical given the scale of eventual recipients
  across many organisations' own independent mail policies.
- Reply-To was never affected either way - `sender_email` already correctly
  resolves to the real, authenticated SMTP login, so replies land at a
  monitored inbox regardless of what display name is showing.

### Comment prompt merged with brevity guidance, self/rater split — DONE 2026-08-21
The per-dimension comment prompt (asking whether to comment) and the
guidance line below the box (encouraging brevity, added earlier) were two
separate lines - split that way, "Optional" read as if it only qualified
the second sentence, not the whole box. Merged into one line above the box
(`ui_comment_prompt_self` / `ui_comment_prompt_rater`), removing the
separate line below. Self and rater versions are genuinely different
strings, not one template with a swapped clause: a self-assessment comment
has no one to trace it back to, so the trace-back clause is dropped
entirely for Self rather than reworded. Only the dimension comment box was
touched - the Overall Feedback keep/change boxes keep their separate
below-the-box guidance line, unchanged. Trade-off, not an oversight: this
guidance is now only visible before typing starts, not while composing,
since the old below-the-box version stayed in view once the placeholder
text had disappeared.

### Mobile rating-scale layout — three follow-up fixes, DONE 2026-08-21 to 2026-08-22
The five frequency options plus "No opportunity..." wrapped unevenly across
two or three rows below a certain viewport width. Three passes, because
each fix surfaced a real problem the first pass hadn't checked for.

- SELECTOR: the actual flex container that wraps is
  `[data-testid="stButtonGroup"] [role="radiogroup"]`, not the outer
  `stButtonGroup` div (which is `display:block`, just a wrapper). A rule
  targeting the outer div does nothing.
- BREAKPOINT moved twice, both times because testing found the wrap
  persisted further than assumed - do not "simplify" this back to a small
  number without re-running the same sweep. Started at 480px, but 600px
  already showed the exact uneven wrap this fix exists to prevent. Swept
  the full range and found the survey card's own content column is
  viewport-constrained up to ~940px, then hits a content-driven width
  (~709-710px for English) only marginally sufficient for one row
  (708px still wraps, 709px doesn't) - moved to 960px. Then, checking the
  breakpoint's margin against future translated content (placeholder
  German-length labels, not real translations - none exist yet): 960px
  FAILED - German-length labels need ~771px unwrapped and wrapped again at
  970-1000px viewport. Moved to **1100px**, tuned to clear the realistic
  German case with margin, not a deliberately-extreme stress case that
  needed ~1500px (going that wide would force the column layout onto
  ordinary desktop widths today's content doesn't justify). REVISIT ONCE
  REAL SIX-LANGUAGE TRANSLATIONS ARE COMMISSIONED - re-run the same sweep
  against actual shipped strings, not placeholder text.
- WIDTH: buttons were narrower than the card even after stacking into a
  column, `width:100%` on the buttons did nothing on its own. Root cause,
  found by checking computed styles and matching stylesheet rules directly
  rather than guessing: Streamlit applies `width:fit-content` on the
  widget's own `stElementContainer` wrapper, AND SEPARATELY sets
  `max-width:fit-content` directly on the radiogroup itself - two
  independent shrink-to-content rules stacked on each other. Needed all
  three overridden together (`stElementContainer`, `stButtonGroup`, and the
  radiogroup's `width` AND `max-width`) - fixing only one left the others
  still capping it.
- BORDER: rotating the "No opportunity..." divider from a `border-left`
  (correct in the horizontal row) to a `border-top` (for the stacked
  column) REPLACED that button's own normal top border instead of adding
  to it - `border-top` is a shorthand, it always overwrites, never layers.
  Fixed by resetting `border-left`/`border-top` back to the button's own
  measured normal border (`1px solid rgba(49,51,63,0.2)`) and drawing the
  actual divider line with `box-shadow` instead, which sits outside the
  border box and can't touch any of the four declared sides.
- Verified at every stage against a real Arabic-locale rater too, not just
  English - the column stack composes correctly with the existing
  forced-LTR rule on this same widget (different CSS properties,
  `direction` vs `flex-direction`, genuinely orthogonal).

### Cohort near-duplicate prevention — DONE 2026-08-23
Real incident: the Overview tab showed two separate "Self Assessment Test
August 2026" cohort cards (1 leader vs 2 leaders) instead of one combined
card with 3 - visually identical text, but not byte-identical underneath
(same category of bug as the non-ASCII name/email-header issue above: what
you see on screen isn't a reliable guide to what's actually stored).
Diagnosis of the SPECIFIC affected row(s) needed live Turso access this
environment didn't have - not resolved here, still needs the human to run
the `hex()`/`length()` comparison against the real database and report
back what's found before the existing bad row(s) can be fixed. What WAS
built is the prevention:
- `normalise_cohort_text()` in `framework.py` (same pattern as the existing
  `normalise_relationship`) - canonicalises non-breaking/zero-width
  spaces, smart quotes, en/em dashes to plain ASCII equivalents.
- `db.get_leader_cohort_options()` - merges the existing (previously
  unused-by-leader-creation) `cohorts` table with any `leaders.cohort`
  values not yet in it, DEDUPLICATED ON THE NORMALISED FORM, so two rows
  differing only by an invisible character collapse into one dropdown
  option instead of showing as two visually-identical entries.
- The single "Add Leader" form's cohort field is now a dropdown of
  existing cohorts plus "+ Add a new cohort...", which reveals a text
  field. Had to live OUTSIDE `st.form` - forms only rerun on submit, so a
  selectbox inside one can't dynamically reveal anything. A typed new name
  runs through `_resolve_new_cohort_name()`, which normalises it and checks
  case-insensitively against every existing cohort BEFORE accepting it as
  new - a match silently returns the EXISTING cohort's exact stored value,
  not the newly-typed variant. Genuinely new names get registered into the
  `cohorts` table, closing a separate pre-existing gap where the cohort
  management UI's own text promised this ("they'll be created automatically
  when adding leaders") but no code path actually did it.
- CSV import gets the same normalise-and-resolve treatment silently
  (it can't offer a dropdown), rather than blocking - a genuinely new
  cohort in a CSV is a legitimate bulk-import case, not an error.
- Verified against a REAL byte-level repro, not just the normaliser in
  isolation: seeded a leader locally with an actual `U+00A0` in their
  cohort (confirmed via `hex()`), reproduced the exact reported bug live
  in the dashboard (two identical-looking cards), then ran both entry
  paths against that same variant and confirmed every resulting row landed
  on the byte-identical canonical value in the database.

### Admin notification system — VERIFIED 2026-08-23, one known gap
Confirmed fully wired, not a partial/orphaned build: `send_admin_notification`
exists, both triggers (self-assessment-complete, Full-360-threshold-crossed)
have live call sites in `feedback_form.py`'s `_render_review_page`, right
after a successful `submit_feedback`, and every send attempt logs to
`email_log` regardless of outcome. `ADMIN_NOTIFICATION_EMAIL` resolves
env-first then `st.secrets["app"]["admin_notification_email"]`, matching the
SMTP config pattern. NOT verified from this environment (no live Turso
access): whether that env var/secret is actually set in the deployed
sandbox, and whether a notification has actually fired and logged
successfully there.
KNOWN GAP, NOT YET FIXED: Full 360 has a real atomic once-only guard -
`full_360_notified_at`, claimed via `try_claim_full_360_notification`'s
conditional `UPDATE ... WHERE full_360_notified_at IS NULL`. Self-assessment
has NO equivalent column or claim - it relies entirely on the fact that a
completed rater's token routes to the thank-you page instead of back into
the form, so genuine resubmission isn't possible in the normal flow. That's
an app-routing safeguard, not a database-level one - functionally holds
today but architecturally weaker than the Full 360 case. Add a
`self_assessment_notified_at` column for consistency if this is worth
closing.

### First-name-style greetings — CONSIDERED AND REJECTED, do not implement
Every greeting in this system uses the person's full stored name ("Dear
Seher Başar Turgut,"), never a derived first name. Splitting a stored full
name on the first space to guess a first name is unsafe for this cohort
specifically: Vietnamese and Chinese naming conventions are commonly
family-name-first, and this cohort includes participants from Ho Chi Minh
City and Taipei - a naive split risks greeting someone by their surname. If
a first-name-style greeting is wanted later, it must come from an explicit,
self-reported "preferred name" field, never derived automatically from the
stored name.

### Overview tab: self-assessment readiness count — DONE 2026-08-23
Each cohort card on the admin Overview tab now shows a "ready for
Self-Assessment" count alongside the existing "ready for Full 360" figure
and response rate, using `self_completed` (the same completion flag already
read everywhere else a leader's own self-assessment status is checked -
see `get_all_leaders` in `database.py`). Scoped deliberately to the
per-cohort cards only, per the request; the "Overall Statistics" section
and the filtered single-cohort view below it were left unchanged.

### Reports table logging gap — CLOSED 2026-08-23, VERIFIED LIVE 2026-08-25
The `reports` table existed in the schema from the start but nothing ever
wrote to it, so every generated report - Full 360, Self-Assessment, batch -
was invisible to it regardless of success.

- Added `db.log_report(leader_id, report_type, file_path, assessment_year)`,
  the same pairing pattern as the existing `log_email`, plus a paired
  `get_reports_for_leader()` getter. Wired into all three generation call
  sites in `admin_dashboard.py`: the single Full 360/Self-Assessment/
  Progress button, the Self-Assessment-only button, and the "Generate All
  Full 360 Reports" batch loop (whose discarded `_` return value had to
  become `output_path` to make logging possible there).
- Removed the dead `generate_all_reports` import from `app.py` - the batch
  button has its own inline loop and never called it. Left the function
  itself untouched in `report_generator.py`.
- Audited every other table for the same pattern. `ratings` looked like a
  second gap on a first grep but isn't - it writes via `INSERT OR REPLACE`,
  which a plain `INSERT INTO` grep misses. `translations` genuinely has
  zero inserts anywhere, but that's the already-documented, deliberate i18n
  scaffold pending the six-language commissioning, not a hidden bug.
- VERIFIED LIVE 2026-08-25 against the deployed sandbox at
  `portal.thedevelopmentcatalyst.co.uk`, after the fix was deployed: clicked
  all three real Generate buttons through the actual admin UI (single Full
  360 for Ian Moreton-Thickett, single Self-Assessment for Ian Lewis, and
  the "Generate All Full 360 Reports" batch button) and got a clean
  "Report(s) generated!" with no error on every one. CONFIRMED WITH DIRECT
  DB EVIDENCE the same day: the human checked the sandbox Turso `reports`
  table directly and saw three rows, matching the three generate actions
  above. Gap fully closed, not just indirectly inferred from the absence
  of an error.

### Scoring scale explanation added to reports — DONE 2026-08-25
Scores appear throughout both report types (Executive Summary, PAPU-NANU
quadrants, item-level charts) with no on-page explanation that they measure
behaviour frequency, not quality - a reader could reasonably misread "3.5"
as a performance grade. Since this is a linear, front-to-back read once per
coaching conversation, not a navigable app, a single statement placed
before the first number appears is sufficient; it is not repeated near
every chart.

- `add_scoring_scale_note(doc, no_opportunity_label)` in
  `report_generator.py`, styled to match the existing
  `add_fold_transparency_note` convention (9pt italic grey, `#666666`), so
  it reads as the same family of explanatory aside rather than a new visual
  idiom.
- Same core sentence for both report types (explains the instrument, not
  the person - no self/other branching needed there), but the quoted
  "No opportunity to..." phrase matches whichever wording is already
  correct for that report type per the existing self/other split in
  `feedback_form.py`: "No opportunity to demonstrate" for Self-Assessment,
  "No opportunity to observe" for Full 360. No third variant introduced.
- Hardcoded English, consistent with the rest of the report content -
  flagged in the function's docstring as needing the same
  `_t()`/`get_translation()` treatment as everything else once the i18n
  work resumes.
- PLACEMENT DECIDED BY REAL PAGINATION CHECK, NOT ASSUMPTION: generated
  actual Full 360 and Self-Assessment reports from a real leader's data
  (Ian Moreton-Thickett, 12 responses), converted to PDF via Word
  (AppleScript automation - no LibreOffice in this environment), and
  measured true rendered whitespace with PyMuPDF, including image bounding
  boxes for the radar chart (a first pass that only checked text blocks
  under-counted the radar's height and had to be redone).
  - Full 360's "About This Report" page carries Response Summary and
    Executive Summary on the same page (by design, ahead of the radar's
    own deliberate page break - see the page-geometry section above), but
    had ~3.36in of genuine trailing whitespace before the forced break, not
    the "already packed" page that section implied. Room existed at both
    candidate locations here.
  - Self-Assessment's "About This Report" is its own page with ~7.22in
    free. Its score-table-plus-radar page, by contrast, had only ~1.05in
    free - consistent with the existing "watch heights" warning elsewhere
    in this file - so inserting text directly above that table (the
    Self-Assessment equivalent of "above the Executive Summary") would have
    risked pushing the radar onto a new page.
  - Placed in "About This Report" for BOTH report types, not because the two
    reports were required to match, but because it's the only location
    proven safe in both, and consistency here is simpler than tracking two
    different placements for one static note.
- RE-VERIFIED END TO END after making the change: regenerated both reports,
  reconverted to PDF, and confirmed identical total page counts (27 and 17)
  and identical leading content on every single page against the
  pre-change baseline - proof nothing shifted anywhere in either document,
  not just on the page that changed.
- ONE VERIFICATION GAP, WORTH KNOWING ABOUT: the Contents page is a Word TOC
  field, populated by Word's own layout engine on open/update, not by
  anything this code writes - so it always renders as literal
  "right-click and select 'Update Field'" placeholder text in a PDF
  produced without a human (or a VBA-driven update) opening it in Word
  first, and no Word automation route to force that update was available
  in this environment. Not treated as a blocker: since the page-by-page
  diff proves no section moved to a different page, the TOC will compute
  to the same correct numbers it already had once genuinely opened and
  updated in Word - but if the human wants to see the actual computed
  numbers rather than take that inference, opening either regenerated
  report in Word and updating the field (right-click, or Ctrl+A then F9)
  will show it directly.

### Leader Portal Redesign — design rationale (BUILT 2026-08-26, see the section after this one for the actual build)
Captured now so these two constraints are known going in, rather than
rediscovered mid-build. Nothing below has been implemented; there is no
new screen, table, or code yet. Treat this as design input for whenever
the redesign is actually built, not a changelog entry.

**Standing anonymity rule — applies to any current or future leader-facing
screen, not just this redesign.** Caught during early concepting: a draft
"Nominate Raters" screen included a per-row status column showing
`Responded` / `Awaiting response` next to each named rater - a genuine
individual-level anonymity leak, exactly what severed identity,
`ANONYMITY_THRESHOLD` grouping, and the per-category minimums (see section
4, "Anonymity design principle") already exist to prevent. Caught before
it went further, but worth stating as a rule rather than relying on it
being caught again by luck.

The rule: anything shown next to a named individual may describe the
LEADER's own action (have I invited them, have I nominated them, what
category did I put them in) but must never describe or imply the RATER's
own behaviour (opened the link, responded, close to finishing). Response
counts, progress, and completion status are only ever safe in aggregate -
category or cohort level, never attached to a name. This is the exact
pattern the existing Response Progress view and the Overview cohort cards
already get right; the redesign must not regress it.

Applies to: any future "Nominate Raters" / rater-list screen (name, email,
category, invitation-sent status are fine; response status is not); any
new screen introduced by this redesign that lists raters by name for any
reason. Explicitly does NOT apply to `admin_dashboard.py`'s Links &
Tracking tab - per-rater status there is legitimately visible to the
ADMINISTRATOR, not the leader, and that distinction is correct today.
Worth re-confirming it stays intact if that screen is ever touched as
part of this work, since it would be easy to accidentally carry a leader-
facing pattern back over there.

When this gets built (or reviewed), "does this leak individual response
status to the leader" is a standing check on every leader-facing screen -
the same category of check as the self/rater consent-copy differentiation
work, not a one-off fix to remember once.

**Mobile requirement for this redesign specifically.** Whenever this moves
from concept to build, it needs the same real-breakpoint discipline
already applied to the feedback form (see the mobile rating-scale section
above) - actual rendered-content sweeps, not an assumption that Streamlit/
CSS reflows acceptably by default.

- Card grids (the four rater-category cards on Overview, any admin-
  dashboard-equivalent cohort cards) need a real stacking breakpoint
  checked at actual phone widths, not assumed to reflow acceptably.
- The Nominate Raters list is the highest-risk element: a five-column row
  (Name / Email / Category / Status / Actions) cannot realistically stay
  one row on a phone screen. Needs a deliberate mobile layout - most
  likely each rater as a stacked card, not a table row - never a silent
  horizontal scroll or illegible truncated columns.
- Any fixed-pixel-width element is exactly the pattern that caused the
  original card-width bug on the feedback form (`width: fit-content`
  fighting a separate `max-width` rule on a different ancestor - see the
  mobile rating-scale section above). Check computed styles directly for
  any new element here rather than assuming a percentage-based width alone
  is sufficient.
- Test against the project's established width sweep - ~360px, ~430px,
  ~600px, and the existing desktop breakpoint - for every new screen this
  redesign introduces, not spot-checked once and assumed to generalise.

STILL NEEDS: an actual design/build conversation with the human before any
of this is implemented. Nothing here authorises starting the build.

**Self-Assessment date indicator — use completion date, not send date.**
The Overview mockup's Self-Assessment status card shows a date next to
"Self-Assessment complete." Placeholder text with no real data source
behind it in the concept. Decided: use completion date, labelled
"Completed on [date]," not "sent" - the system can't currently back a
"sent" claim, since the actual PDF hand-off happens manually outside the
app (Contents-page update in Word, PDF conversion, sent via Outlook) and
has no timestamp anywhere in the system today. Completion date is the one
value that's always true, always available, and needs no new tracking.
PRECISE SOURCE, since "self_completed" is easy to reach for and isn't
quite it: `leaders`/admin queries expose `self_completed` as a computed
0/1 COUNT (see `get_all_leaders` in `database.py`), not a date - there is
no `self_completed_at` column anywhere. The actual date is
`raters.completed_at` on that leader's Self-relationship rater row (fetch
via `get_raters_for_leader(leader_id)`, filter `relationship == 'Self'`).
Whenever this is built, read the date from there, not from a column that
doesn't exist.
If a genuine "sent" date is wanted later, that needs a new deliberate
action - e.g. a "mark as sent" button in the admin dashboard that stamps a
real timestamp at the moment the finished PDF is actually emailed - not
something inferred from existing data. Not needed now; noted so it isn't
re-derived from scratch if it comes up again.

**What's already real vs. what's still concept-only.** Worth being
explicit, since most of what this redesign reskins is existing, working
backend functionality, not new capability to build.

Already exists and works in the live system - this redesign is a visual
reskin of it, not a rebuild: batch "Send Invitations" for not-yet-invited
raters; the single, blind "remind everyone still to respond" action
(already rate-limited server-side, 48h between reminders per rater via
`reminder_sent_at`/`REMINDER_THROTTLE_HOURS`, no named per-rater
reminders - matches the anonymity rule above); self-assessment completion
tracking; category minimums, response counts, anonymity threshold logic.

Genuinely outstanding - not yet real anywhere, treat as actual small tasks
whenever this moves to a build:
1. The status-card copy itself ("Completed on [date], discussed at your
   Module 1 coaching session," per the decision above) doesn't exist in
   the current live UI yet.
2. The "Send reminders" control needs to SURFACE real rate-limit state,
   not just have it exist underneath. CHECKED, NOT LEFT AS AN ASSUMPTION
   (2026-08-26): today it does the opposite of surfacing gracefully.
   `render_progress_section` in `leader_portal.py` (~line 861) calls
   `send_rater_reminder(rater, ...)` for every incomplete rater and
   discards the return value entirely, then unconditionally shows
   "Reminders sent to anyone who hasn't responded yet." `send_rater_
   reminder` (`email_sender.py:673`) returns `(False, "Reminded
   recently")` and sends nothing when a rater is inside the 48h window -
   so if every incomplete rater happens to be throttled, the leader still
   sees an unconditional success message despite zero emails actually
   going out. Not a silent no-op, an actively misleading one. The
   underlying rate-limit logic itself is correct and doesn't need
   rebuilding; surfacing its real state (e.g. a visibly disabled/cooling-
   down button with "available again in Nh", computed from the earliest
   `reminder_sent_at` among incomplete raters) is the actual new work.
   Worth fixing independently of the redesign too, since it's a real bug
   in what ships today, not just a gap in the concept.

Everything else in this document (the anonymity rule, the mobile
requirement) applies to genuinely new screens (Nominate Raters,
Guidelines) being built for the first time in this visual language, not
existing features being touched.

### Leader Portal Redesign — THE BUILD, DONE 2026-08-26
Moved from concept to a real build in `leader_portal.py` (full rewrite),
plus a correctness fix carried into `admin_dashboard.py`/`email_sender.py`
per the redesign doc's section 4 audit requirement. Built against the three
concept mockups in `assets/` (Overview, Nominate Raters, Guidelines HTML
files) as binding reference material for the visual language.

- **Routing**: three screens, not client-side tabs. `?portal=<token>&view=
  overview|nominate|guidelines`, defaulting to overview. Nav links are plain
  `<a href="?portal=...&view=...">` - a real navigation/rerun, simpler than
  session-state tab machinery for something that's fundamentally "which page
  am I on". `render_leader_portal` is now a thin router; each screen has its
  own `render_portal_*` function.
- **Logo**: the mockups' plain green-circle "B" placeholder is replaced with
  the real Bentley wing mark, negative (white) variant via the existing
  `get_logo_data_uri(negative=True)` (already built for exactly this - dark
  backgrounds), since the positive variant would be invisible on the dark
  green topbar.
- **CSS namespaced `cp-`** (Compass Portal) throughout, self-contained in
  `leader_portal.py`'s own `PORTAL_CSS` block rather than added to app.py's
  already-large global stylesheet - keeps this redesign reviewable and
  revertable as one unit. Values adapted directly from the mockups' own CSS
  variables (`--green`, `--heritage`, etc.), not reinterpreted.
- **REAL BUG FOUND AND FIXED DURING BUILD, not in the original concept
  work**: every multi-line HTML string passed to `st.markdown(...,
  unsafe_allow_html=True)` was written with the function body's own 4+-space
  Python indentation. CommonMark's own syntax treats 4+ leading spaces on a
  line as a fenced code block, and Streamlit runs markdown parsing BEFORE
  honouring `unsafe_allow_html` - so every card rendered as literal escaped
  HTML text on the page instead of an actual styled card, caught live in
  browser testing (screenshot showed raw `<div class="cp-status-card">...`
  text). Fixed with two helpers, `_html()` (textwrap.dedent + strip) and
  `_md()` (`st.markdown(_html(...), unsafe_allow_html=True)`), applied
  programmatically across all 18 affected call sites (a Python script did
  the mechanical rewrite, verified by import + live re-render, not by hand
  across that many sites). Worth remembering for any future HTML block
  added to this file: multi-line HTML must go through `_html`/`_md`, never
  a bare indented triple-quoted string.
- **Category ring cards show NOMINATED count, not response count.** The
  mockup's ring/fraction math doesn't reduce to a single formula from its
  own placeholder numbers (checked directly against the rendered SVG
  `stroke-dashoffset` values - they don't correspond to count/suggested,
  count/min, or count/max consistently), so rather than reverse-engineer
  illustrative dummy data, the ring was built from the real, actual business
  rule: fraction = nominated count / (suggested, or min_if_any, or min,
  whichever applies), capped at 1.0. This is deliberately NOT a response-
  progress ring - showing nomination count is unambiguously the leader's
  own action under the anonymity rule; a per-category response ring would
  have needed a separate, harder judgement call this build didn't need to
  make.
- **Nominate Raters list Status column is "Invited" / "Not yet sent" ONLY**,
  sourced from `get_raters_pending_invitation` matched by email against the
  roster - never response status. This is the anonymity rule from this same
  document's section 1 implemented as actual logic, verified by checking
  rendered output (not just code): with a leader whose raters were a mix of
  invited/not-yet-sent, the list showed exactly those two states and
  nothing else.
- **ONE DELIBERATE DEVIATION FROM THE MOCKUP**: the Nominate Raters mockup's
  list rows include a "Remove" action. This app does not offer self-serve
  rater removal (see "Leader portal: sending an invitation is a separate,
  deliberate action..." above) - a real, already-reasoned decision this
  build wasn't asked to revisit, and a working Remove button would
  contradict it. Only Edit (correct email/relationship, pre-existing logic,
  functionally unchanged) is offered. If the human wants Remove revisited,
  that's a separate decision, not a redesign side-effect.
- **Reminder accuracy (redesign doc section 2), VERIFIED LIVE with
  constructed data, not just read from code**: added `_reminder_cooldown_
  state()` (computes real eligibility/hours-remaining from `reminder_sent_
  at`) and `_send_reminders_and_report()` (uses `send_bulk_reminders`'s
  sent/throttled/failed tally to build an honest message). Tested against
  three local raters with `reminder_sent_at` set to -5h (throttled),
  -60h (eligible), and NULL (eligible, never reminded):
  - Mixed case (1 throttled + 2 attempted): button enabled, caption "Nudges
    the N who haven't responded yet.", and after clicking the message read
    "All 1 rater still within their 48-hour window — no reminders were
    sent. Try again in about 42h. 2 failed to send — check back or contact
    your programme coordinator." (the 2 "failed" are the non-throttled
    attempts genuinely failing against a fake local SMTP target used only
    for this test - correctly NOT counted as throttled).
  - All-throttled case (all 3 within window): button correctly rendered
    DISABLED with "Available again in 42h." - verified via computed style,
    not just visual inspection. Since a disabled button can't be clicked
    through the UI (correctly), the pure "all throttled, zero other
    failures" message text was verified via a direct call to
    `_send_reminders_and_report`: "All 3 raters still within their 48-hour
    window — no reminders were sent. Try again in about 42h." No false
    "reminders sent" claim in either case - the bug this section exists to
    fix is confirmed closed.
  - Test raters and the temporary `.streamlit/secrets.toml` (fake SMTP
    creds, needed to make `is_email_configured()` return True locally so
    the button would render at all) were both removed after verification -
    nothing test-related was left in the local dev DB or gitignored
    secrets file.
- **Admin-side audit (redesign doc section 4)**: found the SAME category of
  bug, in the opposite direction, in two places - `admin_dashboard.py`'s
  Links & Tracking bulk "Send Reminders" button and its single-rater
  reminder toast both lumped a throttled skip (`"Reminded recently"`, not a
  failure) into the same bucket as a genuine SMTP failure, showing "N failed
  to send" / a red error toast for raters who were simply correctly rate-
  limited - a false alarm, not a false success, but the same "confident
  wrong result" pattern the leader-side bug was. Fixed by changing
  `send_bulk_reminders`'s return signature from `(sent, failed, results)` to
  `(sent, throttled, failed, results)` (its one call site updated
  accordingly) and special-casing `"Reminded recently"` in the single-rater
  toast. Confirmed the Links & Tracking per-rater status view itself -
  documented here as the legitimate admin-side exemption to the anonymity
  rule - was not touched by this build; it still shows real response status
  to the administrator, correctly distinct from the leader-side restriction.
- **Mobile**: swept ~360px, ~430px, ~600px, and desktop against the live
  local app (Streamlit 1.60.0 via `.venv_test_1_60`, not the system 1.53.1 -
  see the environment gotchas section) for both Overview and Nominate
  Raters. Nominate Raters' list - the highest-risk element per the redesign
  doc - genuinely switches to stacked cards with visible field labels below
  700px, verified by screenshot at all three widths, not assumed from the
  CSS alone. ONE REAL BUG FOUND AND FIXED here too: `.cp-field-label`
  (Name/Email/Category/Status) had no default `display:none` for desktop,
  so the labels appeared inline next to every value on desktop too
  ("NameMichael Stocks") - the mobile-only media query rule set the label's
  font styling but never explicitly restored `display:block`, so once a
  base `display:none` was added it also needed adding to the mobile
  override, or the labels would have stayed hidden at every width. Both
  fixed together; re-verified live after the fix at both a desktop and a
  360px width.
- **Local dev environment note**: `.claude/launch.json` gained a second
  config, `compass-360-1.60`, pointed at `.venv_test_1_60`'s `python3 -m
  streamlit` (not the venv's own `streamlit` executable - that wrapper
  script failed with a `getcwd`/sandbox permission error specific to this
  environment, `-m streamlit` avoids it entirely). Use this config, not
  `compass-360-local` (system Streamlit, 1.53.1), for any future work
  touching this file's widget-adjacent CSS - same reasoning as the existing
  environment-gotchas entry for `.venv_test_1_60`.
- **NOT verified**: real email delivery (local SMTP was intentionally fake
  for the reminder-accuracy test above); the live deployed sandbox (this
  was local-only, matching the pattern for prior UI work in this project -
  worth a live pass after this deploys, the same way the mobile rating-
  scale and button-contrast work were later confirmed live).

### Leader Portal Rebuild: Rendering & Navigation Bug Audit — FIXED 2026-08-26
Ten items found via live screenshot review of the deployed rebuild. All
fixed and re-verified live (screenshots, not just code reading) against
`leader_portal.py` locally on Streamlit 1.60.0. Two of the ten turned out
to be genuinely new bugs (not present-but-unverified) introduced by the
rebuild itself, worth knowing about if this pattern recurs elsewhere:

- **Icons (item 1)**: the status-card checkmark/clock and the failed-
  invitation warning triangle were raw HTML entities (`&#10003;`, `&#128340;`,
  `&#9888;`), not the Material Symbols set the rest of the app uses via
  Streamlit's `:material/name:` shortcode. Added `_icon(name, size, color)`,
  which renders `<span style="font-family:'Material Symbols Rounded'">name
  </span>` for use inside raw HTML - confirmed live that Streamlit already
  loads that font globally (it's how this file's own Edit button icon
  renders), so a plain span naming the icon works anywhere on the page, not
  just inside Streamlit's own widget markup. The CSV-upload toggle's 📄
  emoji was dropped in favour of the button's own `icon=` parameter instead.
  REAL BUG FOUND WHILE FIXING THIS: the first version used double quotes for
  the CSS font-family value inside an already-double-quoted HTML `style="..."`
  attribute, which terminates the attribute early - confirmed live via
  computed style (the browser had parsed it as `style="font-family:"` plus
  two bogus boolean attributes, `material=""` and `symbols=""`, so the icon
  rendered as the literal word "check"). Fixed with single quotes around the
  font name.
- **"Send pending invitations" invisible text (item 2)**: only reproduced in
  the button's ENABLED state (a leader with something actually pending) -
  the disabled/grey state was already legible, which is why this wasn't
  caught in the original build's verification pass. REAL BUG, confirmed live
  via computed style: `button{color:#FFFFFF !important}` doesn't win against
  Streamlit's own colour set directly on the inner `<p>` label (inheritance
  always loses to an explicit rule on the element itself, `!important` or
  not - same root cause as an already-documented fix elsewhere in this app,
  the segmented-control button styling in `app.py`). Fixed the same way that
  fix does it: also target `button *` explicitly, not just `button`, across
  all three button namespaces (primary/secondary/ghost) and their disabled
  states.
- **Stats strip and Full 360 description (items 3, 4, 7)**: NOT a static
  placeholder - `_progress_stats_safe` already switched between real numbers
  and a vague fallback correctly, confirmed live in three states (real
  numbers at 11/13, vague "Responses are coming in" when gated at
  outstanding==1, real zeros at total==0). The one genuine fix: total==0
  used to return the SAME vague-fallback path as the anonymity gate,
  showing "You haven't nominated any raters yet." instead of a 0/0/0%/0
  strip - there is nothing to protect at zero raters, so this was an
  over-broad reuse of the gating logic, not a privacy requirement. Split
  `_progress_stats_safe` so total==0 is its own safe=True branch with real
  zeros plus a short caption ("Nominate your raters to start tracking
  responses."), while keeping the genuine anonymity gate (total <
  ANONYMITY_THRESHOLD, or outstanding == 1) as the one deliberate exception
  where numbers still don't render - explained plainly here because the
  original ask, read literally, would have removed that protection, and it
  is a documented, intentional hard floor (CLAUDE.md section 4), not a bug.
- **Item 8 (empty rings at zero)**: confirmed correct as-is, no change -
  matches the human's own note that this is expected behaviour, not a
  rendering failure.
- **Send Reminders spacing (item 5)**: `margin-top` on the "Your progress"
  label's own HTML only pushed that column's content down - the Send
  Reminders button, a real widget in the neighbouring column with no
  equivalent margin, stayed flush against the category cards above it,
  visibly squashed on desktop. Confirmed via the human's own observation
  that mobile was already fine (columns stack there with natural gaps) -
  fixed by wrapping both columns in one `st.container(key="cp_progress_row")`
  and moving the margin to that container, so it applies evenly to the row
  as a whole rather than to one column's inner content.
- **Guide-card alignment (item 6)**: the "Who should you nominate?" 4-column
  text sat inside the guide card's own 26px side padding, while the rater-
  category cards below it have no such wrapper and sit directly in the page
  flow - different available width, different starting X position, so no
  possible column-count match could align them. Fixed by cancelling the
  card's padding for the list row specifically (`margin: 0 -26px`) and
  matching the category grid's own 18px gap (was 16px), so both grids
  compute identical column tracks against the identical width. Restored on
  mobile, where the alignment requirement no longer applies (single column)
  and flush-to-border text would look cramped.
- **Navigation opening new tabs (item 9, "most important")**: root-caused
  live, not assumed - inspecting the actual rendered DOM showed Streamlit's
  own markdown renderer force-injects `target="_blank" rel="noopener
  noreferrer"` onto EVERY `<a>` tag rendered via `unsafe_allow_html`, even a
  plain same-origin query-string href; nothing in this file's own source set
  that attribute. A `<script>`-tag workaround (strip the attribute, or
  attach a same-tab click handler) was tried and confirmed NOT to work
  either - script tags never execute inside `unsafe_allow_html` content,
  standard browser behaviour for anything inserted via innerHTML, not a
  Streamlit-specific bug. FIX: stopped using `<a>` tags for in-app
  navigation entirely. Added `_go_to_view(view)` (sets `st.query_params
  ['view']` and calls `st.rerun()`) and converted every nav control - the
  three topbar links, "+ Add a rater", "Open full guidelines" - to real
  `st.button()` calls wired to it, styled via container-key CSS to read as
  plain links/buttons rather than boxed Streamlit buttons. This meant
  rebuilding `_render_portal_topbar` around real `st.columns` (brand / nav /
  account) instead of one raw HTML bar with an embedded `<nav>`. Verified
  live end to end: `tabs_context` checked before and after every click
  across the full flow named in the acceptance checks (Overview → Nominate
  Raters → add a rater → Overview again, plus a category-card link) - tab
  count never changed. Multi-tab session-state risk (also asked about):
  not applicable any more, since there is no longer any code path that can
  open a second tab against the same portal token in the first place.
- **Category cards not clickable (item 10)**: added a real "→ Nominate"
  `st.button()` under each card (same column, pulled up flush with
  `margin-top:-9px` so it reads as part of the card, not a stray control
  below it), wired to the same `_go_to_view('nominate')`. Deliberately NOT
  deep-linked to pre-select that category in the add-rater form - the
  relationship dropdown has no default on purpose (`render_portal_nominate`'s
  own docstring: a leftover selection once caused a leader to add too many
  Bosses), and pre-filling a category would undo that already-reasoned
  safety choice. A plain link to Nominate Raters is the correct scope here,
  not a corner cut for time, so this wasn't attempted.
- **Mobile re-swept 360/430/600px + desktop** on Overview and Nominate
  Raters after all of the above, specifically checking the new real-button
  topbar (Streamlit's own column-stacking handles it; nav items stack
  vertically with normal spacing, no overlap) and the new per-card
  "Nominate" buttons (attach cleanly to the bottom of each stacked card).
  No regressions found against the sweep already confirmed in the prior
  build entry above.
- Test leaders/raters and the temporary `.streamlit/secrets.toml` used to
  reach the enabled-button and zero-state cases were all removed after
  verification, same discipline as the original build pass.

### Leader Portal: Amendments + Begin Here/Help page — DONE 2026-08-26
A bundled follow-up covering seven numbered items plus a new Begin Here
page and its nav link, all verified live (screenshots and computed-style
inspection, not code review alone), several with real bugs found only
once actually rendered.

- **Item 1, read-only category cards on Nominate Raters**: `_render_
  category_cards_row(rater_counts, clickable)` extracted as a shared
  helper between Overview and Nominate Raters, so both stay wired to the
  identical rendering path rather than two copies drifting apart. The
  Nominate Raters copy passes `clickable=False` - no "Nominate" button,
  since a self-referential link back to the page you're already on adds
  nothing. Placed above "Add a rater", matching the ask.
- **Item 2, Nominate button overlapping the card's accent bar**: the
  previous version pulled the button flush against the card's bottom edge
  with matching corner radius, sized to the exact same column width as the
  card above - which meant its own left edge sat exactly where the card's
  4px accent-bar `::before` sits, reading as bleeding into it. Fixed by
  dropping the flush/joined treatment and reusing the SAME `cp_secondary_`
  button styling already used for "Open full guidelines" elsewhere
  (white fill, green border/text, fully rounded), with ordinary positive
  spacing (`margin-top:10px`) below the card instead of overlapping it.
- **Item 3, guide-card alignment - genuinely fixed this time, with the
  full story of why it kept failing**: the human explicitly asked not to
  assume a previous attempt worked, and it hadn't. Three attempts, in
  order, each diagnosed live before moving to the next:
  1. First "fix" (from the previous session) used `.cp-guide-list{gap:18px}`
     to match what the category-card grid used to use - but that grid had
     since become real `st.columns(4, gap="medium")` for the clickable-card
     requirement, and Streamlit's actual "medium" gap turned out to be
     32px, confirmed via `getBoundingClientRect`. Converting the guide row
     to the same `st.columns(4, gap="medium")` mechanism fixed the gap
     mismatch but not the alignment - a residual growing drift (1/13/26/40px
     across the four columns) remained.
  2. Second attempt added a negative margin (`-26px`, then `-27px` to also
     clear a 1px border) to cancel the guide card's own side padding, on
     the theory that the row needed to escape its parent's inset to match
     the un-padded cards below. Measured live: the row's own width never
     changed (688px vs the card row's 742px, no matter the margin value).
     Root cause: the row is a flex item inside Streamlit's own
     `stVerticalBlock` (`display:flex; flex-grow:1; flex-basis:0%`), and a
     flex item's main-axis size is computed by the flex algorithm against
     its parent's content-box BEFORE margins apply - a negative margin on
     a flex item shifts/overlaps visually but does not retroactively
     enlarge the box `st.columns()` inside it was actually sized against,
     unlike a plain block-level div where this trick reliably works
     elsewhere in this file (e.g. the topbar).
  3. Actual fix: stopped trying to escape the padding after the fact.
     `cp_guide_card`'s own padding is now vertical-only (`padding:24px 0`);
     the heading row (title + "Open full guidelines") gets its own
     horizontal inset via a new `cp_guide_heading_row` wrapper instead, and
     the item row now shares the literal same un-padded width as the
     category cards below with nothing to cancel. Re-verified live:
     `getBoundingClientRect` on all four column pairs matched within 1px
     (sub-pixel rounding), and a screenshot confirms "Boss/Peers/Direct
     Reports/Others" sit directly above their matching cards.
  - Side effect caught in the same pass: `.cp-step-body b{display:block}`
    (Begin Here, unrelated to this item but the same category of bug) was
    a descendant selector that also matched the `<b>` nested inside
    `.cp-sub-note`, forcing "Upload a CSV instead" onto its own isolated
    bold line instead of flowing inline mid-sentence. Fixed by scoping to
    `.cp-step-body > b` (direct child only) and giving `.cp-sub-note b` its
    own explicit `display:inline`.
- **Items 4 and 5, table header alignment and the missing Edit label**:
  `.cp-list-head` now sets `text-align:left` explicitly (no single stray
  rule was found causing the centred look, but the mismatch was real
  regardless, so it's no longer left to default behaviour). The Edit
  column had no header at all - added via a matching `st.columns([9, 1])`
  split at the header row, same ratio the content rows already use for
  their Edit button column, so "EDIT" lands directly above the actual
  pencil icons.
- **Item 6, Begin Here / Help page**: new `render_portal_begin_here()`,
  content taken from `assets/Bentley Compass 360 — Begin Here Concept.html`
  (supplied as binding reference material) - 5 numbered how-to steps, a
  divider, and 5 "Good to know" cards in the mockup's order (editing
  mistakes and adding-later cards first, per the human's note that these
  are the two most likely practical questions after a first session).
  "Help" added as a 4th topbar nav item, which - because all three
  existing screens already render through the same shared
  `_render_portal_topbar` - automatically appears on Overview, Nominate
  Raters, and Guidelines too, satisfying "the other pages already built
  should also carry the link to the help page" with no separate change
  needed there.
  - ONE MOCKUP DEVIATION, same reasoning as the earlier one for category
    cards: the "See Guidelines" reference inside the category-minimums
    card is a real `st.button()` (`_go_to_view('guidelines')`), not the
    mockup's inline `<a href="#">` - a raw anchor there would have
    reintroduced the exact new-tab bug item 9 (below) exists to fix,
    since Streamlit force-adds `target="_blank"` to markdown-rendered
    links regardless of source. Rendered as a small link-styled control
    after the card's text rather than inline mid-sentence, since a
    Streamlit button can't sit inside a markdown paragraph's own flow.
  - REAL BUG FOUND ADDING THE 4TH NAV ITEM: at this project's actual
    "desktop" preset width (902px, confirmed via `window.innerWidth` -
    narrower than it sounds, and specifically the width used throughout
    this project's own desktop testing), four nav buttons at the original
    font-size/padding/column-ratio wrapped their own labels onto two lines
    ("Guideline" / "s") rather than fitting on one. Fixed by widening the
    nav column's share of the topbar (`[2.1, 4.0, 2.1]` → `[1.6, 5.4,
    1.6]`), shrinking nav font-size slightly (14.5px → 13.5px) and its own
    padding, adding `white-space:nowrap` so a genuinely-too-narrow future
    case fails as a clipped label rather than a silent wrap, and using
    `gap="small"` between nav columns. Re-verified live at exactly 902px
    (all four items on one line, real spacing) and at 1500px (unchanged).
- **Item 7, failed re-send after an email correction was invisible**: the
  diagnosis-only finding from the prior conversation, now actually fixed.
  `get_raters_pending_invitation` and `get_failed_invitation_emails` both
  used to key off "has this rater EVER had a successful send" - so a rater
  invited successfully once, then corrected, whose re-send to the
  corrected address then failed, stayed permanently invisible to both
  checks (their one historical success excluded them forever). Both
  queries now join against a `MAX(id)`-per-`rater_id` subquery over
  `email_log` (id is chronological for this table) so they check only the
  LATEST invitation attempt, not every attempt ever made. A failed re-send
  now correctly flips status back to "Not yet sent" AND surfaces the same
  warning icon a first-time failure gets - both are the right combined
  signal ("this needs your attention, here's why"), not just the icon
  alone.
  - VERIFIED LIVE END TO END, exactly as the acceptance check asked (not
    just code inspection): seeded a rater with a genuine prior successful
    invitation log entry, corrected their email through the real Edit UI
    with a fake local SMTP target configured (so the automatic re-send
    genuinely fires and genuinely fails), and confirmed via a fresh page
    load that the row now shows the warning triangle AND "Not yet sent",
    with the bottom send-bar correctly counting them as 1 pending. Database
    checked directly before relying on the UI screenshot, not assumed from
    it.
- **Confirmed working, no action needed**: item 9 from the prior audit
  (same-tab navigation) - re-verified via `tabs_context` across every new
  navigation path added in this pass (Begin Here's CTA and its Guidelines
  link, the new nav item itself), tab count never changed.
- **Full mobile re-sweep** (360/430/600px + desktop) across Overview,
  Nominate Raters, and the new Begin Here page after all of the above - no
  regressions against the layout already confirmed in the prior two build
  passes.
- Test raters/leaders and the temporary `.streamlit/secrets.toml` used for
  the item 7 live test were removed after verification; local dev DB
  confirmed back at its 13-rater baseline before finishing.

### Leader Portal: Two Layout Fixes Found in Live Review — FIXED 2026-08-27
Two regressions found via live screenshot review after the previous deploy,
plus a third found mid-fix while re-screenshotting the first one (fixed
under the human's standing instruction: fix anything else spotted while
verifying, not just what was asked). All three needed a second (or third)
pass beyond the first attempt already in the file - re-verifying computed
values live is what caught it, code review alone would have looked correct
at every stage.

- **Category cards not actually equal height, despite the CSS already
  claiming to fix this**: the `.cp-card{height:100%}` rule (added in the
  prior "Rendering & Navigation Bug Audit" pass, with its own confident
  comment explaining the fix) turned out not to work. Confirmed live via a
  `getComputedStyle` chain walk: `height:100%` only resolves against the
  nearest ancestor with a DEFINITE (non-auto) height, and Streamlit wraps
  each card's raw-HTML markdown in its own chain of wrapper divs -
  `stElementContainer` > `stMarkdown` > an unnamed flex div > `stMarkdown-
  Container` - every one of which is `height:auto`, sized to its own
  content, except the true per-column `stVerticalBlock` two levels further
  out, which correctly stretches to match its tallest sibling (Streamlit's
  own `align-items:stretch` on the row). Because of the auto-height links
  in between, `.cp-card`'s `height:100%` was resolving against its own
  auto-height immediate parent and collapsing back to its own content
  height - the four cards measured 264/244/264/244px at 902px width, not
  equal, and the previous fix's own height:100% rule had silently never
  been doing anything. Fixed by explicitly giving every wrapper level in
  that chain `height:100%` too (targeted by their stable `data-testid`
  attributes plus `:has(.cp-card)`, not by Streamlit's hashed emotion
  classes), so the definite height on the real stretched column actually
  propagates down to `.cp-card`. VERIFIED LIVE with real getBoundingClientRect
  measurements (not just a screenshot) at 902px, 1000px (the exact width the
  bug was originally reproduced at), 768px, and confirmed both usages of the
  shared `_render_category_cards_row` helper (Overview's clickable cards and
  Nominate Raters' read-only ones) - all four cards measured byte-identical
  height at every width. Below 768px the cards stack to a single column
  (no equal-height question applies there), confirmed unaffected at 600/430/
  360px.
- **Topbar not spanning full width at mobile/tablet widths, and the
  full-bleed CSS fix that looked complete didn't take effect either**: the
  full-bleed breakout (`position:relative;left:50%;width:100vw;margin-left:
  -50vw`) - the standard, correct pattern for escaping a padded parent - was
  already in the file from an earlier attempt in this same task, replacing
  an even earlier negative-margin version that measured provably wrong
  (missing exactly 32px on the right at every width tested, root-caused to
  the same "flex item's own width is computed before its margins apply"
  mechanism that broke the guide-card alignment fix in the prior session -
  a negative margin on a flex item shifts one edge but can't retroactively
  enlarge the box). But even the full-bleed version measured 328px wide at
  360px viewport, not 360px, when re-checked live after a genuine server
  restart (not just a page reload - Streamlit's file watcher does not
  auto-rerun on save in this dev setup, so a page reload alone was serving
  STALE CSS from before the edit; confirmed by reading the live `<style>`
  tag's actual text content and finding the OLD rule still there after a
  plain reload, only fixed by stopping and restarting the whole server
  process). Once genuinely on the new CSS, `width:100vw !important` still
  computed to 328px, not 360px - traced to a SEPARATE, unrelated property:
  Streamlit's own `.st-emotion-cache-18kf3ut{width:100%;max-width:100%;...}`
  rule (non-`!important`, but on the SAME element) sets `max-width:100%`,
  and `max-width` always caps a used width regardless of what `width` itself
  says, `!important` on `width` alone doesn't touch a separate `max-width`
  declaration. Fixed by adding `max-width:100vw !important` alongside the
  existing `width:100vw !important`. VERIFIED LIVE with real
  `getBoundingClientRect` measurements (not just visual screenshots, which
  had misleadingly looked full-width at a glance even when 32px short) at
  the full required sweep - 360px, 430px, 600px, 768px (tablet, where the
  bug was first spotted), and 902px (the width the 4th nav item's wrapping
  fix was tuned against) - confirming `left:0, right:<viewport>, width:
  <viewport>` exactly at every one, with no regression to the nav-item
  layout at 902px.
- **THIRD ISSUE FOUND WHILE SCREENSHOTTING THE FIX ABOVE, not part of the
  original report but fixed under the same authority - the status pill
  inside each category card ("Requirement met" / "Nominated" / "N more
  needed") sat at inconsistent heights within a row**: caught live, not in
  the original two-item brief, while screenshotting the card-height fix at
  1000px - two cards with 1-line descriptions had their pill 16px higher
  than the two with 2-line descriptions, even though the CARDS themselves
  were already confirmed equal height. Root cause, found in three layers,
  each only visible after fixing the one before it: `.cp-card-foot`'s
  `margin-top:auto` correctly anchors the pill to the bottom of the
  (equal-height) card, but only when every card's content ABOVE the pill
  needs the same amount of room - it doesn't reserve space, it just
  distributes whatever's left over, so a card with more text above pushes
  the pill down further than a neighbour with less. Three independent
  places this showed up, swept across the full multi-column range down to
  where it collapses to a single stacked column (~630-640px):
  1. The description paragraph (`.cp-req`) wraps to a different number of
     lines per category at a given width (e.g. at 1000px, Boss/Others wrap
     to 2 lines, Peers/Direct Reports stay on 1).
  2. Fixing (1) alone still left one width (~650px) misaligned - the
     CATEGORY LABEL ABOVE it ("LINE MANAGER" vs "COLLEAGUES") *also* wraps
     to 2 lines independently, and even the h3 TITLE below the ring
     ("Line Manager"/"Direct Reports" wrap, "Peers"/"Others" don't) - a
     second and third source of the identical problem, only surfaced by
     re-measuring after the first attempt still didn't fully align.
  3. Fixing all three of those still left ONE card off at 650px - the pill
     TEXT ITSELF wraps to 2 lines when its own label is long enough
     ("Requirement met" vs "Nominated"), growing the foot container by a
     different amount per card.
  Fixed by reserving the worst-case 2-line (3-line for the description)
  height on each of the four elements via `min-height`, rather than
  chasing the auto-margin math - `.cp-cat-label`, `.cp-card h3`, and
  `.cp-req` all reserve enough room that neither the actual wrap count nor
  the viewport width matters any more, and `.cp-card-foot` (not the pill
  itself) reserves the room for a 2-line pill so the visible pill stays its
  normal compact size and just centres within the taller box - reserving
  on the pill directly was tried first and rejected, it made every pill
  look like an oversized button even on a single line. VERIFIED LIVE with
  real `getBoundingClientRect` measurements of `footTop` (not just
  screenshots) at 1000px, 902px, 768px, and 650px (the worst case that
  exposed all three layers at once) - all four cards land on the identical
  pill offset at every one, on both the clickable Overview cards and the
  read-only Nominate Raters ones. Also re-confirmed clean at 600/430/360px
  (single column - the equal-height/equal-offset question doesn't apply
  there, but nothing regressed).
- **Topbar nav collision at ~640-750px — FIXED 2026-08-27, same session,
  restructured rather than patched**: flagged above as a different scale
  of problem needing a real design decision, not a self-contained CSS
  reservation. The human's own suggestion (asked as a question, not an
  instruction) was the actual fix: split the single brand/nav/account row
  into TWO rows - row 1 brand (left) + account (right), row 2 nav alone,
  full width. This removes the constraint rather than working around it:
  nav no longer shares its row with brand+account (previously only the
  middle 5.4/8.6 of the width), so it gets roughly 1.6x the room at any
  given viewport and never needs to compress in the 640-750px gap between
  Streamlit's native column-stacking breakpoint and the width the old
  single-row nav was tuned against. `_render_portal_topbar` in
  `leader_portal.py` rebuilt around this: row 1 (`cp_topbar_row1`) is
  plain flex HTML with `justify-content:space-between`, not st.columns -
  neither brand nor account is interactive, so there was never a need for
  real Streamlit columns there. Row 2 (`cp_topbar_row2`) keeps the
  existing real `st.columns(4)` + `st.button()` nav (still needs real
  widgets for same-tab navigation), now spanning the full bar width, with
  a subtle `border-top` divider between the two rows.
  - BONUS FIX THAT CAME FREE: the brand text wrapping to 3 lines at
    768-902px (flagged, not fixed, in the pill-alignment entry above) is
    also gone - it no longer competes with nav+account for row width, so
    it now renders on one line at every width tested.
  - Row 1 needed its OWN mobile stacking rule (`flex-direction:column`
    below 700px) since it's raw HTML, not st.columns - Streamlit only
    auto-stacks its own native column widgets, and row 2's nav still gets
    that for free since it's still real `st.columns`.
  - VERIFIED LIVE, not just at the four standard sweep points but
    specifically at the widths that exposed the original bug: 650px (the
    original repro width) and 690px (row 1 stacked per the new mobile
    rule, row 2 still a single Streamlit-native row since its own
    ~640px native threshold hadn't hit yet) - both show a clean, fully
    legible nav row with a real 16px gap between every button
    (`getBoundingClientRect` confirmed, not just visual), no collision.
    Re-swept 360/430/600/768/902px afterward to confirm no regression -
    topbar still spans full viewport width at every one (confirmed via
    `getBoundingClientRect`, not just screenshot), the 902px nav-wrapping
    fix from the prior session is untouched, and the pill-alignment fix
    above is unaffected (re-checked live on Nominate Raters after the
    topbar change). Also checked the one OTHER code path through this
    same function - the consent gate's `show_nav=False` call, tested
    against a real leader who hadn't consented yet - renders correctly as
    a single un-divided row with no account block, no error.
  - Confirmed same-tab navigation still holds after the restructure
    (`tabs_context` before/after a real click on "Nominate Raters" - tab
    count unchanged), since row 2's nav buttons are functionally the same
    `st.button()` + `_go_to_view` mechanism as before, just relocated.
- Local dev server restarted from a clean state before each re-measurement
  in this task, specifically because of the stale-CSS trap found above; no
  test data was created or needed for any of these fixes, so there was
  nothing to clean up afterward.

### Begin Here: the one-time onboarding gate was never actually built — FIXED 2026-08-27
When Begin Here/Help was originally built (see the "Amendments + Begin
Here/Help page" section above), the spec called for it to show once,
automatically, before the leader reaches the portal proper - similar to
the consent gate - and be reachable afterwards via Help in the nav. Only
the second half got built: `render_portal_begin_here()` existed and Help
worked, but nothing ever forced it to show automatically. Caught when the
human asked directly whether it was actually behaving that way, having
noticed it wasn't while clicking through screenshots for other work -
confirmed by reading the router (`render_leader_portal` in
`leader_portal.py`), which only ever gated on `consent_given`, with no
equivalent check for Begin Here anywhere, and no DB column to back one.

- Gate order, per the human's explicit instruction: consent first, then
  Begin Here - "the consent one is more important so should come first."
- New column `leaders.begin_here_seen_at` (`_safe_add_column`, same
  pattern as `consent_given_at`), and `db.set_leader_begin_here_seen
  (leader_id)`, guarded `WHERE begin_here_seen_at IS NULL` so a second
  call (e.g. from a legacy leader who existed before this column did)
  can't clobber the original first-seen timestamp.
- `render_leader_portal` now checks it right after the consent check,
  before reading the `view` query param at all - deliberately
  unconditional on which view the leader was actually headed for, same
  reasoning as consent: a leader landing on a deep link they'd never
  visited before still needs the onboarding first.
- Marked seen the moment it's SHOWN, not gated behind a specific button
  click the way consent is. Consent has an affirmative checkbox because
  there's something to actually agree to; Begin Here is pure information
  with nothing to agree to, so "shown once" is the whole requirement -
  marking on display, not on a particular exit action, also means the
  requirement is met however the leader leaves the page (the CTA, or any
  other nav item), not only if they happen to click the one button meant
  for it.
- `render_portal_begin_here()` itself is completely unchanged - the gate
  reuses it as-is (topbar shown with full nav, `active_view='help'`, same
  content, same "Go to Overview" CTA at the bottom) rather than
  duplicating or forking it, so the gate and the on-demand Help page can
  never drift apart from each other.
- VERIFIED LIVE end to end, DB checked directly rather than inferred from
  the UI alone: loaded leader 1's portal (already consented, brand new
  column so `begin_here_seen_at` was NULL) - the gate rendered
  automatically with no `?view=` param needed to trigger it, DB then
  showed a real timestamp. Reloaded the same portal URL fresh (a genuinely
  new page load, not a same-session rerun) - went straight to Overview,
  proving the skip is backed by the database and not just session state.
  Confirmed Help in the nav still reaches the identical content on demand,
  same tab. Separately verified the ORDER against a leader who hadn't
  consented yet (Jordan Reeves): consent gate showed first as expected:
  checked the box, clicked Continue, and the Begin Here gate appeared
  immediately after, in the same page load - the full two-gate sequence
  working end to end, not just each gate tested in isolation. Both test
  leaders' `consent_given`/`begin_here_seen_at` values were reset to their
  original state afterward.

### Logic Check: Nominations Beyond the "Suggested" Target — CONFIRMED + ONE REAL BUG FIXED 2026-08-27
Human's ask: "suggested 5" for Peers/Direct Reports/Others implies a
target, not a ceiling - confirm nothing silently caps a leader at 5
who wants to nominate more, and if the ring/chip breaks past that
number, fix it. Explicitly diagnosis-first: "don't assume either the
cap or the ring bug exists without checking."

- **Part 1, hidden cap - CONFIRMED NOT PRESENT, no fix needed.** Read
  every enforcement point: the add-rater form's `at_max` check, CSV
  import's `_parse_rater_csv`, and the nomination-edit validator
  `_validate_nomination_change` all check against `RATER_REQUIREMENTS
  [cat]['max']` (10 for Peers/DRs/Others), never `['suggested']` (5).
  VERIFIED LIVE, not just read: constructed a real test leader with 5
  Peers already nominated, added a 6th through the actual browser form
  (typed name/email, selected the category, clicked +Add) - not
  blocked, "+Add" was never disabled. Separately called the real
  `_parse_rater_csv` function directly (not a reimplementation) with 6
  existing + 2 more via CSV - both imported clean, zero problems. Then,
  as a sanity check that the REAL max (10) still works correctly and
  nothing in this check broke it: called the same function with 6
  existing + 6 more (would total 12) - correctly blocked starting at
  the row that would exceed 10, with the right message naming the right
  number. System behaves exactly as documented: no cap at "suggested",
  real cap only at "max", consistent across every entry point.
- **Part 2, ring denominator - CONFIRMED, REAL BUG, FIXED.** `_category_
  card_html`'s `target` used to be hardcoded to the suggested/min_if_any/
  min number alone, with no regard for whether the leader had actually
  gone past it. `_ring_dashoffset` already clamped the ARC itself to a
  full circle past 100%, so the ring never visually overflowed - but the
  LABEL kept the stale target. VERIFIED LIVE with the constructed 6-Peer
  leader: before the fix this would have read "6/5"; after, the ring
  renders as a genuinely full circle labelled "6/6", confirmed via
  screenshot on both Overview and Nominate Raters (they share the same
  `_render_category_cards_row` helper). Fixed via `target = max(base_
  target, count)` - whichever is larger wins, so the denominator can
  never under-report the actual count. SIDE EFFECT, not asked for but a
  strict improvement from the same root cause: Boss (suggested=1, but a
  real hard max of 2) had the identical mislabelling at its own genuine
  ceiling - 2 Bosses would have shown "2/1". Now correctly shows "2/2".
  Not separately verified live (no live test leader had 2 Bosses at the
  time), but it's the same code path, same fix, same guarantee.
- **Part 3, status chip - CONFIRMED, no fix needed.** Chip logic reads
  `min_if_any` and `req['min']` directly, never `target` or `count`
  against `suggested` - there is no upper-bound branch that could flip
  "Requirement met" to a warning state as count grows. VERIFIED LIVE:
  the 6-Peer test leader's Peers chip read "Requirement met" throughout,
  same tone/colour as at 5, no regression.
- **Part 4, Others copy - contradiction fixed across all three surfaces,
  live warning reworded.** Every upfront Others surface ("Add at least 3
  if you use this category") changed to "Minimum 3, ideally 4 or 5 if
  you have them" - `CATEGORY_REQ_TEXT['Others']` (the Overview/Nominate
  cards) and `GUIDELINE_CATEGORIES`'s Others `badge` (shortened to
  "Minimum 3, ideally 4 or 5" for the badge's terser style). Begin
  Here's "Why the category minimums exist" card was checked and, per the
  task's own conditional, left untouched - it never names a specific
  number for Others, only speaks generically about "a category of one
  or two people". VERIFIED LIVE on all three surfaces via screenshot
  (category card, Guidelines page). The live in-app warning at exactly
  3 nominated (`_render_nomination_warnings`) now branches on `cat ==
  'Others'`: Others gets new wording opening "as mentioned when you were
  adding raters" so it reads as reinforcement, not a fresh catch; Peers/
  DRs keep their original wording verbatim (their upfront copy already
  states the buffer, so there was never a contradiction to fix there).
  VERIFIED LIVE side by side: constructed a leader with exactly 3 Others
  AND exactly 3 Direct Reports at once, loaded Nominate Raters, and
  confirmed both warnings render together with the expected, different
  wording each - Direct Reports' text unchanged from before this task,
  Others' text now reinforcing. Ring target for Others changed
  independently: new `RATER_REQUIREMENTS['Others']['ring_target'] = 5`,
  consumed by the same `target = max(base_target, count)` fix from Part
  2 via `req.get('ring_target') or req['suggested'] or ...` - gives a
  full ring at 5 (visual consistency with the other three categories)
  without changing the copy's own "4 or 5" range, and without touching
  the chip logic at all (chip reads `min_if_any` directly, confirmed
  unaffected). VERIFIED LIVE: Others ring read "3/5" at 3 nominated
  (proportionate fill, not "3/3"), and still shows a bare "0" with no
  fraction at zero nominated (the zero-state display condition was left
  untouched - only the target NUMBER changed, not when a fraction shows
  at all).
- Test leader (id 39, "Ring Test Leader") and all its raters/email_log
  rows were deleted entirely after verification, not just reset - it
  was created solely for this test, unlike leader 1/Jordan Reeves who
  are pre-existing baseline fixtures other tests rely on. Leader 1's
  13-rater baseline confirmed unchanged afterward.

### Diagnose: Is the Nomination Cap Deliberate, and Can the Anonymity Fold Ever Collide With It? — DIAGNOSED 2026-08-27, NOTHING CHANGED
Three questions, diagnosis only, no fix or copy change made - none was
needed. Findings below are load-bearing for any future Guidelines
copy work around the nomination cap, so recorded here rather than
just answered in chat and lost.

- **Is 10 deliberate or arbitrary?** ARBITRARY, with high confidence.
  Traced `RATER_REQUIREMENTS['max']` back through the entire git
  history: the very first commit (`2bcbf35`, a bulk "Add files via
  upload" with no authored reasoning) already had `max: 10` for
  Peers/DRs/Others, with no comment anywhere near it. Every commit
  since that has touched this dict - most significantly `1737e2d`
  ("Rework instrument, anonymity handling..."), which deliberately
  changed DRs from optional (`min: 0`) to required (`min: 3`) and added
  `min_if_any` for Others, both with real documented anonymity
  reasoning - left `max: 10` completely untouched. No commit message,
  code comment, or prior CLAUDE.md entry has ever explained why 10
  specifically. Contrast with `min` (3, tied directly to
  `ANONYMITY_THRESHOLD`) and `suggested` (5, reasoned about explicitly
  in the "Nominations Beyond the 'Suggested' Target" entry above): both
  have a real, traceable rationale; `max` has never had one, in this
  system's entire history. Reads as a generous-but-arbitrary guard
  rail (large enough nobody realistic hits it, small enough to catch a
  fat-fingered CSV import), not a considered recommendation. NOT worth
  publicising in Guidelines as "maximum 10" in a way that implies a
  real, deliberated ceiling - if it's surfaced at all, it should read
  as a soft technical backstop, not a number anyone chose for a reason.
- **Does Others share the same cap as Peers/DRs?** YES, confirmed
  directly from the dict, not assumed: `Peers: max 10`, `DRs: max 10`,
  `Others: max 10` - identical, and has been since the very first
  commit. Boss is the sole outlier at `max: 2`, which - unlike the
  other three - IS explained everywhere it appears ("max 2 if matrix
  reporting"), a genuinely different, deliberate, already-surfaced
  number.
- **Can the anonymity fold ever collide with the nomination cap?**
  NO - traced and empirically verified, not inferred. `get_leader_
  feedback_data` in `database.py` is PURELY a SELECT + in-memory
  Python aggregation: it reads `raters.relationship` fresh on every
  call and folds via `map_group()`, a pure function whose output only
  ever lives in local variables for that one function call. There is
  no `UPDATE`/`INSERT` touching `raters` anywhere in it - nothing is
  ever physically recategorised in storage. Every score list
  (`item_scores[item_num][mapped_group].append(...)`) and every
  comment list (`comments['keep'].append(...)`) is a plain unbounded
  Python list with `sum()/len()` averaging - no size check, no cap,
  anywhere in the aggregation OR in `report_generator.py`'s table
  rendering (`row[1].text = str(response_counts[group])` - a group
  count is just printed as text, however large).
  - VERIFIED LIVE with the exact scenario the human described:
    constructed a leader with 9 completed Direct Reports and 2
    completed Peers (real `ratings` rows too, DRs scored 4, Peers
    scored 2, so the averaging math had real data to prove itself
    against), 0 Others, then called the REAL `get_leader_feedback_data`
    function directly (not a reimplementation). Result: `response_
    counts['DRs'] = 11` - genuinely exceeding the nomination cap of
    10 - with `hidden_groups: ['Peers']`, `others_fold_target: 'DRs'`,
    and item 1's DRs score correctly computed as 3.6 (the true
    weighted mean of all 11 responses: (9×4 + 2×2)/11 = 3.636…,
    confirming every folded response was actually counted, not
    truncated at some limit). Read `raters.relationship` directly from
    the database immediately after: both Peer rows still said
    `'Peers'`, completely unchanged - the fold never touched storage.
  - Went one step further and fed that exact returned data into the
    REAL `add_response_summary` function from `report_generator.py`
    (not a mock), rendering an actual docx table: "Direct Reports | 11"
    printed cleanly, Total row correctly 11, no crash, no truncation.
  - Confirmed definitively: the nomination cap (data-entry constraint,
    enforced at add/CSV-import time against `raters` as rows are
    created) and the anonymity fold (reporting constraint, computed
    fresh at report-generation time from whatever `raters` currently
    contains) operate on different data at different times and cannot
    interact, let alone collide. A folded group CAN legitimately
    display a number larger than any single category's cap - this is
    normal, safe, and already proven to render correctly.
  - Test leader (id 40, "Fold Test Leader") and all its raters/ratings/
    email_log rows deleted entirely after verification. Leader 1's
    13-rater baseline confirmed unchanged.

### Final Category Guidance Copy — DONE 2026-08-27, two real layout bugs found and fixed along the way
Content-only change, per the human's explicit brief and the diagnostic
findings above: Peers/DRs now read "Minimum 3, suggested 5, up to 10 if
needed"; Others reads "Minimum 3, ideally 4 or 5 if you have them, up
to 10 if needed" - three distinct strings, not a shared template, since
Others deliberately keeps its own softer framing. Boss's copy
("Minimum 1, max 2 if matrix reporting" / "1 required, max 2") is
untouched - confirmed via grep after editing, not just by not touching
it. Applied to `CATEGORY_REQ_TEXT` (Overview/Nominate Raters cards) and
`GUIDELINE_CATEGORIES`'s `badge` field (Guidelines page) - this
supersedes the shortened badge wording from the prior "Nominations
Beyond the 'Suggested' Target" pass; this task's brief explicitly asked
for the exact wording verbatim across all surfaces, not a terser
badge-specific variant. Begin Here checked again and confirmed
unchanged, correctly: it still names no specific numbers for any of
these three categories.

Two real, previously-invisible layout bugs surfaced by lengthening this
copy, both found live (not assumed) and both fixed under the same
screenshot-driven authority as earlier sessions:

- **Category cards (Overview/Nominate): the equal-height/pill-alignment
  fix from two tasks ago silently stopped covering the new worst
  case.** That fix reserved a fixed 58px (3 lines) for `.cp-req`, sized
  against the OLD copy. Others' new, longer text needs up to 5 lines
  (96px) at the same ~630-710px squeeze width the reservation was
  originally tuned against - confirmed via a natural-height probe (an
  off-screen clone of the text at the real column width, since the
  visible element was being silently flex-shrunk below what it actually
  needed, clipping text with no visual overflow indicator). Bumped
  `.cp-req`'s `min-height` to 98px. Re-verified the entire original
  sweep (360/430/600/645/710/768/902px) with `scrollHeight >
  clientHeight` overflow checks at each, not just visual screenshots.
- **Guidelines page: the title+badge header row had no wrapping
  behaviour at all**, and had never needed any before - the old badge
  text always fit beside the title on one line at every width tested.
  At 430px the new, longer Others badge forced the title into an
  unreadable "Ot/he/rs" vertical sliver while the badge itself measured
  past the card's own right edge (confirmed via `getBoundingClientRect`
  comparison, not just eyeballed) despite the card's `overflow:hidden`.
  Fixed in two steps, each addressing a distinct symptom: `flex-wrap:
  wrap` on `.cp-cat-top` let the badge drop to its own line instead of
  fighting the title for space on one row - this alone fixed everything
  down to 430px, but at 360px the badge ALONE, on its own row, was
  still wider than the card, because it was still `white-space:nowrap`
  and had nowhere left to shrink to. Dropped `nowrap` (the default
  `normal` still renders as one line whenever there's room, so nothing
  changed at wider widths) and added `max-width:100%` as a backstop.
  Re-verified at 360/430/768/902px via direct badge-vs-card
  `getBoundingClientRect` comparison plus screenshots - no overflow
  anywhere, and the shorter Boss/Peers/DRs badges at wider widths render
  identically to before (same single-line height, confirmed).

No test data needed creating or cleaning up for this task - all
verification was against the existing sandbox portal_token, reading and
resizing only.

### Category card ring pushed outside its card at ~640-700px — FIXED 2026-08-27, two attempts before the real fix
Found by the human directly in a screenshot from the task above (a width
none of that task's own sweeps happened to land on) - the progress ring
in a category card (label + ring side by side, `.cp-card-top`) was
visibly sitting partly outside the card's right edge at a narrow band of
widths.

- **Root cause, confirmed via `getBoundingClientRect`, not assumed**:
  the ring is a fixed 48px box with `flex-shrink:0` (an SVG ring can't
  usefully shrink), and the category label is sometimes a single
  unbreakable word ("COLLEAGUES", "OPTIONAL") with no space to wrap at,
  so a flex item's default `min-width:auto` stops the label shrinking
  below that word's own width either. At widths where the two items'
  combined natural width exceeded the row's, `justify-content:space-
  between` had no spare space left to remove - it can't create a
  negative gap, so the ring just overflowed with nothing to stop it.
  Reproduced precisely: Peers overflowed at every width from ~640-700px
  (worst case 13.3px past the edge at 645px), Others came within a few
  px without quite crossing.
- **First fix attempt, `flex-wrap` on `.cp-card-top`**: let the ring
  drop to its own line only when it didn't fit beside the label. This
  genuinely stopped the overflow (confirmed, zero overflow across the
  full sweep) but traded it for a DIFFERENT problem, found immediately
  by re-checking wider widths that were previously fine: whether the
  ring wrapped now depended on each card's OWN label text length, not
  the row's width alone - at 768px and 902px, "LINE MANAGER"/
  "COLLEAGUES" wrapped the ring below while "YOUR TEAM"/"OPTIONAL" kept
  it beside the label, so the row of four cards no longer matched each
  other. Confirmed via the same `getBoundingClientRect` measurements,
  not just eyeballed - this was a real regression this fix introduced,
  not a pre-existing issue newly noticed.
- **Actual fix, the human's own suggestion**: stop trying to fit label
  and ring side by side at any width - put the ring on its own line
  below the label ALWAYS, removing the whole category of "does this fit
  today" bug rather than chasing it further. `.cp-card-top` changed from
  a `justify-content:space-between` row to a simple `flex-direction:
  column` stack. Since the ring no longer needs to squeeze beside label
  text at any width, it grew too (48px -> 60px, r 19 -> 24, matching
  `_ring_dashoffset`'s circumference 119.4 -> 150.8 and the SVG markup
  in `_category_card_html`) - bigger and more legible, at the human's
  suggestion once the layout no longer constrained it.
- VERIFIED LIVE at every width in the standard sweep plus the exact
  widths that exposed both the original bug and the flex-wrap
  regression (360/430/600/645/690/768/902px): all four cards now measure
  byte-identical ring position relative to their own card at every
  single width (confirmed via `getBoundingClientRect` diff, not just
  screenshots) - genuinely impossible for the ring to ever be pushed out
  again, since it no longer shares a row with anything that could push
  it. Re-confirmed the pill-alignment fix from two tasks ago still holds
  with the taller card-top (footTop identical across all four cards).
  Checked both usages of the shared card-rendering code (Overview's
  clickable cards, Nominate Raters' read-only ones).
- No test data needed for this fix - verification was against the
  existing sandbox portal_token only.

### Inconsistent Anonymity Gating: Stats Strip vs. Reminder Caption — FIXED 2026-08-27, SUPERSEDED THE SAME DAY
CORRECTED by the entry directly below ("Correction: Remove the Your
Progress Gating Entirely") - the fix documented here (extending the
same suppression to every element) turned out to be built on a flawed
premise: this data was never actually anonymity-sensitive in the first
place, so extending its suppression was consistent but wrong, not
cautious. Left in place below as the historical record of what was
tried and why it wasn't the real fix - the gating described here no
longer exists in the code at all.

Found by the human actually using the rebuilt portal, not hypothetical:
at `outstanding == 1` the "Your Progress" stats strip correctly fell
back to vague text ("Responses are coming in"), but the reminder
caption two inches below it stated the identical fact in plain digits -
"Nudges the 1 who haven't responded yet." One text element on the page
was defeating what another was deliberately hiding.

- **Swept for every other instance, not just the reported one.** Found a
  SECOND real leak in the same feature: `_send_reminders_and_report`
  (the message shown after actually clicking Send Reminders) also
  stated bare counts in every branch - "Reminded 1 rater.", "All 1
  rater still within their 48-hour window...", "1 failed to send...".
  At `outstanding == 1` any of these would have shown "1" just as
  plainly as the caption did. The Full 360 status card (the "X of Y
  responses received" / percentage pill near the top of Overview) was
  checked and confirmed ALREADY correctly gated via the same
  `_progress_stats_safe` call - no change needed there, but see below
  for why it's now wired to the same value as everything else rather
  than merely reaching the same answer independently. Nominate Raters
  was checked too - it renders no response-count text at all (only
  nomination counts, which are the leader's own action and explicitly
  outside this rule per CLAUDE.md section 4), so nothing to fix there.
  The admin dashboard's Links & Tracking view was deliberately NOT
  touched - real per-rater response status there is a documented,
  legitimate exemption (the administrator, not the leader), unrelated
  to this leak.
- **Confirmed the exact trigger condition, not assumed**: `_progress_
  stats_safe`'s `gated = total < ANONYMITY_THRESHOLD or outstanding ==
  1` - the same condition already driving the stats strip and status
  card.
- **Fix, per the human's own recommendation (option 1: extend the
  protection, don't loosen it)**: `render_portal_overview` now computes
  `_progress_stats_safe(...)` exactly ONCE, into `overview_stats`, at
  the top of the function, and threads that single value through every
  element that touches response counts - the Full 360 status card (now
  takes `stats` as a parameter instead of recomputing it), the reminder
  caption, and `_send_reminders_and_report` (gained a `reveal_counts`
  parameter). This isn't just "compute the same gate twice, correctly" -
  a single shared value is what makes it structurally impossible for
  any of these to independently drift out of sync with each other
  again, which is exactly the category of bug this task exists to fix.
  When `reveal_counts=False`, every branch of the send-reminders result
  message states an action/outcome with literally no number in it, not
  a differently-worded number - "Reminder sent to whoever was eligible."
  / "Still within the 48-hour window — no reminder was sent." / "A
  reminder failed to send...".
- VERIFIED LIVE, both the reported case and the fix: constructed a real
  test leader with 4 completed + 1 incomplete rater (outstanding == 1,
  total == 5, so the ONLY gating reason is the outstanding==1 branch,
  matching the human's exact reported scenario, not the low-total one) -
  screenshotted the full Overview page after the fix and confirmed NO
  numeric outstanding/responded count appears anywhere on it (status
  card, reminder caption, stats strip all read generically). Clicked
  Send Reminders for real against a fake local SMTP target (so it
  genuinely failed) and confirmed the result message read "A reminder
  failed to send — check back or contact your programme coordinator." -
  no count. The other three message branches (sent-only, throttled-only,
  mixed) aren't reachable live without a working SMTP listener, so
  verified by calling the real `_send_reminders_and_report` function
  directly (not a reimplementation) with `send_bulk_reminders`
  monkey-patched to return each tally, confirming both `reveal_counts=
  True` (unchanged from before - still states real numbers, e.g.
  "Reminded 1 rater.") and `reveal_counts=False` (fully generic, zero
  digits) for all four branches.
- Test leader (id 41, "Gate Test Leader") and the temporary
  `.streamlit/secrets.toml` (fake SMTP, needed to make `is_email_
  configured()` true so the Send Reminders button would render at all)
  both removed after verification. Leader 1's 13-rater baseline
  confirmed unchanged.

### Correction: Remove the Your Progress Gating Entirely — DONE 2026-08-27
Supersedes the entry directly above, the same day. Live use surfaced a
real problem with that fix, and a deeper one behind it.

- **The shallow problem**: suppressing the stats strip only at
  `outstanding == 1` doesn't hide that fact from someone who saw the
  real numbers a moment earlier. A leader who sees `outstanding == 2`,
  gets one more response, and watches the strip go blank has just been
  told "outstanding is now exactly 1" - via the disappearance itself,
  not a stated digit, but told all the same. Threshold suppression only
  works against someone with no prior context; here the leader always
  has prior context, since they're the one who's been watching this
  same strip the whole time.
- **The deeper problem, the actual point of this correction**: this
  data was never anonymity-sensitive to begin with, so gating it at
  ANY threshold - fixed correctly or not - was the wrong instinct from
  the start. The real protections in this system (category-level
  score/comment thresholds in generated reports, the Nominate Raters
  table showing only invited/not-sent, never response status) exist to
  stop content or identity being tied to a specific person. A bare
  completion count ("12 invited, 10 responded") names no one, breaks
  down by no category, and reveals not one word of anyone's feedback -
  the same category of information as a delivery tracker showing "3 of
  5 delivered". The leader also already knows exactly who's outstanding
  regardless of what this number shows, since they nominated these
  people by name themselves - the system was never trying to (and
  shouldn't try to) prevent that. Applying the anonymity-gating pattern
  here borrowed a protection from where it genuinely matters and put it
  somewhere its threat model doesn't reach.
- **`total < ANONYMITY_THRESHOLD` was reconsidered separately, not kept
  by default just because it wasn't the one originally reported.**
  Looked for a genuine reason to keep it that wasn't just "borrowed from
  the anonymity pattern" - the closest candidate was "a percentage is a
  noisy, near-meaningless statistic at n=1" (real, but not an anonymity
  concern), and even that doesn't justify what the gate actually did,
  which was hide ALL FOUR numbers (invited/responded/rate/outstanding),
  not just the one derived percentage that's genuinely volatile at low
  n. No standalone justification survived scrutiny, so it's removed too
  - same fix, same reasoning, not left in place by default.
- **Fix**: `_progress_stats_safe` no longer has a `gated`/`safe` branch
  at all - for any total > 0 it always returns real `invited`/
  `responded`/`rate`/`outstanding` numbers (the total == 0 case already
  returned real zeros from an earlier fix and is unchanged). Removed
  as genuinely dead code once the gating was gone, not left as inert
  scaffolding: `_progress_summary_text` (the vague-text generator,
  now uncallable), the `reveal_counts` parameter on `_send_reminders_
  and_report` and its whole generic-message branch, the `.cp-stats-
  vague` CSS rule, and the `if stats['safe']` branches in `_full360_
  status_card_html` and the stats-strip rendering. The SHARED-
  COMPUTATION architecture from the previous fix stays exactly as
  built - `render_portal_overview` still computes `overview_stats`
  once and threads it through the status card, reminder caption, and
  send-result message - only now it's a single source of truth for the
  real numbers rather than for whether to hide them, which is the
  right thing for it to be a single source of truth FOR regardless of
  which way this correction had gone.
- VERIFIED LIVE against both the exact originally-reported scenario and
  the low-total case: a leader with 4 completed + 1 incomplete rater
  (outstanding == 1, total == 5) now shows real numbers everywhere -
  status card ("4 of 5 responses received"), reminder caption ("Nudges
  the 1 who haven't responded yet."), and stats strip (5/4/80%/1) all
  consistent, all real. A second leader with exactly 1 rater invited
  (total == 1, below the removed threshold) shows real numbers too
  (1/0/0%/1), confirming the low-total condition is genuinely gone, not
  just the outstanding==1 one. Clicked Send Reminders for real (against
  a fake SMTP target, so it genuinely failed) and confirmed the result
  message read "1 failed to send — check back or contact your
  programme coordinator." - the real count restored, matching the
  pre-gating original behaviour exactly. The other three message
  branches (sent-only, throttled-only, mixed) verified the same way as
  the previous task - calling the real `_send_reminders_and_report`
  directly with `send_bulk_reminders` mocked - confirming all four now
  unconditionally state real numbers with no `reveal_counts` parameter
  to vary.
- Two test leaders (ids 42 "Gate Removed Leader", 43 "Low Total
  Leader") and the temporary `.streamlit/secrets.toml` used for the
  live Send Reminders test were removed after verification. Leader 1's
  13-rater baseline confirmed unchanged.

### Disable Streamlit's Default Heading Anchor Links — DONE 2026-08-27
Hovering over a card heading ("Direct Reports" etc.) showed a small
link icon - Streamlit's automatic heading-anchor behaviour, stray
default chrome for a page with no in-page anchor navigation to serve.

- Confirmed live, not assumed, which headings this actually reaches:
  every `<h1>`-`<h3>` in this file is raw HTML rendered via
  `unsafe_allow_html=True` (this file uses no `st.header`/`st.subheader`/
  `st.title` at all), and Streamlit still injects the anchor machinery
  (`id="direct-reports"`, a wrapping `stHeadingWithActionElements`, a
  hover-revealed `stHeaderActionElements` link) onto those too - not
  only onto headings created via its own Markdown `#`/`##` syntax or
  its dedicated heading widgets. Confirmed via the rendered DOM
  (`outerHTML` on a live card heading), not inferred from Streamlit's
  docs.
- Checked for a global/config.toml equivalent before defaulting to a
  per-call fix, per the brief's own preference - read the installed
  Streamlit 1.60.0 source directly (`elements/markdown.py` and
  `config.py`) rather than guessing: `st.markdown()` takes a real
  `anchors: bool = True` keyword parameter, but there is no
  config.toml/global setting for it anywhere in `config.py` - the
  per-call keyword is the only mechanism Streamlit exposes.
- Fixed at this file's own single choke point instead of touching
  every heading individually: `_md()` (the one helper every top-level
  HTML block in this file already goes through - confirmed by grep
  that all six h1-h3 call sites route through it, none render via a
  separate raw `st.markdown()`) now passes `anchors=False`. One
  four-character change covers every heading on every screen at once,
  which is the actual "fix it once globally for these pages" the brief
  asked for, given Streamlit itself has no coarser lever.
- VERIFIED LIVE on all four named surfaces (Overview, Nominate Raters,
  Guidelines, Begin Here) plus the consent gate (touched by the same
  fix, not separately named in the brief but worth confirming): every
  `h1`-`h6` on each page now has no `stHeaderActionElements` child at
  all - not merely hidden by CSS, genuinely absent from the DOM, which
  is stronger than "no visible icon" (a hover binding could not
  possibly attach to hide/show an element that was never rendered).
  Cross-checked against a real screenshot with the cursor hovering
  directly over "Direct Reports" - no icon. Confirmed the rest of each
  page renders identically to before (no visual regression from the
  change).

### Bentley Typeface Integration and Live Bold Comparison — BUILT AND LIVE-VERIFIED 2026-08-27, AWAITING IAN'S REVIEW
Scope: Leader Portal (Overview, Nominate Raters, Guidelines, Begin Here)
and the feedback forms (self-assessment and rater). Admin Dashboard
explicitly out of scope, confirmed unchanged. Licensed for this scope
per Ian's permission from Xiao (Bentley brand hub). Generated Word
reports are a separate, purely technical problem (python-docx doesn't
embed fonts) - not touched here, flagged as future work if wanted.

- **`@font-face` integration**: `get_bentley_font_face_css()` in
  `framework.py` (new, alongside `get_logo_data_uri()`) declares ONLY
  Light (300) and Regular (400) - deliberately NO 700-weight face for
  `Bentley-Regular.woff`, since declaring one would tell the browser
  that weight is covered and suppress its own synthetic bold. Base64-
  embedded (`data:font/woff;base64,...`), same reasoning as
  `get_logo_data_uri()`: Streamlit deployment targets don't reliably
  serve arbitrary static folders over HTTP. `BENTLEY_FONT_STACK` keeps
  the full fallback chain (`-apple-system, BlinkMacSystemFont, "Segoe
  UI", Helvetica, Arial, sans-serif`).
- **Applied via page-specific stylesheets, never touching app.py's own
  global CSS**: `leader_portal.py`'s `PORTAL_CSS` gained a small
  f-string prefix (font-face + `font-family` override on headings and
  buttons, `!important`) concatenated onto the front of the existing
  ~1500-line plain CSS constant - deliberately not edited internally,
  to avoid escaping hundreds of pre-existing literal braces.
  `feedback_form.py` gained an equivalent constant injected at the very
  top of `render_feedback_form`, before the locale/consent gates, so
  both of those (not just the paginated survey itself) get the
  typeface too. This works, and is guaranteed not to leak into Admin
  Dashboard, because `app.py`'s `main()` is genuine one-route-at-a-time
  `if/elif` routing - the admin route never calls either function that
  injects this CSS, so broad-looking selectors are safe by construction,
  no DOM-scoping needed.
- **`Bentley-Logotype.woff` deliberately NOT applied anywhere** - its
  intended use was never confirmed. STILL NEEDS ASKING: is the topbar
  "BENTLEY COMPASS 360" lockup (leader portal + feedback form headers)
  the intended use case? Not assumed; not yet answered.
- **Live comparison page at `?fonttest=1`** (`app.py`,
  `render_font_comparison()`) - TEMPORARY, unlinked, direct-URL only,
  remove once Ian picks a treatment. Column A: `'Bentley'` requested at
  `font-weight:700` with no 700 face declared, so the browser
  genuinely synthesises it. Column B: `Bentley-Expanded Bold.woff`
  declared as its own separate family, used directly at its own
  natural weight (400) - no synthesis, no weight trickery.
- **A REAL BUG FOUND WHILE VERIFYING THIS LIVE, not caught by syntax
  checking or a screenshot glance**: the first version rendered as
  literal escaped HTML text instead of an actual page - the exact
  "REAL BUG FOUND DURING BUILD" already documented against
  `leader_portal.py` above (CommonMark treats 4+ leading spaces as a
  code fence; this file's own 4-space function-body indentation was
  baked into the f-string). Fixed with `textwrap.dedent(...).strip()`,
  same as `leader_portal.py`'s `_html()` helper - but dedenting alone
  turned out NOT sufficient here: a SECOND, different bug remained
  even after dedenting correctly (verified the dedented string was
  byte-correct, `<div>` starting at column 0, via a standalone Python
  check). A single `st.markdown()` call combining a `<style>` block
  immediately followed by `<div>` content markup still rendered the
  `<div>` portion as a literal `<pre><code>` block - confirmed via
  `document.querySelector('.fonttest-wrap')` returning null and
  `document.querySelector('pre, code')` finding the escaped text
  instead. Streamlit's client-side markdown renderer appears to close
  its raw-HTML handling at `</style>` and re-parse what follows as a
  fresh block, and something about that adjacency (no separate call
  between them) trips it. Fixed by splitting into two separate
  `st.markdown()` calls - CSS in its own call, content markup in its
  own - the same pattern already used everywhere else in this app
  (`PORTAL_CSS` is always injected separately from the cards it
  styles). Re-verified live after the fix: `.fonttest-wrap` now found
  as a real DOM node, screenshot shows two genuine rendered cards, not
  code-block text.
- **VERIFIED LIVE, not assumed from code**, across every page in
  scope, via `document.fonts` (the actual `FontFaceSet` API - reports
  what's genuinely loaded/rendering, not just what's requested) plus
  `getComputedStyle`: Overview, Nominate Raters, Guidelines, Begin
  Here, the rater-form locale picker, the rater consent gate, the
  self-assessment consent gate (confirmed genuinely different copy
  from the rater version, per the existing self/rater split), and a
  real dimension/item page (`.dimension-header`/`.item-text`) all show
  `computedFontFamily` starting with `Bentley` and
  `{"family":"Bentley","weight":"400","status":"loaded"}` present in
  `document.fonts` - the Regular face is genuinely in use, not a
  silent fallback. The Light (300) face shows `"unloaded"` on every
  page checked, which is expected, not a fault: nothing currently on
  these pages renders text at weight 300, and browsers only fetch a
  font-face's binary data when something actually needs to render at
  that weight - it is registered and ready, just not yet pulled.
- **Admin Dashboard confirmed genuinely unchanged**: `?admin=1`
  computed heading font is `"Source Sans Pro", sans-serif` and
  `document.fonts` contains zero entries with `family` containing
  `"Bentley"` at all - not merely visually unchanged, structurally
  incapable of having changed, per the routing argument above.
- **Bold comparison page verified live, both columns**: Column A's
  "Direct Reports" title has computed `font-family: Bentley,
  -apple-system, sans-serif` at `font-weight: 700`, with
  `document.fonts` showing only `{"family":"Bentley","weight":"400",
  "status":"loaded"}` registered for that family - confirming the 700
  request has no matching face and is genuinely browser-synthesised
  from the loaded 400 face, not silently falling back to a system
  font (which would show a completely different family name in
  `computedFontFamily`, not `Bentley` at all). Column B's title has
  computed `font-family: "Bentley Expanded Bold", -apple-system,
  sans-serif` at `font-weight: 400` (no trickery), with
  `document.fonts` showing `{"family":"Bentley Expanded Bold",
  "weight":"400","status":"loaded"}` - a genuinely distinct, separate
  face, actually loaded. `document.fonts.check()` confirmed positive
  for both. This is the exact failure mode the task explicitly warned
  about (an earlier out-of-session attempt at this same comparison
  silently fell back to a generic system font in one column and was
  briefly mistaken for a valid finding) - not repeated here, caught
  and fixed before being presented as ready.
- **No test data left behind**: one throwaway Self-relationship test
  rater (`fonttestselfver1`, leader 1) was created to verify the
  self-assessment consent-gate copy differs correctly from the rater
  version, then deleted immediately after. Nothing else was created
  for this task.
- **Logotype question answered by Ian same day: apply it to the topbar
  lockup.** `get_bentley_logotype_face_css()` added to `framework.py`
  alongside the others - deliberately under its OWN family name
  ('Bentley Logotype'), not folded into `BENTLEY_FONT_STACK`, since a
  display logotype face is not guaranteed to carry the same even Latin
  glyph coverage as Regular/Light and must stay opt-in per element, not
  applied broadly by the general typeface rule. Applied to exactly two
  places, both already carrying the literal "BENTLEY COMPASS 360"
  wordmark: `leader_portal.py`'s `.cp-brand-text .cp-b1` (the topbar
  eyebrow line, text-transformed to uppercase by existing CSS) and a
  new `.feedback-header-title` class added to the three identical
  `<h1>BENTLEY COMPASS 360</h1>` occurrences in `feedback_form.py`
  (self-assessment intro, rater form intro, and the third - previously
  unnamed and unclassed, now given the same class for consistency).
  VERIFIED LIVE, not assumed: real risk with any logotype webfont is
  that it defines glyphs only for the brand's own word and renders
  tofu/garbled boxes for other Latin letters - confirmed via screenshot
  (both the leader portal topbar and the feedback form header render
  "BENTLEY COMPASS 360" as a clean, fully legible stylised wordmark,
  no missing glyphs) AND via `document.fonts` showing
  `{"family":"Bentley Logotype","weight":"400","status":"loaded"}`
  with `getComputedStyle` confirming `'Bentley Logotype'` as the
  actually-resolved font-family on both elements, not a fallback.
- **Bold treatment (Column A vs B vs neither) still Ian's own call,
  not decided here** - the comparison page exists precisely so this is
  judged from real letterforms in his own browser, not inferred from
  computed-style data alone.
- COMMITTED AND PUSHED to `sandbox` 2026-08-27 (`bf0dd4f`), on Ian's
  explicit "Deploy it on sandbox so I can see it rendered there and
  check" instruction, so he could review `?fonttest=1` in the actual
  deployed sandbox app rather than only locally. The six `.woff` files
  went in alongside the `.py` changes.

### Genuine Bold Rollout, and Extending the Bentley Font to Report Charts — DONE 2026-08-27
Two related pieces, same task. Part 1 finalised the bold-treatment
decision from the live comparison above (genuine Expanded Bold, not
browser-synthesised); Part 2 extended Bentley to the server-generated
report chart images, using the TTF file set (not the WOFF set the UI
work already uses).

**Part 1 surfaced a much bigger gap than the task itself was about, per
Ian's own live catch.** Reviewing a screenshot sweep for the bold
rollout, Ian noticed some text wasn't in Bentley at all and asked
directly: "Can you check that anywhere text is displayed it is in
Bentley font? The addition of the font should apply to every single
instance of text, not just headings or buttons." Investigated rather
than assumed - confirmed live via `getComputedStyle` that a Streamlit
BUTTON element correctly showed `font-family: Bentley` (from the
existing `button[data-testid=...]` rule) while its own inner `<p>`
label showed `"Source Sans"` (Streamlit's own built-in default, a
DIFFERENT font from the Google-Fonts "Source Sans Pro" app.py imports
for its own classes) - Streamlit renders button/widget labels as a `<p>`
inside a nested `stMarkdownContainer` div, and font-family only
inherits down through ancestors that don't set their own value;
Streamlit's own stylesheet sets that `<p>`'s font-family directly,
breaking inheritance from the button around it. The same gap reached
every widget label, caption, input/textarea, and rating-scale option
text in both `leader_portal.py` and `feedback_form.py` - none of it was
h1-h3, a button element itself, or one of the hand-picked classes from
the original typeface pass, so none of it was ever actually getting
Bentley.

- **Fixed with a genuinely universal rule**, replacing the earlier
  selector-list approach (which had already needed widening once, from
  h1-h3-only to a `[class*="cp-*"]` wildcard, and STILL missed this):
  `.stApp, .stApp * { font-family: BENTLEY_FONT_STACK !important; }` in
  both `PORTAL_CSS` and `_BENTLEY_TYPEFACE_CSS`. Reaches every descendant
  of Streamlit's own root app container unconditionally, so no current
  or future Streamlit-internal element type can silently fall outside
  it the way individual selectors already have twice. `!important` wins
  against a Streamlit default that isn't itself `!important` (framework
  defaults essentially never are) without needing to out-specify
  anything selector by selector.
- **REQUIRED EXCEPTION, a real regression found and fixed twice before
  it actually worked**: Material Symbols icons render the literal icon
  NAME as text ("arrow_forward", "check_circle"...) mapped to a glyph
  via the "Material Symbols Rounded" icon font specifically - a blanket
  override replaces that font too, and the result isn't a missing icon,
  it's the icon's NAME rendering as readable text next to the button
  label. Two icon code paths, two different failures:
  - Streamlit's own native `icon=":material/name:"` parameter (19 call
    sites across both files) renders via `[data-testid="stIconMaterial"]`
    - fixed with a same-specificity exception rule declared AFTER the
      broad one, so source order wins the tie (not higher specificity).
  - `leader_portal.py`'s own `_icon()` helper (used for the status-card
    checkmark/clock, etc.) sets its icon font via an INLINE style, which
    should normally beat any external rule regardless of specificity -
    except it didn't, confirmed live via screenshot: "check"/"schedule"
    rendered as literal readable text. Root cause: an inline style
    WITHOUT `!important` loses to an external rule WITH `!important`,
    regardless of the inline style's normally-higher specificity - a
    real CSS gotcha, not a typo. The obvious fix (add `!important` to
    the inline declaration too) does NOT work either: confirmed live via
    `outerHTML` that Streamlit strips `!important` out of inline `style`
    attributes entirely during rendering (the `font-family` declaration
    was completely ABSENT from the rendered span, not merely losing the
    cascade fight) - not documented anywhere found, discovered by
    inspecting the actual served DOM after the `!important` fix visibly
    didn't work. Actual fix: moved `_icon()`'s icon font out of the
    inline style entirely into a real CSS class (`.cp-icon-glyph` in
    `PORTAL_CSS`), sidestepping the inline-vs-external precedence
    question altogether - same mechanism as the `stIconMaterial`
    exception, same specificity tier, same "declared after the broad
    rule" reasoning.
- **Inline `<strong>` tags reconsidered, not carved out.** An earlier
  version of this task's own reasoning (see the bold-rollout brief)
  worried genuine Expanded Bold would read as "a distracting, constant
  width-mismatch" in running body text - consent-gate copy,
  instructions, "unless you are the direct line manager..." etc. Once
  `.stApp *` made every element inherit Bentley family, and `<strong>`
  is bold by browser default, excluding it would have meant giving it
  back a DIFFERENT, non-Bentley font, directly contradicting "every
  single instance of text" - and would have needed its own careful
  weight/font trickery to still look bold without picking up the real
  700 face. Checked live instead of assumed: genuine Expanded Bold
  inline mid-sentence reads cleanly at running-text size on both the
  rater-form intro and the Self consent gate - not distracting or
  cramped, the original worry didn't materialise in practice. No
  exception; `<strong>` gets the same treatment as everything else now.
- **Every page in scope re-swept live** after the fix: Overview,
  Nominate Raters (including the "Add a Rater" form, its table, and the
  edit-pencil icons), Guidelines, Begin Here, the rater-form locale
  picker and consent gate, the self-assessment consent gate, the item
  pages (including the segmented-control rating scale text - "Rarely or
  never" through "No opportunity to observe" - previously never covered
  at all, now genuinely Bentley, confirmed in both unselected and
  selected states), and the comment box/Continue page. Admin Dashboard
  re-confirmed genuinely unchanged (`document.fonts` shows zero Bentley
  entries, heading font still `"Source Sans Pro"`) - structurally
  guaranteed by the same one-route-at-a-time routing argument as before,
  re-verified rather than just re-asserted.
- **Width-increase layout sweep** (the bold-rollout task's own explicit
  acceptance check) at 360/430/645/902px: card titles, chips, and stats
  numbers all held up with no overflow. Two things worth noting, not
  breakage: the Overview "Welcome, Ian Moreton-Thickett" h1 wraps to two
  lines at full width where it previously fit one (genuine reflow, not
  overlap - the neighbouring buttons stay correctly aligned) - accepted,
  not fixed, since a heading wrapping is normal web behaviour, not
  broken layout. A pre-existing "Nominate" button ("Nomi"/"nate")
  wrapping at ~600-700px was found in the same sweep and confirmed, via
  computed style, to be COMPLETELY UNRELATED to this task - the button
  text was already non-bold and picking up Bentley from the very first
  typeface pass, unaffected by anything changed today. Flagged as a
  separate follow-up task rather than fixed here, to stay inside this
  task's actual scope.
- Genuine Expanded Bold (weight 700) is now registered as a THIRD real
  cut of the shared `'Bentley'` family in `get_bentley_font_face_css()`
  (framework.py), alongside the existing Light (300) and Regular (400) -
  not a separate family name this time, deliberately: this lets every
  element already resolving to family 'Bentley' at weight 700 (h1-h3,
  which browsers bold by default, and every explicit `font-weight:700`
  rule already using `BENTLEY_FONT_STACK`) pick up the genuine face
  automatically, with no need to hunt down and individually retarget
  each "bold moment" selector - card titles, chips ("Requirement met",
  "N more needed"), stats-strip numbers, section labels all resolve
  correctly just from existing weight:700 declarations once the real
  face exists to match against. The old "do NOT add a 700-weight face"
  warning in that function's docstring was about mislabelling REGULAR as
  bold (no true bold exists in that width) - Expanded Bold IS a genuine,
  deliberately heavier-and-wider cut, so labelling it 700 is accurate,
  not a repeat of that mistake; the docstring was updated to say so
  rather than left contradicting the new behaviour.

**Part 2, chart fonts - a genuinely different problem, closed for
good rather than worked around.** The report's charts (radar, item bar
charts) are rasterised to PNG by matplotlib at generation time, so the
font only needs to be available on the machine GENERATING the report,
not whoever later opens the .docx - sidesteps the harder "Word body
text needs the font installed on the READER's machine" problem
entirely (still not addressed, still flagged separately). Previously
this only worked reliably on Ian's own Mac, which happens to have the
real Bentley OTF family installed system-wide (`resolve_chart_font()`
checked installed-font NAMES via `CHART_FONT_PREFERENCE`, found
"Bentley" there, and never found anything on Render) - the "generate
client-facing reports locally to keep them consistent" caution
elsewhere in this file exists because of exactly that gap.

- **Genuinely closed, not just documented around**: three TTF files
  (`Bentley-Regular_web.ttf`, `Bentley-Light_web.ttf`, `Bentley-Expanded
  Bold_web.ttf`) are committed to `assets/` and loaded DIRECTLY BY FILE
  PATH via matplotlib's `FontProperties(fname=...)` - identical on every
  machine regardless of what's installed there, no per-environment
  inconsistency any more.
- **REAL BLOCKER FOUND AND WORKED AROUND, not assumed away**: these
  three TTF files (a different set from the WOFF files already wired up
  for the web) have a CORRECT family name ("Bentley", "Bentley Light",
  "Bentley Expanded Bold") on their Macintosh (platform 1) name-table
  entry, but every Windows-platform (platform 3) name field - family,
  full name, PostScript name - is the literal DEL control character
  (U+007F), confirmed directly with `fontTools` (not assumed from
  matplotlib's behaviour alone). matplotlib/freetype reads the Windows-
  platform entries for name-based lookup on any non-Mac machine
  (i.e. Render) - `fm.fontManager.addfont()` on these files registers
  them under that garbled name, not "Bentley", so the OLD name-based
  mechanism (`plt.rcParams['font.family'] = 'Bentley'`) would have
  silently never matched them there. Very likely a deliberate anti-
  extraction measure from the foundry on this specific "_web" file set,
  not a bug - the WOFF files used on the actual web pages don't have
  this problem (name resolution for `@font-face` works differently,
  browsers don't do the same platform-3-name lookup matplotlib does).
  Fixed by using `FontProperties(fname=...)` throughout instead of any
  name-based `rcParams` setting - this bypasses name resolution
  entirely and loads the file's own glyph/outline data directly, so the
  name-table corruption doesn't matter for rendering, only for lookup-
  by-name (which this code no longer does).
- **Confirmed genuinely the real typeface, not a substituted placeholder
  - a real, justified concern given a foundry that scrubs names on
    purpose might also ship deliberately-degraded outlines in a trial/
    web kit**: decompressed the ALREADY-verified-genuine
  `Bentley-Regular.woff` (confirmed rendering correctly on the live web
  pages via `document.fonts`) back to raw TTF with `fontTools` (WOFF
  decompression is lossless - it recovers the exact original SFNT
  table data) and compared it byte-for-byte against
  `Bentley-Regular_web.ttf`: identical glyph count (670), identical
  units-per-em (1000), and identical bounding box + contour count for
  the 'B' glyph. Genuinely the same font data, just a different
  container format - not a placeholder.
- **`chart_font(size, bold=False)` helper** in `report_generator.py`
  returns a correctly-SIZED COPY of the shared module-level
  `CHART_FONT_REGULAR`/`CHART_FONT_BOLD` FontProperties objects (never
  the shared singleton itself - mutating its size in place would leak
  into every other call site using it). REQUIRED, not a convenience:
  confirmed live that matplotlib applies `fontproperties=` AFTER a
  separate `size=`/`fontsize=` kwarg on the same call, so
  `set_xticklabels(size=14, fontproperties=CHART_FONT_BOLD)` silently
  DISCARDS the 14 and falls back to the FontProperties object's own
  default (10pt) - confirmed by rendering and reading back
  `label.get_size()`, not assumed from matplotlib's docs. Every text
  call in `create_radar_chart`/`create_item_bar_chart`/
  `create_self_only_bar` now goes through `chart_font()` instead of the
  old `fontsize=`/`fontweight='bold'` kwargs.
- **Weight mapping**: every element that was ALREADY `fontweight='bold'`
  in the pre-existing chart code (radar spoke labels, the "1-5" scale
  numbers, bar-chart group names, bar-value labels like "4.0") now uses
  `chart_font(size, bold=True)` - genuine Expanded Bold. Everything else
  (legend text, the numeric x-axis tick labels) uses plain
  `chart_font(size)` - Regular. `CHART_FONT_LIGHT` is loaded and
  available but not currently applied anywhere - nothing in these three
  chart functions has an existing lighter-than-default-weight moment to
  attach it to, and none was invented for this task. INTERPRETATION
  FLAG FOR IAN: the task text's own wording ("Use Regular/Light for
  these [axis labels, legend, dimension labels, bar-value labels]...
  Expanded Bold only if there's a genuine emphasis point... a title,
  perhaps") could be read more narrowly than this - as meaning NONE of
  the current chart text should be Expanded Bold, since none of it is a
  literal chart title. Went with the broader reading instead (preserve
  each element's EXISTING bold/non-bold styling, swap in the correct
  genuine face for whichever weight was already chosen) because the
  task also says to treat genuine emphasis points "the same way as the
  UI rollout above" - and bar-value labels/dimension labels are
  arguably the chart equivalent of Part 1's own named categories
  (stats numbers, card titles/section headings). Flagged rather than
  silently decided either way, in case Ian's intent was the narrower
  reading - easy to change, `chart_font(size, bold=True)` -> `chart_font(size)`
  at the handful of call sites listed above.
- **Verified against real generated sample images, not assumed from the
  code path**: called `create_radar_chart`/`create_item_bar_chart`/
  `create_self_only_bar` directly with realistic data (9 real dimension
  names including the long "Building High-Performing Teams" spoke label
  that has its own documented wrapping history) and inspected the
  actual PNG output. Genuinely the Bentley typeface, not a fallback -
  visually distinctive once compared side-by-side, and independently
  confirmed via the byte-identical-glyph check above, since a visual
  glance alone was judged not trustworthy enough on its own (a lesson
  already learned once this same task, on the UI side).
- **Legibility checked at ACTUAL embed size, not raw PNG resolution -
  the acceptance check's own explicit requirement**: the radar chart is
  generated at a 12in-wide figure but embedded in the document at only
  `CONTENT_WIDTH_IN` (6.27in - a ~0.52x reduction); the item bar chart
  is generated at 4.5in but embedds at only `ITEM_CHART_WIDTH_IN`
  (2.9in - a ~0.64x reduction) - a raw glance at the generated PNG at
  full resolution would have been misleadingly generous, since the text
  ends up meaningfully smaller once actually placed in the report. Both
  sample images were resized down to their real embed proportions
  before judging - dimension labels, the 1-5 scale, group names, and
  value labels all stayed genuinely legible at that reduced size, no
  blur or illegibility, on both the radar and the item bar chart. The
  self-assessment-only bar chart (2.9in embed, smaller still) was
  checked the same way - legible but genuinely small, consistent with
  how it already looked before this change (not something Bentley
  specifically makes worse - this bar has always been tiny by design).
- Old name-based `resolve_chart_font()`/`CHART_FONT_PREFERENCE`
  mechanism kept as a LAST-RESORT fallback only (fires if a
  `BENTLEY_CHART_*_PATH` file is ever missing from disk entirely), not
  the primary path any more - `CHART_FONT_REGULAR is None` is the actual
  gate, confirmed non-None in this environment so that fallback branch
  never executes today.
- Not touched: Word document BODY text (headings, paragraphs outside
  chart images) - still the separate, harder "reader's machine needs
  the font installed" problem, unaddressed, exactly as flagged in the
  task brief. Admin Dashboard - untouched by either part of this task,
  re-confirmed rather than just assumed for Part 1.
- No test data created for this task - all live verification used the
  existing sandbox portal_token/rater tokens already established as
  baseline fixtures, plus one throwaway Self-relationship rater
  (`fontsweepself1`, leader 1) created to re-check the self-assessment
  consent-gate copy, deleted immediately after. Chart sample images
  were generated to a local scratchpad directory outside the repo, not
  committed.

### Two follow-up fixes from Ian's own review — DONE 2026-08-27
Both caught by Ian looking directly at the sent sample images/reports,
not flagged by any of the verification above - a reminder that
generated-and-inspected beats generated-and-assumed-fine even after a
thorough pass.

- **Radar legend ("Self"/"All Raters") switched to genuine Expanded
  Bold**, matching every other label on that chart (spoke names, the
  1-5 scale). It was already genuinely rendering in Bentley Regular
  before this - verified by pixel-diffing the rendered "All Raters"
  text against matplotlib's own default font at the identical size
  (10,624 differing pixels out of the glyph area, not a silent
  fallback) - but Regular is a visually plain cut next to Expanded
  Bold, and being the ONLY non-bold text on that specific chart made it
  read as "not Bentley" at a glance even though it technically was.
  One-line change: `chart_font(14)` -> `chart_font(14, bold=True)` in
  `create_radar_chart`'s `ax.legend(...)` call.
- **Self-Assessment bar chart thickened to match the Full 360's.**
  Ian's own observation, unprompted: "the bar graphs rendered for the
  Self-Assessment report are thinner than the bars in the Full 360...
  plenty of page real estate... to thicken them to the same depth."
  Confirmed real via direct pixel measurement (scanning the saved PNG
  for `bentley_green`-coloured rows, not eyeballing): the old
  `create_self_only_bar` (figsize height 0.65in) produced a 12px-thick
  bar; a real densest-case (6-bar, every group present) Full 360 item
  chart's own "Self" bar measured 17px at the same native resolution
  and the same eventual embed scale (both charts share the same 4.5in
  native width -> `ITEM_CHART_WIDTH_IN` 2.9in embed width, so comparing
  raw pixel thickness between them is a fair, direct stand-in for final
  embedded size). Root cause: matplotlib reserves a roughly FIXED
  amount of a short figure for x-axis tick-label margin regardless of
  total figure height, so the earlier 0.4->0.6 bar-height-FRACTION fix
  (documented above) improved things without ever closing the gap - at
  a short 0.65in figure most of that height WAS margin, leaving little
  for the bar itself.
  - Fixed by raising the figure height specifically (0.65in -> 0.72in),
    found by empirically sweeping heights and re-measuring against the
    16-6-bar target rather than computed analytically - the
    height-to-thickness relationship is NOT linear (0.65->0.85in jumps
    12px->30px, confirmed, not assumed) because of that fixed margin.
    Landed on 18px (1px over the 17px target, not under - erring toward
    Ian's explicit "thicken" direction).
  - Densest 6-bar Full 360 case was chosen as the deliberate matching
    target, not the sparser 1-2 bar cases (which run much thicker still
    - measured 39px - due to a separate, unrelated 0.8in figure-height
    FLOOR already documented in `create_item_bar_chart` above) - a
    completed 360 typically shows every group, so that's the
    genuinely representative comparison for what a leader sees when
    flipping between their own Self-Assessment and Full 360 reports.
  - VERIFIED THROUGH THE REAL ADMIN UI, not just the isolated function:
    regenerated Ian's own real Self-Assessment report via the actual
    "Generate" button/dropdown, extracted an embedded item-bar image
    from the resulting .docx, and confirmed it visibly thicker,
    matching the standalone-function test. Report generated cleanly
    with no errors; 14 `pageBreakBefore` markers present (dimension/
    section breaks, consistent with the existing page-break rules), no
    crash. NOT independently re-verified with a full PyMuPDF page-count
    diff (the rigour used for larger placement changes elsewhere in
    this file) - the magnitude here is small (~0.07in of extra height
    per item, well short of pushing a full extra item onto a new page
    on its own) and Ian's own "plenty of page real estate" assessment
    was taken as informed rather than re-litigated from scratch; worth
    a proper page-diff check if a real self-assessment report is ever
    seen to reflow unexpectedly.

### Locale Picker Removed from Self-Assessment Only — DONE 2026-08-28
Ian's instruction, prompted by a question raised while discussing an
unrelated change: the picker was built for RATERS who might be less
fluent in English than the leader nominating them, not for leaders
themselves - every leader attending the programme has decent English.
Raters still need it (translating rater comments for the Full 360 is a
separate, larger conversation Ian still needs to have with Bentley, not
resolved by this change) - this is scoped to Self only.

- `render_feedback_form` in `feedback_form.py`: the locale-gate
  condition now short-circuits on `is_self` (hoisted above the gate,
  ahead of its previous computation point further down the function -
  the later duplicate assignment was removed, not left as dead code).
  A Self rater's `locale` column simply stays unset, which the i18n
  scaffold already treats as the English fallback everywhere (`_t()`/
  `get_translation()` short-circuit `None`/`'en'` to the hardcoded
  English text) - no other change needed for this to be a no-op
  functionally, just a removed screen. Skipping straight past the gate
  means a Self rater now lands directly on the consent gate on their
  first visit, same as always for a rater who already has a locale set.
- VERIFIED LIVE with two fresh, never-before-seen test raters (not
  inferred from reading the code alone): a new Self rater
  (`localetestself1`) loaded straight into the consent gate with no
  locale picker shown at all; a new Peers rater (`localetestrater1`)
  created the same way still saw the full picker (English, Arabic,
  German, French, Dutch, Vietnamese, Traditional Chinese) exactly as
  before - confirming the change is genuinely scoped to Self and raters
  are completely unaffected. Both test raters deleted after
  verification; leader 1's 13-rater baseline confirmed unchanged.

### New Production Environment: Branch, Domain, and a Real Incident — 2026-08-28
The real October cohort deployment. A new `production` branch, a new Render
service, and a new Turso database - genuinely separate from both `main`
(Mark's, untouched) and `sandbox` (still the working/test environment).

- **Step 1, confirmed before touching anything**: Mark's original deployment
  (`main` branch) is still live and connected. Directly checked (not
  assumed): navigated to `catalyst-360-arbncruhflmazjemep8uzh.streamlit.app`
  (the `DEFAULT_BASE_URL` in `email_sender.py`) - genuinely live, and its
  masthead/tab title still reads "The 360 Development Catalyst", the
  pre-white-label name that only ever existed pre-2026-08-04 and has never
  been merged past `sandbox` - strong evidence `main` hasn't been touched
  since original setup. Ian then confirmed directly from the Streamlit
  dashboard: `main` is live and connected. Per the resulting risk (a new
  production branch reusing `main` or being merged into it could
  accidentally redeploy Mark's environment), created a genuinely new
  `production` branch from `sandbox`'s HEAD (not from `main`, which is
  stale and pre-dates the white-label rename, the typeface work, and
  everything else built since) and pushed it to origin.
- **Step 2, domain routing - confirmed empirically, not assumed**: checked
  the actual public DNS for `thedevelopmentcatalyst.co.uk` directly (`dig`,
  no credentials needed - DNS is public). Confirmed Ian's own assumption
  held: SPF (`v=spf1 include:spf.protection.outlook.com -all`) sits on the
  root domain, DMARC on `_dmarc.<root>`, DKIM on `selectorN._domainkey.<root>`
  (Microsoft 365's own delegation pattern) - none of them reference the
  `portal` subdomain specifically, so repointing `portal`'s CNAME to a new
  Render service touches none of this authentication setup. Also confirmed
  the registrar is GoDaddy (`ns71/72.domaincontrol.com`), matching the
  GoDaddy M365 reference already in `admin_dashboard.py`'s SMTP help text.
  Flagged a real ordering dependency: repointing `portal` needs the new
  production Render service's own hostname first, so Step 3 (create the
  service) has to happen before Step 2 can actually be finished - both
  need Ian's own hands-on access to Render + GoDaddy, which this session
  has no credentials or connected tool for.

### Real Incident: `load_demo_data_if_empty()` Silently Seeded the New Production Database
Found via Ian's own question, not caught by any process here first: "Is
there any seed script... that could run automatically... particularly
anything that might fire on first startup against a database it detects
as empty?" - asked specifically because he'd found unexpected data on the
brand-new production database and wanted the mechanism identified and
explained BEFORE anything was deleted, not the reverse.

- **The mechanism**: `load_demo_data_if_empty()` in `app.py`, called
  unconditionally at module top level (`load_demo_data_if_empty()`, no
  guard). It checks `len(leaders) == 0` and, if true, inserts three fully-
  scored demo leaders (Sarah Mitchell, James Thompson, Emma Richardson)
  with complete synthetic Full 360 data across all 45 items -
  `np.random.seed(42)` makes this fully deterministic, not occasional.
  This runs as a side effect of Streamlit executing `app.py`, identical
  behaviour on any host, any empty database - nothing Render-specific
  about it (checked: no `render.yaml`/`Procfile`/`start.sh` in the repo to
  find a Pre-Deploy Command in anyway). The very first request served by
  the new production service - Ian checking it, a health check, anything -
  hit the empty table and fired it instantly.
- **A REAL, REPRODUCIBLE RELIABILITY BUG surfaced while investigating,
  not just the "fires unexpectedly" problem**: on BOTH production and
  (checked afterward) sandbox, only Sarah Mitchell was ever actually
  created - never James Thompson or Emma Richardson. On production,
  confirmed precisely via row counts: all 13 of Sarah Mitchell's intended
  raters were created (the "add all raters" loop completed), but only the
  first 6 (Self, Boss, 4×Peers) got `submit_feedback()` called on them
  before something stopped the whole function - the 5 DRs and 2 Others
  raters exist as bare rows with zero ratings/comments. Sandbox's own
  leftover (`id=1`, `created_at` 2026-08-05 - present since very early in
  this project, sitting undetected alongside real test data this whole
  time) shows the IDENTICAL pattern: only Sarah Mitchell, nothing further.
  Two independent occurrences stopping at the exact same point is real
  evidence this function does not reliably run to completion against a
  remote Turso database - most likely a transient failure on one of the
  many per-rater network round-trips (each `submit_feedback()` call is a
  real remote write, not a local file operation), not a logic bug specific
  to DRs/Others (read through the ratings/comments generation code for
  both - nothing in it behaves differently for those relationship types).
  Not fixed here beyond the opt-in gate below - worth knowing before
  anyone relies on `SEED_DEMO_DATA=true` for a real demo: verify all three
  leaders actually appear rather than assuming a clean run.
- **Confirmed NOT a notification-email risk**: `db.submit_feedback()` in
  `database.py` is pure data (ratings, comments, mark-complete, sever) -
  the admin-notification triggers live in `feedback_form.py`'s UI flow,
  never in `database.py` itself. Since the seed calls `submit_feedback()`
  directly, bypassing that UI layer entirely, this could not have sent
  Ian a stray "Full 360 ready" email.
- **Fix, per Ian's explicit instruction: gate, don't delete.** The
  capability is genuinely useful (a fresh dev environment, a one-off demo,
  testing the admin dashboard with something to look at) - the bug was
  never the function existing, it was firing itself silently the moment a
  table happened to be empty. `load_demo_data_if_empty()` now returns
  immediately unless `SEED_DEMO_DATA` is set to `"true"` in the
  environment - checked BEFORE the `get_all_leaders()` query even runs, so
  a production deployment that never sets this variable can never trigger
  it, regardless of how empty its database is. VERIFIED LIVE both
  directions, not assumed from reading the code: imported the real
  `app.py` (not a reimplementation) against a genuinely fresh empty
  database with no flag set - 0 leaders, confirmed the gate holds; against
  another fresh database with `SEED_DEMO_DATA=true` - all 3 demo leaders
  appeared exactly as before, confirming the capability is fully
  preserved, not removed.
- **Production cleanup, done via Ian's own hands via Turso's SQL console -
  no credentials shared into this session, consistent with how every
  database change in this project has been handled.** Confirmed the
  precise leader ID and full dependent-row counts first (`raters`:13,
  `ratings`:270, `comments`:22, `reports`:0, `historical_scores`:0,
  `email_log`:0) before any deletion, per Ian's own explicit instruction
  not to delete before understanding whether this could recur. Two real
  snags hit and resolved along the way, both worth remembering for any
  future manual Turso cleanup:
  - A pasted multi-statement `DELETE` block came back as a SQL syntax
    error mentioning tokens that appeared nowhere in the actual SQL given
    - traced to Ian having copied an EARLIER draft that still had
    `<ID1>, <ID2>, <ID3>` placeholder text in it (the literal `<`
    character is what broke the parser), not the corrected version with
    the real ID substituted in.
  - Once corrected, a second attempt hit a genuine `FOREIGN KEY constraint
    failed` error when the full 7-statement block was pasted and run as
    one batch - but the read-only recheck immediately after showed EVERY
    count still at its original value, meaning the whole batch had been
    rolled back atomically by whichever single statement failed, not
    partially applied. Resolved by having Ian run each of the 7 DELETEs
    one at a time instead of as one pasted block - all 7 then succeeded
    individually with no error at all, an inconsistency between batched
    and single-statement execution that was never root-caused (no access
    to Turso's own console internals to explain it) but is worth knowing
    as a pattern: if a batched multi-statement delete errors on this
    platform, don't assume partial application - verify actual state, and
    fall back to one-at-a-time execution rather than debugging the batch
    further.
  - Final state confirmed with a real query, not inferred from the
    deletes appearing to succeed: every dependent-table count at 0, and
    `leaders` itself empty. Production is genuinely clean.
- **Sandbox's own leftover left in place**, per Ian's explicit call - not
  urgent, sandbox is allowed to be messy, and it's been sitting there
  undetected since 2026-08-05 without causing any actual harm.

### "Consent Not Recorded" Investigation — NOT A BUG, Two Separate Consent Columns Explained (2026-08-28)
Flagged as a priority/compliance issue after Ian checked a real leader's
row on the new production database post-self-assessment and found
`leaders.consent_given = 0`, `consent_given_at = NULL` despite having
genuinely ticked the consent checkbox and completed the self-assessment.
Investigated end to end (code trace + a live production data check)
before any fix was attempted, per Ian's own explicit instruction not to
assume a cause. Conclusion: **the write is working correctly. The wrong
table was checked.**

- This codebase has TWO SEPARATE, INTENTIONALLY DIFFERENT consent
  columns, and confusing them is an easy mistake to make when verifying
  by hand:
  - `raters.consent_given` / `consent_given_at` - the self-assessment
    (and rater feedback) consent. Self-relationship submissions are
    stored as `raters` rows (`relationship = 'Self'`), so THIS is where
    self-assessment consent lands, written by `db.set_rater_consent()`
    from `render_consent_gate()` in `feedback_form.py` - the SAME
    function and code path handles both Self and non-Self raters,
    just with different on-screen copy (see fix 1 below for the one
    real gap in that copy split).
  - `leaders.consent_given` / `consent_given_at` - a DIFFERENT consent,
    asked on the leader's own portal visit (nominating raters, being
    responsible for their data), written by a different function
    (`db.set_leader_consent()`) from `render_leader_consent_gate()` in
    `leader_portal.py`. Per this project's own two-stage programme
    timeline (self-assessment before Module 1, the leader portal/rater
    nomination after), a leader who has only done their self-assessment
    has legitimately not been through this second, separate gate yet -
    `leaders.consent_given = 0` in that state is CORRECT, not evidence
    of a lost write.
- Traced the full code path before checking any live data (per Ian's own
  "don't assume" instruction): button click -> `db.set_rater_consent
  (rater_info['id'])` -> a plain `UPDATE raters SET consent_given=1,
  consent_given_at=CURRENT_TIMESTAMP WHERE id=?` with an explicit
  `conn.commit()`, no try/except to swallow a failure silently. Checked
  `rater_info['id']` traces cleanly to the rater's own primary key via
  `get_rater_by_token()`'s join (no column collision with the joined
  `leaders` table's own `id`). Checked for duplicate/shadowing
  definitions of `set_rater_consent`/`set_leader_consent` - each defined
  exactly once. Nothing in the code looked broken before ever touching
  live data.
- VERIFIED LIVE against the real production database (Ian ran the query,
  no credentials shared into this session, same discipline as every
  other database change in this project): the actual Self-relationship
  rater row for the leader in question showed `consent_given: 1`,
  `consent_given_at: "2026-08-28 12:51:53"`, roughly 17 minutes before
  `completed_at` - a real, durable, provable timestamp exactly where the
  design puts it. Confirms the write path is genuinely sound, not just
  theoretically sound from reading the code.
- No code change made here - there was nothing to fix. If this
  confusion comes up again during manual verification (via Turso's
  console or otherwise), check `raters.consent_given` for a self-
  assessment or rater consent question, and `leaders.consent_given`
  only for a question about the leader's own portal-level consent -
  they are never the same value and were never meant to be.

### Three Fixes from the Production Walkthrough — DONE 2026-08-28

**Fix 1, rater-only "hard to trace back" language on the self-assessment.**
The Overall Feedback keep/change comment guidance line was one shared
string_key with the trace-back clause baked in, so a leader doing their
own self-assessment read "...keeps your feedback harder to trace back to
you" - nonsensical when there's no one to trace it back to and nothing
being anonymised. `_render_comment_guidance` in `feedback_form.py` now
takes `prompt` ('keep'/'change') and `keep_form` ('self'/'other') and
resolves one of four distinct string_keys
(`ui_comment_guidance_{prompt}_{keep_form}`), matching the pattern already
used for the dimension-level comment prompt
(`ui_comment_prompt_self`/`_rater`, 2026-08-21). Self drops the trace-back
clause entirely rather than rewording it. Swept the whole file for other
leftover instances via grep for "trace back" - the dimension-level prompt
was already correctly split from the earlier pass; leader_portal.py's one
other hit is unrelated anonymity-threshold copy, not personal comment
attribution.

**Fix 2, Self-Assessment report spacing between the dimension description
and Q1.** Scoped to Self-Assessment only, per Ian's own direct
instruction after watching the Full 360 sample render on his screen
during a (subsequently abandoned) automated-verification attempt: "the
spacing on that version of the report is already fine, this fix should
only apply to the Self-Assessment report." `add_dimension_section` in
`report_generator.py` now sets `space_after = Pt(16) if is_self_only else
Pt(6)` on the description paragraph - Full 360's original Pt(6) untouched.
Regenerated Ian's real Self-Assessment report and had him view it
directly; confirmed "Much better."
- WORD/APPLESCRIPT PDF AUTOMATION IS CURRENTLY BROKEN in this
  environment's installed Word version (16.112) - both `docx2pdf` and
  direct AppleScript `save`/`save as` calls fail with "doesn't understand
  the message" errors, a regression from automation that reportedly
  worked in earlier sessions. `sdef` (to inspect Word's real AppleScript
  dictionary) also fails, needing a full Xcode install this machine
  doesn't have. GUI/keystroke-level automation was tried once and
  deliberately abandoned - there is no visual access to the desktop to
  verify blind keystroke automation is doing what's intended, and that
  risk wasn't worth taking. PRACTICAL CONSEQUENCE: page-break-impact
  verification for report layout changes currently needs a human to
  actually view the rendered Word/PDF output (as Ian did here) rather
  than an automated PyMuPDF page-diff - PyMuPDF itself still works fine
  for measurement, it's only the .docx -> PDF conversion step that's
  broken.

**Fix 3, page doesn't scroll to top on dimension advance in the paginated
feedback form.** Added `_scroll_to_top_if_page_changed(page_idx)` in
`feedback_form.py`, called once near the end of `render_feedback_form`
(after the page-type dispatch block renders the new page's own content,
not before - see the crash note below), tied to `st.session_state
['_scrolled_to_page_idx']` so it only fires when `form_page_idx` has
genuinely changed, never on a rerun caused by rating a question or typing
a comment. Uses `st.iframe` (not `st.components.v1.html`, deprecated in
this Streamlit version) since a bare `<script>` in `unsafe_allow_html`
markdown never executes, and targets `[data-testid="stMain"]` (not
`window`) since that's this app's real scrollable container.
- THREE DISTINCT BUGS FOUND AND FIXED BEFORE THIS ACTUALLY WORKED, each
  only found by testing live rather than trusting the code:
  1. **A genuine, reproducible server crash** (no Python traceback
     anywhere) when the scroll call was placed BEFORE the page-dispatch
     block, specifically on the Overall Feedback -> Development
     Priorities transition. Fixed by moving the call to fire AFTER the
     new page's widgets have already been rendered into the script.
  2. **`el.scrollTo({top:0, left:0, behavior:'instant'})` silently failed
     to reach top specifically on transitions into or out of the Review
     page** (by far the longest, most element-heavy page), while working
     everywhere else. Root-caused live via `iframe.contentWindow.eval`:
     a direct `el.scrollTop = 0` property assignment, invoked the same
     way, measurably worked (before/after scrollTop read) where the
     options-object `scrollTo()` call didn't. Switched every scroll call
     in this function to the plain property assignment.
  3. **The real cause of the Review-page failure, found only after fix 2
     alone still didn't work live**: `st.iframe`'s HTML content was a
     fixed literal string, identical on every call regardless of which
     page changed to which. Streamlit's frontend appears to treat a
     repeated `st.iframe` call with byte-identical content as the same
     element across reruns and never reloads it, so the `<script>` only
     ever executed on its first mount in a browser session - explaining
     the exact symptom pattern (dimension-to-dimension and Overall
     Feedback -> Priorities worked because each was effectively the
     FIRST scroll iframe mounted in a given test run; Priorities -> Review
     and Review -> Edit-jump-back failed because an iframe with that same
     content had already mounted once before). Fixed by embedding
     `page_idx` into the iframe's HTML as a comment, forcing genuinely
     different content - and therefore a genuine reload and script
     re-execution - on every real page change.
- RETRIED BRIEFLY (three calls at 50/100/150ms), kept as a defensive
  margin against a genuine render-timing race on a long page like Review,
  even after finding the real cause above.
- VERIFIED LIVE end to end after all three fixes, using real user-driven
  scrolls (never JS-injected) followed by real clicks, then a passive
  `scrollTop` read: Continue on a dimension page, Overall Feedback ->
  Priorities, Priorities -> Review, Edit-jump-back-to-a-dimension-page,
  and Review-after-edit (back to Review) all correctly reset to 0.
  Selecting a rating and typing+blurring a comment box both correctly did
  NOT reset scroll (confirmed the scroll position held at its genuine
  user-set value through both). Re-verified the full sequence again at a
  375x812 mobile viewport - same results, since the scroll logic itself
  is plain JS with no viewport-dependent branching.
- A FALSE ALARM WORTH DOCUMENTING FOR FUTURE SESSIONS: while testing at
  mobile width, the browser tool's synthetic click repeatedly triggered a
  native right-click-style context menu (Copy/Select All) instead of a
  tap, which blocked the intended click and coincided with the dev
  server becoming briefly unreachable - initially misdiagnosed as a real,
  mobile-width-specific crash in the scroll fix. Ian caught this directly
  ("this dialogue box showed up each time you were trying to click
  continue") and clicked Continue himself, which worked immediately with
  no crash - proving the app was fine throughout and the issue was purely
  the mobile-emulated click/touch translation in the test tooling, not
  application code. WORTH REMEMBERING: at a `resize_window` mobile preset
  (which enables real touch-point/mouse-to-touch emulation), a
  `computer{action:"left_click"}` can misfire as a long-press and open a
  context menu - if a click seems to hang or a server seems to vanish
  right after clicking at mobile width, check for a stray context menu
  before concluding the app crashed.
- Test rater `fixestestself2` (leader 1) and its ratings/comments/
  email_log rows deleted after verification; leader 1's 13-rater baseline
  confirmed unchanged.

### Fourth Material Symbols Icon Gap: Streamlit's Built-In Alert Icon — FIXED 2026-08-28
Spotted by Ian directly in a screenshot taken while testing Fix 3 above,
not something either of us was looking for: stray "histor" text bleeding
into the left edge of the Self-Assessment form's "Welcome back!" resume
banner. He'd captured it but the screenshot got overwritten by a later
one in the same testing session, so it had to be reproduced fresh rather
than shown directly.

- Reproduced live by creating a disposable test rater
  (`reprotestself1`, id 157, deleted after) with a saved draft and
  consent pre-set, landing straight on the form where the resume banner
  renders. Inspected the actual DOM rather than guessing: `<span
  data-testid="stAlertDynamicIcon">history</span>` - the literal Material
  Symbols icon name ("history", the clock-arrow icon Streamlit shows by
  default next to `st.info(...)`) rendering as visible text instead of
  being mapped to its glyph.
- SAME ROOT CAUSE AS THE THREE MATERIAL-SYMBOLS GAPS ALREADY DOCUMENTED
  in "Genuine Bold Rollout..." above (Streamlit's `[data-testid=
  "stIconMaterial"]` icon spans and leader_portal.py's own `_icon()`
  helper), but a FOURTH, previously unfound instance: this specific icon
  element - Streamlit's own automatic icon on `st.info`/`st.warning`/
  `st.success`/`st.error`, not an explicit `icon=":material/name:"`
  parameter this codebase passes anywhere - carries its own distinct
  testid, `stAlertDynamicIcon`, which that earlier audit's grep-for-
  `icon=` approach had no way to find, since there's no call site to grep
  for. Both `feedback_form.py` and `leader_portal.py` use `st.info`/
  `st.warning`/`st.success`/`st.error` extensively (the resume banner,
  nomination warnings, CSV-import results, form-validation errors...), so
  both files carried the same exposure.
- Fixed by adding `[data-testid="stAlertDynamicIcon"]` to the existing
  Material-Symbols-font exception rule in both files' Bentley-typeface
  `<style>` blocks, alongside the pre-existing `[data-testid=
  "stIconMaterial"]` exception - same mechanism, same reasoning, just a
  fourth selector added to the same list.
- VERIFIED LIVE on `feedback_form.py`: reloaded the same reproduction
  case after the fix, confirmed via screenshot (a genuine clock icon
  glyph, no stray text) AND via computed style
  (`getComputedStyle(el).fontFamily` on the alert-icon span now reads
  `"Material Symbols Rounded"`, not the inherited Bentley stack).
  NOT independently re-verified on `leader_portal.py` with a live-rendered
  alert (none of leader 1's current state happens to trigger one) - the
  CSS rule is identical and keyed to a generic Streamlit-internal testid
  with no per-file logic involved, so the feedback_form.py verification
  stands for both; flagged here rather than silently assumed.
- Test rater `reprotestself1` (id 157) and its rows deleted after
  verification; leader 1's 13-rater baseline confirmed unchanged.

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

Items 1-7, 9 and 10 were completed and verified on `sandbox` (1-4 on 2026-08-03,
the rest on 2026-08-04). NOT yet committed and NOT merged to `main`.
Remaining: 8 (guidance artefacts), plus the app-URL rename which is
infrastructure and needs the human (see the white-label subsection in section 5).

1. ~~Fix the ANONYMITY_THRESHOLD bug in framework.py (section 6).~~ DONE — it was
   already present at framework.py:180 (`= 3`); confirmed `database.py` imports
   cleanly, so reports were not in fact blocked.
2. ~~Fold in the paired frequency-scale item set.~~ DONE — 45 paired items,
   `SCALE_FREQUENCY`, `OPEN_PROMPTS`, `get_item_text()`, `get_prompt_text()` are
   now in framework.py. Callers updated in database.py, feedback_form.py,
   report_generator.py, and the demo seeder in app.py. `COMMENT_SECTIONS` now
   ends `['keep', 'change']` instead of `['strengths', 'development']`.
   Verified in-browser (They/I forms, frequency dropdown, no N/A, Q46-47 gone).
   BUG FIXED en route: `save_draft` filtered ratings with `if v`, silently
   dropping "no opportunity" (0) answers because 0 is falsy. Scoring was never
   affected (that path already excluded NULL scores correctly).
3. ~~Rework the report generator.~~ DONE — removed `add_overall_effectiveness`
   and `OVERALL_ITEMS`; keep/change keys wired through the report and the AI
   theme synthesis; inline whole-item coverage ("Rated by X of Y respondents")
   added under each item, never per-group. Verified by generating real .docx
   files: exactly Q1-Q45, correct headings, coverage line correct on an item
   with no-opportunity answers.
4. ~~Rework `render_progress_section` + delete_rater guard.~~ DONE — progress is
   now total-only via `_progress_summary_text()`, which falls back to a vague
   "Responses are coming in" when the total is below ANONYMITY_THRESHOLD or when
   exactly one person is outstanding. One blind "Remind Everyone Still to
   Respond" button, no counts or names. 48h per-rater throttle added in
   `email_sender.send_rater_reminder` via `REMINDER_THROTTLE_HOURS`.
   `delete_rater` guard added and tested both ways. Self-serve removal dropped
   in favour of email correction (see section 5).
5. ~~Wire identity severing into submit_feedback.~~ DONE — see the severing
   subsection in section 5 for the full design, including the roster collision
   and how `leaders.nomination_roster` resolves it. `sever_rater_identity` nulls
   name and email and overwrites `email_log.to_email`; hooked into
   `submit_feedback` after the completion commit; verified through the real form
   UI. NULL-email skip added to the portal's bulk-reminder loop.
6. ~~Build the self-identified development priorities flow.~~ DONE 2026-08-04.
   Spec as agreed with the human: the leader ranks up to
   `DEVELOPMENT_PRIORITY_COUNT` (3) priorities, each chosen from DIMENSIONS, with
   a free-text field used to zero in on the specific behaviours and the actions
   they intend to take. Chosen over free-text-only or per-item picking because
   dimension-level choices can be triangulated against the scores, and the
   report/radar are already organised that way.
   - Stored as JSON on `leaders.development_priorities` (NOT on the Self rater
     row) so they are unaffected by severing and outlive any change to how
     self-assessment rows are handled. Surfaced to the report via
     `data['development_priorities']` inside `get_leader_feedback_data`, so no
     report caller signature changed.
   - Rendered in `feedback_form.py` only when `is_self`; raters never see it
     (verified in-browser).
   - `add_development_priorities` in report_generator.py renders a section placed
     after Overall Qualitative Feedback and before Next Steps in the Full 360,
     and after the detailed dimensions in the Self-Assessment. In the Full 360 it
     prints Your rating / Others / Gap beside each stated priority, which is the
     analytical point: where the leader's own intent and the feedback agree or
     diverge.
   - AT LEAST ONE PRIORITY IS COMPULSORY (changed 2026-08-04 on the human's
     instruction). `DEVELOPMENT_PRIORITY_MINIMUM = 1` in framework.py drives both
     the submit validation and the UI: Priority 1 carries a red asterisk,
     Priorities 2 and 3 are marked optional. Submitting with none chosen is
     blocked with a message that also points the leader back to what they wrote in
     the closing keep/change questions, per the human's suggestion that they can
     build a priority from those answers. Raise the constant if more should be
     required. Picking the same dimension twice is also blocked, since a duplicate
     ranking is meaningless.
   - THE ACTIONS TEXT IS REQUIRED WHENEVER A DIMENSION IS CHOSEN (added 2026-08-04
     on the human's instruction, closing a real gap: a leader could previously
     pick three dimensions, write nothing, and submit, leaving the report printing
     bare dimension names with no actions under them). Enforced by
     `_priorities_missing_actions` in feedback_form.py against
     `DEVELOPMENT_PRIORITY_ACTION_MIN_CHARS = 10`, which blocks "." and "n/a"
     without obstructing a terse but genuine answer. Dimension and actions travel
     as a pair: choosing an area commits the leader to saying what they will do
     about it. Stray text left against an UNCHOSEN dimension is ignored rather
     than blocking, so changing your mind and clearing the dropdown works. The
     error names the offending priority numbers and offers the escape route of
     resetting that dimension to "Select a dimension...".
   - Saved on both "Save & Continue Later" and Submit, and on Submit they are
     written BEFORE `submit_feedback` so the irreversible severing step cannot
     lose what the leader typed.
   - Verified end-to-end through the real form UI: duplicate guard blocks with a
     clear message, happy path saves both priorities with their action text,
     priorities survive severing, and the section renders correctly in a
     generated .docx with the score comparison.
7. ~~White-label rename to Bentley Compass 360.~~ DONE 2026-08-04 — see the
   white-label subsection in section 5 for what changed, what was deliberately
   left alone, and the one outstanding infrastructure item (the app URL).
8. Write the two guidance artefacts (rater-facing: "comment on behaviour and its
   effect, not identifying incidents"; coach/debrief: "do not attempt to
   attribute feedback; discourage the leader from doing so"). These carry part
   of the anonymity protection per the relaxed stance.
11. ~~Rework reports and copy for the phased timeline; make reports live working
   documents.~~ DONE 2026-08-04 — see section 1a for the timeline and what it
   drove. Changes: corrected `add_what_happens_next` sequence; `add_writing_lines`,
   `add_writing_prompt` and `add_priority_capture_table` helpers added to
   report_generator.py; ruled lines under every Reflection Question; a writing
   block in the Full 360's Next Steps; an additive priority-capture table in both
   reports (wording differs by report type, and there is a third variant for a
   leader who stored no priorities at all, which can happen for anyone who
   submitted before at least one became compulsory); Reflection Question 4
   reframed because it duplicated the priorities section; Self-Assessment "About
   This Report" now names both stages and tells the reader to write on the
   document; portal welcome copy now frames nomination as the current step;
   "360-degree self-assessment" corrected to "leadership self-assessment" in the
   invitation and reminder emails, since a self-assessment is not a 360.
   The TOOL NAME was reviewed and deliberately KEPT as Bentley Compass 360: the
   self-assessment is stage one of the same instrument (same 45 items, same
   framework), each report already carries its own subtitle, and the About section
   now explains the two stages. If the human ever revisits this, the best
   alternative is dropping to "Bentley Compass", at the cost of being nearly
   identical to the programme name.
10. ~~Fix button text contrast across all UI.~~ DONE 2026-08-04 — raised by the
   human ("submission buttons text is currently white, which is hard to read").
   See the button contrast subsection in section 5. NOTE THE RULE FOR FUTURE WORK:
   in that CSS block, never set a text colour without also setting its background.
9. ~~Housekeeping: add a `.gitignore`.~~ DONE 2026-08-04 — excludes
   secrets.toml/.env, `*.db`, `reports/` (generated .docx can contain real
   feedback), `__pycache__`, and `.claude/settings.local.json`. Rules verified
   with `git check-ignore`. `.claude/launch.json` is deliberately NOT ignored so
   a fresh session can start the app without rebuilding the config. Nothing
   sensitive was ever tracked, so no history rewrite is needed.

Do NOT merge any of this to `main` until the human explicitly says so, after
they've reviewed it working on the sandbox.

---

## 8a. Leader Portal Walkthrough: Full Findings — DONE 2026-08-29
A genuine end-to-end test of the leader/rater journey (nominating, CSV
import, deleting, reminders, completing feedback), organised by priority.
All Code-owned items (A-F below) addressed; the four "not for Code" items
(duplicate detection, time estimate wording, bookmark reminder, bounce-
notification observation) were deliberately left as flagged decisions for
Ian, not resolved unilaterally.

**A1, invitation email nomination guidance out of sync with portal copy.**
The email's "Who should you nominate?" box (`_get_portal_invitation_html`
in `email_sender.py`) still read the OLD wording ("Minimum 3, suggest 5",
"Optional... add at least 3") from before the portal's own category copy
was finalised. Root cause: two independent hardcoded copies of the same
numbers, one in `leader_portal.py`'s `RATER_REQUIREMENTS`/
`CATEGORY_REQ_TEXT`, one in the email template - nothing kept them in
sync. Fixed at the source: `RATER_REQUIREMENTS` MOVED from
`leader_portal.py` to `framework.py` (alongside `ANONYMITY_THRESHOLD`,
which it already depended on) so both files import the same numbers.
`email_sender.py` gained `NOMINATION_GUIDANCE_TEXT`, built from those
numbers with the identical wording template `leader_portal.py`'s
`CATEGORY_REQ_TEXT` uses (plain text, not HTML-bolded like the portal's
version - the email's table already bolds the category NAME in its own
column). The email table also gets a genuine layout fix: the label column
is now a fixed 110px with `white-space:nowrap` and both columns
`vertical-align:top`, so "Line Manager" and "Direct Reports" can never
wrap onto a second line the way they did before, and Others' longer line
wraps cleanly without misaligning against its label. Verified by rendering
the real HTML to a local file and screenshotting both a desktop width and
a 375px mobile-email width (the email itself uses a fixed, non-responsive
container width by design, unrelated to this fix - only the internal
table's own wrapping was in scope).

**A2, consent screen doesn't account for the Boss/Line Manager exception.**
The rater consent gate's `ui_consent_rater_body_1` bullet
(`render_consent_gate` in `feedback_form.py`) made a blanket claim
("scores are only ever shown combined with others") that contradicted a
real, already-built exception: Boss/Line Manager feedback (scores AND
comments) is always shown attributably, never blended, because that
category's max of 2 can never reach `ANONYMITY_THRESHOLD` on its own. The
rater FORM's own instructions (`ui_instructions_other_4`) already stated
this correctly for comments ("unless you are the direct line manager") -
the consent screen just hadn't caught up for scores. Fixed by adding the
same exception, matching wording/tone. The SELF consent variant was
checked and confirmed NOT to need the same fix - it makes no "shown
combined with others" claim at all, since a self-assessment was never
blended with anyone else's. Swept for the same gap elsewhere and found
one more: the Guidelines page's "A note on anonymity" card
(`render_portal_guidelines` in `leader_portal.py`) made the identical
unqualified claim to the LEADER - fixed the same way.

**A3, "Response progress only ever shows as a total across each
category" is inaccurate.** This line, in Begin Here's "What your rater
list does and doesn't show" section (`leader_portal.py`), implied
category-level granularity that doesn't exist - the actual behaviour is a
single overall aggregate across all categories combined (e.g. "11
invited... 64% response rate"), never broken down by category. Reworded
to "Response progress only ever shows as an overall total across
everyone invited, never broken down by category or by name." Swept for
the same phrasing elsewhere - no other instances found (the other
"per-category" hits in this file all correctly describe NOMINATION
guidance, which genuinely is per-category, not response progress).

**A4, "Each page saves as you go" doesn't hold if the page isn't fully
completed.** Investigated the actual save mechanism before touching the
copy, per the task's own instruction not to assume: the rating widgets
sit inside `st.form` (which doesn't fire `on_change`), so nothing saves
from selecting a rating or typing a comment alone - confirmed live,
zero-DB-write, by rating one item and checking `raters.draft_ratings`
directly. But Save & Continue Later turned out to have NO completeness
check at all (`_render_dimension_page`'s `save_clicked` branch, unlike
`continue_clicked`, which blocks until every item is rated) - confirmed
live by rating only 1 of 5 items on a page, clicking Save & Continue
Later, and finding `draft_ratings = {"1": "3"}` genuinely saved with the
other four correctly absent. So this was NOT the feature gap the task
worried it might be - Save & Continue Later already correctly allows
leaving a page partially filled. The fix is purely the copy
(`ui_instructions_other_6` in `feedback_form.py`), which now accurately
states that nothing saves automatically and names which of the two
buttons does what: "Nothing saves automatically as you type or select an
answer. Click **Save & Continue Later** at any point, even with a page
only partly finished, or complete a page and click Continue - either one
saves your answers so far."

**B, confirmed bug: deleted rater still appears in the nominated list.**
Root-caused, not just patched: `leaders.nomination_roster` is a separate,
persisted JSON snapshot of nominees (kept independent of `raters` rows
specifically so it survives identity severing - see section 5's severing
subsection) - and `delete_rater` in `database.py` never touched it, only
the live `raters` row. Every OTHER surface (the category ring, admin
totals, the progress bar) reads live from `raters` and correctly updated
on delete; "People You've Nominated" reads the roster snapshot instead,
so a deleted person kept showing there indefinitely. Not a Streamlit
cache - a genuinely separate copy of the data nothing was keeping in
sync. Fixed: `delete_rater` now also removes the matching roster entry
(new `_remove_from_nomination_roster`, matching identity the same way
`update_nomination_entry` already does - by email where there is one,
else by name+relationship). VERIFIED LIVE end to end, twice (the first
attempt was run against a server that hadn't picked up the fix yet - this
project's dev server doesn't hot-reload, a lesson already documented
elsewhere in this file, relearned here): added a real rater through the
actual Nominate Raters form, confirmed it appeared in the list, deleted
it through the actual admin dashboard's Links & Tracking delete button,
and confirmed the list updated immediately - matching what the ring/
admin totals/progress bar already correctly did.

**C, deleting a rater who has already completed feedback.** Investigated
before deciding on a fix, per the task's own instruction. The DB-level
safeguard already exists and already works: `delete_rater` refuses
outright when `completed_at IS NOT NULL` (a guard documented in this file
since 2026-08-14). VERIFIED LIVE with a genuine completed-and-severed
test rater (45 real ratings, 2 real comments): clicking the admin
dashboard's delete button on it left the row, all 45 ratings, and both
comments completely untouched. So there was no data-loss risk to fix -
the actual gap (also already documented as a KNOWN GAP in this file) was
purely that the admin dashboard's delete button ignored `delete_rater`'s
return value, so a refused delete looked identical to a successful one:
no error, no toast, the row just staying put with no explanation. Fixed
in `admin_dashboard.py`: the button now checks the return value and shows
`st.toast("Can't delete: this rater has already submitted feedback.")`
when refused. VERIFIED LIVE: same test rater, same delete button, now
shows the toast instead of silently doing nothing.

**D, stale content on Overall Feedback → Development Priorities
transition.** Investigated rather than dismissed as a one-off. This is
the exact same transition that caused the real, reproducible crash fixed
in the "Two follow-up fixes"/scroll-to-top work above (call-ordering
issue, already fixed) - plausible that a milder "stale content" symptom
was a lesser manifestation of the same timing sensitivity. Attempted live
reproduction 5 times in a row (fresh page loads, genuine clicks, no
JS-injected shortcuts) on the current, already-fixed code - did not
reproduce once. NOT confirmed as fully resolved with certainty (a rare,
one-off intermittent issue can't be proven absent from 5 attempts alone),
but no evidence found that it persists on the current code either. Worth
a note if it recurs: capture a screenshot immediately if seen live again,
since the one report so far had none to compare against.

**E, extend the scroll-to-top fix to Leader Portal navigation.** The
feedback form's dimension-page scroll-to-top (see the "Three Fixes" entry
above) only covered that form - every navigation action in the leader
portal itself (Begin Here → Overview, into Guidelines, any topbar nav
item) left scroll position wherever it was on the previous page. Fixed
with a direct port of the same mechanism: `_scroll_to_top_if_view_changed
(view)` in `leader_portal.py`, keyed on `view` instead of `page_idx`,
reusing every lesson already learned building the original (plain
`el.scrollTop = 0`, not `scrollTo()`; embed `view` into the iframe's HTML
so Streamlit can't treat repeated calls as the same unchanged element;
fire AFTER the view's content renders, not before). Since `_go_to_view`
is the single choke point ALL portal navigation already goes through
(topbar nav, category-card "Nominate" links, Begin Here's own CTA), one
call site in `render_leader_portal`'s dispatch covers every case. VERIFIED
LIVE: genuine scroll-down-then-click on Overview→Nominate, Nominate→
Guidelines, Guidelines→Help, and Begin Here's own "Go to Overview" CTA -
all four correctly reset `stMain`'s scrollTop to 0, confirmed via
`getBoundingClientRect`/`scrollTop` reads, not just visual screenshots.

**F, category card pills still cramped against the bottom edge.**
Re-checked properly this time, with real measurements, not another quick
single-width tweak - this exact spot had already been patched multiple
times before and kept resurfacing. Root-caused precisely via a full
ancestor-chain measurement (`getBoundingClientRect` at every level):
Overview's cards share their column with a "Nominate" button below them,
and the existing `height:100%` cascade (four CSS rules, added 2026-08-27
to force equal card heights) resolves the card's flex-basis against the
column's full height, but default `flex-shrink` then compresses it back
down to make room for that button sibling - measured 357px against the
card's own true content need of 371px (the min-height reservations +
padding + gaps), with the 14-16px shortfall silently eaten by
`overflow:hidden`, consuming almost all the intended bottom padding.
Trimming the card's own internal spacing (tried first) didn't fix it:
shrinking the card's natural content proportionally shrank what the
matched height resolved to as well, since the two are entangled - the
deficit persisted at the same ~16px regardless of how much was trimmed.
THE ACTUAL FIX: the four categories' min-height floors (tuned 2026-08-27
to the worst-case text length across all four, at the narrowest
multi-column width) are now IDENTICAL regardless of category, which
means the cards are ALREADY guaranteed equal natural height without any
explicit height-matching machinery - confirmed live by temporarily
setting the whole chain to `height:auto` and re-measuring: still equal
(373px each), no clipping, comfortable 21px gap. The entire four-rule
`height:100%` cascade plus `.cp-card`'s own `height:100%` were REMOVED
(matching the same "stop forcing it, remove the constraint" reasoning
already used once before in this exact card, for the ring-placement fix).
VERIFIED LIVE across a full width sweep (360/430/600/645/690/768/902/
1400px) on BOTH Overview (has the button) and Nominate Raters (read-only,
no button) - zero clipping and a comfortable 17-19px gap at every width
tested. ONE HONEST RESIDUAL FINDING, not silently hidden: at 645-690px
specifically, one card (whichever category's actual wrapped text happens
to exceed even the generously-tuned floor at that exact width) renders
~14px taller than its three siblings - the min-height floors guarantee a
MINIMUM, not a maximum, so a card whose real content occasionally exceeds
even that floor will legitimately be taller. Confirmed this does NOT
affect pill position (the `footTop` of all four cards stays byte-
identical at every width, including 645-690px) or spacing (17-19px
throughout) - only the card's own border sits slightly higher for the
shorter siblings. A real, minor trade-off against the alternative (force
exact pixel-equal card height, at the cost of reintroducing the clipping
bug this task exists to fix) - not chased further within this task's
scope, since the actual reported bug (the cramped pill) is fixed
everywhere tested.

Test data used across this task (rater ids up to 164, various tokens)
all created fresh and deleted after verification; leader 1's 13-rater /
12-entry-roster baseline confirmed unchanged throughout.

### Category card pills: "Minimum 3" on Others card not bold — FIXED 2026-08-29
Ian spotted this directly: the Others category card's minimum number
wasn't bold, unlike Line Manager/Peers/Direct Reports. Confirmed in
`CATEGORY_REQ_TEXT` (leader_portal.py) - Boss/Peers/DRs all wrap their
minimum in `<b>...</b>`, Others' entry was the one left plain when the
"Final Category Guidance Copy" pass (2026-08-27) rewrote its wording.
Checked `GUIDELINE_CATEGORIES`'s parallel `badge` text too - that one
never bolds any category's number, so it's already internally consistent
and didn't need touching. Fixed, verified live on both Overview and
Nominate Raters.

### Duplicate Rater Name Warning — BUILT 2026-08-29
Approved design (soft, non-blocking nudge; exact name match, case-
insensitive and trimmed, within the same category only; checked against
both the existing list and, for CSV, other rows in the same batch).

**A real correctness issue found before any live testing could even
start**: every one of leader 1's existing raters was already severed
(name/email nulled after responding), so a duplicate check sourced from
`existing_raters` (the live `raters` table) would have been blind to
exactly the people most likely to be a genuine duplicate target - the
severed name normalises to `''`, which never matches a real typed name.
Fixed by sourcing the name-check from `leaders.nomination_roster`
instead (fetched once in `render_portal_nominate` as `nomination_roster`,
threaded down into `_render_csv_import`/`_parse_rater_csv`) - the same
roster "People You've Nominated" already reads from for the identical
reason (survives severing by design). `existing_raters` is still used
for its original purposes (category counts/caps); only the NAME check
moved.

- `_normalise_name(name)` (case-insensitive, trimmed) and
  `_find_duplicate_name(raters, name, relationship)` in `leader_portal.py`
  are the single shared definition of "same name" both the manual form
  and the CSV importer use, so the two can't drift on what counts as a
  match. Deliberately never checks across categories - see that
  function's own docstring.
- **Manual "Add a Rater" form**: `clear_on_submit` changed from `True` to
  `False`, and the three widgets given explicit keys
  (`add_rater_name`/`add_rater_email`/`add_rater_relationship`), so a
  duplicate-triggered submit can hold the typed values in place rather
  than Streamlit auto-clearing them. On a genuine collision, the add is
  NOT committed - the typed values go into
  `st.session_state['pending_duplicate_add']` instead, and a warning
  ("There's already a {category} called {name} on your list. Add this
  one anyway?") renders with Add anyway / Cancel. Add anyway commits
  exactly as an unblocked add would; Cancel just clears the pending flag,
  deliberately leaving the form's own fields untouched so a typo (e.g.
  the email) can be fixed without retyping the rest. A genuine add
  (either path) sets `_clear_add_rater_form`, checked at the TOP of the
  function on the next run (before the widgets are recreated) to reset
  their session_state - has to happen there, since Streamlit refuses to
  set a widget's value after it's already been instantiated in the same
  run.
- **CSV import**: `_parse_rater_csv` now returns `(rows, problems,
  warnings)`, not `(rows, problems)` - `warnings` are the non-blocking
  duplicate-name nudges, built the same way `seen_emails` already builds
  its (blocking) email-duplicate set: seeded from the roster, then grown
  as each row is processed, so a row colliding with an EARLIER row in the
  same upload is caught too, not just a row colliding with someone
  already on the list. Rendered in `_render_csv_import` right after the
  preview table, before Import All - which stays fully enabled
  regardless of how many warnings show, since these are informational,
  never a reason to withhold the import (unlike `problems`, which still
  blocks the whole import as before).
- VERIFIED LIVE end to end through the real Streamlit rerun cycle (DB
  state checked before/after every step, not just visual screenshots -
  one early screenshot round genuinely was stale/mid-transition and
  would have been misread as a failure without the DB check):
  - Manual form: submitting "Jon Newman" as Peer (an existing Peer)
    correctly held the add and showed the warning; clicking Add anyway
    committed a real second "Jon Newman"/Peers row and cleared the form
    (confirmed via `raters` table and the page's own live DOM state, not
    the screenshot, which lagged behind both).
  - Manual form: submitting "Simon Moreton-Thickett" as Peer (an
    existing Peer) showed the warning; clicking Cancel left the name/
    email/relationship fields exactly as typed (confirmed via each
    input's actual `.value`) and added nothing to the database.
  - Manual form: the same "Simon Moreton-Thickett" resubmitted as Direct
    Report (a different category, no existing DR with that name) showed
    NO warning and committed immediately - confirmed live.
  - CSV import: a 5-row file (3x "Priya Anand"/Peer, "Jon Newman"/Peer,
    "Raj Patel"/Direct Report) uploaded via a synthetic
    `DataTransfer`-based file input (no OS file picker available to this
    tooling) produced exactly three warnings - the 2nd and 3rd Priya
    Anand rows (colliding with the 1st, within the same batch) and the
    Jon Newman row (colliding with the existing roster) - with the FIRST
    Priya row and Raj Patel correctly unflagged. Import All stayed
    enabled throughout (confirmed via the button's own `.disabled`
    property, not appearance) and, on click, all 5 rows landed in
    `raters` with the correct names/emails/categories, including every
    flagged duplicate.
- A ROOT CAUSE FOUND MID-TEST, not a bug in the feature itself: the very
  first manual-form test appeared to silently skip the warning entirely
  and add the duplicate straight through - traced to the dev server
  still running the code from BEFORE the roster-sourcing fix above (this
  project's dev server doesn't hot-reload on save, a lesson already
  documented elsewhere in this file and relearned here). Restarting the
  server and rerunning the identical test produced the correct warning.
- Test raters and roster entries created for this verification (Jon
  Newman #2, Simon Moreton-Thickett as DR, the Priya Anand x3/Raj Patel
  CSV batch) all deleted after; leader 1's 13-rater / 12-entry-roster
  baseline confirmed unchanged.

### Duplicate Rater Name Warning: cross-category reversal — DONE 2026-08-29
Same day as the build above, Ian reversed the original same-category-only
decision after seeing the feature live: a name reused under a DIFFERENT
category might mean a leader changed their mind about which group a
nominee belongs in, or picked the wrong one first time - worth a nudge
too, not silently ignored.

- `_find_duplicate_name(raters, name)` dropped its `relationship`
  parameter and now searches across ALL categories; the caller compares
  the match's own category against the new entry's to pick same-category
  vs cross-category wording.
- Manual form: same-category wording unchanged ("...Add this one
  anyway?"). Cross-category wording additionally points at the fix Ian
  asked for: "...on your list, under a different category. If this is
  the same person but you need to change their category, you can edit
  them in People You've Nominated below instead of adding a new entry.
  Add this one anyway?" Both variants keep the identical Add anyway /
  Cancel mechanism already built - only the message text branches.
- CSV import: `_parse_rater_csv`'s `seen_names` (a flat set of
  `(relationship, name)` tuples) became `seen_by_name` (a dict mapping
  each normalised name to the SET of categories already seen for it), so
  a row can be told apart as a same-category repeat versus a
  cross-category reuse. The cross-category CSV wording points at fixing
  it via People You've Nominated AFTER import (there's no per-row inline
  edit in a batch import), not before.
- VERIFIED: the manual form live (added "Jane Smith" - an existing Direct
  Report - as Peer; the cross-category warning rendered with the exact
  wording above, no DB write happened while it was showing, and Cancel
  correctly dismissed it with still nothing written) and the CSV path via
  a direct call to the real `_parse_rater_csv` (not a reimplementation)
  with a same-category repeat, a cross-category reuse, and a clean row
  all in one file - each got exactly the wording its own case should.
- No test data left behind: the manual-form spot-check ended on Cancel,
  so nothing needed cleaning up; leader 1's 13-rater baseline reconfirmed
  unchanged.

### Admin Dashboard: Rater List Leaked Identity by Elimination — FIXED 2026-08-30
Ian's own investigation, prompted while reviewing the duplicate-name work
above: does the Admin Dashboard's Links & Tracking view retain severed
raters' names? Confirmed it does not for the rater-facing side (severing
is unaffected), but the ADMIN side genuinely leaked identity, via a
mechanism this session traced precisely before proposing any fix.

- **The leak, confirmed against the actual code**:
  `render_links_tab`'s per-rater row used
  `display_name = rater.get('name') or f"{category} {i}"` - a real name
  for anyone not yet completed (severing hasn't nulled it yet), a generic
  positional label for anyone who has, tagged "Pending"/"Complete"
  respectively. Within one category, this means the non-completers are
  named and the completers are anonymous BUT COUNTABLE - so with 5 Peers
  and 4 responses, the 1 named "Pending" row identifies by elimination
  who the other 4 anonymous "Complete" rows must be, since Ian already
  knows all 5 names from having reviewed or nominated them himself. The
  risk sharpens as fewer remain outstanding - at 1 of 5 there is no
  ambiguity left at all. Confirmed separately that report-generation-time
  folding (Tier 1/2 in `get_leader_feedback_data`) never touches
  `raters.relationship`, so a lone folded "Others" respondent still shows
  standalone here as an unambiguous single "Complete" row - the worst
  case, since this screen gave a group of one zero protection even though
  the report itself never shows it unfolded.
- **Ian's first instinct (anonymise names once any completion occurs in a
  category) was explicitly rejected before being built**, because it
  would have broken a genuine, common operational need: Ian regularly
  has to find and act on a SPECIFIC named individual on a leader's rater
  list, most often because the leader has asked for that person to be
  removed for a reason they can't action themselves. Names disappearing
  the moment responses start coming in would remove exactly that ability
  at the point in a cohort's life it's most likely to be needed. The
  actual leak needs BOTH a real name AND an individual completion status
  on the same row at once - removing either stops it, and removing names
  specifically was the one Ian actually needed kept.
- **The fix, per Ian's own final spec**: real names stay visible on every
  row, permanently, no exceptions - unchanged from before. Individual
  per-row "Pending"/"Complete" status is removed entirely, replaced by a
  single category-level aggregate line ("4 of 5 responded"), never tied
  to an individual row. This removes the elimination mechanism itself -
  there is no longer a per-row signal to eliminate against - while
  leaving every real name fully intact everywhere, which is what Ian's
  actual workflow depends on.
- **A real problem with recovering the name at all**: severing nulls
  `raters.name`/`email` on submission, which is exactly why the old code
  fell back to a generic label for completers in the first place - so
  simply "always show the name" wasn't available without a genuine schema
  change. `leaders.nomination_roster` (the leader-facing list that
  survives severing) couldn't be reused here: it has no stable join key
  back to a specific `raters` row once email is also nulled, and matching
  by name+relationship risked misattributing rows in an edge case. Fixed
  with a new admin-only shadow-column pair, `raters.admin_name`/
  `admin_email` (`_safe_add_column`, same pattern as `consent_given`),
  populated identically to `name`/`email` at creation (`add_rater`) and
  kept in sync on legitimate corrections (`update_rater`), but
  DELIBERATELY never touched by `sever_rater_identity` - confirmed by
  leaving its actual UPDATE statements completely unchanged, still only
  nulling `name`/`email`, still overwriting `email_log.to_email` to
  `'[severed]'`. A one-time backfill
  (`UPDATE raters SET admin_name = name WHERE admin_name IS NULL AND name
  IS NOT NULL`, mirrored for email) covers every row that hadn't yet been
  severed at the time this shipped. Rows already severed BEFORE this fix
  are genuinely unrecoverable - shown as "Name not recorded (submitted
  before this update)" rather than guessed at, an honest disclosed gap,
  not a silent one.
- **Two further leaks of the same category found and closed in the same
  pass, neither explicitly named in Ian's spec but caught by the
  project's standing "sweep for the same gap" practice**:
  - The Links & Tracking CSV export had its own `Status` column
    ("Complete"/"Pending") sitting beside `name`/`email` - removed
    entirely, and the name/email columns switched to `admin_name`/
    `admin_email` so the export doesn't regress to the old severed-blank
    behaviour either.
  - The "+Add email" button and the invitation/reminder buttons'
    visibility were BOTH previously correlated with completion status
    indirectly - the live `email` field goes blank on severing, so
    "+Add email" appearing was itself a completion tell, and the
    invitation/reminder buttons were hidden outright for completed
    raters, which is a status signal by omission. Fixed by driving both
    off `admin_email`/`has_email` (unaffected by severing) instead of the
    live `email` field, and by moving the completion check from button
    VISIBILITY into the button's CLICK HANDLER - a completed rater's row
    looks identical to any other, but clicking Send now shows a graceful
    toast ("Already completed - nothing to send.") instead of silently
    doing nothing or never rendering the control in the first place.
  - `get_email_log_for_leader`'s query (`r.name as rater_name`) was a
    THIRD instance, found during this same pass - switched to
    `r.admin_name`. ONE RESIDUAL GAP, DELIBERATELY NOT FIXED, FLAGGED IN
    CODE: that same modal's `to_email` column still shows the literal
    `'[severed]'` string for a completed rater's historical log rows,
    which is itself a completion tell. Closing this fully needs a new
    admin-only, never-severed column on `email_log` itself - judged
    beyond the scope of this pass and flagged rather than silently left.
- **Deletion safety was deliberately NOT duplicated here.** Ian's spec
  explicitly separates this: the completed-rater deletion guard is
  walkthrough item C (already built - `delete_rater` refuses when
  `completed_at IS NOT NULL`, admin UI shows a toast on refusal rather
  than silently doing nothing). Removing the status badge does not
  reopen that risk, since deletion safety was never based on Ian noticing
  the badge - it's enforced at the point of deletion itself, independent
  of what the row displays.
- **VERIFIED LIVE against a purpose-built test leader** ("Elimination
  Test Leader", matching Ian's own example numbers exactly - 5 Peers, 4
  completed (Alice/Bob/Carol/Dave) + 1 pending (Eve), plus 1 completed
  lone Others (Frank)) - existing leader 1 couldn't be used for this
  specific check, since every one of its raters was already either
  severed or created via a legacy path with no name captured at all.
  Confirmed directly in the database that the 4 completed Peers plus
  Frank had `name = NULL` (correctly severed) while `admin_name` held
  the correct real name, and Eve (pending) still had both columns intact
  with `completed_at IS NULL`. Screenshotted the live Links & Tracking
  view: "**Peers** (5)" with "4 of 5 responded" directly beneath it, then
  all 5 rows (Alice, Bob, Carol, Dave, Eve) with real names, real emails,
  and delete buttons - completely uniform, zero visual distinction of any
  kind between the 4 completed and the 1 pending row. Scrolled to
  "**Others** (1)" / "1 of 1 responded" and confirmed Frank Other's row
  identically uniform - real name shown, nothing on the row revealing he
  is the one who responded. Both of Ian's own explicit must-verify-live
  scenarios (4-of-5, no longer eliminable; 1-of-1 thin category, not
  distinguishable) confirmed satisfied. Separately re-confirmed
  `delete_rater(174)` (a completed Peer) still returns `False` and leaves
  the row untouched, unaffected by the rendering rewrite. Test leader and
  all 6 raters (plus their ratings/comments/email_log rows) deleted after
  verification.
- Committed and pushed to both `production` (`1fa14fb`) and `sandbox`
  (`cc9572a`) 2026-08-30, alongside the rater-correction feature below.

### Admin Dashboard: Rater Email/Relationship Correction — BUILT 2026-08-30
Ian's own observation, prompted by the elimination-leak fix above: the
Leader Portal already lets a leader correct a nominee's email and
relationship (typos, wrong category), but the Admin Dashboard never got
the equivalent feature. Built as a close parallel to
`leader_portal.py`'s own mechanism (`_validate_nomination_change`/
`_apply_nomination_correction`), with one constraint neither of those
needed to consider: it must not reopen the elimination leak just fixed.

- **The constraint that shaped the whole design**: an Edit control whose
  visible behaviour (enabled/disabled, shown/hidden, a different result
  message) differed by completion status would recreate the exact same
  class of leak fixed hours earlier, just through a new route - "can this
  admin tell which raters are pending vs completed by whether Edit
  behaves differently" is now a standing check for anything added to this
  screen, not just the specific badge that was removed. So the Edit
  button and the edit form it opens render IDENTICALLY on every row,
  completed or not - same fields, same layout, same "Rater details
  updated." message either way. The actual protections (below) are
  enforced silently inside the save logic, never through a visible
  difference in the form itself.
- `_validate_rater_correction`/`_apply_rater_correction` in
  `admin_dashboard.py` are parallel functions, not shared imports from
  leader_portal.py (avoids a leader_portal <-> admin_dashboard import
  cycle) - kept deliberately in step with the same rules:
  - Email format validated (must contain '@' if provided, blank allowed).
  - A relationship change is blocked with a full-width `st.error(...)`
    if the target category is already at `RATER_REQUIREMENTS[...]['max']`
    (e.g. Line Manager's cap of 2) - identical rule to the leader
    portal's own cap enforcement.
  - For a rater who has NOT yet completed: `db.update_rater(...)` updates
    `email`/`relationship` normally (mirrors into `admin_name`/
    `admin_email` automatically, per that function's existing behaviour),
    and a changed email triggers a fresh invitation send if email is
    configured - matching leader_portal's own "only re-invite when the
    address actually changed" reasoning.
  - For a rater who HAS completed: `raters.email` stays NULL (writing an
    address back would re-identify a severed response) and
    `raters.relationship` never changes (their answers belong to the
    category they were invited under - see `update_rater`'s own
    docstring). Only `admin_email`, the permanent admin-only record,
    gets corrected. This happens silently - no error, no different
    message - so attempting a blocked relationship change on a completed
    rater looks, from the UI, exactly like a successful save.
  - `leaders.nomination_roster` is updated UNCONDITIONALLY in both
    cases, matching leader_portal's own behaviour exactly - and for the
    same underlying reason, not just consistency for its own sake: if
    the roster only updated when the live row could still be changed,
    the leader could infer completion status from whether their own
    view of the roster changed after an admin correction. A safe no-op
    if the rater was never on the roster to begin with (e.g. added via
    this dashboard's single-add or Quick Add forms, which don't
    currently write to the roster - a separate, pre-existing gap, not
    introduced by this feature).
  - Self is excluded from the relationship dropdown (fixed label
    instead) - there's only ever one Self per leader, so reassigning it
    is meaningless. This is keyed off relationship, not completion, so
    it doesn't reintroduce any leak: every Self row, completed or not,
    gets the identical fixed-label treatment.
- **A real layout bug found live before this could be called done**: the
  Save/Cancel button column was too narrow (1.3 of ~7.9 relative units,
  split into two), and the validation error was rendered INSIDE that same
  narrow column - both wrapped one character per line at the project's
  own standard 902px test width, confirmed via screenshot while testing
  the Line-Manager-at-max case. Fixed by widening the button column
  (1.3 -> 2.4) and, more importantly, moving the error/success handling
  entirely OUTSIDE the column layout - `st.error(...)` now renders
  full-width below the row regardless of how narrow the button columns
  are, rather than being trapped inside whichever column the triggering
  button happened to sit in.
- **VERIFIED LIVE** against a purpose-built test leader ("Edit Test
  Leader": 2 Line Managers at the real max of 2, one pending Peer "Pat
  Peer", one completed/severed Peer "Pete Peer", both added via
  `add_rater` + `add_to_nomination_roster` so both admin_name/admin_email
  and the roster were populated realistically):
  - Confirmed the Edit form for the pending and the completed rater
    render pixel-identical (same fields, same layout) - no visual tell.
  - Attempted moving the pending Peer into Line Manager (already at max
    2): blocked with "Already at the maximum of 2 for Line Manager. Move
    or remove one first.", rendered full-width and legible, nothing
    written.
  - Corrected the pending Peer's email for real: `raters.email` and
    `admin_email` both updated to the new address, relationship
    unchanged, and the roster entry updated to match - confirmed via
    direct DB query, not just the UI.
  - Attempted correcting the COMPLETED Peer's email AND moving them to
    Others: `admin_email` updated to the new address, `raters.email`
    stayed NULL, `raters.relationship` stayed 'Peers' (the attempted
    move was silently dropped) - confirmed via direct DB query. The
    roster entry, per the unconditional-update design above, DID show
    'Others' - a deliberate, documented divergence between the roster's
    cosmetic display and the real scored category, identical to what
    already happens today via the leader portal's own edit path for a
    completed rater, not a new inconsistency introduced here.
  - Confirmed Cancel discards typed changes with no write - typed a
    throwaway email, clicked Cancel, confirmed via direct DB query that
    neither `email` nor `admin_email` changed.
  - Re-confirmed the completed-rater delete guard (built in the earlier
    elimination-leak fix) still works correctly under the new five-column
    layout - clicking delete on the completed Peer still shows "Can't
    delete: this rater has already submitted feedback." and leaves the
    row untouched.
- Test leader and its 4 raters (plus ratings/comments/email_log rows)
  deleted after verification.
- Committed and pushed to both `production` (`1fa14fb`) and `sandbox`
  (`cc9572a`) 2026-08-30, alongside the elimination-leak fix above.

### Bookmark Reminder and Realistic Time Estimate — DONE 2026-08-30
Two small, related copy fixes across every place someone is invited to
complete something, requested together: nothing told a rater or leader
they could bookmark their way back if they needed more than one sitting,
and the time estimate everywhere ("approximately 15-20 minutes") had
drifted well short of how long the 45-item paired instrument with two
open prompts actually takes in practice.

**Time estimate.** Every occurrence of "approximately 15-20 minutes" was
a search away - only two, both in `email_sender.py` (the rater invitation
and the rater reminder email; `feedback_form.py` and `leader_portal.py`
had no time estimate at all). Both now read "It should take around 30
minutes to complete, depending on how much detail you add in your
comments." - Ian's own wording, kept close to verbatim.

**Bookmark reminder.** Added in six places, wordsmithed per location
rather than one string pasted everywhere, since the audience and the
thing being bookmarked genuinely differ:
- `_get_rater_invitation_html` (email_sender.py) - new
  `email_bookmark_note`, shared for Self and everyone else since nothing
  in it is relationship-specific. Deliberately says "click Save &
  Continue Later", not "your progress saves automatically" - nothing in
  this survey auto-saves (see `ui_instructions_other_6`'s own docstring),
  and restating that overclaim here would undo the correction already
  made once to the in-app copy.
- `_get_reminder_html` (email_sender.py) - a shorter `email_reminder_
  bookmark_note`, not the same text reused. Someone getting a reminder
  has likely already started, so this leads with "haven't finished yet"
  rather than re-explaining the whole save mechanism from scratch.
- `_get_portal_invitation_html` (email_sender.py) - new `email_leader_
  bookmark_note`, framed around the leader's own repeat visits (add
  raters, check progress, send reminders) rather than "multiple
  sessions", since nominating raters isn't a single form to finish, it's
  an ongoing task across a cohort's life.
- `render_portal_guidelines` (leader_portal.py) - a new `cp-sub-note`
  styled box directly under the page intro, above the category cards.
  Reused the existing light beige tip style rather than inventing a new
  visual idiom for a single line.
- `render_portal_begin_here` (leader_portal.py) - a new watch-card
  appended to `BEGIN_HERE_WATCH_CARDS` ("Worth bookmarking this page"),
  after the existing five - not urgent troubleshooting info like its
  neighbours, so it goes last rather than competing for the "two most
  likely practical questions" priority slot at the top.
- `feedback_form.py`'s own survey instructions - the "other" (rater)
  variant already explained resuming (`ui_instructions_other_6`, added
  during an earlier walkthrough fix); extended with the same bookmark
  sentence. Self had NO equivalent explanation of the save mechanism at
  all until now - a real, pre-existing gap, not something this task
  introduced - closed with a new `ui_instructions_self_3`, identical in
  substance to the rater version since nothing about resuming a
  self-assessment is relationship-specific.
- Genuinely considered and left out: the admin dashboard. Nothing there
  is a multi-session task for the person completing it (an admin adding
  raters isn't the one who has to come back and finish a survey), so a
  bookmark reminder there would be solving a problem that doesn't exist
  on that screen.

VERIFIED LIVE: all three emails regenerated via their real functions
(not reimplementations) to a local HTML file and screenshotted in the
browser - correct wording, correct placement, no layout regression.
Guidelines and Begin Here checked live in the running app (leader 1's
portal). The feedback-form instructions checked against both variants -
a real pending Peer rater (existing) and a fresh throwaway Self rater
(`Copy Test Self`, created for this check since leader 1's own Self was
already completed and severed, deleted immediately after) - confirming
the new self-assessment paragraph renders correctly and the rater
paragraph's pre-existing bold/green styling isn't disturbed by the
appended sentence.
- Committed and pushed to both `production` (`809f583`) and `sandbox`
  (`1b5df9f`) 2026-08-30.

### Temporary Font Comparison Route Removed — DONE 2026-08-31
The `?fonttest=1` scaffolding (`app.py`) had served its purpose - Ian
picked genuine Expanded Bold, already rolled out everywhere bold is
used (see "Genuine Bold Rollout..." above) - so it came out entirely,
not just unlinked: the `'fonttest'` branch in `get_route()`, the whole
`render_font_comparison()` function, and the `elif route == 'fonttest'`
dispatch in `main()`.

- Checked for knock-on dead code rather than just deleting the three
  named pieces: `textwrap`, `pathlib.Path`, and `get_bentley_font_face_css`
  (alongside `font_face_css`, imported from `framework.py`) had no other
  call site anywhere in `app.py` - that comparison page was their only
  user - so all three imports came out too, genuinely unused rather than
  speculative cleanup. `get_logo_data_uri` stayed, since
  `render_landing_page` still calls it directly. Confirmed
  `get_bentley_font_face_css`/`font_face_css` themselves are untouched in
  `framework.py` and still genuinely used by `leader_portal.py` and
  `feedback_form.py` for the real production typeface CSS - this only
  removed `app.py`'s own now-dead import of them.
- VERIFIED LIVE against every acceptance check: `?fonttest=1` now falls
  straight through to the normal landing page (screenshotted, no
  comparison content, no error); grepped the whole codebase for
  `fonttest`/`render_font_comparison` and found zero remaining
  references anywhere; Overview, Nominate Raters, Guidelines, and the
  admin dashboard all re-checked live afterward and render exactly as
  before, Bentley typeface still applied throughout (confirming the
  import removal didn't touch the real typeface pipeline, which lives
  in `leader_portal.py`/`feedback_form.py`, not `app.py`).
- Cleanup only, no functional change to anything a real user could
  reach - the route was never linked from any navigation in the app.

### Cohort Averages — Self-Assessment Reports Only — BUILT 2026-08-31
Per-dimension cohort average shown alongside a leader's own self-assessment
score: a table column, a third radar line, and a per-dimension comparison
in the Detailed Self-Assessment section. SELF-ASSESSMENT ONLY, deliberately
- Full 360 report generation is untouched and this must not be extended
there without a separate, deliberate decision. Three reasons, from the
human's own brief, not just "it's harder": (1) a Full 360 score is already
an aggregate of a different set of specific raters per leader, so a cohort
average of averages compounds noise about who a leader's raters happened
to be, not signal about the leader; (2) in a mid-size cohort, a cohort-
level Full 360 average combined with a leader's own known score risks
back-calculating other leaders' results, an anonymity concern self-
assessment doesn't carry since it isn't subject to ANONYMITY_THRESHOLD at
all; (3) the programme is built around self-referential development, not
leader-vs-leader comparison - a Full 360 cohort figure invites "am I rated
better or worse than my peers," a different and less useful question than
what this instrument is designed to answer.

- **`COHORT_AVERAGE_MIN_SIZE = 8`** (framework.py, alongside
  `ANONYMITY_THRESHOLD`) - a defensive floor, not expected to bite at the
  programme's real target cohort size (18-20). Distinct in kind from
  `ANONYMITY_THRESHOLD`: this isn't an anonymity protection, it's a
  statistical-reliability floor against averaging too few people and
  calling it a cohort.
- **`db.get_cohort_self_assessment_average(leader_id)`** (database.py) is
  the single source of truth, returning a `{dimension: average}` dict or
  `None`. TWO GATING CONDITIONS, both checked explicitly against the
  database on every call, never assumed to hold:
  1. The whole cohort's self-assessments must be complete - every ACTIVE
     leader currently in the cohort (the report's own subject included)
     has a completed Self rater row. One leader who hasn't started blocks
     the whole cohort's averages, not just their own. This already aligns
     with existing release timing (reports aren't handed out until end of
     Module 1 regardless), so it isn't a new constraint in practice, but
     it's enforced in code now rather than assumed to coincidentally hold.
  2. The cohort must clear `COHORT_AVERAGE_MIN_SIZE`.
  - Calculation deliberately EXCLUDES the requesting leader's own score
    (comparing someone against themselves would dilute the contrast this
    exists to provide), and averages each OTHER leader's OWN per-dimension
    self-assessment score (their personal mean across that dimension's
    five items, the same number their own report would show) rather than
    re-pooling every individual item rating across the cohort - the
    latter would let a leader with more "no opportunity" answers quietly
    carry less weight than everyone else's single vote in the average.
- **Wiring, Self-Assessment only, two call sites in `admin_dashboard.py`**
  (the dropdown-driven single-leader tab and the dedicated Self-Assessment-
  only tab): `db.get_cohort_self_assessment_average(leader_id)` is called
  ONLY when `report_type == 'Self-Assessment'`, not on every generation
  regardless of type, and passed into `generate_report(...,
  cohort_averages=...)` - a new, purely additive keyword argument. The
  batch "Generate All Full 360 Reports" loop is untouched, never even
  imports the new method.
- **`report_generator.py` changes, all additive**:
  - `create_radar_chart` gained `combined_label='All Raters'` - the Full
    360 call site (`add_executive_summary`) never passes this kwarg, so
    its own radar is byte-for-byte unaffected. The Self-Assessment radar
    call in `generate_report` passes `combined_label='Cohort Average'`
    along with the cohort-average dict in place of `combined_scores` -
    same line/fill construction as the existing "All Raters" line (same
    `heritage_white`/`heritage_white_deep` colours), different label.
  - New `add_cohort_average_note(doc, available)` - the required framing
    copy, styled to match `add_scoring_scale_note`'s own convention (9pt
    italic grey, explained ONCE before the number's first appearance in
    "Your Self-Assessment Overview", not repeated near every chart - this
    is a linear document read once per coaching conversation, not a
    navigable app). NOT OPTIONAL per the feature's own spec: without it, a
    cohort average reads as a leaderboard, which contradicts the self-
    referential design the whole report is built around. Two variants -
    the real framing statement when available, and a gated-off message
    ("A cohort comparison isn't shown for this report...") when not,
    deliberately reason-agnostic (doesn't distinguish incomplete cohort
    vs too-small cohort vs no cohort at all - the specific reason isn't
    the leader's concern, and naming a cohort's size or completion count
    here would edge toward the kind of disclosure this project is
    otherwise careful to avoid elsewhere).
  - "Your Self-Assessment Overview" table: 2 columns (unchanged) when no
    cohort average is available, 3 (`Dimension` / `Your Score` / `Cohort
    Average`) when it is - decided once via `cohort_available = bool(
    cohort_averages)`, threaded through the table, the radar, and every
    dimension section, so none of them can independently drift out of
    sync with each other.
  - `add_dimension_section` gained `cohort_averages=None` (the Full 360
    call site never passes it, so `is_self_only=False` gates the new code
    off regardless): a "Your score: X.X    Cohort average: Y.Y" line right
    after the dimension description, shown only when a value exists for
    THAT specific dimension (the dict can be present while one dimension
    is still missing, in the unlikely case every other leader marked
    every item in it "no opportunity"). Absorbs the "room before Q1"
    spacing the description paragraph would otherwise carry alone (see
    that paragraph's own space_after comment, from the 2026-08-28 spacing
    fix) - tightened there and moved onto this new line, so the total gap
    before Q1 doesn't double up now that a second paragraph sits between
    the description and the first item.
- **VERIFIED with a real constructed test, both correctness and every
  acceptance check**, per the task's own explicit requirement not to
  trust the code in isolation:
  - Built an 8-leader cohort (exactly `COHORT_AVERAGE_MIN_SIZE`, the
    boundary case) with one "Subject Leader" and 7 "others", each other
    leader given a distinct, deterministic per-dimension score pattern
    (`1 + ((leader_index + dimension_index) % 4)`) and the subject given
    a constant, extreme 5 on every item specifically to prove it's
    excluded from the average. Computed the expected cohort average
    independently (not via the same code path) and asserted an exact
    match against `get_cohort_self_assessment_average`'s real output -
    matched on every one of the 9 dimensions.
  - Gate 1: reset one "other" leader's self-assessment to incomplete via
    `reset_rater_response` - confirmed the function returns `None` for
    the whole cohort, not a partial average excluding just that leader.
  - Gate 2: built a separate 5-leader cohort (below the floor, all
    complete) - confirmed `None`.
  - Generated TWO real `.docx` reports for the same subject leader via
    the real `generate_report` function (not a reimplementation) - one
    with `cohort_averages` populated, one with `None` - and inspected
    both with `python-docx`: the "available" report showed the correct
    framing paragraph, a 3-column table with the right numbers, and a
    "Your score: 5.0    Cohort average: X.X" line under every one of the
    9 dimensions; the gated report showed the "not shown for this
    report" framing, a 2-column table, and zero cohort-average text
    anywhere. Extracted the embedded radar chart PNG directly from the
    generated `.docx` (via its zip structure) and visually confirmed a
    correctly labelled "Cohort Average" legend and a distinct inner line
    at the right per-dimension values, matching the table exactly.
  - Repeated the "with cohort averages" generation through the REAL admin
    dashboard UI (not just direct function calls) - clicked the actual
    Generate button for "Subject Leader" on the Reports tab, confirmed
    "Report generated!", downloaded it, and confirmed the resulting file
    carried the identical correct content, proving the two
    `admin_dashboard.py` call sites are wired correctly, not just the
    underlying functions in isolation.
  - Generated a real Full 360 report (leader 1, real existing data) and
    confirmed zero cohort-average text appears anywhere in it - the
    feature's own explicit "Full 360 untouched" requirement, checked
    live rather than inferred from not having edited that code path.
  - All 13 test leaders (plus their raters/ratings/comments/email_log
    rows) and every generated test `.docx` deleted after verification;
    leader 1's 13-rater baseline confirmed unchanged.
- Committed and pushed to both `production` (`1292f75`) and `sandbox`
  (`6e43dfd`) 2026-09-03.

### Admin Dashboard Cohort Averages — BUILT 2026-09-03
Extends the Self-Assessment cohort-average feature above with a whole-
cohort summary view in the admin dashboard: aggregate, dimension-level
self-assessment averages for one cohort at a time, on the Overview tab's
filtered single-cohort page. Aggregate-only, deliberately never a per-
leader breakdown - that already exists via each leader's own generated
report; this view answers a different question ("where is this cohort
collectively strong or weak"), not "how does leader X compare to leader
Y", which this project has been careful never to build (see the report-
side feature's own rationale above for why leader-vs-leader comparison
is out of scope for this instrument).

- **`database.py` refactored, not duplicated**, per the task's own
  explicit instruction not to let the two features diverge: the report-
  side `get_cohort_self_assessment_average(leader_id)`'s entire
  calculation moved into a new private `_cohort_dimension_averages(cohort,
  exclude_leader_id=None)`, which both public methods now call - the
  report-side one passing the requesting leader to exclude, the new
  `get_cohort_dimension_averages(cohort)` passing nothing (a whole-cohort
  read has no single leader to exclude). Same two gates (whole-cohort
  completeness, `COHORT_AVERAGE_MIN_SIZE`), same per-leader-then-average
  calculation, in exactly one place - the two features cannot show
  different numbers for the same cohort because there is only one
  calculation to disagree with itself.
- **`admin_dashboard.py`**: a new "Cohort Self-Assessment Averages"
  section on `render_overview_tab`'s filtered single-cohort view (reached
  via "View" on a cohort card), placed after the existing Leaders/Total
  Raters/Response Rate/Ready-for-Report stats and before the per-leader
  "Leader Status" list - keeps it clearly scoped to one cohort at a time,
  and clearly separate from the pre-existing per-leader section
  immediately below it. A plain `Dimension | Cohort Average` table when
  available; an explicit `st.info` ("Cohort averages aren't available
  yet...") when gated off, never a blank or partial table.
- **VERIFIED LIVE with a real regression + correctness test**, not just
  code review of the refactor: rebuilt the same deterministic-scores test
  pattern as the report-side feature's own verification (8 leaders, each
  given a distinct per-dimension score via `1 + ((leader_index +
  dimension_index) % 4)`), and asserted THREE things against independently
  computed expectations: (1) `get_cohort_dimension_averages` (whole
  cohort, all 8) matches an average computed by hand outside the code
  under test; (2) `get_cohort_self_assessment_average` (excludes one
  leader) STILL matches its own pre-refactor expected values exactly - a
  genuine regression check on the report-side feature already shipped,
  not assumed safe because the refactor "looked" equivalent; (3) the two
  results are genuinely different numbers for the same cohort, proving
  the exclusion parameter actually does something rather than the two
  functions accidentally converging.
  - Gate 1 (incomplete cohort): reset one leader's self-assessment,
    confirmed BOTH functions return `None` for that cohort.
  - Gate 2 (below floor): a separate 4-leader cohort, all complete,
    confirmed `None`.
  - Reproduced both the working and gated states live in the actual admin
    UI (not just direct function calls): an 8-leader complete cohort
    showed the real "Cohort Self-Assessment Averages" table with the
    correct 2.5 average on every one of the 9 dimensions (matching the
    constructed data's known uniform average), screenshotted; a 4-leader
    complete-but-below-floor cohort showed the "Cohort averages aren't
    available yet..." message instead, screenshotted - confirming the
    withheld state renders correctly, not silently, when gated.
  - Confirmed aggregate-only, no per-leader breakdown: the new table
    lists dimensions only: the pre-existing "Leader Status" section
    immediately below it, which does show per-leader detail, is
    untouched and visually distinct, not merged with the new table.
  - All 12 test leaders (plus raters/ratings/comments/email_log) deleted
    after verification; leader 1's 13-rater baseline confirmed unchanged.
- NOT committed/pushed yet - awaiting Ian's explicit instruction, per
  standing practice.

### Flagged for later: measuring self-assessment movement over time
Idea, not built, deliberately deferred: re-running the self-assessment
later in the programme (e.g. at the end) to measure movement against the
original. Genuinely useful in principle - the same instrument, same
person, two points in time - but explicitly NOT started now, for one
reason: this feature's entire value depends on retaining someone's
original self-assessment data for long enough to compare against later,
which means it directly depends on the data retention period, still an
open decision (`ui_consent_retention` on the consent screens currently
says "We're still finalising our data retention timeline with Bentley" -
see section 5's consent-copy work). Building "measure movement" ahead of
that decision means building on a foundation retention could pull out
from under it the moment it's actually settled - not a new problem, the
same tension already flagged between `historical_scores` existing at all
and any short retention period actually being chosen.

**Checked now, cheaply, per the human's own instruction not to assume
`historical_scores` is further along than it actually is** (this project
already found one table - `reports` - that sat completely unused for
months before anyone noticed, so this was worth ruling out rather than
assumed): `historical_scores` is GENUINELY DORMANT. Confirmed by grep
across the entire codebase (`historical_scores`, `save_historical_data`,
`get_historical_data`) - the only matches are the table's own `CREATE
TABLE` and the two accessor methods' own definitions in `database.py`.
NEITHER `save_historical_data` NOR `get_historical_data` has a single
call site anywhere else in the codebase - no UI calls either, no
scheduled job, nothing. The local dev database's own `historical_scores`
table has zero rows, consistent with there being no code path that could
ever have written one, in any environment: `save_historical_data` isn't
reachable from anywhere, so this conclusion doesn't depend on which
database happens to be inspected. This table and its two functions are
exactly the same category of dormant scaffolding the `reports` table
was before it got wired up (see that fix earlier in this file) - schema
and helper functions that exist, but were never connected to a real
feature.

**When retention is actually resolved, pick this up deliberately, not
assumed complete because the table already exists:**
- `historical_scores` schema and its two accessor methods are a
  reasonable starting point, but genuinely untested and unconnected -
  treat them as a sketch, not a working foundation.
- The real work is: (1) an admin action to snapshot a leader's CURRENT
  self-assessment data into `historical_scores` at a deliberate point
  (most likely when a fresh self-assessment round begins, so the
  ORIGINAL data is preserved before being overwritten - `ratings`/
  `comments` have no history of their own, only the current values), (2)
  a UI to actually initiate a second self-assessment round for someone
  who already has one on record (doesn't exist today - the current flow
  assumes exactly one Self rater per leader ever), (3) a report section
  or view that reads two snapshots and shows the delta, and (4) deciding
  what "movement" means for the priorities/keep-change qualitative
  fields, not just the numeric dimension scores.
- None of this should be started before the retention question is
  settled - the point of this note is to make that dependency explicit
  and visible to whoever picks this up next, not to pre-empt it.

## 9. Working style the human prefers

- Name trade-offs explicitly BEFORE building; propose a better way if you see one.
- Don't pre-justify or check in mid-task unless something is genuinely ambiguous.
- British English. Direct, not hedging. No em dashes. Avoid "not just X but Y",
  throat-clearing, reflexive three-item lists.
- The human reviews logic directly and makes architectural calls conversationally.
- On anything irreversible or affecting Mark's live environment: STOP and confirm.
- STANDING AUTHORITY (given 2026-08-27): when live-testing/screenshotting a
  fix the human specifically asked for, if something ELSE in that same
  screenshot looks off, fix it too rather than just flagging it - don't
  wait to be asked separately. Reserve flagging-without-fixing for issues
  that are a genuinely different scale of problem (e.g. a design/breakpoint-
  strategy decision, not a self-contained CSS fix) - see the "third issue"
  vs. the "NEW OBSERVATION, NOT FIXED" split in the Two Layout Fixes entry
  above for how that line was actually drawn in practice.
