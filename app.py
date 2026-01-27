#!/usr/bin/env python3
"""
THE 360 DEVELOPMENT CATALYST - Complete Web Application
========================================================

A Streamlit application that replaces Microsoft Forms for 360 feedback collection.

Features:
- Admin dashboard for managing leaders and tracking responses
- Clean feedback forms for raters
- Automated report generation
- Real-time response tracking

Run with: streamlit run app.py
"""

import streamlit as st
import sqlite3
import hashlib
import secrets
from datetime import datetime
import pandas as pd
import json
from pathlib import Path

# Import our modules
from database import Database
from feedback_form import render_feedback_form
from admin_dashboard import render_admin_dashboard
from report_generator import generate_all_reports

# Page config
st.set_page_config(
    page_title="The 360 Development Catalyst",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Bentley-appropriate styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    :root {
        --bentley-green: #024731;
        --bentley-gold: #B8860B;
        --bentley-cream: #F5F5DC;
        --bentley-charcoal: #2C2C2C;
    }
    
    .stApp {
        background: linear-gradient(180deg, #FAFAFA 0%, #F0F0F0 100%);
    }
    
    h1, h2, h3 {
        font-family: 'Cormorant Garamond', serif !important;
        color: var(--bentley-green) !important;
    }
    
    .main-title {
        font-family: 'Cormorant Garamond', serif;
        font-size: 2.8rem;
        font-weight: 600;
        color: #024731;
        text-align: center;
        margin-bottom: 0.5rem;
        letter-spacing: 0.05em;
    }
    
    .subtitle {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    .leader-card {
        background: white;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 4px solid #024731;
        margin-bottom: 1rem;
    }
    
    .stat-box {
        background: white;
        border-radius: 8px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    .stat-number {
        font-family: 'Cormorant Garamond', serif;
        font-size: 2.5rem;
        font-weight: 600;
        color: #024731;
    }
    
    .stat-label {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 0.9rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .progress-complete {
        color: #024731;
        font-weight: 600;
    }
    
    .progress-partial {
        color: #B8860B;
        font-weight: 600;
    }
    
    .progress-none {
        color: #999;
    }
    
    /* Form styling */
    .feedback-header {
        background: linear-gradient(135deg, #024731 0%, #035D40 100%);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .feedback-header h1 {
        color: white !important;
        margin-bottom: 0.5rem;
    }
    
    .dimension-header {
        background: #024731;
        color: white;
        padding: 0.8rem 1.2rem;
        border-radius: 6px;
        margin: 1.5rem 0 1rem 0;
        font-family: 'Cormorant Garamond', serif;
        font-size: 1.3rem;
    }
    
    .item-container {
        background: white;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        border: 1px solid #E0E0E0;
    }
    
    .item-text {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 1rem;
        color: #333;
        margin-bottom: 0.8rem;
        line-height: 1.5;
    }
    
    /* Radio button styling */
    .stRadio > div {
        display: flex;
        gap: 0.5rem;
    }
    
    .stRadio label {
        background: #F5F5F5;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        border: 1px solid #DDD;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .stRadio label:hover {
        background: #E8E8E8;
        border-color: #024731;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #024731 0%, #035D40 100%);
        color: white;
        border: none;
        padding: 0.6rem 2rem;
        font-family: 'Source Sans Pro', sans-serif;
        font-weight: 600;
        letter-spacing: 0.05em;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(2, 71, 49, 0.3);
    }
    
    /* Thank you page */
    .thank-you-container {
        text-align: center;
        padding: 4rem 2rem;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        max-width: 600px;
        margin: 2rem auto;
    }
    
    .thank-you-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Initialize database
db = Database()

def get_route():
    """Determine which page to show based on URL parameters."""
    params = st.query_params
    
    # Check for feedback form token
    if 'token' in params:
        return 'feedback', params['token']
    
    # Check for admin access
    if 'admin' in params:
        return 'admin', None
    
    # Default to landing page
    return 'landing', None

def render_landing_page():
    """Render the main landing/info page."""
    st.markdown('<p class="main-title">THE 360 DEVELOPMENT CATALYST</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Bentley Compass Leadership Programme</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); text-align: center;">
            <h3 style="margin-bottom: 1rem;">Welcome</h3>
            <p style="color: #666; line-height: 1.8;">
                This platform supports the 360-degree feedback process for the Bentley Compass Leadership Programme.
            </p>
            <p style="color: #666; line-height: 1.8; margin-top: 1rem;">
                If you've received a feedback link, please use that link to access the feedback form.
            </p>
            <p style="color: #999; font-size: 0.9rem; margin-top: 2rem;">
                For administrator access, please contact your programme coordinator.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick admin access for development
        with st.expander("🔐 Administrator Access"):
            admin_code = st.text_input("Enter admin code:", type="password")
            if st.button("Access Dashboard"):
                if admin_code == "compass360":  # Simple auth for now
                    st.query_params["admin"] = "true"
                    st.rerun()
                else:
                    st.error("Invalid code")

def main():
    """Main application entry point."""
    route, param = get_route()
    
    if route == 'feedback':
        # Validate token and show feedback form
        rater_info = db.get_rater_by_token(param)
        if rater_info:
            if rater_info['completed']:
                render_thank_you_page(already_completed=True)
            else:
                render_feedback_form(db, rater_info)
        else:
            st.error("Invalid or expired feedback link. Please contact your programme coordinator.")
    
    elif route == 'admin':
        render_admin_dashboard(db)
    
    else:
        render_landing_page()

def render_thank_you_page(already_completed=False):
    """Render the thank you page after submission."""
    st.markdown("""
    <div class="thank-you-container">
        <div class="thank-you-icon">✓</div>
        <h2>Thank You</h2>
        <p style="color: #666; font-size: 1.1rem; line-height: 1.8; margin-top: 1rem;">
            {message}
        </p>
        <p style="color: #999; margin-top: 2rem;">
            You may now close this window.
        </p>
    </div>
    """.format(
        message="Your feedback has already been recorded." if already_completed 
        else "Your feedback has been successfully submitted and will help support this leader's development."
    ), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
