#!/usr/bin/env python3
"""
Admin dashboard for the 360 Development Catalyst.

Provides management interface for leaders, raters, and report generation.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from framework import RELATIONSHIP_TYPES, GROUP_DISPLAY, MIN_RESPONSES_FOR_REPORT

def render_admin_dashboard(db):
    """Render the admin dashboard."""
    
    # Header
    st.markdown('<p class="main-title">THE 360 DEVELOPMENT CATALYST</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Administrator Dashboard</p>', unsafe_allow_html=True)
    
    # Navigation tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "👥 Leaders", "📧 Links & Tracking", "📄 Reports", "⚙️ Settings"])
    
    with tab1:
        render_overview_tab(db)
    
    with tab2:
        render_leaders_tab(db)
    
    with tab3:
        render_links_tab(db)
    
    with tab4:
        render_reports_tab(db)
    
    with tab5:
        render_settings_tab(db)


def render_settings_tab(db):
    """Render the settings/admin tab."""
    
    settings_subtab1, settings_subtab2, settings_subtab3 = st.tabs(["📁 Cohorts", "🗄️ Database", "ℹ️ App Info"])
    
    with settings_subtab1:
        render_cohort_management(db)
    
    with settings_subtab2:
        render_database_management(db)
    
    with settings_subtab3:
        render_app_info(db)


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
        if st.button("➕ Add Cohort", disabled=not new_cohort):
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
                    if st.button("🗑️", key=f"del_cohort_{cohort['id']}", help="Delete cohort"):
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
    
    st.warning("⚠️ These actions cannot be undone. Use with caution.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Clear All Data**")
        st.write("Delete all leaders, raters, and feedback. Reloads demo data on next refresh.")
        
        if st.button("🗑️ Clear Database", type="secondary"):
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
        
        if st.button("📥 Export All Data"):
            # Get all leaders and their data
            leaders = db.get_all_leaders()
            if leaders:
                export_data = []
                for leader in leaders:
                    data, comments = db.get_leader_feedback_data(leader['id'])
                    for item_num, scores in data['by_item'].items():
                        row = {
                            'Leader': leader['name'],
                            'Dealership': leader.get('dealership', ''),
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
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Database location:** compass_360.db")
        st.write(f"**Total leaders:** {stats['total_leaders']}")
        st.write(f"**Total raters:** {stats['total_raters']}")
    
    with col2:
        st.write(f"**Completed responses:** {stats['completed_responses']}")
        st.write(f"**Ready for Full 360:** {stats['ready_for_report']}")
        
        # Count cohorts
        cohorts = db.get_all_cohorts()
        st.write(f"**Cohorts:** {len(cohorts)}")


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
                if st.button("View →", key=f"view_cohort_{cohort_name}"):
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
            if st.button("← All Cohorts"):
                st.session_state['active_cohort_filter'] = None
                st.rerun()
        with col2:
            st.subheader(f"📁 {cohort_filter}")
        
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
        
        # Show leaders in this cohort
        for leader in leaders:
            completed = leader['completed_raters']
            total = leader['total_raters']
            self_done = leader['self_completed'] > 0
            
            if total == 0:
                status_text = "No raters assigned"
                status_type = "info"
            elif completed >= MIN_RESPONSES_FOR_REPORT:
                status_text = f"✓ Ready for Full 360 ({completed}/{total})"
                status_type = "success"
            elif self_done and completed < MIN_RESPONSES_FOR_REPORT:
                status_text = f"✓ Self done, awaiting others ({completed}/{total})"
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
                    self_icon = '✓' if self_done else '○'
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
            email = st.text_input("Email")
        
        with col2:
            dealership = st.text_input("Dealership")
            cohort = st.text_input("Cohort (e.g., 'January 2026')")
        
        if st.form_submit_button("Add Leader"):
            if name:
                leader_id = db.add_leader(name, email, dealership, cohort)
                st.success(f"Added {name} successfully!")
                st.rerun()
            else:
                st.error("Please enter a leader name")
    
    st.markdown("---")
    
    st.subheader("Existing Leaders")
    
    leaders = db.get_all_leaders()
    
    if not leaders:
        st.info("No leaders added yet.")
        return
    
    for leader in leaders:
        with st.expander(f"**{leader['name']}** - {leader.get('dealership', 'No dealership')}"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**Email:** {leader.get('email', 'Not set')}")
                st.write(f"**Cohort:** {leader.get('cohort', 'Not set')}")
            
            with col2:
                st.write(f"**Dealership:** {leader.get('dealership', 'Not set')}")
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
    Upload a CSV file with columns: `name`, `email` (optional), `dealership` (optional), `cohort` (optional)
    """)
    
    uploaded_file = st.file_uploader("Choose CSV file", type="csv")
    
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.write("Preview:")
        st.dataframe(df.head())
        
        if st.button("Import All"):
            count = 0
            for _, row in df.iterrows():
                if pd.notna(row.get('name')):
                    db.add_leader(
                        name=row['name'],
                        email=row.get('email') if pd.notna(row.get('email')) else None,
                        dealership=row.get('dealership') if pd.notna(row.get('dealership')) else None,
                        cohort=row.get('cohort') if pd.notna(row.get('cohort')) else None
                    )
                    count += 1
            st.success(f"Imported {count} leaders!")
            st.rerun()


def render_links_tab(db):
    """Render the links generation and tracking tab."""
    
    leaders = db.get_all_leaders()
    
    if not leaders:
        st.info("Add leaders first in the 'Leaders' tab.")
        return
    
    # Leader selector
    leader_options = {l['id']: f"{l['name']} ({l.get('dealership', 'No dealership')})" for l in leaders}
    selected_leader_id = st.selectbox(
        "Select Leader",
        options=list(leader_options.keys()),
        format_func=lambda x: leader_options[x]
    )
    
    selected_leader = next(l for l in leaders if l['id'] == selected_leader_id)
    
    st.markdown("---")
    
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
            rater_email = st.text_input("Rater Email (optional)")
            
            if st.form_submit_button("Add Rater"):
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
                    db.add_rater(selected_leader_id, 'Self', selected_leader['name'])
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
    
    if not raters:
        st.info("No raters added yet for this leader.")
        return
    
    # Get base URL (would need to be configured for production)
    base_url = st.text_input(
        "Base URL for links",
        value="https://catalyst-360-arbncruhflmazjemep8uzh.streamlit.app",
        help="Change this to your deployed app URL"
    )
    
    # Group raters by relationship
    raters_by_group = {}
    for rater in raters:
        rel = rater['relationship']
        if rel not in raters_by_group:
            raters_by_group[rel] = []
        raters_by_group[rel].append(rater)
    
    # Display links table
    link_data = []
    for rel in ['Self', 'Boss', 'Peers', 'DRs', 'Others']:
        if rel in raters_by_group:
            for i, rater in enumerate(raters_by_group[rel], 1):
                link = f"{base_url}?t={rater['token']}"
                status = "✓ Complete" if rater['completed'] else "○ Pending"
                
                link_data.append({
                    'Group': GROUP_DISPLAY.get(rel, rel),
                    'Name': rater.get('name') or f"{GROUP_DISPLAY.get(rel, rel)} {i}",
                    'Status': status,
                    'Link': link,
                    'rater_id': rater['id']
                })
    
    # Show as table with copy functionality
    for item in link_data:
        col1, col2, col3, col4 = st.columns([1.5, 2, 1, 0.5])
        
        with col1:
            st.write(item['Group'])
        with col2:
            st.write(item['Name'])
        with col3:
            if "Complete" in item['Status']:
                st.markdown(f"<span style='color: green;'>{item['Status']}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color: orange;'>{item['Status']}</span>", unsafe_allow_html=True)
        with col4:
            if st.button("🗑️", key=f"del_rater_{item['rater_id']}", help="Delete rater"):
                db.delete_rater(item['rater_id'])
                st.rerun()
        
        st.code(item['Link'], language=None)
        st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #EEE;'>", unsafe_allow_html=True)
    
    # Export links
    st.markdown("---")
    if st.button("📋 Export All Links as CSV"):
        df = pd.DataFrame([{
            'Group': item['Group'],
            'Name': item['Name'],
            'Status': item['Status'],
            'Link': item['Link']
        } for item in link_data])
        
        csv = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            f"feedback_links_{selected_leader['name'].replace(' ', '_')}.csv",
            "text/csv"
        )


def render_reports_tab(db):
    """Render the report generation tab."""
    
    st.subheader("Generate Reports")
    
    # Check for cohort filter
    cohort_filter = st.session_state.get('active_cohort_filter')
    
    if cohort_filter:
        st.info(f"📁 Filtered by cohort: **{cohort_filter}** (change in Settings → Cohorts)")
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
                            output_path = generate_report(
                                leader['name'],
                                report_type,
                                data,
                                comments,
                                leader.get('dealership'),
                                leader.get('cohort')
                            )
                            
                            st.success(f"Report generated!")
                            
                            with open(output_path, 'rb') as f:
                                st.download_button(
                                    "📥 Download Report",
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
                            output_path = generate_report(
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
                                    "📥 Download Report",
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
                    generate_report(
                        leader['name'],
                        'Full 360',
                        data,
                        comments,
                        leader.get('dealership'),
                        leader.get('cohort')
                    )
                except Exception as e:
                    st.error(f"Error for {leader['name']}: {str(e)}")
                
                progress.progress((i + 1) / len(ready_for_full_360))
            
            status.text("All reports generated!")
            st.success(f"Generated {len(ready_for_full_360)} reports. Check the 'reports' folder.")
    else:
        st.info("No leaders are ready for Full 360 report generation yet.")
