#!/usr/bin/env python3
"""
BENTLEY COMPASS 360 - Complete Web Application
===============================================

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
from framework import get_logo_data_uri
from database import Database
from feedback_form import render_feedback_form
from admin_dashboard import render_admin_dashboard
from leader_portal import render_leader_portal

# Page config
st.set_page_config(
    page_title="Bentley Compass 360",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Bentley-appropriate styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@300;400;600;700&display=swap');
    
    :root {
        --bentley-green: #183319;
        --bentley-cream: #F5F5DC;
        --bentley-charcoal: #2C2C2C;
    }
    
    .stApp {
        background: linear-gradient(180deg, #FAFAFA 0%, #F0F0F0 100%);
    }
    
    h1, h2, h3 {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: var(--bentley-green) !important;
    }

    .main-title {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 2.8rem;
        font-weight: 600;
        color: #183319;
        text-align: center;
        margin-bottom: 0.5rem;
        letter-spacing: 0.05em;
    }

    .main-title-logo {
        display: block;
        max-height: 76px;
        margin: 0 auto 0.75rem auto;
    }

    .subtitle {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    /* Hairline border, not a shadow — see the item-container/thank-you-container
       rules below for the same treatment. .leader-card and .stat-box aren't
       applied anywhere in the app yet (no template currently uses these
       classes), updated here so they're consistent whenever they are used. */
    .leader-card {
        background: white;
        border-radius: 8px;
        padding: 1.5rem;
        border: 1px solid #E2E0D8;
        border-left: 4px solid #183319;
        margin-bottom: 1rem;
    }

    /* Supporting/secondary detail gets the bordered treatment; a primary stat
       number is meant to sit with no card at all (see .stat-number), so this
       class is for the label/context around it, not the number itself. */
    .stat-box {
        background: white;
        border-radius: 8px;
        padding: 1.2rem;
        text-align: center;
        border: 1px solid #E2E0D8;
    }

    .stat-number {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 2.5rem;
        font-weight: 600;
        color: #183319;
    }
    
    .stat-label {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 0.9rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .progress-complete {
        color: #183319;
        font-weight: 600;
    }
    
    .progress-partial {
        color: #4D4D4F;
        font-weight: 600;
    }
    
    .progress-none {
        color: #999;
    }
    
    /* Form styling. Plain background, wordmark carried by type, a thin green
       rule underneath — no gradient. Gold retired from the brand palette
       2026-08-06 (the confirmed Bentley green replaced an earlier estimate,
       and gold/tan/leather tones aren't in the real brand book at all). */
    .feedback-header {
        background: #FFFFFF;
        color: #183319;
        padding: 1.5rem 2rem;
        border-bottom: 2px solid #183319;
        margin-bottom: 2rem;
        text-align: center;
    }

    .feedback-header h1 {
        color: #183319 !important;
        margin-bottom: 0.5rem;
    }

    .feedback-header p {
        color: #505046;
    }

    .feedback-header-logo {
        max-height: 56px;
        margin-bottom: 0.5rem;
    }
    
    .dimension-header {
        background: #183319;
        color: white;
        padding: 0.8rem 1.2rem;
        border-radius: 6px;
        margin: 1.5rem 0 1rem 0;
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 1.3rem;
    }
    
    .item-container {
        background: white;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        border: 1px solid #E0E0E0;
    }

    /* The whole feedback form card (dimension header, description, item
       boxes, comment box, buttons) - Heritage White per the report's Bentley
       brand palette (framework.py COLOURS['heritage_white'], #DCD8C0), so
       the survey pages read as part of the same document family as the
       report. The form itself has a transparent background by default (the
       pale card look in the old screenshots was just the page background
       showing through its border), so this sets a real fill for the first
       time rather than overriding one.
       Scoped to the "compass_survey_form" container key (wrapping just the
       rater/self-assessment st.form calls in feedback_form.py) rather than
       the bare stForm testid - stForm has no key-based class of its own, and
       an unscoped rule here would silently reach every other st.form in the
       app (leader_portal.py's Add a Rater, admin_dashboard.py's add-leader/
       add-rater/quick-add forms), none of which were part of this request. */
    div[class*="st-key-compass_survey_form"] div[data-testid="stForm"] {
        background: #DCD8C0;
        border: 1px solid #C9C4A8;
    }

    /* "Welcome back" resume banner (st.info) - recoloured from Streamlit's
       default blue to match the instructions box's white-card-with-green-
       accent family, so it reads as part of this page rather than a generic
       system alert. Scoped to the info variant only via stAlertContentInfo -
       success/error/warning alerts keep their default colours (red for
       errors is universal and deliberately left alone). */
    .stAlertContainer:has([data-testid="stAlertContentInfo"]) {
        background: white;
        border: 1px solid #E0E0E0;
        border-left: 4px solid #183319;
    }
    .stAlertContainer:has([data-testid="stAlertContentInfo"]) [data-testid="stAlertContentInfo"],
    .stAlertContainer:has([data-testid="stAlertContentInfo"]) [data-testid="stAlertContentInfo"] * {
        color: #183319;
    }

    /* Text areas (comment boxes, keep/change, priority actions) default to
       Streamlit's own pale grey fill (#F0F2F6) - switched to white so they
       read as the same kind of card as the question boxes, not a different
       control style, against the Heritage White form background. Scoped the
       same way as the form background above, for the same reason. */
    div[class*="st-key-compass_survey_form"] div[data-testid="stTextAreaRootElement"],
    div[class*="st-key-compass_survey_form"] div[data-testid="stTextAreaRootElement"] div {
        background-color: white;
    }
    div[class*="st-key-compass_survey_form"] div[data-testid="stTextAreaRootElement"] {
        border: 1px solid #E0E0E0;
    }

    /* Leader portal's "Add a Rater" fields (Name, Email, Relationship) -
       same pale-grey-to-white treatment as the survey's text areas above,
       scoped to this one form via its container key so it doesn't reach the
       admin dashboard's own add-leader/add-rater/quick-add forms, which
       weren't part of this request. The relationship dropdown's fill has no
       stable testid of its own (BaseWeb's select renders it as a plain div),
       so it's matched structurally as the direct child of [data-baseweb=
       "select"] instead. */
    div[class*="st-key-portal_add_rater_form"] div[data-testid="stTextInputRootElement"],
    div[class*="st-key-portal_add_rater_form"] div[data-testid="stTextInputRootElement"] div {
        background-color: white;
    }
    div[class*="st-key-portal_add_rater_form"] div[data-testid="stTextInputRootElement"] {
        border: 1px solid #E0E0E0;
    }
    /* Two selectors for the same widget, deliberately: st.selectbox's internal
       markup changed between Streamlit versions (BaseWeb's [data-baseweb=
       "select"] on 1.53.x, a React Aria [role="group"] on 1.60.0, which is
       what's actually pinned in requirements.txt for deployment). Found
       2026-08-14 when this rule tested white locally but stayed pale grey on
       the deployed sandbox - local dev was running 1.53.1, unrelated to
       what's deployed. A selector that doesn't match on a given version is
       harmless, so keeping both here means this doesn't silently break again
       the next time Streamlit changes a widget's internals either way. */
    div[class*="st-key-portal_add_rater_form"] div[data-baseweb="select"] > div,
    div[class*="st-key-portal_add_rater_form"] [data-testid="stSelectbox"] [role="group"] {
        background-color: white;
    }

    /* "Or upload multiple raters" box - stretched to the same depth as its
       neighbouring "Add a Rater" form. The two columns already stretch to
       equal height (Streamlit's own flex row does that), but a bordered
       st.container only fills that height at the outer stColumn level - its
       own inner wrapper (stLayoutWrapper) still shrinks to fit its content,
       leaving empty space below the visible border. Reaching that wrapper
       needs :has(), since it carries no key or class of its own to select by. */
    div[data-testid="stLayoutWrapper"]:has(> div[class*="st-key-portal_upload_raters"]) {
        height: 100%;
    }
    div[class*="st-key-portal_upload_raters"] {
        height: 100%;
        box-sizing: border-box;
    }

    /* Upload CSV dropzone - same pale-grey-to-white treatment as the other
       fields in this section, scoped to this one uploader. */
    div[class*="st-key-portal_upload_raters"] [data-testid="stFileUploaderDropzone"] {
        background-color: white;
        border: 1px solid #E0E0E0;
    }

    /* Per-item rating box on the live dimension page (question + segmented
       control together) - reverted to white so it reads as a distinct card
       against the Heritage White form background surrounding it. */
    div[class*="st-key-item_box_"] {
        background: white;
        padding: 1rem 1.2rem 0.6rem 1.2rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        border: 1px solid #E0E0E0;
    }

    /* Review page's "Edit" buttons only (key="edit_<page_idx>"), matched to
       the dimension-header bar's own rendered height (measured 58.87px at
       font-size 1.3rem + 0.8rem vertical padding) so the two line up top
       and bottom, not just top. Scoped to this key prefix rather than all
       secondary buttons, which must keep their own height elsewhere. */
    div[class*="st-key-edit_"] button[data-testid="stBaseButton-secondaryFormSubmit"] {
        height: 58.87px;
    }
    /* The element-container itself (matched above) shrinks to fit the button
       and has no spare width to justify within, so the right-align has to go
       on its parent column block, which does hold the column's full width.
       That block is already flex-direction:column (Streamlit's default), so
       the cross-axis property is align-items, not justify-content. :has()
       reaches "up" to find the vertical block wrapping our specific edit
       button, without affecting any other column layout. */
    div[data-testid="stVerticalBlock"]:has(> div[class*="st-key-edit_"]) {
        align-items: flex-end;
    }

    .item-text {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 1rem;
        color: #333;
        margin-bottom: 0.8rem;
        line-height: 1.5;
    }

    /* Review page item rows only. Fixed-width right-hand column for the
       rating label so it lands in a straight vertical line regardless of
       question length, instead of trailing at the end of variable-length
       question text. */
    .review-item-row {
        display: flex;
        align-items: baseline;
        gap: 1rem;
        background: white;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        border: 1px solid #E0E0E0;
    }
    .review-item-question {
        flex: 1 1 auto;
        min-width: 0;
    }
    .review-item-question .item-text {
        margin-bottom: 0;
    }
    .review-item-rating {
        flex: 0 0 160px;
        text-align: right;
        font-weight: 700;
        color: #183319;
        white-space: nowrap;
    }

    /* Rating scale (st.segmented_control, one per item). Verified against the
       real rendered DOM rather than guessed: the widget's own selected/
       unselected data-testid suffix ("...segmented_control" vs
       "...segmented_controlActive") is what actually distinguishes state —
       theme.primaryColor in .streamlit/config.toml only gives a light tint on
       its own, not the solid fill this needed. */
    div[data-testid="stButtonGroup"] {
        margin-bottom: 0.5rem;
    }
    button[data-testid="stBaseButton-segmented_controlActive"] {
        background: #183319 !important;
        border-color: #183319 !important;
    }
    button[data-testid="stBaseButton-segmented_controlActive"] * {
        color: #FFFFFF !important;
    }

    /* Set apart the last of the six options ("No opportunity to observe") as
       a muted, functionally-different answer to the five frequency options
       before it — a hairline divider and muted colour, not a numbered pill.
       Font-size was also reduced to 0.85em here originally, but that read as
       just "the text is too small" on the actual button rather than as a
       deliberate distinction (the button itself is still full-size, so a
       smaller label alone looked like an inconsistency, not a design
       choice) - dropped back to full size; the divider and colour alone
       already carry the "set apart" signal. */
    div[data-testid="stButtonGroup"] [role="radiogroup"] > button:last-child {
        margin-left: 1.25rem;
        padding-left: 1.25rem;
        border-left: 1px solid #DDDDDD;
    }
    div[data-testid="stButtonGroup"] [role="radiogroup"] > button:last-child,
    div[data-testid="stButtonGroup"] [role="radiogroup"] > button:last-child * {
        color: #777777 !important;
    }
    div[data-testid="stButtonGroup"] [role="radiogroup"] > button:last-child[data-testid="stBaseButton-segmented_controlActive"] * {
        color: #FFFFFF !important;
    }

    /* Phone-width fix for the rating scale: below the breakpoint the six
       options (five frequency + "No opportunity...") wrap unevenly across
       two or three rows instead of reading as a deliberate layout. Verified
       against the real rendered DOM before writing this, not assumed: the
       actual flex container that wraps is [role="radiogroup"] INSIDE
       stButtonGroup (display:flex, flex-wrap:wrap) - the outer
       stButtonGroup div itself is only display:block, so a rule targeting
       it directly would do nothing. A pure viewport-width media query, not
       user-agent/device sniffing, so a resized desktop window behaves
       identically to a phone at the same width.

       BREAKPOINT IS 1100px, NOT the ~480px "phone portrait" starting point,
       and NOT the 960px this shipped with originally - measured
       empirically, three times over, not assumed. Checked 390/430/600px
       per the original ask; 600px still wrapped awkwardly (4 buttons then
       2, the exact uneven split this fix exists to prevent). Swept every
       width from 480 up looking for the real single-row fit point: the
       survey card's content column is viewport-constrained up to ~940px,
       then hits a content-driven width around ~709-710px for today's
       English labels - only marginally sufficient for one row (708px still
       wraps, 709px doesn't).

       RETESTED 2026-08-21 against placeholder German-length translations
       (before real six-language translations exist, per the human's
       request) - and the 960px breakpoint this originally shipped with
       FAILED the retest: German-length labels ("Keine Gelegenheit zur
       Beobachtung" vs "No opportunity to observe", +27%) need ~771px
       unwrapped, not ~709px, and wrapped again at 970-1000px viewport
       (clean again only from ~1010px) - the exact "silently reintroduced
       for non-English locales" bug this check existed to catch, confirmed
       real rather than hypothetical. A further deliberately-extreme stress
       test (not realistic, just to find the outer bound) needed ~1233px
       unwrapped and didn't stop wrapping until ~1500px viewport - proof
       there is no single breakpoint that survives arbitrarily long future
       translations, only ones tuned to a given length assumption.

       1100px is tuned to clear the REALISTIC German-length case (~1010px)
       with real margin, not the deliberately-extreme stress case (~1500px)
       - widening all the way to 1500px now would force the column layout
       on far more ordinary desktop widths than today's content justifies.
       REVISIT THIS ONCE REAL SIX-LANGUAGE TRANSLATIONS ARE COMMISSIONED:
       re-run this same width sweep against the actual shipped strings,
       not placeholder text, since a real translation could still land
       longer than this placeholder guessed. Below 1100px: clean single-
       column stack, six full-width rows, regardless of content length or
       font metrics. At or above: unchanged horizontal row. */
    @media (max-width: 1100px) {
        /* FIXED 2026-08-21: buttons were narrower than the card, a visible
           gap on the right. width:100% on the buttons alone did nothing,
           because their actual containing chain was each shrunk to its own
           content by THREE separate Streamlit defaults, found by checking
           computed styles and matching stylesheet rules directly rather
           than guessing: stElementContainer has width:fit-content, and
           [role="radiogroup"] separately has max-width:fit-content (its own
           width is auto, but max-width caps it regardless of what width is
           set to). All three needed overriding together - fixing only the
           radiogroup left it still capped by stElementContainer above it,
           and fixing width alone on the radiogroup left it capped by its
           own separate max-width rule. Verified the result matches the
           card's own established content width exactly (52px/338px on
           both the question text and every button, at a 390px viewport) -
           this is the card's real content edge, inside its own padding,
           not the outer card border. */
        div[class*="st-key-item_box_"] div[data-testid="stElementContainer"] {
            width: 100%;
        }
        div[data-testid="stButtonGroup"] {
            width: 100%;
        }
        div[data-testid="stButtonGroup"] [role="radiogroup"] {
            flex-direction: column;
            flex-wrap: nowrap;
            gap: 0.4rem;
            width: 100%;
            max-width: none;
        }
        div[data-testid="stButtonGroup"] [role="radiogroup"] > button {
            width: 100%;
        }
        /* The "No opportunity..." divider (above) uses a LEFT border to set
           it apart in a horizontal row. FIXED 2026-08-21: rotating that to
           border-top for the stacked column REPLACED the button's own
           normal top border instead of adding to it (border-top is a
           shorthand - it always overwrites, never layers), leaving this one
           button visibly missing an edge the other five still had. The
           divider now has to be genuinely additive: border-left/top here
           are reset back to the button's own normal border (measured
           directly from an unmodified button: 1px solid rgba(49,51,63,0.2))
           rather than left in the "none"/custom-colour state the first
           version of this fix left them in, and the actual "set apart from
           the five frequency options" line is drawn with box-shadow
           instead, which sits outside the border box entirely and can't
           overwrite any of the button's four normal border sides. */
        div[data-testid="stButtonGroup"] [role="radiogroup"] > button:last-child {
            margin-left: 0;
            padding-left: 0;
            border-left: 1px solid rgba(49, 51, 63, 0.2);
            margin-top: 0.5rem;
            box-shadow: 0 -1px 0 0 #DDDDDD;
        }
    }

    /* One prominent progress readout per page (since the paginated redesign,
       not a slim per-item readout repeated 45 times as originally built) -
       thicker track and a larger, bolder percentage than that earlier,
       easy-to-miss version. */
    .item-progress {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin: 0 0 1.2rem 0;
    }
    .item-progress-track {
        flex: 1;
        height: 10px;
        background: #E2E0D8;
        border-radius: 5px;
        overflow: hidden;
    }
    .item-progress-fill {
        height: 100%;
        background: #183319;
        border-radius: 5px;
        transition: width 0.2s;
    }
    .item-progress-text {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 1.15rem;
        font-weight: 700;
        color: #183319;
        white-space: nowrap;
    }

    /* ============================================
       BUTTONS
       Every rule below sets text colour and background TOGETHER. Setting one
       without the other is what produced white-on-white buttons: Streamlit
       renders a light default background on its "secondary" variants, so a
       blanket `color: white` made the label invisible.
       Selectors hook the data-testid on the button element itself rather than
       using `.stButton > button`, because Streamlit nests a div between the
       wrapper and the button, which breaks the direct-child selector.
       ============================================ */

    /* Primary actions — solid Bentley green, white label. No gradient, no
       movement or shadow growth on hover — hover only shifts to a slightly
       darker solid shade. */
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-primaryFormSubmit"] {
        background: #183319 !important;
        color: #FFFFFF !important;
        border: 1px solid #183319 !important;
        padding: 0.6rem 2rem;
        font-family: 'Source Sans Pro', sans-serif;
        font-weight: 600;
        letter-spacing: 0.05em;
        transition: background-color 0.2s, border-color 0.2s;
    }
    button[data-testid="stBaseButton-primary"] *,
    button[data-testid="stBaseButton-primaryFormSubmit"] * {
        color: #FFFFFF !important;
    }
    button[data-testid="stBaseButton-primary"]:hover,
    button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
        background: #013825 !important;
        color: #FFFFFF !important;
    }
    button[data-testid="stBaseButton-primary"]:hover *,
    button[data-testid="stBaseButton-primaryFormSubmit"]:hover * {
        color: #FFFFFF !important;
    }

    /* Secondary actions — white with a green label and green border. Hover
       only changes the border, no fill/movement/shadow change. */
    button[data-testid="stBaseButton-secondary"],
    button[data-testid="stBaseButton-secondaryFormSubmit"] {
        background: #FFFFFF !important;
        color: #183319 !important;
        border: 1px solid #183319 !important;
        /* Matches the primary button's padding above - Streamlit's own
           default secondary padding (4px 12px) is noticeably shorter than
           its default primary padding (9.6px 32px), so a secondary and
           primary button side by side (e.g. "Save & Continue Later" next to
           "Continue") rendered at visibly different heights without this. */
        padding: 0.6rem 2rem;
        font-family: 'Source Sans Pro', sans-serif;
        font-weight: 600;
        transition: border-color 0.2s, opacity 0.2s;
    }
    button[data-testid="stBaseButton-secondary"] *,
    button[data-testid="stBaseButton-secondaryFormSubmit"] * {
        color: #183319 !important;
    }
    button[data-testid="stBaseButton-secondary"]:hover,
    button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
        background: #FFFFFF !important;
        color: #183319 !important;
        border-color: #013825 !important;
        opacity: 0.85;
    }
    button[data-testid="stBaseButton-secondary"]:hover *,
    button[data-testid="stBaseButton-secondaryFormSubmit"]:hover * {
        color: #183319 !important;
    }

    /* Download buttons — neutral grey, distinct from the green action buttons */
    .stDownloadButton button {
        background: #FFFFFF !important;
        color: #333333 !important;
        border: 1px solid #DDDDDD !important;
        transition: border-color 0.2s;
    }
    .stDownloadButton button * {
        color: #333333 !important;
    }
    .stDownloadButton button:hover {
        background: #FFFFFF !important;
        color: #183319 !important;
        border-color: #183319 !important;
    }
    .stDownloadButton button:hover * {
        color: #183319 !important;
    }

    /* Disabled buttons — muted but still legible */
    button[data-testid="stBaseButton-primary"]:disabled,
    button[data-testid="stBaseButton-primaryFormSubmit"]:disabled,
    button[data-testid="stBaseButton-secondary"]:disabled,
    button[data-testid="stBaseButton-secondaryFormSubmit"]:disabled {
        background: #F0F0F0 !important;
        color: #666666 !important;
        border-color: #CCCCCC !important;
    }
    button[data-testid="stBaseButton-primary"]:disabled *,
    button[data-testid="stBaseButton-primaryFormSubmit"]:disabled *,
    button[data-testid="stBaseButton-secondary"]:disabled *,
    button[data-testid="stBaseButton-secondaryFormSubmit"]:disabled * {
        color: #666666 !important;
    }

    /* Thank you page */
    .thank-you-container {
        text-align: center;
        padding: 4rem 2rem;
        background: white;
        border-radius: 12px;
        border: 1px solid #E2E0D8;
        max-width: 600px;
        margin: 2rem auto;
    }
    
    .thank-you-icon {
        display: flex;
        justify-content: center;
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

# Auto-load demo data on first run if database is empty
def load_demo_data_if_empty():
    """Load demo data if no leaders exist."""
    leaders = db.get_all_leaders()
    if len(leaders) == 0:
        import numpy as np
        from framework import DIMENSIONS, ITEMS
        
        # Demo leaders
        demo_leaders = [
            {'name': 'Sarah Mitchell', 'email': 'sarah.mitchell@bentley.com', 'dealership': 'Bentley London', 'cohort': 'January 2026'},
            {'name': 'James Thompson', 'email': 'james.thompson@bentley.com', 'dealership': 'Bentley Manchester', 'cohort': 'January 2026'},
            {'name': 'Emma Richardson', 'email': 'emma.richardson@bentley.com', 'dealership': 'Bentley Edinburgh', 'cohort': 'January 2026'}
        ]
        
        comments_pool = {
            'Leading Self': ["Could benefit from stepping back from operational detail more often.", "Always makes time for us even when busy.", "Handles pressure exceptionally well."],
            'Developing Others': ["Really invests in their people.", "The coaching conversations have been transformational.", "Creates genuine learning opportunities."],
            'Building High-Performing Teams': ["Creates a great team spirit.", "Knows how to get the best out of different personalities.", "Brings positive energy even on tough days."],
            'Driving Results': ["Consistently delivers. One of the most reliable leaders.", "Sets high standards and meets them.", "Clear on expectations."],
            'Leading Change': ["Communication during change could be earlier.", "Not always the first to embrace new initiatives.", "Helps the team understand the 'why'."],
            'Communicating & Influencing': ["Great listener. Makes you feel heard.", "Adapts communication style brilliantly.", "Feedback is always constructive."],
            'Building Trust': ["Completely trustworthy.", "One of the most genuine people in the leadership team.", "Always admits when they've got something wrong."],
            'Thinking Strategically': ["Would like to see more strategic thinking.", "Good at their area but could connect more with wider business.", "Excellent at balancing priorities."],
            'strengths': ["Builds excellent relationships with the team.", "Trustworthy, consistent, and genuinely cares.", "Really invests in development.", "Great at building team spirit."],
            'development': ["Could be more strategic and less operational.", "Could be quicker to embrace change.", "Would like more delegation.", "Communication during change could be more proactive."]
        }
        
        np.random.seed(42)
        
        for leader_info in demo_leaders:
            leader_id = db.add_leader(leader_info['name'], leader_info['email'], leader_info['dealership'], leader_info['cohort'])
            
            # Add raters
            for rel, name, count in [('Self', leader_info['name'], 1), ('Boss', None, 1), ('Peers', None, 4), ('DRs', None, 5), ('Others', None, 2)]:
                for _ in range(count):
                    db.add_rater(leader_id, rel, name)
            
            raters = db.get_raters_for_leader(leader_id)
            leader_strengths = list(np.random.choice(list(DIMENSIONS.keys()), 3, replace=False))
            leader_dev_areas = [d for d in DIMENSIONS.keys() if d not in leader_strengths][:2]
            
            for rater in raters:
                ratings = {}
                rel = rater['relationship']
                
                for item_num in range(1, 46):
                    dim_name = None
                    for d, (start, end) in DIMENSIONS.items():
                        if start <= item_num <= end:
                            dim_name = d
                            break

                    base = 4.3 if dim_name in leader_strengths else (3.5 if dim_name in leader_dev_areas else 4.0)
                    if rel == 'Self' and dim_name in leader_dev_areas:
                        base += 0.5

                    score = int(round(min(5.0, max(1.0, base + np.random.uniform(-0.5, 0.5)))))
                    ratings[item_num] = 0 if (rel == 'Others' and np.random.random() < 0.1) else score

                comments = {}
                for dim in list(np.random.choice(list(DIMENSIONS.keys()), np.random.randint(2, 4), replace=False)):
                    if dim in comments_pool:
                        comments[dim] = np.random.choice(comments_pool[dim])

                if rel != 'Self':
                    comments['keep'] = np.random.choice(comments_pool['strengths'])
                    comments['change'] = np.random.choice(comments_pool['development'])

                db.submit_feedback(rater['id'], ratings, comments)

load_demo_data_if_empty()

def get_route():
    """Determine which page to show based on URL parameters."""
    params = st.query_params
    
    # Check for feedback form token (supports both 't' and 'token' for backwards compatibility)
    if 't' in params:
        return 'feedback', params['t']
    if 'token' in params:
        return 'feedback', params['token']
    
    # Check for leader portal
    if 'portal' in params:
        return 'portal', params['portal']
    
    # Check for admin access
    if 'admin' in params:
        return 'admin', None
    
    # Default to landing page
    return 'landing', None

def render_landing_page():
    """Render the main landing/info page."""
    logo_uri = get_logo_data_uri()
    logo_html = f'<img src="{logo_uri}" class="main-title-logo">' if logo_uri else ''
    st.markdown(f'{logo_html}<p class="main-title">BENTLEY COMPASS 360</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">360-Degree Leadership Feedback</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="background: white; padding: 2rem; border-radius: 12px; border: 1px solid #E2E0D8; text-align: center;">
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
        with st.expander("Administrator Access", icon=":material/lock:"):
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
    
    elif route == 'portal':
        # Validate portal token and show leader portal
        leader_info = db.get_leader_by_portal_token(param)
        if leader_info:
            render_leader_portal(db, leader_info)
        else:
            st.error("Invalid or expired portal link. Please contact your programme coordinator.")
    
    elif route == 'admin':
        render_admin_dashboard(db)
    
    else:
        render_landing_page()

def render_thank_you_page(already_completed=False):
    """Render the thank you page after submission."""
    st.markdown("""
    <div class="thank-you-container">
        <div class="thank-you-icon">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="#183319" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
        </div>
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
