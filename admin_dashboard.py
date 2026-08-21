#!/usr/bin/env python3
"""
Admin dashboard for Bentley Compass 360.
Provides management interface for leaders, raters, and report generation.
"""
import streamlit as st
import pandas as pd
import random
from datetime import datetime
from framework import (
    RELATIONSHIP_TYPES, GROUP_DISPLAY, MIN_RESPONSES_FOR_REPORT,
    RELATIONSHIP_INPUT_HELP, normalise_relationship, DIMENSIONS, get_logo_data_uri
)

# Try to import email functionality
try:
    from email_sender import (
        is_email_configured, 
        send_rater_invitation, 
        send_rater_reminder,
        send_bulk_invitations,
        send_bulk_reminders,
        send_leader_notification,
        send_portal_invitation,
        send_leader_nomination_reminder,
        send_bulk_portal_invitations,
        get_app_base_url
    )
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

    def get_app_base_url():
        """Fallback when email_sender is unavailable; links are display-only then."""
        return ""


def _search_leaders(leaders, query):
    """
    Filter leaders by a case-insensitive substring match against name or
    retailer. Name is a single field (not split first/last), so a plain
    substring search already covers "search by first or last name" without
    needing two separate inputs.
    """
    if not query:
        return leaders
    q = query.strip().lower()
    if not q:
        return leaders
    return [
        l for l in leaders
        if q in (l.get('name') or '').lower() or q in (l.get('dealership') or '').lower()
    ]


def render_admin_dashboard(db):
    """Render the admin dashboard."""
    
    # Header
    logo_uri = get_logo_data_uri()
    logo_html = f'<img src="{logo_uri}" class="main-title-logo">' if logo_uri else ''
    st.markdown(f'{logo_html}<p class="main-title">BENTLEY COMPASS 360</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Administrator Dashboard</p>', unsafe_allow_html=True)
    
    # Navigation tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        ":material/bar_chart: Overview",
        ":material/group: Leaders",
        ":material/rocket_launch: Leader Portals",
        ":material/mail: Links & Tracking",
        ":material/description: Reports",
        ":material/settings: Settings"
    ])
    
    with tab1:
        render_overview_tab(db)
    
    with tab2:
        render_leaders_tab(db)
    
    with tab3:
        render_portal_management_tab(db)
    
    with tab4:
        render_links_tab(db)
    
    with tab5:
        render_reports_tab(db)
    
    with tab6:
        render_settings_tab(db)


def render_settings_tab(db):
    """Render the settings/admin tab."""
    
    settings_subtab1, settings_subtab2, settings_subtab3, settings_subtab4 = st.tabs(
        [":material/folder: Cohorts", ":material/mail: Email", ":material/database: Database", ":material/info: App Info"]
    )
    
    with settings_subtab1:
        render_cohort_management(db)
    
    with settings_subtab2:
        render_email_settings(db)
    
    with settings_subtab3:
        render_database_management(db)
    
    with settings_subtab4:
        render_app_info(db)


def render_email_settings(db):
    """Render email configuration status and settings."""
    
    st.subheader("Email Configuration")
    
    if not EMAIL_AVAILABLE:
        st.error("Email module not available. Check that email_sender.py exists.", icon=":material/error:")
        return
    
    if is_email_configured():
        st.success("Email is configured and ready to send", icon=":material/check_circle:")
        
        st.markdown("""
        **Email features available:**
        - Send rater invitations with unique feedback links
        - Send reminders to incomplete raters
        - Notify leaders when their feedback is ready
        
        Go to **Links & Tracking** tab to send emails.
        """)
        
        # Test email option
        st.markdown("---")
        st.markdown("**Test Email**")
        test_email = st.text_input("Send test email to:", placeholder="your@email.com")
        if st.button("Send Test Email") and test_email:
            from email_sender import _send_email, _get_rater_invitation_html
            
            html = _get_rater_invitation_html("Test Recipient", "Test Leader", "Peers", "https://example.com/test")
            success, message = _send_email(
                test_email,
                "Test Recipient",
                "Test Email — Bentley Compass 360",
                html
            )
            
            if success:
                st.success(f"Test email sent to {test_email}", icon=":material/check_circle:")
            else:
                st.error(f"Failed: {message}", icon=":material/error:")
    
    else:
        st.warning("Email is not configured", icon=":material/warning:")
        
        st.markdown("""
        To enable email sending, add the following to your Streamlit secrets 
        (in the Streamlit Cloud dashboard or `.streamlit/secrets.toml` locally):
        
        ```toml
        [email]
        smtp_server = "smtp.office365.com"  # or your SMTP server
        smtp_port = 587
        username = "your-email@domain.com"
        password = "your-app-password"
        sender_email = "your-email@domain.com"
        ```

        The From name recipients see is always "Bentley Compass 360" — it's
        not configurable here, so replies always go to a real monitored
        inbox rather than a personal name with no way back to the system.
        
        **For Microsoft 365:**
        - Use `smtp.office365.com` with port 587
        - Generate an app password in your Microsoft account security settings
        
        **For Gmail:**
        - Use `smtp.gmail.com` with port 587
        - Enable 2FA and generate an app password
        
        **For GoDaddy M365:**
        - Use `smtp.office365.com` with port 587
        - Use your GoDaddy M365 email and app password
        """)


def render_cohort_management(db):
    """Render cohort management section."""
    
    st.subheader("Cohort Management")
    
    # Get existing cohorts from leaders
    leaders = db.get_all_leaders()
    existing_cohorts = sorted(set(l.get('cohort', 'Unassigned') for l in leaders if l.get('cohort')))
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Add New Cohort**")
        new_cohort = st.text_input("Cohort Name", placeholder="e.g., April 2026")
        if st.button("Add Cohort", icon=":material/add:", disabled=not new_cohort):
            if new_cohort not in existing_cohorts:
                # Store cohort in a cohorts table
                db.add_cohort(new_cohort)
                st.success(f"Cohort '{new_cohort}' created!")
                st.rerun()
            else:
                st.warning("Cohort already exists.")
    
    with col2:
        st.markdown("**Existing Cohorts**")
        all_cohorts = db.get_all_cohorts()
        if all_cohorts:
            for cohort in all_cohorts:
                cohort_leaders = [l for l in leaders if l.get('cohort') == cohort['name']]
                completed = sum(1 for l in cohort_leaders if l['completed_raters'] >= 5)
                
                col_name, col_stats, col_del = st.columns([3, 2, 1])
                with col_name:
                    st.write(f"**{cohort['name']}**")
                with col_stats:
                    st.caption(f"{len(cohort_leaders)} leaders, {completed} ready")
                with col_del:
                    if st.button("", icon=":material/delete:", key=f"del_cohort_{cohort['id']}", help="Delete cohort"):
                        db.delete_cohort(cohort['id'])
                        st.rerun()
        else:
            st.info("No cohorts created yet. Add one or they'll be created automatically when adding leaders.")
    
    st.markdown("---")
    
    # Cohort filtering for main views
    st.markdown("**Dashboard Filter**")
    st.write("Select a cohort to filter the Overview, Links, and Reports tabs:")
    
    filter_options = ["All Cohorts"] + [c['name'] for c in db.get_all_cohorts()]
    
    # Also include any cohorts from leaders that aren't in the cohorts table
    for cohort in existing_cohorts:
        if cohort and cohort not in filter_options:
            filter_options.append(cohort)
    
    selected_filter = st.selectbox(
        "Active Cohort Filter",
        options=filter_options,
        key="cohort_filter"
    )
    
    # Store in session state for other tabs to use
    if selected_filter == "All Cohorts":
        st.session_state['active_cohort_filter'] = None
    else:
        st.session_state['active_cohort_filter'] = selected_filter
    
    if st.session_state.get('active_cohort_filter'):
        st.success(f"Filtering by: {st.session_state['active_cohort_filter']}")
    else:
        st.info("Showing all cohorts")


def render_database_management(db):
    """Render database management section."""
    
    st.subheader("Database Management")
    
    st.warning("These actions cannot be undone. Use with caution.", icon=":material/warning:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Clear All Data**")
        st.write("Delete all leaders, raters, and feedback. Reloads demo data on next refresh.")
        
        if st.button("Clear Database", icon=":material/delete:", type="secondary"):
            st.session_state['confirm_clear'] = True
        
        if st.session_state.get('confirm_clear'):
            st.error("Are you sure? This will delete ALL data.")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, clear everything", type="primary"):
                    # Delete the database file
                    import os
                    if os.path.exists('compass_360.db'):
                        os.remove('compass_360.db')
                    st.session_state['confirm_clear'] = False
                    st.success("Database cleared. Refresh the page to reload demo data.")
                    st.rerun()
            with col_no:
                if st.button("Cancel"):
                    st.session_state['confirm_clear'] = False
                    st.rerun()
    
    with col2:
        st.markdown("**Export Data**")
        st.write("Download all feedback data as CSV for backup.")
        
        if st.button("Export All Data", icon=":material/download:"):
            # Get all leaders and their data
            leaders = db.get_all_leaders()
            if leaders:
                export_data = []
                for leader in leaders:
                    data, comments = db.get_leader_feedback_data(leader['id'])
                    for item_num, scores in data['by_item'].items():
                        row = {
                            'Leader': leader['name'],
                            'Retailer': leader.get('dealership', ''),
                            'Cohort': leader.get('cohort', ''),
                            'Item': item_num,
                            'Statement': scores.get('text', ''),
                            'Self': scores.get('Self'),
                            'Boss': scores.get('Boss'),
                            'Peers': scores.get('Peers'),
                            'DRs': scores.get('DRs'),
                            'Others': scores.get('Others'),
                            'Combined': scores.get('Combined'),
                            'Gap': scores.get('Gap')
                        }
                        export_data.append(row)
                
                df = pd.DataFrame(export_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    f"compass_360_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
            else:
                st.info("No data to export.")


def render_app_info(db):
    """Render app info section."""
    
    st.subheader("App Information")
    
    stats = db.get_dashboard_stats()
    conn_info = db.get_connection_info()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Database:** {conn_info['type']}")
        if conn_info['type'] == 'Turso Cloud':
            st.write(f"**URL:** {conn_info['url'][:50]}...")
        else:
            st.write(f"**Path:** {conn_info.get('path', 'N/A')}")
        st.write(f"**Status:** {conn_info['status']}")
    
    with col2:
        st.write(f"**Total leaders:** {stats['total_leaders']}")
        st.write(f"**Total raters:** {stats['total_raters']}")
        st.write(f"**Completed responses:** {stats['completed_responses']}")
        st.write(f"**Ready for Full 360:** {stats['ready_for_report']}")
        
        # Email status
        if EMAIL_AVAILABLE and is_email_configured():
            st.write("**Email:** :material/check_circle: Configured")
        else:
            st.write("**Email:** :material/cancel: Not configured")


def render_overview_tab(db):
    """Render the overview/stats tab."""
    
    # Check for cohort filter
    cohort_filter = st.session_state.get('active_cohort_filter')
    
    # Get all leaders
    all_leaders = db.get_all_leaders()
    
    if not all_leaders:
        st.info("No leaders added yet. Go to the 'Leaders' tab to add leaders.")
        return
    
    # Group leaders by cohort
    cohorts = {}
    for leader in all_leaders:
        cohort_name = leader.get('cohort') or 'Unassigned'
        if cohort_name not in cohorts:
            cohorts[cohort_name] = []
        cohorts[cohort_name].append(leader)
    
    # If no filter active, show cohort summary buttons
    if not cohort_filter:
        st.subheader("Cohorts")
        
        # Calculate stats per cohort
        for cohort_name in sorted(cohorts.keys()):
            cohort_leaders = cohorts[cohort_name]
            total_leaders = len(cohort_leaders)
            total_raters = sum(l['total_raters'] for l in cohort_leaders)
            completed = sum(l['completed_raters'] for l in cohort_leaders)
            ready = sum(1 for l in cohort_leaders if l['completed_raters'] >= MIN_RESPONSES_FOR_REPORT)
            response_rate = round(completed / total_raters * 100) if total_raters > 0 else 0
            
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Cohort summary card
                st.markdown(f"""
                **{cohort_name}**  
                {total_leaders} leaders · {ready} ready for Full 360 · {response_rate}% response rate
                """)
            
            with col2:
                if st.button("View", icon=":material/arrow_forward:", key=f"view_cohort_{cohort_name}"):
                    st.session_state['active_cohort_filter'] = cohort_name
                    st.rerun()
            
            st.divider()
        
        # Overall stats at bottom
        st.markdown("---")
        st.subheader("Overall Statistics")
        
        total_leaders = len(all_leaders)
        total_raters = sum(l['total_raters'] for l in all_leaders)
        completed_responses = sum(l['completed_raters'] for l in all_leaders)
        ready_for_report = sum(1 for l in all_leaders if l['completed_raters'] >= MIN_RESPONSES_FOR_REPORT)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Leaders", total_leaders)
        with col2:
            st.metric("Total Raters", total_raters)
        with col3:
            completion_rate = round(completed_responses / total_raters * 100) if total_raters > 0 else 0
            st.metric("Response Rate", f"{completion_rate}%")
        with col4:
            st.metric("Ready for Report", ready_for_report)
    
    else:
        # Filtered view - show leaders in selected cohort
        leaders = [l for l in all_leaders if (l.get('cohort') or 'Unassigned') == cohort_filter]
        
        # Back button and cohort header
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("All Cohorts", icon=":material/arrow_back:"):
                st.session_state['active_cohort_filter'] = None
                st.rerun()
        with col2:
            st.subheader(f":material/folder: {cohort_filter}")
        
        # Stats for this cohort
        total_leaders = len(leaders)
        total_raters = sum(l['total_raters'] for l in leaders)
        completed_responses = sum(l['completed_raters'] for l in leaders)
        ready_for_report = sum(1 for l in leaders if l['completed_raters'] >= MIN_RESPONSES_FOR_REPORT)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Leaders", total_leaders)
        with col2:
            st.metric("Total Raters", total_raters)
        with col3:
            completion_rate = round(completed_responses / total_raters * 100) if total_raters > 0 else 0
            st.metric("Response Rate", f"{completion_rate}%")
        with col4:
            st.metric("Ready for Report", ready_for_report)
        
        st.markdown("---")
        st.subheader("Leader Status")

        search_query = st.text_input(
            "Search leaders", key="overview_tab_search",
            placeholder="Name or retailer...", label_visibility="collapsed"
        )
        leaders = _search_leaders(leaders, search_query)
        if search_query and not leaders:
            st.info(f"No leaders match \"{search_query}\".")

        # Show leaders in this cohort
        for leader in leaders:
            completed = leader['completed_raters']
            total = leader['total_raters']
            self_done = leader['self_completed'] > 0
            
            if total == 0:
                status_text = "No raters assigned"
                status_type = "info"
            elif completed >= MIN_RESPONSES_FOR_REPORT:
                status_text = f":material/check: Ready for Full 360 ({completed}/{total})"
                status_type = "success"
            elif self_done and completed < MIN_RESPONSES_FOR_REPORT:
                status_text = f":material/check: Self done, awaiting others ({completed}/{total})"
                status_type = "success"
            elif completed > 0:
                status_text = f"In progress ({completed}/{total})"
                status_type = "warning"
            else:
                status_text = f"Awaiting responses (0/{total})"
                status_type = "info"
            
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    dealer_text = f" ({leader['dealership']})" if leader.get('dealership') else ""
                    st.markdown(f"**{leader['name']}**{dealer_text}")
                    year = leader.get('assessment_year', 1)
                    self_icon = ':material/check:' if self_done else ':material/circle:'
                    st.caption(f"Self: {self_icon} | Year: {year}")
                with col2:
                    if status_type == "success":
                        st.success(status_text)
                    elif status_type == "warning":
                        st.warning(status_text)
                    else:
                        st.info(status_text)
                st.divider()


def render_leaders_tab(db):
    """Render the leader management tab."""
    
    st.subheader("Add New Leader")
    
    with st.form("add_leader_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Leader Name *")
            email = st.text_input("Email *")

        with col2:
            dealership = st.text_input("Retailer *")
            cohort = st.text_input("Cohort (e.g., 'January 2026') *")

        if st.form_submit_button("Add Leader"):
            missing = []
            if not name:
                missing.append("leader name")
            if not email:
                missing.append("email")
            elif '@' not in email:
                missing.append("a valid email address")
            if not dealership:
                missing.append("retailer")
            if not cohort:
                missing.append("cohort")

            if missing:
                st.error(f"Please provide: {', '.join(missing)}")
            else:
                leader_id = db.add_leader(name, email, dealership, cohort)
                # Every leader completes a self-assessment, so their link is
                # created immediately rather than needing a separate manual step.
                db.add_rater(leader_id, 'Self', name, email)
                st.success(f"Added {name} successfully, with their self-assessment link ready.")
                st.rerun()
    
    st.markdown("---")
    
    st.subheader("Existing Leaders")

    leaders = db.get_all_leaders()

    if not leaders:
        st.info("No leaders added yet.")
        return

    search_query = st.text_input(
        "Search leaders", key="leaders_tab_search",
        placeholder="Name or retailer...", label_visibility="collapsed"
    )
    leaders = _search_leaders(leaders, search_query)
    if search_query and not leaders:
        st.info(f"No leaders match \"{search_query}\".")

    for leader in leaders:
        with st.expander(f"**{leader['name']}** - {leader.get('dealership', 'No retailer')}"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**Email:** {leader.get('email', 'Not set')}")
                st.write(f"**Cohort:** {leader.get('cohort', 'Not set')}")
            
            with col2:
                st.write(f"**Retailer:** {leader.get('dealership', 'Not set')}")
                st.write(f"**Assessment Year:** {leader.get('assessment_year', 1)}")
            
            with col3:
                if st.button("Delete", key=f"delete_leader_{leader['id']}", type="secondary"):
                    if st.session_state.get(f"confirm_delete_{leader['id']}"):
                        db.delete_leader(leader['id'])
                        st.success(f"Deleted {leader['name']}")
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_{leader['id']}"] = True
                        st.warning("Click again to confirm deletion")
    
    # Bulk import
    st.markdown("---")
    st.subheader("Bulk Import Leaders")
    
    st.markdown("""
    Upload a CSV file with columns: `name`, `email`, `retailer`, `cohort` — all four are required for every row.
    """)

    uploaded_file = st.file_uploader("Choose CSV file", type="csv")

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.write("Preview:")
        st.dataframe(df.head())

        if st.button("Import All"):
            errors = []
            valid_rows = []

            for i, row in df.iterrows():
                row_num = i + 2  # header is row 1
                name = row.get('name')
                email = row.get('email')
                retailer = row.get('retailer')
                cohort = row.get('cohort')

                if not pd.notna(name) or not str(name).strip():
                    errors.append(f"Row {row_num}: missing name")
                elif not pd.notna(email) or '@' not in str(email):
                    errors.append(f"Row {row_num} ({name}): missing or invalid email")
                elif not pd.notna(retailer) or not str(retailer).strip():
                    errors.append(f"Row {row_num} ({name}): missing retailer")
                elif not pd.notna(cohort) or not str(cohort).strip():
                    errors.append(f"Row {row_num} ({name}): missing cohort")
                else:
                    valid_rows.append({
                        'name': str(name).strip(),
                        'email': str(email).strip(),
                        'retailer': str(retailer).strip(),
                        'cohort': str(cohort).strip(),
                    })

            if errors:
                st.error(
                    "Import stopped — fix these rows and re-upload:\n\n" +
                    "\n".join(f"- {e}" for e in errors)
                )
            else:
                for r in valid_rows:
                    leader_id = db.add_leader(
                        name=r['name'],
                        email=r['email'],
                        dealership=r['retailer'],
                        cohort=r['cohort']
                    )
                    db.add_rater(leader_id, 'Self', r['name'], r['email'])
                st.success(f"Imported {len(valid_rows)} leader(s), each with their self-assessment link ready.")
                st.rerun()


def render_portal_management_tab(db):
    """Render the leader portal management tab."""
    
    st.subheader("Leader Portal Management")
    
    st.markdown("""
    This tab manages the **leader self-service portals** where leaders nominate their own raters.
    
    **Workflow:**
    1. Leaders complete self-assessment (via Links & Tracking)
    2. After Module 1, send them their portal link
    3. Leaders add their raters through the portal
    4. Raters automatically receive invitation emails
    """)
    
    # Check email configuration
    email_configured = EMAIL_AVAILABLE and is_email_configured()
    if not email_configured:
        st.warning("Email not configured. Go to Settings :material/arrow_forward: Email to set up.", icon=":material/warning:")
    
    # Get base URL
    base_url = st.text_input(
        "Base URL for portal links",
        value=get_app_base_url(),
        help="Your deployed app URL. Set [app] base_url in this deployment's secrets "
             "so it defaults correctly and links never point at another environment."
    )
    
    st.markdown("---")
    
    # Get all leaders with their status
    leaders = db.get_all_leaders()
    
    if not leaders:
        st.info("No leaders added yet. Go to Leaders tab to add them.")
        return
    
    # Categorise leaders by their stage in the process
    no_self_assessment = []
    ready_for_portal = []  # Self done, no portal email sent
    portal_sent_no_raters = []  # Portal email sent, but no/few raters nominated
    portal_sent_with_raters = []  # Portal sent and raters nominated
    
    for leader in leaders:
        raters = db.get_raters_for_leader(leader['id'])
        self_rater = next((r for r in raters if r['relationship'] == 'Self'), None)
        self_complete = self_rater and self_rater.get('completed')
        other_raters = [r for r in raters if r['relationship'] != 'Self']
        
        leader['self_complete'] = self_complete
        leader['other_rater_count'] = len(other_raters)
        leader['other_raters'] = other_raters
        
        if not self_complete:
            no_self_assessment.append(leader)
        elif not leader.get('portal_email_sent_at'):
            ready_for_portal.append(leader)
        elif len(other_raters) < 5:
            portal_sent_no_raters.append(leader)
        else:
            portal_sent_with_raters.append(leader)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Awaiting Self-Assessment", len(no_self_assessment))
    with col2:
        st.metric("Ready for Portal Email", len(ready_for_portal))
    with col3:
        st.metric("Need to Nominate Raters", len(portal_sent_no_raters))
    with col4:
        st.metric("Raters Nominated", len(portal_sent_with_raters))
    
    st.markdown("---")
    
    # Section 1: Ready for Portal Email
    st.subheader(":material/send: Send Portal Invitations")
    
    if ready_for_portal:
        st.success(f"{len(ready_for_portal)} leader(s) have completed self-assessment and are ready for portal email")
        
        # Show list
        for leader in ready_for_portal:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{leader['name']}**")
                st.caption(f"{leader.get('dealership', '')} · {leader.get('cohort', '')}")
            with col2:
                st.write(f":material/mail: {leader.get('email', 'No email')}")
            with col3:
                if email_configured and leader.get('email'):
                    if st.button("Send Portal", key=f"send_portal_{leader['id']}"):
                        success, msg = send_portal_invitation(leader, base_url, db)
                        if success:
                            st.success(f"Sent to {leader['name']}", icon=":material/check_circle:")
                            st.rerun()
                        else:
                            st.error(f"Failed: {msg}")
        
        # Bulk send button
        st.markdown("---")
        leaders_with_email = [l for l in ready_for_portal if l.get('email')]
        if email_configured and leaders_with_email:
            if st.button(f"Send Portal Email to All ({len(leaders_with_email)})", icon=":material/send:", type="primary"):
                with st.spinner("Sending portal invitations..."):
                    sent, failed, results = send_bulk_portal_invitations(leaders_with_email, base_url, db)
                    if sent > 0:
                        st.success(f"Sent {sent} portal invitation(s)", icon=":material/check_circle:")
                    if failed > 0:
                        st.warning(f"{failed} failed", icon=":material/warning:")
                    st.rerun()
    else:
        st.info("No leaders ready for portal email. They need to complete their self-assessment first.")
    
    st.markdown("---")
    
    # Section 2: Need to Nominate Raters
    st.subheader(":material/warning: Leaders Who Need to Nominate Raters")
    
    if portal_sent_no_raters:
        st.warning(f"{len(portal_sent_no_raters)} leader(s) have received their portal but haven't nominated enough raters")
        
        for leader in portal_sent_no_raters:
            col1, col2, col3, col4 = st.columns([2.5, 1.5, 1.5, 1])
            with col1:
                st.write(f"**{leader['name']}**")
                st.caption(f"{leader.get('dealership', '')}")
            with col2:
                st.write(f"Raters: {leader['other_rater_count']}")
            with col3:
                portal_sent = leader.get('portal_email_sent_at', '')
                if portal_sent:
                    st.caption(f"Portal sent: {str(portal_sent)[:10]}")
            with col4:
                if email_configured and leader.get('email') and leader.get('portal_token'):
                    if st.button("Remind", icon=":material/notifications:", key=f"remind_nom_{leader['id']}"):
                        leader['nominated_count'] = leader['other_rater_count']
                        success, msg = send_leader_nomination_reminder(leader, base_url, db)
                        if success:
                            st.toast(f"Reminder sent to {leader['name']}")
                        else:
                            st.toast(f"Failed: {msg}")
        
        # Bulk remind
        st.markdown("---")
        leaders_to_remind = [l for l in portal_sent_no_raters if l.get('email') and l.get('portal_token')]
        if email_configured and leaders_to_remind:
            if st.button(f"Send Reminder to All ({len(leaders_to_remind)})", icon=":material/notifications:"):
                sent = 0
                for leader in leaders_to_remind:
                    leader['nominated_count'] = leader['other_rater_count']
                    success, _ = send_leader_nomination_reminder(leader, base_url, db)
                    if success:
                        sent += 1
                st.success(f"Sent {sent} reminder(s)")
    else:
        st.info("All leaders who have received portal invitations have nominated raters.")
    
    st.markdown("---")
    
    # Section 3: Leaders with Raters Nominated (overview)
    st.subheader(":material/check_circle: Leaders with Raters Nominated")
    
    if portal_sent_with_raters:
        for leader in portal_sent_with_raters:
            # Calculate response stats
            completed = sum(1 for r in leader['other_raters'] if r.get('completed'))
            total = leader['other_rater_count']
            
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{leader['name']}**")
                st.caption(f"{leader.get('dealership', '')}")
            with col2:
                if completed == total:
                    st.success(f"{completed}/{total} responses", icon=":material/check:")
                else:
                    st.warning(f"{completed}/{total} responses", icon=":material/schedule:")
            with col3:
                # Link to view portal
                if leader.get('portal_token'):
                    portal_url = f"{base_url}?portal={leader['portal_token']}"
                    st.markdown(f"[View Portal]({portal_url})")
    else:
        st.info("No leaders have nominated raters yet.")
    
    st.markdown("---")
    
    # Section 4: Awaiting Self-Assessment
    with st.expander(f"Awaiting Self-Assessment ({len(no_self_assessment)})", icon=":material/assignment:"):
        if no_self_assessment:
            for leader in no_self_assessment:
                st.write(f"• {leader['name']} ({leader.get('dealership', 'No retailer')})")
        else:
            st.info("All leaders have completed their self-assessment.")
    
    st.markdown("---")
    
    # Section 5: All Portal Links (for reference)
    st.subheader(":material/link: All Portal Links")
    
    with st.expander("View/Generate Portal Links"):
        st.caption("Generate portal tokens for leaders who don't have one yet, or view existing links.")
        
        for leader in leaders:
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                st.write(f"**{leader['name']}**")
            with col2:
                if leader.get('portal_token'):
                    portal_url = f"{base_url}?portal={leader['portal_token']}"
                    st.code(portal_url, language=None)
                else:
                    st.caption("No token generated")
            with col3:
                if not leader.get('portal_token'):
                    if st.button("Generate", key=f"gen_token_{leader['id']}"):
                        token = db.generate_portal_token(leader['id'])
                        st.success(f"Generated token")
                        st.rerun()


def _has_self_rater(db, leader_id):
    """True if this leader already has a Self rater row (added via Add Leader)."""
    return any(r['relationship'] == 'Self' for r in db.get_raters_for_leader(leader_id))


_TEST_KEEP_COMMENTS = [
    "Keep bringing the same energy and consistency to the team.",
    "Keep making time for people even when things are busy.",
    "Keep setting the standard on follow-through.",
    "Keep being someone people feel comfortable raising problems with.",
    "Keep pushing the team to aim higher without burning people out.",
]

_TEST_CHANGE_COMMENTS = [
    "Delegate a little more to free up time for strategic thinking.",
    "Bring the team into changes earlier, before decisions feel final.",
    "Be a bit more explicit about the 'why' behind priorities.",
    "Slow down in meetings to make sure quieter voices get heard.",
    "Follow up more consistently on things raised in one-to-ones.",
]

# Comment templates keyed by whether the rater's actual generated score for that
# dimension came out high or low, so comments correlate with the numbers instead
# of reading as generic praise regardless of rating — closer to how real raters
# write, and gives the Key Themes synthesis genuine texture to work with instead
# of the same sentence repeated across every rater.
_TEST_STRENGTH_COMMENTS = [
    "One of the real strengths — comes through consistently.",
    "This is where they genuinely shine, especially under pressure.",
    "Others notice this a lot; it's a clear asset.",
    "Consistently strong here, worth them knowing that landed.",
    "A standout area compared to most leaders I've worked with.",
]

_TEST_DEVELOPMENT_COMMENTS = [
    "Room to grow here — doesn't always land as intended.",
    "This is the area I'd most like to see develop further.",
    "Inconsistent at times, particularly when things get busy.",
    "Would benefit from more focus on this going forward.",
    "Not the strongest area currently; worth prioritising.",
]


def _generate_test_feedback():
    """
    Fabricate a plausible ratings + comments payload for one rater, for testing
    report generation without filling in every form by hand. Same shape
    database.submit_feedback expects from a real submission.
    """
    ratings = {}
    for item_num in range(1, 46):
        # A small share of "no opportunity to observe" answers, same as a real
        # rater population would produce.
        if random.random() < 0.05:
            ratings[item_num] = 0
        else:
            ratings[item_num] = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 25, 35, 25])[0]

    comments = {}
    for dim_name, (start, end) in DIMENSIONS.items():
        if random.random() >= 0.6:
            continue
        dim_scores = [ratings[n] for n in range(start, end + 1) if ratings[n] > 0]
        avg = sum(dim_scores) / len(dim_scores) if dim_scores else 3
        pool = _TEST_STRENGTH_COMMENTS if avg >= 3.5 else _TEST_DEVELOPMENT_COMMENTS
        comments[dim_name] = random.choice(pool)

    comments['keep'] = random.choice(_TEST_KEEP_COMMENTS)
    comments['change'] = random.choice(_TEST_CHANGE_COMMENTS)

    return ratings, comments


def render_links_tab(db):
    """Render the links generation and tracking tab."""
    
    leaders = db.get_all_leaders()
    
    if not leaders:
        st.info("Add leaders first in the 'Leaders' tab.")
        return
    
    # Email status indicator
    email_configured = EMAIL_AVAILABLE and is_email_configured()
    if email_configured:
        st.success("Email sending is enabled", icon=":material/mail:")
    else:
        st.info("Email not configured — go to Settings :material/arrow_forward: Email to set up", icon=":material/mail:")
    
    st.markdown("---")
    
    # Leader selector
    leader_options = {l['id']: f"{l['name']} ({l.get('dealership', 'No retailer')})" for l in leaders}
    selected_leader_id = st.selectbox(
        "Select Leader",
        options=list(leader_options.keys()),
        format_func=lambda x: leader_options[x]
    )
    
    selected_leader = next(l for l in leaders if l['id'] == selected_leader_id)
    
    st.markdown("---")
    
    # Get base URL
    base_url = st.text_input(
        "Base URL for links",
        value=get_app_base_url(),
        help="Your deployed app URL. Set [app] base_url in this deployment's secrets "
             "so it defaults correctly and links never point at another environment."
    )
    
    # Add raters section
    st.subheader(f"Add Raters for {selected_leader['name']}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("add_rater_form"):
            relationship = st.selectbox(
                "Relationship Type",
                options=list(RELATIONSHIP_TYPES.keys()),
                format_func=lambda x: RELATIONSHIP_TYPES[x]
            )
            rater_name = st.text_input("Rater Name (optional)")
            rater_email = st.text_input("Rater Email (optional)", 
                                        help="Add email to enable sending invitations")
            
            if st.form_submit_button("Add Rater"):
                if relationship == 'Self' and _has_self_rater(db, selected_leader_id):
                    st.warning(f"{selected_leader['name']} already has a self-assessment link — not adding another.")
                else:
                    rater_id, token = db.add_rater(selected_leader_id, relationship, rater_name, rater_email)
                    st.success(f"Added rater successfully!")
                    st.rerun()
    
    with col2:
        st.markdown("**Quick Add Multiple Raters**")
        
        with st.form("quick_add_form"):
            num_peers = st.number_input("Number of Peers", min_value=0, max_value=10, value=0)
            num_drs = st.number_input("Number of Direct Reports", min_value=0, max_value=10, value=0)
            num_others = st.number_input("Number of Others", min_value=0, max_value=10, value=0)
            add_self = st.checkbox("Add Self-Assessment", value=True)
            add_boss = st.checkbox("Add Line Manager", value=True)
            
            if st.form_submit_button("Create All Raters"):
                count = 0
                if add_self:
                    if _has_self_rater(db, selected_leader_id):
                        st.info(f"{selected_leader['name']} already has a self-assessment link — skipped.")
                    else:
                        # Use leader's email for self-assessment
                        db.add_rater(selected_leader_id, 'Self', selected_leader['name'], selected_leader.get('email'))
                        count += 1
                if add_boss:
                    db.add_rater(selected_leader_id, 'Boss')
                    count += 1
                for _ in range(num_peers):
                    db.add_rater(selected_leader_id, 'Peers')
                    count += 1
                for _ in range(num_drs):
                    db.add_rater(selected_leader_id, 'DRs')
                    count += 1
                for _ in range(num_others):
                    db.add_rater(selected_leader_id, 'Others')
                    count += 1
                
                st.success(f"Created {count} rater links!")
                st.rerun()
    
    st.markdown("---")
    
    # Existing raters and their links
    st.subheader(f"Feedback Links for {selected_leader['name']}")
    
    raters = db.get_raters_for_leader(selected_leader_id)
    
    # Group raters by relationship (needed for both display and export)
    raters_by_group = {}
    for rater in raters:
        rel = rater['relationship']
        if rel not in raters_by_group:
            raters_by_group[rel] = []
        raters_by_group[rel].append(rater)
    
    if not raters:
        st.info("No raters added yet for this leader. Use the forms above or bulk import below.")
    else:
        # Email action buttons (if email is configured)
        if email_configured:
            st.markdown(":material/mail: **Email Actions**")
            
            col1, col2, col3 = st.columns(3)
            
            # Count raters with emails
            raters_with_email = [r for r in raters if r.get('email')]
            incomplete_with_email = [r for r in raters_with_email if not r.get('completed')]
            
            with col1:
                if st.button(f"Send All Invitations ({len(raters_with_email)})",
                            icon=":material/send:",
                            disabled=len(raters_with_email) == 0,
                            help="Send invitation emails to all raters with email addresses"):
                    with st.spinner("Sending invitations..."):
                        sent, failed, results = send_bulk_invitations(
                            raters_with_email, 
                            selected_leader['name'], 
                            base_url, 
                            db
                        )
                        if sent > 0:
                            st.success(f"Sent {sent} invitation(s)", icon=":material/check_circle:")
                        if failed > 0:
                            st.warning(f"{failed} failed to send", icon=":material/warning:")
                            for r in results:
                                if not r['success']:
                                    st.caption(f"  • {r['rater']}: {r['message']}")
            
            with col2:
                if st.button(f"Send Reminders ({len(incomplete_with_email)})",
                            icon=":material/notifications:",
                            disabled=len(incomplete_with_email) == 0,
                            help="Send reminders to incomplete raters with email addresses"):
                    with st.spinner("Sending reminders..."):
                        sent, failed, results = send_bulk_reminders(
                            incomplete_with_email, 
                            selected_leader['name'], 
                            base_url, 
                            db
                        )
                        if sent > 0:
                            st.success(f"Sent {sent} reminder(s)", icon=":material/check_circle:")
                        if failed > 0:
                            st.warning(f"{failed} failed to send", icon=":material/warning:")
            
            with col3:
                # Show email log
                if st.button("View Email Log", icon=":material/assignment:"):
                    st.session_state[f'show_email_log_{selected_leader_id}'] = True
            
            # Email log display
            if st.session_state.get(f'show_email_log_{selected_leader_id}'):
                email_log = db.get_email_log_for_leader(selected_leader_id, limit=20)
                if email_log:
                    st.markdown("**Recent Emails**")
                    log_df = pd.DataFrame([{
                        'Time': e['sent_at'][:16] if e.get('sent_at') else '',
                        'Type': e['email_type'],
                        'To': e['to_email'],
                        # st.dataframe renders cell values as plain data, not
                        # markdown, so this must stay a plain character rather
                        # than a :material/...: shortcode.
                        'Status': '✓' if e['success'] else '✗',
                        'Rater': e.get('rater_name') or '-'
                    } for e in email_log])
                    st.dataframe(log_df, use_container_width=True, hide_index=True)
                    
                    if st.button("Hide Log"):
                        st.session_state[f'show_email_log_{selected_leader_id}'] = False
                        st.rerun()
                else:
                    st.info("No emails sent yet for this leader.")

            st.markdown("---")

        # Testing tool: fabricate ratings/comments for raters who haven't
        # responded yet, so a report can be generated without filling in every
        # form by hand. Runs through the exact same submit_feedback path a real
        # rater uses (ratings, comments, mark complete, sever identity), so it is
        # a genuine test of report generation, not a shortcut around it.
        incomplete_raters = [r for r in raters if not r.get('completed')]
        if incomplete_raters:
            with st.expander(f"Testing: Simulate Responses ({len(incomplete_raters)} incomplete)", icon=":material/science:"):
                st.caption(
                    "Fills in plausible ratings and comments for every rater who "
                    "hasn't submitted yet and marks them complete, so you can "
                    "generate a full report without waiting on real responses."
                )
                if st.button(
                    f"Simulate {len(incomplete_raters)} response(s)",
                    key=f"simulate_{selected_leader_id}"
                ):
                    for rater in incomplete_raters:
                        ratings, comments = _generate_test_feedback()
                        db.submit_feedback(rater['id'], ratings, comments)
                    st.success(
                        f"Simulated {len(incomplete_raters)} response(s). "
                        f"A report can now be generated in the Reports tab."
                    )
                    st.rerun()

            st.markdown("---")

        # Testing tool: clear responses (ratings, comments, completed_at) for
        # non-Self raters so the same rater rows/tokens can be re-simulated,
        # without touching Self or the leader's own record. Does not restore
        # identity — a completed rater has already been through
        # sever_rater_identity either way, so name/email stay null regardless.
        completed_other_raters = [
            r for r in raters if r.get('completed') and r['relationship'] != 'Self'
        ]
        if completed_other_raters:
            with st.expander(
                f"Testing: Reset {len(completed_other_raters)} Response(s) for Retesting",
                icon=":material/science:"
            ):
                st.caption(
                    "Clears ratings and comments and reopens every non-Self "
                    "rater so you can run Simulate Responses again with the "
                    "same list of raters. Self is never touched. For "
                    "retesting on this sandbox only — clearing a genuinely "
                    "completed real rater's response discards their actual "
                    "feedback with no way to recover it."
                )
                if st.button(
                    f"Reset {len(completed_other_raters)} response(s)",
                    key=f"reset_responses_{selected_leader_id}"
                ):
                    for rater in completed_other_raters:
                        db.reset_rater_response(rater['id'])
                    st.success(
                        f"Reset {len(completed_other_raters)} response(s). "
                        f"Ready to simulate again."
                    )
                    st.rerun()

            st.markdown("---")

        # Display raters table
        for rel in ['Self', 'Boss', 'Peers', 'DRs', 'Others']:
            if rel not in raters_by_group:
                continue
            
            st.markdown(f"**{GROUP_DISPLAY.get(rel, rel)}** ({len(raters_by_group[rel])})")
            
            for i, rater in enumerate(raters_by_group[rel], 1):
                link = f"{base_url}?t={rater['token']}"
                
                # Determine status
                if rater['completed']:
                    status_icon = ":material/check_circle:"
                    status_text = "Complete"
                else:
                    status_icon = ":material/schedule:"
                    status_text = "Pending"
                
                # Get last email info
                has_email = bool(rater.get('email'))
                
                # Layout: Name | Email | Status | Actions
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 2, 0.5])
                
                with col1:
                    display_name = rater.get('name') or f"{GROUP_DISPLAY.get(rel, rel)} {i}"
                    st.write(f"{status_icon} {display_name}")
                
                with col2:
                    if has_email:
                        st.caption(f":material/mail: {rater['email']}")
                    else:
                        # Allow adding email
                        if st.session_state.get(f'edit_email_{rater["id"]}'):
                            new_email = st.text_input(
                                "Email", 
                                key=f"email_input_{rater['id']}", 
                                label_visibility="collapsed",
                                placeholder="Enter email"
                            )
                            if st.button("Save", key=f"save_email_{rater['id']}"):
                                if new_email:
                                    db.update_rater(rater['id'], email=new_email)
                                    st.session_state[f'edit_email_{rater["id"]}'] = False
                                    st.rerun()
                        else:
                            if st.button("+ Add email", key=f"add_email_{rater['id']}", 
                                        type="secondary", use_container_width=True):
                                st.session_state[f'edit_email_{rater["id"]}'] = True
                                st.rerun()
                
                with col3:
                    if rater['completed']:
                        st.markdown(f"<span style='color: green;'>Complete</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span style='color: orange;'>Pending</span>", unsafe_allow_html=True)
                
                with col4:
                    if email_configured and has_email and not rater['completed']:
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("", icon=":material/send:", key=f"send_inv_{rater['id']}", help="Send invitation"):
                                success, msg = send_rater_invitation(rater, selected_leader['name'], base_url, db)
                                if success:
                                    st.toast(f"Sent to {rater['email']}", icon=":material/check_circle:")
                                else:
                                    st.toast(f"Failed: {msg}", icon=":material/error:")
                        with btn_col2:
                            if st.button("", icon=":material/notifications:", key=f"send_rem_{rater['id']}", help="Send reminder"):
                                success, msg = send_rater_reminder(rater, selected_leader['name'], base_url, db)
                                if success:
                                    st.toast(f"Reminder sent", icon=":material/check_circle:")
                                else:
                                    st.toast(f"Failed: {msg}", icon=":material/error:")
                
                with col5:
                    if st.button("", icon=":material/delete:", key=f"del_rater_{rater['id']}", help="Delete rater"):
                        db.delete_rater(rater['id'])
                        st.rerun()
                
                # Show link
                st.code(link, language=None)
            
            st.markdown("---")
    
    # Export/Import section
    st.subheader(":material/download: Export / Import Raters")
    
    export_col, import_col = st.columns(2)
    
    with export_col:
        st.markdown("**Export Current Raters**")
        st.caption("Download all raters with their links for mail merge or records")
        
        if raters:
            # Build export data
            link_data = []
            for rel in ['Self', 'Boss', 'Peers', 'DRs', 'Others']:
                if rel in raters_by_group:
                    for i, rater in enumerate(raters_by_group[rel], 1):
                        link_data.append({
                            'Name': rater.get('name') or '',
                            'Email': rater.get('email') or '',
                            'Relationship': rel,
                            'Status': 'Complete' if rater['completed'] else 'Pending',
                            'Link': f"{base_url}?t={rater['token']}"
                        })
            
            df = pd.DataFrame(link_data)
            csv = df.to_csv(index=False)
            st.download_button(
                "Download Raters CSV",
                csv,
                f"raters_{selected_leader['name'].replace(' ', '_')}.csv",
                "text/csv",
                use_container_width=True
            )
        else:
            st.info("No raters to export")
    
    with import_col:
        st.markdown("**Bulk Import Raters**")
        st.caption("Upload a CSV to add multiple raters at once")
        
        # Template uses plain-English relationships, matching the leader portal.
        # Both importers normalise through framework.normalise_relationship, so
        # capitalisation and wording variants are accepted either side.
        template_df = pd.DataFrame({
            'name': ['John Smith', 'Sarah Jones', 'Mike Brown', 'Raj Patel'],
            'email': ['john@example.com', 'sarah@example.com',
                      'mike@example.com', 'raj@example.com'],
            'relationship': ['Line Manager', 'Peer', 'Direct Report', 'Other'],
        })

        st.download_button(
            "Download Template",
            template_df.to_csv(index=False),
            "rater_import_template.csv",
            "text/csv",
            use_container_width=True,
            help="Download a sample CSV showing the required format"
        )
        st.caption(
            f"Columns: name, email, relationship. Relationship accepts "
            f"{RELATIONSHIP_INPUT_HELP} — capitalisation doesn't matter."
        )

        uploaded_raters = st.file_uploader(
            "Upload Raters CSV",
            type="csv",
            key=f"rater_upload_{selected_leader_id}",
            help=f"Columns: name, email, relationship. "
                 f"Relationship accepts {RELATIONSHIP_INPUT_HELP}, in any case."
        )

        if uploaded_raters is not None:
            try:
                import_df = pd.read_csv(uploaded_raters)

                if 'relationship' not in import_df.columns:
                    st.error("Your CSV needs a 'relationship' column.")
                else:
                    parsed = []
                    problems = []
                    for position, (_, row) in enumerate(import_df.iterrows(), start=2):
                        raw_rel = row.get('relationship')
                        relationship = normalise_relationship(raw_rel)
                        name = str(row.get('name')).strip() if pd.notna(row.get('name')) else None
                        email = str(row.get('email')).strip() if pd.notna(row.get('email')) else None

                        if relationship is None:
                            shown = str(raw_rel).strip() if pd.notna(raw_rel) else '(blank)'
                            problems.append(
                                f"Row {position}: '{shown}' isn't a recognised "
                                f"relationship. Use {RELATIONSHIP_INPUT_HELP}."
                            )
                            continue

                        parsed.append({'name': name, 'email': email,
                                       'relationship': relationship})

                    for problem in problems:
                        st.error(problem)

                    if parsed and not problems:
                        preview = pd.DataFrame([
                            {'name': p['name'], 'email': p['email'],
                             'relationship': RELATIONSHIP_TYPES.get(
                                 p['relationship'], p['relationship'])}
                            for p in parsed
                        ])
                        st.success(f"Found {len(parsed)} raters to import", icon=":material/check:")
                        st.dataframe(preview.head(10), use_container_width=True)
                        if len(parsed) > 10:
                            st.caption(f"...and {len(parsed) - 10} more")

                        if st.button("Import All Raters", icon=":material/check_circle:", type="primary", use_container_width=True):
                            imported = 0
                            errors = []

                            for p in parsed:
                                try:
                                    db.add_rater(selected_leader_id, p['relationship'],
                                                 p['name'], p['email'])
                                    # Keep the leader's own roster in step, or these
                                    # nominees never appear in their portal
                                    if p['relationship'] != 'Self' and (p['name'] or p['email']):
                                        db.add_to_nomination_roster(
                                            selected_leader_id, p['name'],
                                            p['email'], p['relationship']
                                        )
                                    imported += 1
                                except Exception as e:
                                    errors.append(f"{p['name'] or p['email']}: {str(e)}")

                            if imported > 0:
                                st.success(f"Imported {imported} raters!", icon=":material/check_circle:")
                            if errors:
                                st.warning(f"{len(errors)} errors:", icon=":material/warning:")
                                for err in errors[:5]:
                                    st.caption(err)

                            st.rerun()

            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")


def render_reports_tab(db):
    """Render the report generation tab."""
    
    st.subheader("Generate Reports")
    
    # Check for cohort filter
    cohort_filter = st.session_state.get('active_cohort_filter')
    
    if cohort_filter:
        st.info(f"Filtered by cohort: **{cohort_filter}** (change in Settings :material/arrow_forward: Cohorts)", icon=":material/folder:")
        leaders = db.get_leaders_by_cohort(cohort_filter)
    else:
        leaders = db.get_all_leaders()
    
    if not leaders:
        st.info("Add leaders first.")
        return
    
    # Check which leaders are ready for reports
    ready_for_full_360 = []
    ready_for_self_only = []
    not_ready_leaders = []
    
    for leader in leaders:
        raters = db.get_raters_for_leader(leader['id'])
        has_self = any(r['relationship'] == 'Self' and r['completed'] for r in raters)
        
        if leader['completed_raters'] >= MIN_RESPONSES_FOR_REPORT:
            ready_for_full_360.append((leader, has_self))
        elif has_self:
            ready_for_self_only.append(leader)
        else:
            not_ready_leaders.append(leader)
    
    # Leaders ready for Full 360
    if ready_for_full_360:
        st.success(f"{len(ready_for_full_360)} leader(s) ready for Full 360 report")
        
        for leader, has_self in ready_for_full_360:
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(f"**{leader['name']}** ({leader['completed_raters']} responses)")
            
            with col2:
                report_type = st.selectbox(
                    "Report Type",
                    options=['Full 360', 'Self-Assessment', 'Progress Report'] if has_self else ['Full 360'],
                    key=f"report_type_{leader['id']}",
                    label_visibility="collapsed"
                )
            
            with col3:
                if st.button("Generate", key=f"gen_{leader['id']}"):
                    with st.spinner(f"Generating {report_type} for {leader['name']}..."):
                        try:
                            from report_generator import generate_report
                            
                            data, comments = db.get_leader_feedback_data(leader['id'])
                            output_path, theme_warning = generate_report(
                                leader['name'],
                                report_type,
                                data,
                                comments,
                                leader.get('dealership'),
                                leader.get('cohort')
                            )

                            st.success(f"Report generated!")
                            if theme_warning:
                                st.warning(f"Key Themes section could not be generated: {theme_warning}")

                            with open(output_path, 'rb') as f:
                                st.download_button(
                                    "Download Report",
                                    f,
                                    file_name=f"{leader['name'].replace(' ', '_')}_{report_type.replace(' ', '_')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_{leader['id']}"
                                )
                        except Exception as e:
                            st.error(f"Error generating report: {str(e)}")
    
    # Leaders ready for Self-Assessment only
    if ready_for_self_only:
        st.info(f"{len(ready_for_self_only)} leader(s) ready for Self-Assessment report only")
        
        for leader in ready_for_self_only:
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(f"**{leader['name']}** (Self-assessment complete)")
            
            with col2:
                st.write("Self-Assessment")
            
            with col3:
                if st.button("Generate", key=f"gen_self_{leader['id']}"):
                    with st.spinner(f"Generating Self-Assessment for {leader['name']}..."):
                        try:
                            from report_generator import generate_report
                            
                            data, comments = db.get_leader_feedback_data(leader['id'])
                            output_path, _ = generate_report(
                                leader['name'],
                                'Self-Assessment',
                                data,
                                comments,
                                leader.get('dealership'),
                                leader.get('cohort')
                            )

                            st.success(f"Report generated!")

                            with open(output_path, 'rb') as f:
                                st.download_button(
                                    "Download Report",
                                    f,
                                    file_name=f"{leader['name'].replace(' ', '_')}_Self-Assessment.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_self_{leader['id']}"
                                )
                        except Exception as e:
                            st.error(f"Error generating report: {str(e)}")
    
    # Leaders not ready
    if not_ready_leaders:
        st.markdown("---")
        st.warning(f"{len(not_ready_leaders)} leader(s) not ready for any reports")
        
        for leader in not_ready_leaders:
            st.write(f"• {leader['name']}: No self-assessment completed yet")
    
    # Batch generation
    st.markdown("---")
    st.subheader("Batch Report Generation")
    
    if ready_for_full_360:
        if st.button("Generate All Full 360 Reports", type="primary"):
            progress = st.progress(0)
            status = st.empty()
            
            for i, (leader, has_self) in enumerate(ready_for_full_360):
                status.text(f"Generating report for {leader['name']}...")
                
                try:
                    from report_generator import generate_report
                    
                    data, comments = db.get_leader_feedback_data(leader['id'])
                    _, theme_warning = generate_report(
                        leader['name'],
                        'Full 360',
                        data,
                        comments,
                        leader.get('dealership'),
                        leader.get('cohort')
                    )
                    if theme_warning:
                        st.warning(f"{leader['name']}: Key Themes section could not be generated ({theme_warning})")
                except Exception as e:
                    st.error(f"Error for {leader['name']}: {str(e)}")
                
                progress.progress((i + 1) / len(ready_for_full_360))
            
            status.text("All reports generated!")
            st.success(f"Generated {len(ready_for_full_360)} reports. Check the 'reports' folder.")
    else:
        st.info("No leaders are ready for Full 360 report generation yet.")
