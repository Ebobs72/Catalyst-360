#!/usr/bin/env python3
"""
Leader Portal for the 360 Development Catalyst.

Allows leaders to:
- View their assessment status
- Nominate their raters (Boss, Peers, DRs, Others)
- Track rater response progress
- Send reminders to raters
"""

import streamlit as st
import pandas as pd
from datetime import datetime

# Import email functionality if available
try:
    from email_sender import (
        is_email_configured,
        send_rater_invitation,
        send_rater_reminder
    )
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Rater requirements
RATER_REQUIREMENTS = {
    'Boss': {'min': 1, 'max': 2, 'suggested': 1, 'required_nomination': True},
    'Peers': {'min': 3, 'max': 10, 'suggested': 5, 'required_nomination': True},
    'DRs': {'min': 0, 'max': 10, 'suggested': 5, 'required_nomination': False},  # 0 if no direct reports
    'Others': {'min': 0, 'max': 10, 'suggested': 0, 'required_nomination': False}
}


def render_leader_portal(db, leader_info):
    """Render the leader portal page."""
    
    leader_id = leader_info['id']
    leader_name = leader_info['name']
    
    # Header
    st.markdown('<p class="main-title">THE 360 DEVELOPMENT CATALYST</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Your Leadership Feedback Portal</p>', unsafe_allow_html=True)
    
    # Welcome section
    st.markdown(f"""
    <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1.5rem;">
        <h3 style="margin: 0 0 0.5rem 0; color: #024731;">Welcome, {leader_name}</h3>
        <p style="color: #666; margin: 0;">{leader_info.get('dealership', '')} · {leader_info.get('cohort', '')}</p>
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
    
    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["📝 Nominate Raters", "📊 Response Progress", "ℹ️ Guidelines"])
    
    with tab1:
        render_nomination_section(db, leader_info, other_raters)
    
    with tab2:
        render_progress_section(db, leader_info, other_raters)
    
    with tab3:
        render_guidelines_section()


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
        if total_nominated > 0:
            st.metric("Responses Received", f"{completed} of {total_nominated}")
        else:
            st.metric("Responses Received", "0")


def render_nomination_section(db, leader_info, existing_raters):
    """Render the rater nomination section."""
    
    leader_id = leader_info['id']
    
    # Get base URL for sending invitations
    base_url = st.session_state.get('portal_base_url', 
        "https://catalyst-360-arbncruhflmazjemep8uzh.streamlit.app")
    
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
    
    for i, cat in enumerate(categories):
        with status_cols[i]:
            req = RATER_REQUIREMENTS[cat]
            count = rater_counts[cat]
            
            # Determine status
            if cat == 'DRs' and count == 0:
                # DRs are optional if leader has no direct reports
                status_icon = "○"
                status_color = "#666"
                status_text = "Optional"
            elif count >= req['min']:
                status_icon = "✓"
                status_color = "#024731"
                status_text = f"{count} nominated"
            else:
                status_icon = "⚠️"
                status_color = "#B8860B"
                status_text = f"{count}/{req['min']} minimum"
                if req['required_nomination']:
                    all_requirements_met = False
            
            st.markdown(f"""
            <div style="background: white; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #E0E0E0;">
                <div style="font-size: 1.5rem;">{status_icon}</div>
                <div style="font-weight: 600; color: #024731;">{cat}</div>
                <div style="color: {status_color}; font-size: 0.9rem;">{status_text}</div>
            </div>
            """, unsafe_allow_html=True)
    
    if not all_requirements_met:
        st.warning("⚠️ Please ensure you meet the minimum requirements for each category before the deadline.")
    
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
                    # Add the rater
                    rater_id, token = db.add_rater(leader_id, relationship, rater_name, rater_email)
                    
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
        
        # Template download
        template_data = {
            'name': ['Jane Smith', 'Tom Brown', 'Sarah Jones'],
            'email': ['jane@company.com', 'tom@company.com', 'sarah@company.com'],
            'relationship': ['Boss', 'Peers', 'DRs']
        }
        template_df = pd.DataFrame(template_data)
        template_csv = template_df.to_csv(index=False)
        
        st.download_button(
            "📄 Download Template",
            template_csv,
            "rater_template.csv",
            "text/csv",
            use_container_width=True
        )
        
        uploaded_file = st.file_uploader(
            "Upload CSV",
            type="csv",
            help="CSV with columns: name, email, relationship"
        )
        
        if uploaded_file:
            try:
                import_df = pd.read_csv(uploaded_file)
                
                # Validate
                if 'name' not in import_df.columns or 'email' not in import_df.columns or 'relationship' not in import_df.columns:
                    st.error("CSV must have columns: name, email, relationship")
                else:
                    valid_rels = ['Boss', 'Peers', 'DRs', 'Others']
                    import_df['relationship'] = import_df['relationship'].str.strip()
                    invalid = import_df[~import_df['relationship'].isin(valid_rels)]
                    
                    if len(invalid) > 0:
                        st.error(f"Invalid relationship values. Must be: {', '.join(valid_rels)}")
                    else:
                        st.success(f"Found {len(import_df)} raters")
                        st.dataframe(import_df, use_container_width=True, hide_index=True)
                        
                        if st.button("Import All", type="primary", use_container_width=True):
                            imported = 0
                            for _, row in import_df.iterrows():
                                name = row['name'].strip() if pd.notna(row['name']) else None
                                email = row['email'].strip() if pd.notna(row['email']) else None
                                rel = row['relationship'].strip()
                                
                                if name and email:
                                    rater_id, token = db.add_rater(leader_id, rel, name, email)
                                    
                                    # Send invitation
                                    if EMAIL_AVAILABLE and is_email_configured():
                                        rater = db.get_rater(rater_id)
                                        send_rater_invitation(rater, leader_info['name'], base_url, db)
                                    
                                    imported += 1
                            
                            st.success(f"✓ Imported {imported} raters and sent invitations")
                            st.rerun()
                            
            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")


def render_progress_section(db, leader_info, raters):
    """Render the response progress section."""
    
    leader_id = leader_info['id']
    base_url = st.session_state.get('portal_base_url',
        "https://catalyst-360-arbncruhflmazjemep8uzh.streamlit.app")
    
    email_configured = EMAIL_AVAILABLE and is_email_configured()
    
    if not raters:
        st.info("You haven't nominated any raters yet. Go to the 'Nominate Raters' tab to add your feedback providers.")
        return
    
    st.subheader("Your Raters")
    
    # Group by relationship
    for rel in ['Boss', 'Peers', 'DRs', 'Others']:
        rel_raters = [r for r in raters if r['relationship'] == rel]
        
        if not rel_raters:
            continue
        
        completed_count = sum(1 for r in rel_raters if r.get('completed'))
        
        st.markdown(f"**{rel}** ({completed_count}/{len(rel_raters)} complete)")
        
        for rater in rel_raters:
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            
            with col1:
                status_icon = "✅" if rater.get('completed') else "⏳"
                st.write(f"{status_icon} {rater.get('name', 'Unknown')}")
            
            with col2:
                st.caption(rater.get('email', ''))
            
            with col3:
                if rater.get('completed'):
                    st.markdown("<span style='color: green;'>Complete</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color: orange;'>Pending</span>", unsafe_allow_html=True)
            
            with col4:
                if not rater.get('completed') and email_configured:
                    if st.button("🔔", key=f"remind_{rater['id']}", help="Send reminder"):
                        success, msg = send_rater_reminder(rater, leader_info['name'], base_url, db)
                        if success:
                            st.toast(f"Reminder sent to {rater['name']}")
                        else:
                            st.toast(f"Failed to send: {msg}")
                
                # Delete button (only if not completed)
                if not rater.get('completed'):
                    if st.button("🗑️", key=f"del_{rater['id']}", help="Remove rater"):
                        db.delete_rater(rater['id'])
                        st.rerun()
        
        st.markdown("---")
    
    # Bulk reminder option
    incomplete_raters = [r for r in raters if not r.get('completed')]
    if incomplete_raters and email_configured:
        st.markdown("---")
        if st.button(f"🔔 Send Reminder to All Pending ({len(incomplete_raters)})", use_container_width=True):
            sent = 0
            for rater in incomplete_raters:
                success, _ = send_rater_reminder(rater, leader_info['name'], base_url, db)
                if success:
                    sent += 1
            st.success(f"Sent {sent} reminders")


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
    
    **🔄 Others** — *Optional*
    
    Additional stakeholders who can provide valuable perspective. This might include internal 
    customers, matrix reports, key suppliers, or other regular contacts.
    
    *Examples: Brand representatives, key suppliers, internal stakeholders from other functions*
    
    ---
    
    ### Why Minimum Numbers?
    
    We require a minimum of **3 respondents** in Peers and Direct Reports categories to ensure 
    **anonymity**. With fewer than 3, individual responses could be identifiable, which would 
    undermine the candour of the feedback.
    
    We suggest **5 raters per category** as best practice — this provides richer data and 
    accounts for any non-responses.
    
    ---
    
    ### Tips for Better Feedback
    
    - **Choose people who see you regularly** — occasional contacts won't have enough data
    - **Include a range of perspectives** — people you work well with AND those you find challenging
    - **Be realistic about response rates** — not everyone will respond, so nominate more than the minimum
    - **Respect people's time** — let nominees know you've added them and why their input matters
    """)
