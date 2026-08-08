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
- Response progress: TOTAL-LEVEL ONLY, gated behind a threshold so it never
  resolves to a single outstanding person. NO per-group, NO per-person status.
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
- STILL OUTSTANDING: the failure is loud in the logs but invisible in the admin
  UI. If the human wants report generation to surface "Key Themes could not be
  generated", that is a small change in admin_dashboard.py's report tab.

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

## 9. Working style the human prefers

- Name trade-offs explicitly BEFORE building; propose a better way if you see one.
- Don't pre-justify or check in mid-task unless something is genuinely ambiguous.
- British English. Direct, not hedging. No em dashes. Avoid "not just X but Y",
  throat-clearing, reflexive three-item lists.
- The human reviews logic directly and makes architectural calls conversationally.
- On anything irreversible or affecting Mark's live environment: STOP and confirm.
