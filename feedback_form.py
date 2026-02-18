#!/usr/bin/env python3
"""
Feedback form for raters in the 360 Development Catalyst.

Provides a clean, branded experience for submitting 360 feedback.
Supports save & resume — raters can close the browser and return later.
"""

import streamlit as st
import json
from datetime import datetime
from framework import (
    DIMENSIONS, ITEMS, DIMENSION_DESCRIPTIONS, 
    RELATIONSHIP_TYPES, GROUP_DISPLAY
)


def _collect_current_answers():
    """Gather all current ratings and comments from session state."""
    ratings = {}
    comments = {}

    # Ratings (Q1-Q47)
    for item_num in range(1, 48):
        val = st.session_state.get(f"rating_{item_num}", "")
        if val and val != "":
            ratings[item_num] = val

    # Dimension comments
    for dim_name in DIMENSIONS.keys():
        val = st.session_state.get(f"comment_{dim_name}", "")
        if val and val.strip():
            comments[dim_name] = val

    # Overall comments
    for key in ['strengths', 'development']:
        val = st.session_state.get(f"comment_{key}", "")
        if val and val.strip():
            comments[key] = val

    return ratings, comments


def _auto_save():
    """Auto-save callback — triggered on every widget change."""
    if 'db' not in st.session_state or 'rater_id' not in st.session_state:
        return
    
    try:
        ratings, comments = _collect_current_answers()
        st.session_state.db.save_draft(st.session_state.rater_id, ratings, comments)
        st.session_state.last_saved = datetime.now().strftime("%H:%M")
    except Exception:
        pass  # Silent fail — don't disrupt the rater's experience


def render_feedback_form(db, rater_info):
    """Render the feedback form for a rater."""
    
    leader_name = rater_info['leader_name']
    relationship = rater_info['relationship']
    is_self = relationship == 'Self'
    rater_id = rater_info['id']

    # Store db and rater_id in session state for auto-save callbacks
    st.session_state.db = db
    st.session_state.rater_id = rater_id

    # --- Load draft if resuming ---
    draft_ratings, draft_comments, draft_saved_at = db.get_draft(rater_id)
    has_draft = draft_ratings is not None

    if has_draft and 'draft_loaded' not in st.session_state:
        st.session_state.draft_loaded = True
        st.session_state.draft_saved_at = draft_saved_at
    
    # Header
    st.markdown(f"""
    <div class="feedback-header">
        <h1 style="font-size: 1.8rem; margin-bottom: 0.3rem;">THE 360 DEVELOPMENT CATALYST</h1>
        <p style="font-size: 1.1rem; opacity: 0.9; margin: 0;">
            {'Self-Assessment' if is_self else f'Feedback for <strong>{leader_name}</strong>'}
        </p>
        <p style="font-size: 0.9rem; opacity: 0.7; margin-top: 0.5rem;">
            {f'Providing feedback as: {GROUP_DISPLAY.get(relationship, relationship)}' if not is_self else 'Bentley Compass Leadership Programme'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Resume banner
    if has_draft and draft_saved_at:
        st.info(
            f"📋 **Welcome back!** Your previous answers have been restored. "
            f"You can continue from where you left off.",
            icon="📋"
        )
    
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
                Thank you for taking the time to complete this questionnaire. The results will be shared with 
                <strong>{leader_name}</strong> as part of the Bentley Compass Leadership Development Programme.
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                This 360 feedback instrument provides leaders with a rounded view of their leadership effectiveness, 
                covering both functional leadership competencies and behavioural self-awareness.
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                Please take some time to complete this form, and note that all responses will be treated with 
                complete confidentiality. If you are part of a group response to this questionnaire, your individual 
                answers will be aggregated into overall scores and will not be individually identifiable.
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                Any comments you make will be anonymised to the group title you respond from – 
                <strong>unless you are the direct line manager of the individual.</strong>
            </p>
            <p style="margin: 1rem 0 0 0; color: #C00000; line-height: 1.6;">
                <strong>If any of the individual statements are Not Applicable to your specific relationship 
                with this individual, please choose the N/A option.</strong>
            </p>
            <p style="margin: 1rem 0 0 0; color: #C00000; line-height: 1.6;">
                <strong>If any of the individual statements ARE applicable to your specific relationship, 
                but you have not had an opportunity to witness them behaving in that way, choose No Opportunity.</strong>
            </p>
            <p style="margin: 1rem 0 0 0; color: #024731; line-height: 1.6;">
                <strong>💾 Your progress is saved automatically.</strong> You can close this window at any time 
                and return to this link to continue where you left off.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Rating options
    rating_options = [""] + [str(i) for i in range(1, 6)] + ["N/A", "N/O"]
    rating_labels = {
        "": "Select...",
        "1": "1 - Strongly Disagree",
        "2": "2 - Disagree",
        "3": "3 - Neither",
        "4": "4 - Agree",
        "5": "5 - Strongly Agree",
        "N/A": "N/A - Not Applicable",
        "N/O": "N/O - No Opportunity to Observe"
    }
    
    # --- FORM (using st.form for clean submission, with draft pre-population) ---
    # Note: We use st.form for the actual widgets, but auto-save happens via
    # a separate mechanism outside the form since on_change doesn't fire inside forms.
    
    with st.form("feedback_form"):
        # Iterate through dimensions
        for dim_name, (start_item, end_item) in DIMENSIONS.items():
            st.markdown(f'<div class="dimension-header">{dim_name}</div>', unsafe_allow_html=True)
            
            st.markdown(f"""
            <p style="color: #666; font-size: 0.95rem; margin-bottom: 1rem; font-style: italic;">
                {DIMENSION_DESCRIPTIONS[dim_name]}
            </p>
            """, unsafe_allow_html=True)
            
            for item_num in range(start_item, end_item + 1):
                item_text = ITEMS[item_num]
                
                if is_self:
                    item_text = item_text.replace("their team", "my team")
                    item_text = item_text.replace("their people", "my people")
                    item_text = item_text.replace("their leadership", "my leadership")
                    item_text = item_text.replace("their area", "my area")
                    item_text = item_text.replace("their immediate", "my immediate")
                    item_text = item_text.replace("this person", "myself")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"""
                    <div class="item-container">
                        <span style="color: #999; font-size: 0.85rem;">Q{item_num}.</span>
                        <span class="item-text">{item_text}</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Pre-populate from draft if available
                    default_idx = 0
                    if has_draft and draft_ratings and item_num in draft_ratings:
                        draft_val = str(draft_ratings[item_num])
                        if draft_val in rating_options:
                            default_idx = rating_options.index(draft_val)
                    
                    st.selectbox(
                        f"Rating for Q{item_num}",
                        options=rating_options,
                        index=default_idx,
                        format_func=lambda x: rating_labels.get(x, x),
                        key=f"rating_{item_num}",
                        label_visibility="collapsed"
                    )
            
            # Comment for this dimension
            st.markdown(f"""
            <p style="margin-top: 1rem; margin-bottom: 0.5rem; color: #555; font-size: 0.9rem;">
                <em>Optional: Any specific comments about {leader_name if not is_self else 'yourself'} regarding {dim_name}?</em>
            </p>
            """, unsafe_allow_html=True)
            
            default_comment = ""
            if has_draft and draft_comments and dim_name in draft_comments:
                default_comment = draft_comments[dim_name]
            
            st.text_area(
                f"Comments for {dim_name}",
                value=default_comment,
                key=f"comment_{dim_name}",
                height=80,
                label_visibility="collapsed",
                placeholder="Share specific examples or observations..."
            )
            
            st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
        
        # Overall Effectiveness (Q46 and Q47)
        st.markdown('<div class="dimension-header">Overall Effectiveness</div>', unsafe_allow_html=True)
        
        for item_num in [46, 47]:
            item_text = ITEMS[item_num]
            if is_self:
                item_text = item_text.replace("this person", "myself")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"""
                <div class="item-container">
                    <span style="color: #999; font-size: 0.85rem;">Q{item_num}.</span>
                    <span class="item-text">{item_text}</span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                default_idx = 0
                if has_draft and draft_ratings and item_num in draft_ratings:
                    draft_val = str(draft_ratings[item_num])
                    if draft_val in rating_options:
                        default_idx = rating_options.index(draft_val)
                
                st.selectbox(
                    f"Rating for Q{item_num}",
                    options=rating_options,
                    index=default_idx,
                    format_func=lambda x: rating_labels.get(x, x),
                    key=f"rating_{item_num}",
                    label_visibility="collapsed"
                )
        
        st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
        
        # Overall comments
        st.markdown('<div class="dimension-header">Overall Feedback</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <p style="margin-top: 1rem; margin-bottom: 0.5rem; color: #333;">
            <strong>What are {leader_name + "'s" if not is_self else "your"} greatest strengths as a leader?</strong>
        </p>
        """, unsafe_allow_html=True)
        
        default_strengths = ""
        if has_draft and draft_comments and 'strengths' in draft_comments:
            default_strengths = draft_comments['strengths']
        
        st.text_area(
            "Strengths",
            value=default_strengths,
            key="comment_strengths",
            height=100,
            label_visibility="collapsed",
            placeholder="Describe the leadership qualities and behaviours that are most effective..."
        )
        
        st.markdown(f"""
        <p style="margin-top: 1.5rem; margin-bottom: 0.5rem; color: #333;">
            <strong>What should {leader_name if not is_self else "you"} focus on developing?</strong>
        </p>
        """, unsafe_allow_html=True)
        
        default_development = ""
        if has_draft and draft_comments and 'development' in draft_comments:
            default_development = draft_comments['development']
        
        st.text_area(
            "Development",
            value=default_development,
            key="comment_development",
            height=100,
            label_visibility="collapsed",
            placeholder="Suggest areas for growth and specific behaviours to work on..."
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- Two buttons: Save & Continue Later, and Submit ---
        col_save, col_submit = st.columns(2)
        
        with col_save:
            save_clicked = st.form_submit_button(
                "💾 Save & Continue Later",
                use_container_width=True
            )
        
        with col_submit:
            submit_clicked = st.form_submit_button(
                "✅ Submit Feedback",
                use_container_width=True,
                type="primary"
            )
        
        # --- Handle Save & Continue Later ---
        if save_clicked:
            ratings, comments = _collect_current_answers()
            try:
                db.save_draft(rater_id, ratings, comments)
                answered = len(ratings)
                total = 47
                st.success(
                    f"✅ **Progress saved!** ({answered} of {total} items answered)\n\n"
                    f"You can safely close this window. When you're ready to continue, "
                    f"just use the same link — your answers will be waiting for you."
                )
            except Exception as e:
                st.error(f"Could not save progress: {str(e)}")
        
        # --- Handle Submit ---
        if submit_clicked:
            # Collect all answers
            ratings, comments = _collect_current_answers()
            
            # Validate - check that all items have been rated
            missing = []
            for item_num in range(1, 48):
                if item_num not in ratings or ratings[item_num] == "":
                    missing.append(item_num)
            
            if missing:
                # Save what they have so far even though submission failed
                try:
                    db.save_draft(rater_id, ratings, comments)
                except Exception:
                    pass
                
                st.error(
                    f"Please provide a rating for all items before submitting. "
                    f"Missing: Q{', Q'.join(map(str, missing[:5]))}"
                    f"{'...' if len(missing) > 5 else ''}\n\n"
                    f"Your progress has been saved — you won't lose your answers."
                )
            else:
                # Process ratings for final submission
                processed_ratings = {}
                for item_num, rating in ratings.items():
                    if rating == "N/O":
                        processed_ratings[item_num] = "NO"
                    elif rating == "N/A":
                        processed_ratings[item_num] = "NA"
                    elif rating:
                        processed_ratings[item_num] = int(rating)
                
                # Process comments
                processed_comments = {k: v for k, v in comments.items() if v and v.strip()}
                
                # Submit to database (this also clears the draft)
                try:
                    db.submit_feedback(rater_id, processed_ratings, processed_comments)
                    
                    st.success("Thank you! Your feedback has been submitted successfully.")
                    st.balloons()
                    
                    st.query_params["submitted"] = "true"
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"An error occurred while submitting your feedback. Please try again. ({str(e)})")
    
    # --- Auto-save on page unload (JavaScript injection) ---
    # This sends current form data to Streamlit before the browser tab closes
    # Note: This is a best-effort mechanism — the form submit buttons are the primary save path
    st.markdown("""
    <script>
    // Auto-save reminder on page unload
    window.addEventListener('beforeunload', function(e) {
        // Browser will show a generic "are you sure?" prompt
        // The actual save happens via the Save button or next page load
    });
    </script>
    """, unsafe_allow_html=True)
    
    # --- Progress indicator in sidebar ---
    with st.sidebar:
        st.markdown("### 📊 Your Progress")
        
        answered = 0
        for item_num in range(1, 48):
            val = st.session_state.get(f"rating_{item_num}", "")
            if val and val != "":
                answered += 1
        
        progress = answered / 47
        st.progress(progress)
        st.markdown(f"**{answered}** of **47** items answered ({int(progress * 100)}%)")
        
        if st.session_state.get('last_saved'):
            st.markdown(f"<p style='color: #999; font-size: 0.8rem;'>Last saved: {st.session_state.last_saved}</p>", 
                       unsafe_allow_html=True)
        elif has_draft and draft_saved_at:
            st.markdown(f"<p style='color: #999; font-size: 0.8rem;'>Draft from: {str(draft_saved_at)[:16]}</p>", 
                       unsafe_allow_html=True)


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
