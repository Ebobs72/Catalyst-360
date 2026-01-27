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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "👥 Leaders", "📧 Links & Tracking", "📄 Reports"])
    
    with tab1:
        render_overview_tab(db)
    
    with tab2:
        render_leaders_tab(db)
    
    with tab3:
        render_links_tab(db)
    
    with tab4:
        render_reports_tab(db)


def render_overview_tab(db):
    """Render the overview/stats tab."""
    
    stats = db.get_dashboard_stats()
    
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{stats['total_leaders']}</div>
            <div class="stat-label">Leaders</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{stats['total_raters']}</div>
            <div class="stat-label">Total Raters</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        completion_rate = round(stats['completed_responses'] / stats['total_raters'] * 100) if stats['total_raters'] > 0 else 0
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{completion_rate}%</div>
            <div class="stat-label">Response Rate</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{stats['ready_for_report']}</div>
            <div class="stat-label">Ready for Report</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Leaders summary
    st.subheader("Leader Status Overview")
    
    leaders = db.get_all_leaders()
    
    if not leaders:
        st.info("No leaders added yet. Go to the 'Leaders' tab to add leaders.")
        return
    
    for leader in leaders:
        completed = leader['completed_raters']
        total = leader['total_raters']
        self_done = leader['self_completed'] > 0
        
        if total == 0:
            status_class = "progress-none"
            status_text = "No raters assigned"
        elif completed >= MIN_RESPONSES_FOR_REPORT:
            status_class = "progress-complete"
            status_text = f"✓ Ready ({completed}/{total} responses)"
        elif completed > 0:
            status_class = "progress-partial"
            status_text = f"In progress ({completed}/{total} responses)"
        else:
            status_class = "progress-none"
            status_text = f"Awaiting responses (0/{total})"
        
        st.markdown(f"""
        <div class="leader-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong style="font-size: 1.1rem;">{leader['name']}</strong>
                    {f'<span style="color: #999; margin-left: 0.5rem;">({leader["dealership"]})</span>' if leader.get('dealership') else ''}
                </div>
                <div class="{status_class}">{status_text}</div>
            </div>
            <div style="margin-top: 0.5rem; font-size: 0.9rem; color: #666;">
                Self: {'✓' if self_done else '○'} | 
                Cohort: {leader.get('cohort', 'Not set')} | 
                Year: {leader.get('assessment_year', 1)}
            </div>
        </div>
        """, unsafe_allow_html=True)


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
        value="http://localhost:8501",
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
                link = f"{base_url}?token={rater['token']}"
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
    
    leaders = db.get_all_leaders()
    
    if not leaders:
        st.info("Add leaders first.")
        return
    
    # Check which leaders are ready for reports
    ready_leaders = []
    not_ready_leaders = []
    
    for leader in leaders:
        if leader['completed_raters'] >= MIN_RESPONSES_FOR_REPORT:
            ready_leaders.append(leader)
        else:
            not_ready_leaders.append(leader)
    
    if ready_leaders:
        st.success(f"{len(ready_leaders)} leader(s) ready for report generation")
        
        for leader in ready_leaders:
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(f"**{leader['name']}** ({leader['completed_raters']} responses)")
            
            with col2:
                # Check if self-assessment exists
                raters = db.get_raters_for_leader(leader['id'])
                has_self = any(r['relationship'] == 'Self' and r['completed'] for r in raters)
                has_others = any(r['relationship'] != 'Self' and r['completed'] for r in raters)
                
                report_type = st.selectbox(
                    "Report Type",
                    options=['Self-Assessment', 'Full 360', 'Progress Report'] if has_self else ['Full 360'],
                    key=f"report_type_{leader['id']}",
                    label_visibility="collapsed"
                )
            
            with col3:
                if st.button("Generate", key=f"gen_{leader['id']}"):
                    with st.spinner(f"Generating {report_type} for {leader['name']}..."):
                        try:
                            # Import and run report generator
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
                            
                            # Offer download
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
    
    if not_ready_leaders:
        st.markdown("---")
        st.warning(f"{len(not_ready_leaders)} leader(s) need more responses")
        
        for leader in not_ready_leaders:
            st.write(f"• {leader['name']}: {leader['completed_raters']}/{MIN_RESPONSES_FOR_REPORT} minimum responses")
    
    # Batch generation
    st.markdown("---")
    st.subheader("Batch Report Generation")
    
    if ready_leaders:
        if st.button("Generate All Ready Reports", type="primary"):
            progress = st.progress(0)
            status = st.empty()
            
            for i, leader in enumerate(ready_leaders):
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
                
                progress.progress((i + 1) / len(ready_leaders))
            
            status.text("All reports generated!")
            st.success(f"Generated {len(ready_leaders)} reports. Check the 'reports' folder.")
    else:
        st.info("No leaders are ready for report generation yet.")
