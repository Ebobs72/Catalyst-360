#!/usr/bin/env python3
"""
Leader Portal for Bentley Compass 360.

Allows leaders to:
- View their assessment status
- Nominate their raters (Boss, Peers, DRs, Others)
- Track rater response progress
- Send reminders to raters
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from framework import (
    ANONYMITY_THRESHOLD, RELATIONSHIP_TYPES,
    RELATIONSHIP_INPUT_HELP, normalise_relationship
)

# Import email functionality if available
try:
    from email_sender import (
        is_email_configured,
        send_rater_invitation,
        send_rater_reminder,
        get_app_base_url
    )
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

    def get_app_base_url():
        """Fallback when email_sender is unavailable; links are display-only then."""
        return ""


def _progress_summary_text(completed, total):
    """
    Total-level-only progress summary — never reveals a per-group or
    per-person breakdown, and never resolves to a single outstanding (or
    single respondent) individual by simple subtraction.
    """
    if total == 0:
        return "You haven't nominated any raters yet."

    outstanding = total - completed
    if outstanding == 0:
        return "✅ All responses received."
    if total < ANONYMITY_THRESHOLD or outstanding == 1:
        return "🔄 Responses are coming in."
    return f"📊 {completed} of {total} responses received."

# Rater requirements
# 'Others' is optional, but ALL OR NOTHING above the anonymity threshold:
# nominate none, or nominate at least ANONYMITY_THRESHOLD. One or two "Others" is
# the worst case, because unlike a thin Peers or DRs group there is no larger
# group for them to be folded into, so their feedback has to be left out of the
# report entirely to keep them anonymous. `min_if_any` captures that rule.
RATER_REQUIREMENTS = {
    'Boss': {'min': 1, 'max': 2, 'suggested': 1, 'required_nomination': True, 'show_minimum': True},
    'Peers': {'min': 3, 'max': 10, 'suggested': 5, 'required_nomination': True, 'show_minimum': True},
    'DRs': {'min': 3, 'max': 10, 'suggested': 5, 'required_nomination': True, 'show_minimum': True},
    'Others': {'min': 0, 'max': 10, 'suggested': 0, 'required_nomination': False,
               'show_minimum': False, 'min_if_any': ANONYMITY_THRESHOLD}
}


def render_leader_portal(db, leader_info):
    """Render the leader portal page."""
    
    leader_id = leader_info['id']
    leader_name = leader_info['name']
    
    # Header
    st.markdown('<p class="main-title">BENTLEY COMPASS 360</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Your Leadership Feedback Portal</p>', unsafe_allow_html=True)
    
    # Welcome section. This portal is only ever issued after Module 1 (the portal
    # email is admin-triggered, never automatic), so the copy can assume the
    # leader has already completed their self-assessment and had their first
    # coaching conversation. Nominating raters is the task in front of them now.
    st.markdown(f"""
    <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1.5rem;">
        <h3 style="margin: 0 0 0.5rem 0; color: #024731;">Welcome, {leader_name}</h3>
        <p style="color: #666; margin: 0 0 0.75rem 0;">{leader_info.get('dealership', '')} · {leader_info.get('cohort', '')}</p>
        <p style="color: #333; margin: 0; line-height: 1.6;">
            You've completed your self-assessment and talked it through with your coach.
            The next step is to nominate the people who will give you feedback. Their
            responses build your full report, which you'll receive at Module 2.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all raters for this leader
    raters = db.get_raters_for_leader(leader_id)
    
    # Separate self from others
    self_rater = next((r for r in raters if r['relationship'] == 'Self'), None)
    other_raters = [r for r in raters if r['relationship'] != 'Self']
    
    # Status overview
    render_status_overview(self_rater, other_raters)
    
    st.markdown("---")
    
    # Tabs for different sections - Guidelines first so they read instructions
    tab1, tab2, tab3 = st.tabs(["ℹ️ Guidelines", "📝 Nominate Raters", "📊 Response Progress"])
    
    with tab1:
        render_guidelines_section()
    
    with tab2:
        render_nomination_section(db, leader_info, other_raters)
    
    with tab3:
        render_progress_section(db, leader_info, other_raters)


def render_status_overview(self_rater, other_raters):
    """Render the status overview cards."""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if self_rater and self_rater.get('completed'):
            st.success("✓ Self-Assessment Complete")
        elif self_rater:
            st.warning("○ Self-Assessment Pending")
        else:
            st.info("○ Self-Assessment Not Started")
    
    with col2:
        total_nominated = len(other_raters)
        st.metric("Raters Nominated", total_nominated)
    
    with col3:
        completed = sum(1 for r in other_raters if r.get('completed'))
        st.markdown("**Responses Received**")
        st.write(_progress_summary_text(completed, total_nominated))


def render_nomination_section(db, leader_info, existing_raters):
    """Render the rater nomination section."""
    
    leader_id = leader_info['id']
    
    # Get base URL for sending invitations
    base_url = st.session_state.get('portal_base_url', get_app_base_url())

    # Count existing raters by category
    rater_counts = {'Boss': 0, 'Peers': 0, 'DRs': 0, 'Others': 0}
    for r in existing_raters:
        rel = r['relationship']
        if rel in rater_counts:
            rater_counts[rel] += 1
    
    # Show current status per category with validation
    st.subheader("Nomination Status")
    
    status_cols = st.columns(4)
    categories = ['Boss', 'Peers', 'DRs', 'Others']
    
    all_requirements_met = True
    thin_optional_groups = []
    # Groups sitting exactly ON the threshold. The threshold applies to RESPONSES,
    # not nominations, so one non-response tips these under it.
    at_risk_groups = []

    for i, cat in enumerate(categories):
        with status_cols[i]:
            req = RATER_REQUIREMENTS[cat]
            count = rater_counts[cat]
            min_if_any = req.get('min_if_any')

            # Determine status
            if min_if_any and 0 < count < min_if_any:
                # Optional group, but too thin to report anonymously. Warn rather
                # than block, consistent with the soft-warning approach elsewhere.
                status_icon = "⚠️"
                status_color = "#B8860B"
                status_text = f"{count}/{min_if_any} needed"
                thin_optional_groups.append((cat, count, min_if_any))
            elif not req.get('required_nomination', True):
                status_icon = "✓" if count > 0 else "○"
                status_color = "#024731" if count > 0 else "#666"
                status_text = f"{count} nominated" if count > 0 else "Optional"
                if min_if_any and count == min_if_any:
                    at_risk_groups.append((cat, count))
            elif count >= req['min']:
                status_icon = "✓"
                status_color = "#024731"
                status_text = f"{count} nominated"
            else:
                status_icon = "⚠️"
                status_color = "#B8860B"
                status_text = f"{count}/{req['min']} minimum"
                if req.get('required_nomination', True):
                    all_requirements_met = False

            st.markdown(f"""
            <div style="background: white; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #E0E0E0;">
                <div style="font-size: 1.5rem;">{status_icon}</div>
                <div style="font-weight: 600; color: #024731;">{RELATIONSHIP_TYPES.get(cat, cat)}</div>
                <div style="color: {status_color}; font-size: 0.9rem;">{status_text}</div>
            </div>
            """, unsafe_allow_html=True)
    
    if not all_requirements_met:
        st.warning("⚠️ Please ensure you meet the minimum requirements for each category before the deadline.")

    for cat, count, needed in thin_optional_groups:
        label = RELATIONSHIP_TYPES.get(cat, cat)
        st.warning(
            f"⚠️ You've nominated {count} under **{label}**, which isn't enough to "
            f"report anonymously. Unlike the other categories, there's no larger "
            f"group for a small {label} group to be combined with, so their "
            f"feedback would have to be left out of your report altogether. "
            f"Either take it to {needed} or more, or remove them and use another "
            f"category instead."
        )

    for cat, count in at_risk_groups:
        label = RELATIONSHIP_TYPES.get(cat, cat)
        st.info(
            f"You've nominated exactly {count} under **{label}**, which is the "
            f"minimum needed to report that group anonymously. If even one of them "
            f"doesn't respond it drops below the minimum, and their feedback would "
            f"have to be left out. Worth adding one or two more as cover."
        )

    st.markdown("---")
    
    # Add rater form
    st.subheader("Add a Rater")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("add_rater_form", clear_on_submit=True):
            rater_name = st.text_input("Name *", placeholder="e.g., John Smith")
            rater_email = st.text_input("Email *", placeholder="e.g., john.smith@company.com")
            relationship = st.selectbox(
                "Relationship to you *",
                options=['Boss', 'Peers', 'DRs', 'Others'],
                format_func=lambda x: {
                    'Boss': 'Line Manager / Boss',
                    'Peers': 'Peer / Colleague at same level',
                    'DRs': 'Direct Report',
                    'Others': 'Other (stakeholder, customer, matrix)'
                }.get(x, x)
            )
            
            # Check if category is at max
            at_max = rater_counts.get(relationship, 0) >= RATER_REQUIREMENTS[relationship]['max']
            
            submitted = st.form_submit_button("Add Rater", disabled=at_max)
            
            if at_max:
                st.caption(f"Maximum {RATER_REQUIREMENTS[relationship]['max']} {relationship} raters reached")
            
            if submitted:
                if not rater_name or not rater_email:
                    st.error("Please enter both name and email")
                elif '@' not in rater_email:
                    st.error("Please enter a valid email address")
                else:
                    # Add the rater, and record the nomination on the leader's
                    # own roster so it survives identity severing
                    rater_id, token = db.add_rater(leader_id, relationship, rater_name, rater_email)
                    db.add_to_nomination_roster(leader_id, rater_name, rater_email, relationship)

                    # Send invitation email if configured
                    if EMAIL_AVAILABLE and is_email_configured():
                        rater = db.get_rater(rater_id)
                        success, msg = send_rater_invitation(
                            rater, 
                            leader_info['name'], 
                            base_url, 
                            db
                        )
                        if success:
                            st.success(f"✓ Added {rater_name} and sent invitation email")
                        else:
                            st.warning(f"✓ Added {rater_name} but email failed: {msg}")
                    else:
                        st.success(f"✓ Added {rater_name}")
                    
                    st.rerun()
    
    with col2:
        st.markdown("**Or upload multiple raters**")

        # Template shows every relationship in plain English, one row each, so the
        # accepted values are visible rather than something to guess at.
        template_df = pd.DataFrame({
            'name': ['Jane Smith', 'Tom Brown', 'Sarah Jones', 'Raj Patel'],
            'email': ['jane@company.com', 'tom@company.com',
                      'sarah@company.com', 'raj@company.com'],
            'relationship': ['Line Manager', 'Peer', 'Direct Report', 'Other'],
        })

        st.download_button(
            "📄 Download Template",
            template_df.to_csv(index=False),
            "rater_template.csv",
            "text/csv",
            use_container_width=True
        )
        st.caption(
            f"Columns: name, email, relationship. Relationship accepts "
            f"{RELATIONSHIP_INPUT_HELP} — capitalisation doesn't matter."
        )

        uploaded_file = st.file_uploader(
            "Upload CSV",
            type="csv",
            help=f"Columns: name, email, relationship. "
                 f"Relationship accepts {RELATIONSHIP_INPUT_HELP}, in any case."
        )

        if uploaded_file:
            try:
                import_df = pd.read_csv(uploaded_file)
                rows, problems = _parse_rater_csv(import_df, existing_raters)

                for problem in problems:
                    st.error(problem)

                if rows:
                    preview = pd.DataFrame([
                        {
                            'name': r['name'],
                            'email': r['email'],
                            'relationship': RELATIONSHIP_TYPES.get(
                                r['relationship'], r['relationship']
                            ),
                        }
                        for r in rows
                    ])
                    st.success(f"Ready to import {len(rows)} "
                               f"{'person' if len(rows) == 1 else 'people'}")
                    st.dataframe(preview, use_container_width=True, hide_index=True)

                    if st.button("Import All", type="primary", use_container_width=True):
                        imported = 0
                        for r in rows:
                            rater_id, token = db.add_rater(
                                leader_id, r['relationship'], r['name'], r['email']
                            )
                            db.add_to_nomination_roster(
                                leader_id, r['name'], r['email'], r['relationship']
                            )

                            if EMAIL_AVAILABLE and is_email_configured():
                                rater = db.get_rater(rater_id)
                                send_rater_invitation(
                                    rater, leader_info['name'], base_url, db
                                )

                            imported += 1

                        st.success(f"✓ Imported {imported} "
                                   f"{'person' if imported == 1 else 'people'}")
                        st.rerun()
                elif not problems:
                    st.warning("That file didn't contain any rows to import.")

            except Exception as e:
                st.error(f"Could not read that CSV: {str(e)}")

    st.markdown("---")
    render_nominated_list(db, leader_info, base_url)


def render_nominated_list(db, leader_info, base_url):
    """
    List who the leader has nominated, with the option to correct someone's email
    address or the relationship they were nominated under.

    Reads from `leaders.nomination_roster`, NOT from the `raters` rows. Identity
    severing nulls raters.name/raters.email at submission, so sourcing this list
    from `raters` would blank out exactly the people who responded, destroying
    the leader's own record and leaking per-person response status. The roster
    survives severing.

    Deliberately offers NO removal: removing a non-responder changes no score,
    no group count and no report, so its only real effects are to stop further
    reminders and to shrink the progress denominator. Removal for genuine
    reasons (someone has left the business, an address bounces) is an admin
    action. Correcting a mistake is the problem leaders actually hit, and it is
    non-destructive.

    Shows NO response status per person. Every row renders identically and the
    edit control is offered uniformly, so neither the list nor the outcome of an
    edit reveals who has responded.
    """
    roster = db.get_nomination_roster(leader_info['id'])
    if not roster:
        return

    st.subheader("People You've Nominated")
    st.caption(
        "Response status isn't shown per person. If you've got someone's email address "
        "wrong, or nominated them under the wrong relationship, you can correct it here. "
        "Corrections apply to anyone who hasn't given their feedback yet. Once someone "
        "has responded their answers stay in the group they were invited under, because "
        "that is the context they answered in. To remove someone, for example if they've "
        "left the business, contact your programme coordinator."
    )

    # Counts come from the raters rows rather than the roster, because that is what
    # the report actually groups by, and severed rows still carry their relationship.
    live_raters = [
        r for r in db.get_raters_for_leader(leader_info['id'])
        if r['relationship'] != 'Self'
    ]
    counts = {rel: 0 for rel in RATER_REQUIREMENTS}
    for r in live_raters:
        if r['relationship'] in counts:
            counts[r['relationship']] += 1

    relationship_options = ['Boss', 'Peers', 'DRs', 'Others']

    for rel in relationship_options:
        rel_entries = [
            (i, e) for i, e in enumerate(roster) if e.get('relationship') == rel
        ]
        if not rel_entries:
            continue

        st.markdown(f"**{RELATIONSHIP_TYPES.get(rel, rel)}**")
        for idx, entry in rel_entries:
            editing_key = f"edit_nominee_{idx}"
            current_email = entry.get('email') or ""
            current_rel = entry.get('relationship') or rel

            if st.session_state.get(editing_key):
                col1, col2, col3, col4 = st.columns([2, 2.4, 1.8, 0.8])
                with col1:
                    st.write(entry.get('name') or "Unknown")
                with col2:
                    new_email = st.text_input(
                        "Corrected email",
                        value=current_email,
                        key=f"email_input_{idx}",
                        label_visibility="collapsed",
                        placeholder="Correct email address"
                    )
                with col3:
                    new_rel = st.selectbox(
                        "Relationship",
                        options=relationship_options,
                        index=relationship_options.index(current_rel)
                        if current_rel in relationship_options else 0,
                        format_func=lambda x: RELATIONSHIP_TYPES.get(x, x),
                        key=f"rel_input_{idx}",
                        label_visibility="collapsed"
                    )
                with col4:
                    if st.button("Save", key=f"save_nominee_{idx}"):
                        error = _validate_nomination_change(
                            current_rel, new_rel, new_email, counts
                        )
                        if error:
                            st.error(error)
                        else:
                            _apply_nomination_correction(
                                db, leader_info, base_url,
                                current_email, new_email, new_rel
                            )
                            st.session_state[editing_key] = False
                            st.toast("Nomination updated.")
                            st.rerun()
            else:
                col1, col2, col3 = st.columns([3, 3, 1])
                with col1:
                    st.write(entry.get('name') or "Unknown")
                with col2:
                    st.caption(current_email or "No email address")
                with col3:
                    if st.button("✏️", key=f"edit_{idx}",
                                 help="Correct this person's email or relationship"):
                        st.session_state[editing_key] = True
                        st.rerun()


def _parse_rater_csv(import_df, existing_raters):
    """
    Turn an uploaded CSV into rows ready to import, plus human-readable problems.

    Returns (rows, problems). `rows` are dicts of name/email/relationship with the
    relationship already normalised to its internal code. `problems` are messages
    naming the offending spreadsheet row, so the leader can go and fix that line
    rather than being told the whole file is wrong.

    Nothing is imported if there are problems: a partial import of a nominee list
    is worse than none, because the leader cannot easily tell what landed.
    """
    required = ['name', 'email', 'relationship']
    missing_cols = [c for c in required if c not in import_df.columns]
    if missing_cols:
        return [], [
            f"Your CSV is missing the {', '.join(missing_cols)} "
            f"column{'s' if len(missing_cols) > 1 else ''}. "
            f"It needs: name, email, relationship."
        ]

    rows = []
    problems = []
    seen_emails = {
        (r.get('email') or '').strip().lower()
        for r in existing_raters if r.get('email')
    }
    counts = {rel: 0 for rel in RATER_REQUIREMENTS}
    for r in existing_raters:
        if r['relationship'] in counts:
            counts[r['relationship']] += 1

    for position, (_, row) in enumerate(import_df.iterrows(), start=2):
        # start=2 because row 1 of the spreadsheet is the header
        name = str(row['name']).strip() if pd.notna(row['name']) else ''
        email = str(row['email']).strip() if pd.notna(row['email']) else ''
        raw_rel = row['relationship'] if pd.notna(row['relationship']) else None
        relationship = normalise_relationship(raw_rel)

        if not name and not email and raw_rel is None:
            continue  # blank line, ignore silently

        if not name:
            problems.append(f"Row {position}: no name given.")
            continue
        if not email or '@' not in email:
            problems.append(f"Row {position} ({name}): '{email}' isn't a valid email address.")
            continue
        if relationship is None:
            shown = str(raw_rel).strip() if raw_rel is not None else '(blank)'
            problems.append(
                f"Row {position} ({name}): '{shown}' isn't a relationship we "
                f"recognise. Use {RELATIONSHIP_INPUT_HELP}."
            )
            continue
        if relationship == 'Self':
            problems.append(
                f"Row {position} ({name}): your own self-assessment is handled "
                f"separately, so don't include yourself here. Use "
                f"{RELATIONSHIP_INPUT_HELP}."
            )
            continue

        if email.lower() in seen_emails:
            problems.append(
                f"Row {position} ({name}): {email} is already on your list."
            )
            continue
        seen_emails.add(email.lower())

        counts[relationship] += 1
        limit = RATER_REQUIREMENTS.get(relationship, {}).get('max')
        if limit is not None and counts[relationship] > limit:
            label = RELATIONSHIP_TYPES.get(relationship, relationship)
            problems.append(
                f"Row {position} ({name}): this would give you more than the "
                f"maximum of {limit} for {label}."
            )
            continue

        rows.append({'name': name, 'email': email, 'relationship': relationship})

    if problems:
        # Do not import a partial list
        return [], problems

    return rows, problems


def _validate_nomination_change(current_rel, new_rel, new_email, counts):
    """Return an error message if the requested change isn't allowed, else None."""
    if not new_email or '@' not in new_email:
        return "Please enter a valid email address."

    if new_rel != current_rel:
        limit = RATER_REQUIREMENTS.get(new_rel, {}).get('max')
        if limit is not None and counts.get(new_rel, 0) >= limit:
            label = RELATIONSHIP_TYPES.get(new_rel, new_rel)
            return (
                f"You already have the maximum of {limit} for {label}. "
                f"Move or remove one of those first."
            )
    return None


def _apply_nomination_correction(db, leader_info, base_url,
                                 old_email, new_email, new_relationship):
    """
    Update a nominee's email and relationship on the roster, and on their rater
    row if they haven't yet responded.

    The roster is ALWAYS updated, so the visible outcome is identical for
    everyone. That is what stops the result revealing who has responded.

    The rater row is only touched when `get_unsevered_rater_by_email` finds it,
    which by definition means they have not submitted. Two reasons that is right
    on substance, not just a privacy dodge:
      - Writing an address onto a severed row would re-identify an anonymous
        response.
      - Someone who has already answered did so in the context of the
        relationship they were invited under, so their answers belong in that
        group. Recategorising them afterwards would misrepresent their input, and
        moving anonymous responses between groups would let someone work out
        which group a response sits in by watching the averages shift.
    """
    db.update_nomination_entry(
        leader_info['id'], old_email,
        new_email=new_email, new_relationship=new_relationship
    )

    rater = db.get_unsevered_rater_by_email(leader_info['id'], old_email)
    if rater is None or rater.get('completed'):
        return

    email_changed = new_email != old_email
    db.update_rater(rater['id'], email=new_email, relationship=new_relationship)

    # Only re-invite when the address actually changed. A relationship tweak does
    # not alter the invitation copy, so re-sending would just be noise.
    if email_changed and EMAIL_AVAILABLE and is_email_configured():
        updated = db.get_rater(rater['id'])
        if updated:
            send_rater_invitation(updated, leader_info['name'], base_url, db)


def render_progress_section(db, leader_info, raters):
    """
    Render the response progress section — total-level only.

    Per the anonymity design principle, this never shows a per-group or
    per-person breakdown: only the overall total across everyone nominated,
    gated so it can never resolve to a single outstanding (or single
    respondent) individual by subtraction.
    """
    base_url = st.session_state.get('portal_base_url', get_app_base_url())

    email_configured = EMAIL_AVAILABLE and is_email_configured()

    if not raters:
        st.info("You haven't nominated any raters yet. Go to the 'Nominate Raters' tab to add your feedback providers.")
        return

    st.subheader("Response Progress")

    completed_count = sum(1 for r in raters if r.get('completed'))
    total_count = len(raters)

    st.markdown(f"### {_progress_summary_text(completed_count, total_count)}")
    st.caption(
        "To protect anonymity, individual and group-level response status "
        "isn't shown here — only the overall total across everyone you've nominated."
    )

    incomplete_raters = [r for r in raters if not r.get('completed')]

    if incomplete_raters:
        st.markdown("---")
        if email_configured:
            if st.button("🔔 Remind Everyone Still to Respond", use_container_width=True):
                for rater in incomplete_raters:
                    # Skip anyone with no address on file. Severed raters have a
                    # NULL email, but they are complete by definition and so
                    # never reach this loop; this guards raters added without one.
                    if not rater.get('email'):
                        continue
                    send_rater_reminder(rater, leader_info['name'], base_url, db)
                st.success("Reminders sent to anyone who hasn't responded yet.")
        else:
            st.caption("Email isn't configured, so reminders can't be sent automatically yet.")


def render_guidelines_section():
    """Render the guidelines and help section."""
    
    st.subheader("360 Feedback Guidelines")
    
    st.markdown("""
    ### Who Should You Nominate?
    
    The quality of your 360 feedback depends on choosing raters who can provide meaningful insights 
    into your leadership. Here's guidance on each category:
    
    ---
    
    **👔 Line Manager (Boss)** — *1-2 required*
    
    Your direct line manager should always be included. If you also have a dotted-line, matrix, 
    or secondary reporting relationship, you may add them as well.
    
    *Examples: Direct manager, Regional Director, dotted-line VP*
    
    ---
    
    **👥 Peers** — *Minimum 3, suggested 5*
    
    Colleagues at a similar level who work alongside you. They should have regular interaction 
    with you and be able to observe your leadership behaviours.
    
    *Examples: Fellow Dealer Principals, Regional peers, Department heads at same level*
    
    ---
    
    **📋 Direct Reports** — *Minimum 3 if applicable, suggested 5*
    
    People who report directly to you. If you have fewer than 3 direct reports, include all of them 
    and make up the numbers with Peers or Others.
    
    *Examples: Sales Managers, Service Managers, team members who report to you*
    
    ---
    
    **🔄 Others** — *Optional, but 3 or more if you use it at all*

    Additional stakeholders who can provide valuable perspective. This might include internal
    customers, matrix reports, key suppliers, or other regular contacts.

    *Examples: Brand representatives, key suppliers, internal stakeholders from other functions*

    Either leave this category empty or nominate at least 3. One or two is the one combination
    to avoid, for the reason set out below.

    ---

    ### Why Minimum Numbers?

    We require a minimum of **3 respondents** in Peers and Direct Reports to ensure
    **anonymity**. With fewer than 3, individual responses could be identifiable, which would
    undermine the candour of the feedback.

    If a group does fall below 3, we combine it into Others so nobody's individual view can be
    picked out. That is why **Others itself needs 3 or more if you use it**: it is the category
    everything else gets combined into, so there is nothing larger for a thin Others group to
    hide inside. One or two people there cannot be reported anonymously at all, and their
    feedback would have to be left out of your report. Better to ask three or more, or to place
    those people in whichever of the other categories genuinely fits.

    We suggest **5 raters per category** as best practice — this provides richer data and
    accounts for any non-responses.
    
    ---
    
    ### Tips for Better Feedback
    
    - **Choose people who see you regularly** — occasional contacts won't have enough data
    - **Include a range of perspectives** — people you work well with AND those you find challenging
    - **Be realistic about response rates** — not everyone will respond, so nominate more than the minimum
    - **Respect people's time** — let nominees know you've added them and why their input matters
    """)
