# Portal anonymity change set

Four changes, built against the live code (real column names: `name`,
`email`, `to_email`). Apply in this order. Change 1 is an urgent bug fix
independent of the portal work; do it regardless.

Confirmed design decisions these implement:
- Total-level response progress only. No per-group, no per-person counts.
- Progress hidden until a threshold, so it never resolves to one outstanding person.
- One blind "remind everyone outstanding" button. Uniform confirmation, no counts.
- Per-rater 48h rate limit on reminders (reuses existing reminder_sent_at).
- Identity severed at final submission (name/email nulled on raters, to_email nulled in email_log).

---

## Change 1 (URGENT, do first): fix the undefined ANONYMITY_THRESHOLD

`database.py` line 739 imports `ANONYMITY_THRESHOLD` from `framework.py`,
but it is not defined there. `get_leader_feedback_data` (the function
behind every report) will raise ImportError the moment it runs. Reports
cannot generate until this is fixed.

This is the group-size floor for folding a small group into "Others" in
the REPORT, a different threshold from MIN_RESPONSES_FOR_REPORT (which
gates whether a report is producible at all). Keep them separate.

In `framework.py`, in the CONFIGURATION block, add the constant. Value 3
is the standard 360 anonymity floor and matches the portal guidance text
("minimum of 3 respondents ... to ensure anonymity"). Change the number
if you want a different floor.

```python
MIN_RESPONSES_FOR_REPORT = 5
ANONYMITY_THRESHOLD = 3   # Groups (Peers/DRs) with fewer than this many
                          # responses fold into "Others" in the report.
                          # Self and Boss are exempt (handled in database.py).
SIGNIFICANT_GAP = 1.0
HIGH_SCORE_THRESHOLD = 4.0
```

Verify: `python3 -c "from database import Database; d=Database(db_path='/tmp/t.db'); print('ok')"`
then call a report on a leader with test data and confirm no ImportError.

---

## Change 2: wire severing into submission

The real submission path is `feedback_form.py` line ~383, which calls
`db.submit_feedback(rater_id, ratings, comments)`. In `database.py`,
`submit_feedback` calls `mark_rater_complete`. Sever there.

### 2a. Add the sever method to `database.py`

Add this method to the `Database` class (anywhere among the rater
methods, e.g. just after `mark_rater_complete`):

```python
    def sever_rater_identity(self, rater_id):
        """Permanently remove identifying data for a rater at final submit.

        Nulls name/email on the raters row and to_email in email_log, so
        the responses can no longer be resolved to a person by anyone with
        database access. Irreversible by design (Model A). The token,
        relationship and all responses are preserved.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE raters SET name = NULL, email = NULL WHERE id = ?",
            (rater_id,),
        )
        # email_log.to_email is defined NOT NULL, so it cannot be set to
        # NULL without a table migration. Overwrite with a placeholder
        # instead: this removes the actual address while keeping the log
        # row for send-auditing and satisfying the constraint.
        cursor.execute(
            "UPDATE email_log SET to_email = ? WHERE rater_id = ?",
            ('[severed]', rater_id),
        )
        conn.commit()
        conn.close()

    def verify_no_residual_identity(self, leader_id):
        """Audit: return rater_ids that have submitted but still carry a
        name or email (should always be empty if severing is wired). Run
        before handing a report to the client.
        """
        return [
            row['id'] for row in self._fetchall(
                """
                SELECT id FROM raters
                WHERE leader_id = ?
                  AND completed_at IS NOT NULL
                  AND (name IS NOT NULL OR email IS NOT NULL)
                """,
                (leader_id,),
            )
        ]
```

### 2b. Call it from `submit_feedback` in `database.py`

Current (line ~666):

```python
    def submit_feedback(self, rater_id, ratings, comments):
        """Submit complete feedback (ratings + comments) and mark as complete."""
        self.submit_ratings(rater_id, ratings)
        self.submit_comments(rater_id, comments)
        self.mark_rater_complete(rater_id)
```

Replace with:

```python
    def submit_feedback(self, rater_id, ratings, comments):
        """Submit complete feedback, mark complete, then sever identity.

        Severing runs last, after the responses are safely stored and the
        rater is marked complete, so a failure in severing never loses a
        submission. verify_no_residual_identity will catch any un-severed
        row on the next audit.
        """
        self.submit_ratings(rater_id, ratings)
        self.submit_comments(rater_id, comments)
        self.mark_rater_complete(rater_id)
        self.sever_rater_identity(rater_id)
```

Note: `submit_ratings`/`submit_comments` store against `rater_id`, not
name/email, so nulling identity afterward leaves all responses intact.
Confirmed by test.

IMPORTANT deployment note: do NOT apply Change 2 to the environment Mark
is testing until his test concludes or he agrees. Once live, every
subsequent submission is irreversibly de-identified, so any test
submission Mark makes afterward loses its name/email.

---

## Change 3: rework the Progress tab to total-level only + blind nudge

Replace the whole `render_progress_section` function in
`leader_portal.py` (lines ~286-355) with the version below.

What changes from the current version:
- Removes the per-rater name/email/status listing entirely.
- Removes per-group "(X/Y complete)" counts.
- Shows a single total-level progress line, and only once responses reach
  PROGRESS_VISIBILITY_THRESHOLD, so a leader can never read "all but one".
- Replaces both the per-rater bell and the counted bulk button with one
  blind "remind everyone still to respond" button. Uniform confirmation,
  no number, no names. Per-rater 48h rate limit enforced before send.

```python
# Add near the top of leader_portal.py, with the other module constants:
PROGRESS_VISIBILITY_THRESHOLD = 5   # Don't show any progress figure until
                                    # this many responses are in across the
                                    # whole assessment (prevents "all but one"
                                    # inference). Align with MIN_RESPONSES_FOR_REPORT.
REMINDER_COOLDOWN_HOURS = 48        # Per-rater minimum gap between reminders.


def render_progress_section(db, leader_info, raters):
    """Response progress: total-level only, with a single blind nudge.

    Deliberately shows NO per-group or per-person response data. Because
    the leader nominated the raters, they know the roster; any per-group
    count would let them identify a non-responder, and severing at
    submission would be undone by broadcasting response timing. Only a
    whole-assessment figure, gated behind a threshold, is safe.
    """
    from datetime import datetime, timedelta

    leader_id = leader_info['id']
    base_url = st.session_state.get(
        'portal_base_url',
        "https://catalyst-360-arbncruhflmazjemep8uzh.streamlit.app"
    )
    email_configured = EMAIL_AVAILABLE and is_email_configured()

    if not raters:
        st.info("You haven't nominated any raters yet. Go to the "
                "'Nominate Raters' tab to add your feedback providers.")
        return

    total = len(raters)
    completed = sum(1 for r in raters if r.get('completed'))

    st.subheader("Response Progress")

    # Total-level progress, gated. Never show a figure that could resolve
    # to a single outstanding person.
    if completed >= PROGRESS_VISIBILITY_THRESHOLD:
        st.metric("Responses received", f"{completed} of {total}")
        st.progress(completed / total if total else 0)
        if completed < total:
            st.caption("Feedback is still arriving. You can send a reminder "
                       "to anyone who hasn't yet responded using the button below.")
        else:
            st.success("All your nominated raters have responded.")
    else:
        st.info("Your feedback is being collected. To protect the anonymity "
                "of your raters, response progress becomes visible once enough "
                "responses are in. You can still send a reminder at any time.")

    st.markdown("---")

    # Blind nudge. One button. No names, no counts, uniform confirmation.
    # Rate-limited per rater (48h) so it can't be used to pester or to
    # probe response timing by repeated firing.
    st.markdown("**Remind your raters**")
    st.caption("Sends a gentle reminder to anyone who hasn't yet responded. "
               "You won't see who has or hasn't, to keep individual responses "
               "confidential.")

    if not email_configured:
        st.caption("Email sending isn't configured, so reminders can't be sent "
                   "from here. Contact your programme coordinator.")
    else:
        if st.button("Send a reminder to anyone still to respond",
                     use_container_width=True):
            _send_blind_reminders(db, leader_info, raters, base_url)
            # Uniform message regardless of how many (or zero) were sent.
            st.success("Reminder sent. Anyone who has already responded won't "
                       "be contacted, and recent reminders won't be repeated.")


def _send_blind_reminders(db, leader_info, raters, base_url):
    """Send reminders to outstanding raters, silently. Returns nothing the
    caller should surface per-rater. Enforces the per-rater cooldown so
    repeated clicks don't pester or leak timing.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(hours=REMINDER_COOLDOWN_HOURS)

    for rater in raters:
        if rater.get('completed'):
            continue
        # Respect the cooldown. reminder_sent_at is a TEXT timestamp; parse
        # defensively and skip the rater if they were reminded recently.
        last = rater.get('reminder_sent_at')
        if last:
            try:
                last_dt = datetime.fromisoformat(str(last).replace('Z', '').split('.')[0])
                if last_dt > cutoff:
                    continue
            except (ValueError, TypeError):
                pass  # Unparseable -> treat as no prior reminder
        # send_rater_reminder already logs and updates reminder_sent_at on
        # success, and refuses completed/emailless raters.
        send_rater_reminder(rater, leader_info['name'], base_url, db)
```

Nothing else in `leader_portal.py` needs to change. The Nominate tab and
its per-CATEGORY nomination status stay as they are: that shows how many
the leader has ADDED (their own roster, not a leak) and only warns, never
blocks, which matches the "soft warning on thin groups" decision.

---

## Change 4 (optional, tidy-up): guard delete_rater at the source

The portal already hides the delete button for completed raters (correct).
But `delete_rater` in `database.py` will still hard-delete a completed
rater with their responses if ever called elsewhere. Cheap insurance:

```python
    def delete_rater(self, rater_id, force=False):
        """Delete a rater and their responses.

        Refuses to delete a rater who has already submitted unless force=True
        (admin-only), so a responded rater's feedback can never be pruned.
        """
        rater = self.get_rater(rater_id)
        if rater and rater.get('completed_at') and not force:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ratings WHERE rater_id = ?", (rater_id,))
        cursor.execute("DELETE FROM comments WHERE rater_id = ?", (rater_id,))
        cursor.execute("DELETE FROM raters WHERE id = ?", (rater_id,))
        conn.commit()
        conn.close()
        return True
```

The portal's existing call `db.delete_rater(rater['id'])` still works
(the button only shows for non-completed raters, so the guard never
trips there). Admin paths that legitimately need to remove a completed
rater pass `force=True`.

---

## What is NOT changed, and why

- The existing CSV upload in the Nominate tab (leader_portal.py ~218-283)
  already works against the real schema (`name, email, relationship`) and
  sends invitations. It doesn't need the separate rater_import.py module I
  drafted earlier, that was built against the wrong schema and for the
  admin-run workflow. For the leader portal, the built-in uploader is fine.
  If you later want admin-side bulk upload across MULTIPLE leaders at once
  (leader_name column), that's when the standalone importer earns its
  place, re-aligned to name/email. Say the word and I'll redo it correctly.

- Report-side anonymity (folding small groups into Others) already exists
  in get_leader_feedback_data and works once Change 1 is applied.
```
