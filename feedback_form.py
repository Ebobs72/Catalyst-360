#!/usr/bin/env python3
"""
Feedback form for raters in the 360 Development Catalyst.

Provides a clean, branded experience for submitting 360 feedback.
"""

import streamlit as st
from framework import (
    DIMENSIONS, ITEMS, DIMENSION_DESCRIPTIONS, 
    RATING_SCALE, RELATIONSHIP_TYPES
)

def render_feedback_form(db, rater_info):
    """Render the feedback form for a rater."""
    
    leader_name = rater_info['leader_name']
    relationship = rater_info['relationship']
    relationship_display = RELATIONSHIP_TYPES.get(relationship, relationship)
    is_self = relationship == 'Self'
    
    # Header
    st.markdown(f"""
    <div class="feedback-header">
        <h1 style="font-size: 1.8rem; margin-bottom: 0.3rem;">THE 360 DEVELOPMENT CATALYST</h1>
        <p style="font-size: 1.1rem; opacity: 0.9; margin: 0;">
            {'Self-Assessment' if is_self else f'Feedback for <strong>{leader_name}</strong>'}
        </p>
        <p style="font-size: 0.9rem; opacity: 0.7; margin-top: 0.5rem;">
            {f'Providing feedback as: {relationship_display}' if not is_self else 'Bentley Compass Leadership Programme'}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Instructions
    if is_self:
        st.markdown("""
        <div style="background: #F8F9FA; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #024731;">
            <p style="margin: 0; color: #333; line-height: 1.6;">
                <strong>About this self-assessment</strong><br>
                Please rate yourself honestly on each statement below. Your self-assessment will be compared 
                with feedback from others to identify areas of alignment and potential blind spots. 
                There are no right or wrong answers – the value comes from honest reflection.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background: #F8F9FA; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #024731;">
            <p style="margin: 0; color: #333; line-height: 1.6;">
                <strong>About this feedback</strong><br>
                Your honest feedback will help <strong>{leader_name}</strong> understand how their leadership 
                is perceived and identify areas for development. All feedback is confidential and will be 
                aggregated with others in your category. Please be constructive and specific where possible.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Initialize session state for form data
    if 'ratings' not in st.session_state:
        st.session_state.ratings = {}
    if 'comments' not in st.session_state:
        st.session_state.comments = {}
    
    # Rating options
    rating_options = [""] + [str(i) for i in range(1, 6)] + ["N/O"]
    rating_labels = {
        "": "Select...",
        "1": "1 - Strongly Disagree",
        "2": "2 - Disagree",
        "3": "3 - Neither",
        "4": "4 - Agree",
        "5": "5 - Strongly Agree",
        "N/O": "No Opportunity to Observe"
    }
    
    # Form
    with st.form("feedback_form"):
        # Iterate through dimensions
        for dim_name, (start_item, end_item) in DIMENSIONS.items():
            st.markdown(f'<div class="dimension-header">{dim_name}</div>', unsafe_allow_html=True)
            
            # Dimension description
            st.markdown(f"""
            <p style="color: #666; font-size: 0.95rem; margin-bottom: 1rem; font-style: italic;">
                {DIMENSION_DESCRIPTIONS[dim_name]}
            </p>
            """, unsafe_allow_html=True)
            
            # Items in this dimension
            for item_num in range(start_item, end_item + 1):
                item_text = ITEMS[item_num]
                
                # Adjust text for self-assessment (change "their" to "my", etc.)
                if is_self:
                    item_text = item_text.replace("their team", "my team")
                    item_text = item_text.replace("their people", "my people")
                    item_text = item_text.replace("their leadership", "my leadership")
                    item_text = item_text.replace("their area", "my area")
                    item_text = item_text.replace("their immediate", "my immediate")
                    item_text = item_text.replace("this person", "me")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"""
                    <div class="item-container">
                        <span style="color: #999; font-size: 0.85rem;">Q{item_num}.</span>
                        <span class="item-text">{item_text}</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    rating = st.selectbox(
                        f"Rating for Q{item_num}",
                        options=rating_options,
                        format_func=lambda x: rating_labels.get(x, x),
                        key=f"rating_{item_num}",
                        label_visibility="collapsed"
                    )
                    st.session_state.ratings[item_num] = rating
            
            # Comment for this dimension
            st.markdown(f"""
            <p style="margin-top: 1rem; margin-bottom: 0.5rem; color: #555; font-size: 0.9rem;">
                <em>Optional: Any specific comments about {leader_name if not is_self else 'yourself'} regarding {dim_name}?</em>
            </p>
            """, unsafe_allow_html=True)
            
            comment = st.text_area(
                f"Comments for {dim_name}",
                key=f"comment_{dim_name}",
                height=80,
                label_visibility="collapsed",
                placeholder="Share specific examples or observations..."
            )
            st.session_state.comments[dim_name] = comment
            
            st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
        
        # Overall Effectiveness
        st.markdown('<div class="dimension-header">Overall Effectiveness</div>', unsafe_allow_html=True)
        
        for item_num in [41, 42]:
            item_text = ITEMS[item_num]
            if is_self:
                item_text = item_text.replace("this person", "me")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"""
                <div class="item-container">
                    <span style="color: #999; font-size: 0.85rem;">Q{item_num}.</span>
                    <span class="item-text">{item_text}</span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                rating = st.selectbox(
                    f"Rating for Q{item_num}",
                    options=rating_options,
                    format_func=lambda x: rating_labels.get(x, x),
                    key=f"rating_{item_num}",
                    label_visibility="collapsed"
                )
                st.session_state.ratings[item_num] = rating
        
        st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
        
        # Overall comments
        st.markdown('<div class="dimension-header">Overall Feedback</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <p style="margin-top: 1rem; margin-bottom: 0.5rem; color: #333;">
            <strong>What are {leader_name + "'s" if not is_self else "your"} greatest strengths as a leader?</strong>
        </p>
        """, unsafe_allow_html=True)
        
        strengths_comment = st.text_area(
            "Strengths",
            key="comment_strengths",
            height=100,
            label_visibility="collapsed",
            placeholder="Describe the leadership qualities and behaviours that are most effective..."
        )
        st.session_state.comments['strengths'] = strengths_comment
        
        st.markdown(f"""
        <p style="margin-top: 1.5rem; margin-bottom: 0.5rem; color: #333;">
            <strong>What should {leader_name if not is_self else "you"} focus on developing?</strong>
        </p>
        """, unsafe_allow_html=True)
        
        development_comment = st.text_area(
            "Development",
            key="comment_development",
            height=100,
            label_visibility="collapsed",
            placeholder="Suggest areas for growth and specific behaviours to work on..."
        )
        st.session_state.comments['development'] = development_comment
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Submit button
        submitted = st.form_submit_button(
            "Submit Feedback",
            use_container_width=True
        )
        
        if submitted:
            # Validate - check that all items have been rated
            missing = []
            for item_num in range(1, 43):
                rating = st.session_state.ratings.get(item_num, "")
                if rating == "":
                    missing.append(item_num)
            
            if missing:
                st.error(f"Please provide a rating for all items. Missing: Q{', Q'.join(map(str, missing[:5]))}{'...' if len(missing) > 5 else ''}")
            else:
                # Process ratings
                processed_ratings = {}
                for item_num, rating in st.session_state.ratings.items():
                    if rating == "N/O":
                        processed_ratings[item_num] = "NO"
                    elif rating:
                        processed_ratings[item_num] = int(rating)
                
                # Process comments
                processed_comments = {k: v for k, v in st.session_state.comments.items() if v and v.strip()}
                
                # Submit to database
                try:
                    db.submit_feedback(rater_info['id'], processed_ratings, processed_comments)
                    
                    # Clear session state
                    st.session_state.ratings = {}
                    st.session_state.comments = {}
                    
                    # Show success and refresh
                    st.success("Thank you! Your feedback has been submitted successfully.")
                    st.balloons()
                    
                    # Redirect to thank you
                    st.query_params["submitted"] = "true"
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"An error occurred while submitting your feedback. Please try again. ({str(e)})")


def render_thank_you():
    """Render thank you page after submission."""
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; background: white; border-radius: 12px; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 600px; margin: 2rem auto;">
        <div style="font-size: 4rem; margin-bottom: 1rem;">✓</div>
        <h2 style="color: #024731; margin-bottom: 1rem;">Thank You</h2>
        <p style="color: #666; font-size: 1.1rem; line-height: 1.8;">
            Your feedback has been successfully submitted and will help support this leader's development.
        </p>
        <p style="color: #999; margin-top: 2rem;">
            You may now close this window.
        </p>
    </div>
    """, unsafe_allow_html=True)
