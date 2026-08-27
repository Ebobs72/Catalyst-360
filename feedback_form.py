#!/usr/bin/env python3
"""
Feedback form for raters in Bentley Compass 360.

Paginated by dimension: one dimension (5 items + its comment box) per page,
then Overall Feedback, then Development Priorities (self-assessment only),
then a final Review page before the real submit. Supports save & resume —
raters can close the browser and return later, picking up at the first
incomplete page.
"""

import streamlit as st
from datetime import datetime
from framework import (
    DIMENSIONS, DIMENSION_DESCRIPTIONS,
    RELATIONSHIP_TYPES, GROUP_DISPLAY,
    SCALE_FREQUENCY, OPEN_PROMPTS,
    DEVELOPMENT_PRIORITY_COUNT, DEVELOPMENT_PRIORITY_INTRO,
    DEVELOPMENT_PRIORITY_PROMPT, DEVELOPMENT_PRIORITY_MINIMUM,
    DEVELOPMENT_PRIORITY_ACTION_MIN_CHARS,
    get_item_text, get_prompt_text, get_logo_data_uri,
    SUPPORTED_LOCALES, RTL_LOCALES, dimension_slug,
    get_bentley_font_face_css, BENTLEY_FONT_STACK,
    get_bentley_logotype_face_css
)

# Admin report-ready milestone notifications (self-assessment complete, Full
# 360 crossed threshold) - optional the same way every other email feature
# in this app is: a deployment with no SMTP/admin address configured must
# still let raters submit normally.
try:
    from email_sender import send_admin_notification
    ADMIN_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    ADMIN_NOTIFICATIONS_AVAILABLE = False

TOTAL_ITEMS = 45

# Rating scale as a single row of 6 labelled buttons (st.segmented_control),
# not a dropdown. "No opportunity to observe" is functionally a different kind
# of answer to the 5 frequency options — not a 6th point on the scale — and is
# set apart visually via CSS (see the stButtonGroup rules in app.py), but it
# stays one widget with the other five rather than a second, separately-
# coordinated control: widgets inside st.form don't fire on_change, so there is
# no way to keep two separate controls mutually exclusive live as the rater
# clicks. Selected/unselected colouring comes from .streamlit/config.toml's
# theme, not custom CSS here.
SCALE_OPTIONS = [SCALE_FREQUENCY[i] for i in (1, 2, 3, 4, 5, 0)]
SCALE_LABEL_TO_VALUE = {v: str(k) for k, v in SCALE_FREQUENCY.items()}

# translations string_key suffixes for the rating scale (ui_rating_{suffix}).
# st.segmented_control's stored value IS the displayed label text, so once
# this label is translated, reversing it back to a stored code ("0"-"5") has
# to go through a LOCALE-AWARE map, not the English-only SCALE_LABEL_TO_VALUE
# above - see the scale_labels_by_code/scale_label_to_value_localized build in
# render_feedback_form. Getting this wrong silently drops ratings, so it's
# handled explicitly rather than left to the English map's .get(..., "") default.
SCALE_KEY_SUFFIX = {1: 'rarely', 2: 'occasionally', 3: 'sometimes', 4: 'often', 5: 'consistently', 0: 'no_opportunity'}

# Bentley typeface, same reasoning/scope as leader_portal.py's identical
# block (see PORTAL_CSS there): font-face declarations plus overriding
# font-family on the same selectors app.py's global stylesheet sets
# 'Source Sans Pro' on - bare h1-h3, the four button-variant testids, and
# the handful of classes this file's own markup actually uses
# (.dimension-header, .item-text, .item-progress-text, .review-item-rating -
# checked by grep, not guessed; app.py also defines .main-title/.subtitle/
# .stat-number/.stat-label but nothing in this file renders those, so
# overriding them here would be dead weight). Matching selectors +
# !important + later injection order (rendered from inside
# render_feedback_form, which only ever runs on the 'feedback' route -
# Admin Dashboard never receives this stylesheet at all) is what makes this
# win without touching app.py's shared rule, which Admin also depends on
# and is out of scope here.
#
# GENUINE BOLD ROLLOUT, 2026-08-27: get_bentley_font_face_css() now also
# registers Expanded Bold at weight:700 under this same 'Bentley' family
# (see framework.py) - so .item-progress-text (the "X%" progress figure,
# already weight:700 in app.py) and .review-item-rating (the Review page's
# per-item selected-answer label, also weight:700, newly added to this
# selector list for that reason - it wasn't in scope for the earlier
# typeface pass since nothing there was about bold specifically) both
# automatically pick up the genuine face, with no separate override needed.
# .dimension-header is NOT weight:700 (confirmed live via computed style,
# not assumed) - it just reads as emphasised due to the dark green fill and
# size, so it stays on Regular; forcing it bold would be inventing new
# emphasis the design doesn't currently have, which this task is not asking
# for.
#
# INLINE <strong> TAGS, RECONSIDERED 2026-08-27: the bold-rollout task's own
# reasoning explicitly worried about genuine Expanded Bold reading as "a
# distracting, constant width-mismatch" in running body text (consent-gate
# copy, instructions, "unless you are the direct line manager..." etc.),
# and an earlier version of this comment described those <strong> tags as
# deliberately excluded from the rollout for that reason. Superseded the
# same day by the broader "every text instance" pass below (.stApp *) -
# excluding <strong> specifically would have meant giving it back a
# different, non-Bentley font-family, which contradicts "every single
# instance of text" and would need its own careful weight/font trickery to
# still look bold without picking up the real 700 face (not attempted -
# real complexity for a benefit that didn't hold up). Checked live instead
# of assumed: genuine Expanded Bold inline mid-sentence (rater-form intro,
# consent gate) reads cleanly at running-text size, not distracting or
# cramped - the original worry didn't materialise in practice, so <strong>
# now gets the same treatment as everything else, no exception.
_BENTLEY_TYPEFACE_CSS = f"""
<style>
{get_bentley_font_face_css()}
{get_bentley_logotype_face_css()}
/* EVERY TEXT INSTANCE, 2026-08-27 - see the identical rule in
   leader_portal.py's PORTAL_CSS for the full reasoning: selector-by-
   selector coverage (h1-h3, the button testids, a handful of named
   classes) missed Streamlit's own internal markup - a button's own <p>
   label, widget labels, captions, the rating-scale option text, input/
   textarea text - none of which are h1-h3, a button element itself, or
   one of the named classes, so none of it was ever actually getting
   Bentley. Confirmed live: a button showed family:Bentley on the <button>
   itself but "Source Sans" (Streamlit's own built-in default) on its
   inner <p>, since Streamlit's own stylesheet sets that <p>'s font-family
   directly, breaking inheritance from the button around it.
   `.stApp *` reaches every descendant of the page unconditionally rather
   than needing every current and future Streamlit-internal element type
   named individually - !important beats a Streamlit default that isn't
   itself !important (framework defaults essentially never are), so this
   wins without needing to out-specify anything selector by selector.
   REQUIRED EXCEPTION: Material Symbols icons (every st.button(...,
   icon=":material/name:") call in this file - 13 of them) render the
   literal icon name as text inside [data-testid="stIconMaterial"] and
   map it to a glyph via the "Material Symbols Rounded" icon font
   specifically - overriding that font would show the literal name
   ("arrow_forward", "check_circle"...) as readable text next to the
   button label instead of an icon. Declared AFTER the broad rule since
   both are single-attribute-selector specificity - later wins the tie. */
.stApp, .stApp * {{
  font-family: {BENTLEY_FONT_STACK} !important;
}}
[data-testid="stIconMaterial"] {{
  font-family: 'Material Symbols Rounded' !important;
}}
.feedback-header-title {{
  font-family: 'Bentley Logotype', {BENTLEY_FONT_STACK} !important;
}}
</style>
"""


# ============================================
# PAGE SEQUENCE
# ============================================
# Each page is (page_type, page_arg). Dimension pages carry the dimension name
# as page_arg; the rest carry None. Review is always last - code elsewhere
# (the edit-jump-back logic) relies on that.

def _build_pages(is_self):
    pages = [('dimension', dim_name) for dim_name in DIMENSIONS.keys()]
    pages.append(('overall', None))
    if is_self:
        pages.append(('priorities', None))
    pages.append(('review', None))
    return pages


def _dimension_range_answered(start, end, draft_ratings):
    """How many items in [start, end] have a rating right now (session_state,
    falling back to a loaded draft for items not yet touched this session)."""
    count = 0
    for item_num in range(start, end + 1):
        val = st.session_state.get(f"rating_{item_num}")
        if not val and draft_ratings and item_num in draft_ratings:
            val = draft_ratings[item_num]
        if val:
            count += 1
    return count


def _count_answered_ratings(draft_ratings=None):
    """How many of the 45 items have a rating selected right now, across every
    dimension page visited so far this session (session_state persists across
    page transitions even though only one page's widgets are on screen at a
    time) plus anything already in a loaded draft."""
    return _dimension_range_answered(1, TOTAL_ITEMS, draft_ratings)


def _resume_page_index(pages, draft_ratings):
    """Where a rater should land: the first dimension page that isn't fully
    rated yet, or the first trailing page (Overall Feedback) if every
    dimension is already complete. Purely derived from draft_ratings, so it
    works the same whether this is a same-session rerun with nothing saved
    yet or a genuine browser-close-and-reopen days later."""
    for i, (page_type, page_arg) in enumerate(pages):
        if page_type == 'dimension':
            start, end = DIMENSIONS[page_arg]
            if _dimension_range_answered(start, end, draft_ratings) < (end - start + 1):
                return i
        else:
            return i
    return len(pages) - 1


def _collect_current_answers(label_to_value=None, base_ratings=None, base_comments=None):
    """Gather all current ratings and comments from session state.

    label_to_value maps the CURRENTLY DISPLAYED scale label back to its
    stored code ("0"-"5"). Defaults to the English map, but every real call
    site passes the rater's locale-aware map instead: once the rating scale
    labels are translated, the widget's stored value IS the translated label,
    and the English-only default would fail to find it and silently drop the
    rating as "" rather than raise.

    Ratings from EVERY dimension visited so far are gathered here, not just
    the current page's - st.session_state keeps a widget's value even once
    that widget is no longer being re-rendered on later pages, so this is safe
    to call from any page and always reflects the rater's full progress.

    CORRECTION: that last claim was wrong when this was written, and it broke
    real multi-page saving - confirmed empirically (not assumed) by checking
    the actual saved draft after three dimension pages: it only ever held the
    MOST RECENTLY visited page's items. Streamlit does not reliably keep a
    widget's st.session_state entry once that widget stops being instantiated
    on a later run (each page only re-creates its own 5 rating_N/comment_X
    widgets, not every dimension's). So this now takes base_ratings/
    base_comments - the draft already loaded once at the top of
    render_feedback_form - and merges the current page's fresh session_state
    values on top of that, rather than trusting session_state alone to have
    accumulated everything from every page visited so far.
    """
    label_to_value = label_to_value or SCALE_LABEL_TO_VALUE
    ratings = dict(base_ratings or {})
    comments = dict(base_comments or {})

    for item_num in range(1, TOTAL_ITEMS + 1):
        label = st.session_state.get(f"rating_{item_num}")
        if label:
            ratings[item_num] = label_to_value.get(label, "")

    for dim_name in DIMENSIONS.keys():
        val = st.session_state.get(f"comment_{dim_name}", "")
        if val and val.strip():
            comments[dim_name] = val

    for key in ['keep', 'change']:
        val = st.session_state.get(f"comment_{key}", "")
        if val and val.strip():
            comments[key] = val

    return ratings, comments


def _collect_priorities():
    """
    Gather the self-assessment development priorities from session state.

    Returns a list of {'rank', 'dimension', 'actions'}. Entries where no
    dimension was chosen are returned too, so callers can distinguish an
    untouched form from a partially filled one; save_development_priorities
    drops them.
    """
    priorities = []
    for rank in range(1, DEVELOPMENT_PRIORITY_COUNT + 1):
        dimension = st.session_state.get(f"priority_dim_{rank}", "")
        actions = st.session_state.get(f"priority_actions_{rank}", "")
        priorities.append({
            'rank': rank,
            'dimension': dimension if dimension else None,
            'actions': actions,
        })
    return priorities


def _duplicate_priority_dimensions(priorities):
    """Return the dimensions chosen more than once, if any."""
    chosen = [p['dimension'] for p in priorities if p.get('dimension')]
    return sorted({d for d in chosen if chosen.count(d) > 1})


def _priorities_missing_actions(priorities):
    """
    Return the ranks of any priority that has a dimension chosen but no usable
    actions text. Choosing a dimension commits the leader to saying what they
    will do about it, otherwise the priority carries nothing into a coaching
    conversation.
    """
    missing = []
    for p in priorities:
        if not p.get('dimension'):
            continue
        actions = (p.get('actions') or '').strip()
        if len(actions) < DEVELOPMENT_PRIORITY_ACTION_MIN_CHARS:
            missing.append(p['rank'])
    return missing


def _t(db, key, locale, fallback):
    """Shorthand for db.get_translation - returns fallback (the current
    English string, already hardcoded at every call site) until a real
    translation row exists for `locale`. Safe to call with locale=None."""
    return db.get_translation(key, locale, fallback_text=fallback)


def _render_comment_guidance(db, locale):
    """Persistent guidance line below an optional comment box, encouraging
    brevity and specificity. Deliberately NOT placeholder text - placeholder
    text disappears the moment someone starts typing, which is exactly when
    this matters most."""
    guidance = _t(
        db, 'ui_comment_guidance', locale,
        "Optional. A specific example or two, positive or negative, is more useful than a full "
        "account, and keeps your feedback harder to trace back to you."
    )
    st.markdown(f"""
    <p style="margin-top: 0.3rem; margin-bottom: 1rem; color: #777; font-size: 0.82rem;">
        {guidance}
    </p>
    """, unsafe_allow_html=True)


def _active_locale(rater_info):
    """The rater's effective locale for this render.

    A locale just picked in THIS run lives in st.session_state (see
    render_locale_picker) and takes priority; otherwise raters.locale from the
    database is authoritative - it's what a returning rater's fresh
    get_rater_by_token() lookup already carries, so the picker correctly never
    re-appears for them.
    """
    return st.session_state.get('rater_locale') or rater_info.get('locale')


def render_locale_picker(db, rater_info):
    """One-time language choice, shown before any survey content whenever the
    rater has no locale on file yet (raters.locale IS NULL and nothing has
    been picked in this session either).

    This screen's own copy is deliberately NOT run through get_translation -
    there is no locale to translate it into until the rater has made a
    choice - so it stays English plus each option's own native-script name,
    which every rater can recognise regardless of what they read.
    """
    leader_name = rater_info['leader_name']
    relationship = rater_info['relationship']
    is_self = relationship == 'Self'

    logo_uri = get_logo_data_uri()
    logo_html = f'<img src="{logo_uri}" class="feedback-header-logo">' if logo_uri else ''
    st.markdown(f"""
    <div class="feedback-header">
        {logo_html}
        <h1 class="feedback-header-title" style="font-size: 1.8rem; margin-bottom: 0.3rem;">BENTLEY COMPASS 360</h1>
        <p style="font-size: 1.1rem; opacity: 0.9; margin: 0;">
            {'Self-Assessment' if is_self else f'Feedback for <strong>{leader_name}</strong>'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background: white; padding: 1.2rem; border-radius: 8px; margin: 1.5rem 0; border: 1px solid #E0E0E0; border-left: 4px solid #183319;">
        <p style="margin: 0; color: #333; line-height: 1.6;">
            <strong>Choose your language</strong><br>
            Select the language you would like to use to complete this form. You will only be
            asked once, so please choose the language you are most comfortable reading and
            writing in.
        </p>
    </div>
    """, unsafe_allow_html=True)

    codes = list(SUPPORTED_LOCALES.keys())
    labels = list(SUPPORTED_LOCALES.values())
    default_index = codes.index('en')

    choice_label = st.radio(
        "Language",
        options=labels,
        index=default_index,
        label_visibility="collapsed",
        key="locale_picker_choice",
    )

    if st.button("Continue", type="primary", icon=":material/arrow_forward:", use_container_width=True):
        code = codes[labels.index(choice_label)]
        db.set_rater_locale(rater_info['id'], code)
        st.session_state['rater_locale'] = code
        st.rerun()


def render_consent_gate(db, rater_info, locale):
    """One-time data-protection consent screen, shown after locale selection
    and before any survey content, until the rater has given consent
    (raters.consent_given is set either on their row already or, on the run
    they just gave it, in session_state) - same durability pattern as
    render_locale_picker above. Ticking the box is a distinct, deliberate
    action: the checkbox and the Continue button are separate controls, and
    Continue stays disabled until the box is ticked, so consent can't be
    given by clicking through without reading.

    Unlike the locale picker, this screen renders after a locale has already
    been chosen, so its copy - and an Arabic layout - go through the normal
    translation/RTL machinery rather than staying English-only by design.

    Self gets genuinely different copy (ui_consent_self_body_*), not a
    reworded version of the rater copy (ui_consent_rater_body_*): nothing is
    anonymised for a self-assessment, there's no threshold, and no one to
    hide from but the leader themself. See the consent copy addendum
    (2026-08-21) for why these were split - the original single shared
    version read as if scores/anonymity applied to Self too.
    """
    leader_name = rater_info['leader_name']
    is_self = rater_info['relationship'] == 'Self'
    is_rtl = locale in RTL_LOCALES

    with st.container(key="compass_consent_gate"):
        if is_rtl:
            st.markdown("""
            <style>
            div[class*="st-key-compass_consent_gate"] {
                direction: rtl; text-align: right;
            }
            div[class*="st-key-compass_consent_gate"] p {
                unicode-bidi: plaintext;
            }
            </style>
            """, unsafe_allow_html=True)

        logo_uri = get_logo_data_uri()
        logo_html = f'<img src="{logo_uri}" class="feedback-header-logo">' if logo_uri else ''
        st.markdown(f"""
        <div class="feedback-header">
            {logo_html}
            <h1 class="feedback-header-title" style="font-size: 1.8rem; margin-bottom: 0.3rem;">BENTLEY COMPASS 360</h1>
        </div>
        """, unsafe_allow_html=True)

        heading = _t(db, 'ui_consent_heading', locale, "Before you begin")

        if is_self:
            bullets = [
                _t(
                    db, 'ui_consent_self_body_1', locale,
                    "This is your own reflection, not anonymous feedback, so nothing here is "
                    "hidden from you. Your responses form your Self-Assessment report, which is "
                    "the basis for your first coaching conversation."
                ),
                _t(
                    db, 'ui_consent_self_body_2', locale,
                    "Only you, the programme administrator, and your coach can see this, unless "
                    "you choose to share it further once you have your report."
                ),
                _t(
                    db, 'ui_consent_self_body_3', locale,
                    "Any comments you write appear in your own report exactly as you've written "
                    "them, and your development priorities carry forward to be compared against "
                    "what your raters say later."
                ),
            ]
        else:
            bullets = [
                _t(
                    db, 'ui_consent_rater_body_1', locale,
                    "Your individual scores are never shown to {leader_name} alone - they're only "
                    "ever shown combined with others in your category, once enough people have "
                    "responded."
                ).format(leader_name=leader_name),
                _t(
                    db, 'ui_consent_rater_body_2', locale,
                    "Your written comments are shown to {leader_name}, grouped with others' in the "
                    "same category, word-for-word. Your name is never attributed to your comments. "
                    "In fact, your name and email are scrubbed from the system as soon as you "
                    "submit your responses."
                ).format(leader_name=leader_name),
                _t(
                    db, 'ui_consent_rater_body_3', locale,
                    "Please note: comments aren't protected by the anonymity threshold the way "
                    "scores are, so anything specific or identifying you write may be recognisable, "
                    "even if your scores aren't."
                ),
                _t(
                    db, 'ui_consent_rater_body_4', locale,
                    "Beyond {leader_name}, only the programme administrator and their coach can see "
                    "this feedback, unless {leader_name} chooses to share the report with others "
                    "once they receive it."
                ).format(leader_name=leader_name),
            ]

        # Softened 2026-08-23: the literal "[Retention statement to be
        # confirmed]" read as a bug during real GM self-assessment testing.
        # Still a placeholder pending the actual DPA-informed decision - see
        # the outstanding-work note in CLAUDE.md - just one that doesn't
        # look broken while it's pending.
        retention_note = _t(
            db, 'ui_consent_retention', locale,
            "We're still finalising our data retention timeline with Bentley."
        )

        bullets_html = "\n".join(f"<li>{b}</li>" for b in bullets)
        st.markdown(f"""
        <div style="background: white; padding: 1.2rem; border-radius: 8px; margin: 1.5rem 0; border: 1px solid #E0E0E0; border-left: 4px solid #183319;">
            <p style="margin: 0 0 0.8rem 0; color: #183319; font-weight: 600; font-size: 1.1rem;">{heading}</p>
            <ul style="margin: 0; padding-left: 1.2rem; color: #333; line-height: 1.7;">
                {bullets_html}
            </ul>
            <p style="margin: 0.9rem 0 0 0; color: #B45309; font-style: italic; font-size: 0.85rem;">
                {retention_note}
            </p>
        </div>
        """, unsafe_allow_html=True)

        checkbox_label = _t(
            db, 'ui_consent_checkbox_label', locale,
            "I understand how my feedback will be used and stored."
        )
        consented = st.checkbox(checkbox_label, value=False, key="consent_checkbox")

        if st.button(
            _t(db, 'ui_button_continue', locale, "Continue"),
            type="primary", icon=":material/arrow_forward:", use_container_width=True,
            disabled=not consented,
        ):
            db.set_rater_consent(rater_info['id'])
            st.session_state['rater_consent_given'] = True
            st.rerun()


def _render_rtl_css(locale):
    """RTL layout for Arabic - scoped to the form content area only. Numbers,
    Q-numbering, and the 1-5 rating scale are force-kept LTR per the i18n
    build instructions (section 5): mirroring those would misread as
    different numbers, not just flip direction. Every page (including Review)
    wraps its content in st.form specifically so this selector always has
    something to match, regardless of which page is showing.

    div[class*="st-key-item_box_"] span:first-child covers the LIVE dimension
    page's Q-number. Re-verified 2026-08-14 during a post-pagination RTL
    audit: the dimension page's per-item markup moved from a .item-container
    div to this st.container(key=...) wrapper during the same session's
    Heritage-White formatting pass, and this selector was never updated to
    follow it - so the Q-number silently stopped being forced LTR on that
    page type specifically (confirmed via computed style: direction was
    rtl/unicode-bidi normal before this fix, on Q1 of a live Arabic-locale
    dimension page). The Review page's own .review-item-question selector
    was unaffected, since that markup wasn't touched by the same rename.

    unicode-bidi: plaintext on every <p> - found 2026-08-14 (same audit):
    with zero real translations shipped yet, every paragraph inside this
    RTL-direction container is still plain English (LTR-script) text, and a
    forced `direction: rtl` on the ancestor visually relocates trailing
    punctuation to the paragraph's start - "Check everything below before
    submitting. You can still change anything." rendered as ".Check
    everything... anything" (period moved to the front, none at the end).
    The underlying text was never wrong (confirmed via textContent), only
    its bidi-resolved visual order. `unicode-bidi: plaintext` tells the
    browser to derive EACH paragraph's own base direction from its actual
    first strong character, rather than inheriting the forced direction -
    so English fallback text (first char is Latin) correctly lays out LTR
    with punctuation in the expected place, and the SAME rule will correctly
    switch a paragraph to RTL on its own once real Arabic text is dropped
    in later, with no further code change needed either way. Does not
    affect the explicitly-forced-LTR spans above (Q-numbers, rating scale),
    which set direction/unicode-bidi more specifically on themselves.

    Same plaintext fix on textarea - the comment boxes' PLACEHOLDER text
    showed the identical trailing-punctuation-jumps-to-the-front symptom
    ("Describe the leadership qualities...effective..." rendered as
    "...Describe...effective"), confirmed via computed style: the textarea
    inherits direction: rtl same as everything else. Applying the same rule
    here also correctly handles whatever a rater actually TYPES into the
    box later, English or Arabic, not just the placeholder.

    THE PLACEHOLDER NEEDED ITS OWN RULE, and this is the one place plaintext
    on the host element wasn't enough: getComputedStyle(textarea, '::placeholder')
    showed unicode-bidi: isolate, direction: rtl - the ::placeholder
    pseudo-element does not inherit unicode-bidi from the textarea it
    belongs to, so the placeholder kept the bug even after the textarea
    itself was fixed. Found by checking computed style directly rather than
    assuming the textarea rule would cover it."""
    if locale in RTL_LOCALES:
        st.markdown("""
        <style>
        div[data-testid="stForm"] { direction: rtl; text-align: right; }
        div[data-testid="stForm"] p,
        div[data-testid="stForm"] textarea {
            unicode-bidi: plaintext;
        }
        div[data-testid="stForm"] textarea::placeholder {
            unicode-bidi: plaintext;
        }
        div[data-testid="stForm"] .item-container span:first-child,
        div[data-testid="stForm"] .review-item-question span:first-child,
        div[data-testid="stForm"] div[class*="st-key-item_box_"] span:first-child {
            direction: ltr; unicode-bidi: embed; display: inline-block;
        }
        div[data-testid="stForm"] [data-testid="stButtonGroup"] {
            direction: ltr;
        }
        </style>
        """, unsafe_allow_html=True)


def _render_header(db, locale, rater_info, is_self, leader_name, relationship, show_instructions):
    """Branded header, shown on every page. The long instructional paragraph
    block only renders when show_instructions is True (the first page of a
    session) - repeating a wall of text on every one of 9+ page transitions
    would be worse than showing it once up front."""
    logo_uri = get_logo_data_uri()
    logo_html = f'<img src="{logo_uri}" class="feedback-header-logo">' if logo_uri else ''
    self_label = _t(db, 'ui_header_self_label', locale, 'Self-Assessment')
    # leader_name is bolded BEFORE interpolation, not searched-and-replaced
    # afterwards, so the markup travels with the {leader_name} placeholder
    # wherever a translation puts it, rather than relying on the translated
    # sentence containing the exact same substring the fallback does.
    feedback_for_label = _t(db, 'ui_header_feedback_for', locale, 'Feedback for {leader_name}').format(leader_name=f"<strong>{leader_name}</strong>")
    relationship_label = _t(db, f'ui_relationship_{relationship.lower()}', locale, GROUP_DISPLAY.get(relationship, relationship))
    providing_as_label = _t(db, 'ui_header_providing_as', locale, 'Providing feedback as: {relationship}').format(relationship=relationship_label)
    st.markdown(f"""
    <div class="feedback-header">
        {logo_html}
        <h1 class="feedback-header-title" style="font-size: 1.8rem; margin-bottom: 0.3rem;">BENTLEY COMPASS 360</h1>
        <p style="font-size: 1.1rem; opacity: 0.9; margin: 0;">
            {self_label if is_self else feedback_for_label}
        </p>
        <p style="font-size: 0.9rem; opacity: 0.7; margin-top: 0.5rem;">
            {providing_as_label if not is_self else 'Bentley Compass Leadership Programme'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    if not show_instructions:
        return

    if is_self:
        instructions_self = _t(
            db, 'ui_instructions_self', locale,
            "<strong>About this self-assessment</strong><br>"
            "Please rate yourself honestly on each statement below. Your self-assessment will be compared "
            "with feedback from others to identify areas of alignment and potential blind spots. "
            "There are no right or wrong answers – the value comes from honest reflection."
        )
        instructions_self_2 = _t(
            db, 'ui_instructions_self_2', locale,
            "Rate how often you demonstrate each behaviour. If you have not had an opportunity to "
            "demonstrate it in your current role, please choose <strong>\"No opportunity to demonstrate\"</strong> "
            "rather than guessing."
        )
        st.markdown(f"""
        <div style="background: white; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; border: 1px solid #E0E0E0; border-left: 4px solid #183319;">
            <p style="margin: 0; color: #333; line-height: 1.6;">
                {instructions_self}
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                {instructions_self_2}
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        instructions_other = [
            _t(db, 'ui_instructions_other_1', locale,
               "Thank you for taking the time to complete this questionnaire. The results will be shared with "
               "{leader_name} as part of the Bentley Compass Leadership Development Programme."
               ).format(leader_name=f"<strong>{leader_name}</strong>"),
            _t(db, 'ui_instructions_other_2', locale,
               "This 360 feedback instrument provides leaders with a rounded view of their leadership effectiveness, "
               "covering both functional leadership competencies and behavioural self-awareness."),
            _t(db, 'ui_instructions_other_3', locale,
               "Please take some time to complete this form, and note that all responses will be treated with "
               "complete confidentiality. If you are part of a group response to this questionnaire, your individual "
               "answers will be aggregated into overall scores and will not be individually identifiable."),
            # These two keep their emphasis inline (as the original did) rather
            # than bolding the whole sentence, so the fallback renders pixel-
            # identical to today. A translator needs to keep the <strong> tags
            # in place around the equivalent clause - flagged as a rough edge
            # of this foundation pass, not solved generally here.
            #
            # Deliberately says "labelled", not "anonymised" (changed
            # 2026-08-21): "anonymised" overclaimed protection this line never
            # actually provided - only the LABEL is anonymised (group name
            # instead of a person's name), never the CONTENT of what's
            # written. Read next to the new consent-gate warning that
            # comments "aren't protected the way scores are" and "may be
            # recognisable", the old wording read as a flat contradiction
            # rather than the same fact stated twice. See ui_consent_comments_warning.
            _t(db, 'ui_instructions_other_4', locale,
               "Any comments you make will be labelled with the group you respond from, not your name – "
               "<strong>unless you are the direct line manager of the individual.</strong>"),
            _t(db, 'ui_instructions_other_5', locale,
               "Rate how often you have observed each behaviour. If you have not had an opportunity to "
               "observe someone behaving in that way, please choose <strong>\"No opportunity to observe\"</strong> "
               "rather than guessing."),
            _t(db, 'ui_instructions_other_6', locale,
               "Each page saves as you go. You can close this window at any time "
               "and return to this link to continue where you left off."),
        ]
        st.markdown(f"""
        <div style="background: white; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; border: 1px solid #E0E0E0; border-left: 4px solid #183319;">
            <p style="margin: 0; color: #333; line-height: 1.6;">
                {instructions_other[0]}
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                {instructions_other[1]}
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                {instructions_other[2]}
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                {instructions_other[3]}
            </p>
            <p style="margin: 1rem 0 0 0; color: #333; line-height: 1.6;">
                {instructions_other[4]}
            </p>
            <p style="margin: 1rem 0 0 0; color: #183319; line-height: 1.6;">
                <strong>{instructions_other[5]}</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)


def _render_progress_bar(db, locale, draft_ratings):
    """Single progress readout per page (not once per item, as the old
    one-page form had it repeated 45 times). Shown as a plain percentage
    rather than "X of 45": a number plus a bare "%" needs no natural-language
    wrapper (no "of" to translate), so it reads correctly regardless of
    locale with zero translation dependency - the human's own reasoning for
    the change, and it holds up: unlike every other string in this form, this
    one doesn't need a string_key at all."""
    answered = _count_answered_ratings(draft_ratings)
    pct = answered / TOTAL_ITEMS * 100
    st.markdown(f"""
    <div class="item-progress" style="margin: 0 0 1.5rem 0;">
        <div class="item-progress-track">
            <div class="item-progress-fill" style="width: {pct:.1f}%;"></div>
        </div>
        <span class="item-progress-text">{pct:.0f}%</span>
    </div>
    """, unsafe_allow_html=True)


def _advance_from(current_idx, pages):
    """Move to the next page after successfully completing current_idx -
    unless the rater arrived here via an Edit link from the Review page, in
    which case they go straight back to Review instead of walking through
    every subsequent page again (Review is always the last page in `pages`,
    by construction of _build_pages)."""
    if st.session_state.get('return_to_review'):
        st.session_state['return_to_review'] = False
        st.session_state.form_page_idx = len(pages) - 1
    else:
        st.session_state.form_page_idx = current_idx + 1
    st.rerun()


def _render_dimension_page(db, rater_info, dim_name, page_idx, pages, locale, is_self, relationship,
                            leader_name, rater_id, has_draft, draft_ratings, draft_comments,
                            scale_labels_by_code, scale_options_localized, scale_label_to_value_localized):
    start, end = DIMENSIONS[dim_name]
    slug = dimension_slug(dim_name)
    dim_display_name = _t(db, f'dimension_{slug}_name', locale, dim_name)
    dim_display_desc = _t(db, f'dimension_{slug}_desc', locale, DIMENSION_DESCRIPTIONS[dim_name])

    with st.container(key="compass_survey_form"), st.form("feedback_form_page"):
        st.markdown(f'<div class="dimension-header">{dim_display_name}</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <p style="color: #4D4D4D; font-size: 0.95rem; margin-bottom: 1rem; font-style: italic;">
            {dim_display_desc}
        </p>
        """, unsafe_allow_html=True)

        for item_num in range(start, end + 1):
            fallback_item_text = get_item_text(item_num, relationship)
            item_key = f"item_{item_num}_{'self' if relationship == 'Self' else 'other'}"
            item_text = _t(db, item_key, locale, fallback_item_text)

            with st.container(key=f"item_box_{item_num}"):
                st.markdown(f"""
                <span style="color: #999; font-size: 0.85rem;">Q{item_num}.</span>
                <span class="item-text">{item_text}</span>
                """, unsafe_allow_html=True)

                default_label = None
                if has_draft and draft_ratings and item_num in draft_ratings:
                    try:
                        default_label = scale_labels_by_code.get(int(draft_ratings[item_num]))
                    except (TypeError, ValueError):
                        default_label = None

                st.segmented_control(
                    f"Rating for Q{item_num}",
                    options=scale_options_localized,
                    default=default_label,
                    key=f"rating_{item_num}",
                    label_visibility="collapsed"
                )

        # Merged 2026-08-21: the prompt (whether to comment) and the guidance
        # (keep it brief and specific) used to be two separate lines - the
        # question above the box, the brevity/anonymity advice below it. That
        # split made "Optional" read as if it only qualified the second
        # sentence, not the whole box. Self and rater versions differ for
        # real reasons, not just pronoun-swapping: a self-assessment comment
        # has no one to trace it back to, so the trace-back clause is dropped
        # entirely rather than reworded.
        #
        # Trade-off, not an oversight: this guidance is now only visible
        # BEFORE typing starts, not while composing - the old below-the-box
        # line stayed in view once the placeholder text had disappeared.
        if is_self:
            comment_prompt = _t(
                db, 'ui_comment_prompt_self', locale,
                "Optional: any specific comments about yourself regarding {dimension}? A specific "
                "example or two, positive or negative, is more useful than a full account."
            ).format(dimension=dim_display_name)
        else:
            comment_prompt = _t(
                db, 'ui_comment_prompt_rater', locale,
                "Optional: any specific comments about them regarding {dimension}? A specific "
                "example or two, positive or negative, is more useful than a full account, and "
                "keeps your feedback harder to trace back to you."
            ).format(dimension=dim_display_name)
        st.markdown(f"""
        <p style="margin-top: 1rem; margin-bottom: 0.5rem; color: #555; font-size: 0.9rem;">
            <em>{comment_prompt}</em>
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
            placeholder=_t(db, 'ui_dimension_comment_placeholder', locale, "Share specific examples or observations...")
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_save, col_continue = st.columns(2)
        with col_save:
            save_clicked = st.form_submit_button(
                _t(db, 'ui_button_save', locale, "Save & Continue Later"),
                icon=":material/save:", use_container_width=True
            )
        with col_continue:
            continue_clicked = st.form_submit_button(
                _t(db, 'ui_button_continue', locale, "Continue"),
                icon=":material/arrow_forward:", use_container_width=True, type="primary"
            )

    if save_clicked:
        ratings, comments = _collect_current_answers(
            label_to_value=scale_label_to_value_localized,
            base_ratings=draft_ratings, base_comments=draft_comments
        )
        try:
            db.save_draft(rater_id, ratings, comments)
            pct = len(ratings) / TOTAL_ITEMS * 100
            st.success(
                _t(db, 'ui_save_success', locale,
                   "**Progress saved!** ({pct:.0f}% complete)\n\n"
                   "You can safely close this window. When you're ready to continue, "
                   "just use the same link — your answers will be waiting for you."
                   ).format(pct=pct),
                icon=":material/check_circle:"
            )
        except Exception as e:
            st.error(_t(db, 'ui_save_error_prefix', locale, "Could not save progress: {detail}").format(detail=str(e)))

    if continue_clicked:
        ratings, comments = _collect_current_answers(
            label_to_value=scale_label_to_value_localized,
            base_ratings=draft_ratings, base_comments=draft_comments
        )
        missing = [n for n in range(start, end + 1) if n not in ratings or ratings[n] == ""]
        if missing:
            missing_list = ', '.join(f"Q{n}" for n in missing)
            st.error(
                _t(db, 'ui_error_dimension_incomplete', locale,
                   "Please rate all {total} items on this page before continuing. Missing: {missing_list}"
                   ).format(total=(end - start + 1), missing_list=missing_list)
            )
        else:
            try:
                db.save_draft(rater_id, ratings, comments)
            except Exception:
                pass
            _advance_from(page_idx, pages)


def _render_overall_page(db, rater_info, page_idx, pages, locale, is_self, relationship, rater_id,
                          has_draft, draft_ratings, draft_comments, scale_label_to_value_localized):
    keep_form = 'self' if is_self else 'other'

    with st.container(key="compass_survey_form"), st.form("feedback_form_page"):
        header = _t(db, 'ui_overall_feedback_header', locale, "Overall Feedback")
        st.markdown(f'<div class="dimension-header">{header}</div>', unsafe_allow_html=True)

        keep_prompt = _t(db, f'prompt_keep_{keep_form}', locale, get_prompt_text('keep', relationship))
        st.markdown(f"""
        <p style="margin-top: 1rem; margin-bottom: 0.5rem; color: #333;">
            <strong>{keep_prompt}</strong>
        </p>
        """, unsafe_allow_html=True)
        default_keep = draft_comments.get('keep', '') if (has_draft and draft_comments) else ''
        st.text_area(
            "Keep doing", value=default_keep, key="comment_keep", height=100,
            label_visibility="collapsed",
            placeholder=_t(db, 'ui_keep_placeholder', locale, "Describe the leadership qualities and behaviours that are most effective...")
        )
        _render_comment_guidance(db, locale)

        change_prompt = _t(db, f'prompt_change_{keep_form}', locale, get_prompt_text('change', relationship))
        st.markdown(f"""
        <p style="margin-top: 1.5rem; margin-bottom: 0.5rem; color: #333;">
            <strong>{change_prompt}</strong>
        </p>
        """, unsafe_allow_html=True)
        default_change = draft_comments.get('change', '') if (has_draft and draft_comments) else ''
        st.text_area(
            "One change", value=default_change, key="comment_change", height=100,
            label_visibility="collapsed",
            placeholder=_t(db, 'ui_change_placeholder', locale, "Suggest the one change that would make the biggest difference...")
        )
        _render_comment_guidance(db, locale)

        st.markdown("<br>", unsafe_allow_html=True)
        col_save, col_continue = st.columns(2)
        with col_save:
            save_clicked = st.form_submit_button(
                _t(db, 'ui_button_save', locale, "Save & Continue Later"),
                icon=":material/save:", use_container_width=True
            )
        with col_continue:
            continue_clicked = st.form_submit_button(
                _t(db, 'ui_button_continue', locale, "Continue"),
                icon=":material/arrow_forward:", use_container_width=True, type="primary"
            )

    # Both keep/change are optional today (no validation existed for them
    # before this redesign either), so Continue never blocks here.
    if save_clicked or continue_clicked:
        ratings, comments = _collect_current_answers(
            label_to_value=scale_label_to_value_localized,
            base_ratings=draft_ratings, base_comments=draft_comments
        )
        try:
            db.save_draft(rater_id, ratings, comments)
        except Exception as e:
            if save_clicked:
                st.error(_t(db, 'ui_save_error_prefix', locale, "Could not save progress: {detail}").format(detail=str(e)))

    if save_clicked:
        pct = len(ratings) / TOTAL_ITEMS * 100
        st.success(
            _t(db, 'ui_save_success', locale,
               "**Progress saved!** ({pct:.0f}% complete)\n\n"
               "You can safely close this window. When you're ready to continue, "
               "just use the same link — your answers will be waiting for you."
               ).format(pct=pct),
            icon=":material/check_circle:"
        )
    elif continue_clicked:
        _advance_from(page_idx, pages)


def _render_priorities_page(db, rater_info, page_idx, pages, locale, rater_id,
                             draft_ratings, draft_comments, scale_label_to_value_localized):
    leader_id = rater_info['leader_id']
    header = _t(db, 'ui_priorities_header', locale, "Your Development Priorities")

    with st.container(key="compass_survey_form"), st.form("feedback_form_page"):
        st.markdown(f'<div class="dimension-header">{header}</div>', unsafe_allow_html=True)

        priorities_intro = _t(db, 'ui_priorities_intro', locale, DEVELOPMENT_PRIORITY_INTRO)
        st.markdown(f"""
        <p style="margin-top: 1rem; margin-bottom: 1rem; color: #333; line-height: 1.6;">
            {priorities_intro}
        </p>
        """, unsafe_allow_html=True)

        existing_priorities = db.get_development_priorities(leader_id)
        by_rank = {p['rank']: p for p in existing_priorities}

        dimension_options = [""] + list(DIMENSIONS.keys())
        select_placeholder = _t(db, 'ui_priority_select_placeholder', locale, "Select a dimension...")
        priority_optional_note = _t(
            db, 'ui_priority_optional_note', locale,
            "(optional, but if you choose a dimension please say what you'll do)"
        )
        priority_label_template = _t(db, 'ui_priority_label', locale, "Priority {rank}")

        for rank in range(1, DEVELOPMENT_PRIORITY_COUNT + 1):
            saved = by_rank.get(rank, {})

            required_label = (
                ' <span style="color: #C00000;">*</span>'
                if rank <= DEVELOPMENT_PRIORITY_MINIMUM
                else f' <span style="color: #595959; font-weight: 400;">{priority_optional_note}</span>'
            )
            st.markdown(f"""
            <p style="margin-top: 1.2rem; margin-bottom: 0.3rem; color: #183319; font-weight: 600;">
                {priority_label_template.format(rank=rank)}{required_label}
            </p>
            """, unsafe_allow_html=True)

            default_idx = 0
            if saved.get('dimension') in dimension_options:
                default_idx = dimension_options.index(saved['dimension'])

            st.selectbox(
                f"Dimension for priority {rank}",
                options=dimension_options,
                index=default_idx,
                format_func=lambda x: (
                    _t(db, f'dimension_{dimension_slug(x)}_name', locale, x) if x else select_placeholder
                ),
                key=f"priority_dim_{rank}",
                label_visibility="collapsed"
            )

            st.text_area(
                f"Actions for priority {rank}",
                value=saved.get('actions', ''),
                key=f"priority_actions_{rank}",
                height=80,
                label_visibility="collapsed",
                placeholder=_t(db, 'ui_priority_actions_placeholder', locale, "Be specific: which behaviours, and what will you do differently?")
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_save, col_continue = st.columns(2)
        with col_save:
            save_clicked = st.form_submit_button(
                _t(db, 'ui_button_save', locale, "Save & Continue Later"),
                icon=":material/save:", use_container_width=True
            )
        with col_continue:
            continue_clicked = st.form_submit_button(
                _t(db, 'ui_button_continue', locale, "Continue"),
                icon=":material/arrow_forward:", use_container_width=True, type="primary"
            )

    if save_clicked:
        priorities = _collect_priorities()
        try:
            db.save_development_priorities(leader_id, priorities)
            ratings, comments = _collect_current_answers(
                label_to_value=scale_label_to_value_localized,
                base_ratings=draft_ratings, base_comments=draft_comments
            )
            db.save_draft(rater_id, ratings, comments)
            pct = len(ratings) / TOTAL_ITEMS * 100
            st.success(
                _t(db, 'ui_save_success', locale,
                   "**Progress saved!** ({pct:.0f}% complete)\n\n"
                   "You can safely close this window. When you're ready to continue, "
                   "just use the same link — your answers will be waiting for you."
                   ).format(pct=pct),
                icon=":material/check_circle:"
            )
        except Exception as e:
            st.error(_t(db, 'ui_save_error_prefix', locale, "Could not save progress: {detail}").format(detail=str(e)))

    if continue_clicked:
        priorities = _collect_priorities()
        duplicate_dims = _duplicate_priority_dimensions(priorities)
        chosen_priorities = [p for p in priorities if p.get('dimension')]
        too_few_priorities = len(chosen_priorities) < DEVELOPMENT_PRIORITY_MINIMUM
        priorities_without_actions = _priorities_missing_actions(priorities)

        if too_few_priorities:
            try:
                db.save_development_priorities(leader_id, priorities)
            except Exception:
                pass
            st.error(
                _t(db, 'ui_error_too_few_priorities', locale,
                   "Please choose at least one development priority before "
                   "continuing. Pick the dimension you most want to work on and "
                   "say what you intend to do differently. If it helps, build on "
                   "what you wrote in the closing questions above.")
            )
        elif duplicate_dims:
            try:
                db.save_development_priorities(leader_id, priorities)
            except Exception:
                pass
            duplicate_list = ', '.join(
                _t(db, f'dimension_{dimension_slug(d)}_name', locale, d) for d in duplicate_dims
            )
            st.error(
                _t(db, 'ui_error_duplicate_priorities', locale,
                   "Please choose a different dimension for each development "
                   "priority. Currently chosen more than once: {duplicate_list}."
                   ).format(duplicate_list=duplicate_list)
            )
        elif priorities_without_actions:
            try:
                db.save_development_priorities(leader_id, priorities)
            except Exception:
                pass
            ranks = ', '.join(str(r) for r in priorities_without_actions)
            plural = 'ies' if len(priorities_without_actions) > 1 else 'y'
            st.error(
                _t(db, 'ui_error_priorities_missing_actions', locale,
                   "Please say what you intend to do for each priority you've "
                   "chosen. Missing specifics for Priorit{plural} {ranks}.\n\n"
                   "Name the behaviours you want to change and the actions you'll "
                   "take. If you'd rather not commit to one of these areas yet, "
                   "set its dimension back to \"{select_placeholder}\"."
                   ).format(plural=plural, ranks=ranks, select_placeholder=select_placeholder)
            )
        else:
            try:
                db.save_development_priorities(leader_id, priorities)
            except Exception:
                pass
            _advance_from(page_idx, pages)


def _render_review_page(db, rater_info, pages, locale, is_self, relationship, leader_name, rater_id,
                         draft_ratings, draft_comments, scale_labels_by_code, scale_label_to_value_localized):
    """Review page. Deliberately does NOT read item ratings, dimension
    comments, or keep/change straight from st.session_state per field the way
    every other page can - by the time a rater reaches Review they've been
    through several OTHER pages since those widgets last rendered, and
    st.session_state does not reliably keep a widget's value once it stops
    being instantiated (confirmed empirically - see _collect_current_answers).
    Instead this reads the one MERGED ratings/comments dict (session_state
    layered on top of the draft already loaded at the top of the render) and
    priorities freshly from the database, where the Priorities page already
    persists them independently of session_state.
    """
    review_heading = _t(db, 'ui_review_heading', locale, "Review Your Answers")
    review_intro = _t(db, 'ui_review_intro', locale, "Check everything below before submitting. You can still change anything.")
    edit_label = _t(db, 'ui_review_edit_button', locale, "Edit")
    submit_all_label = _t(db, 'ui_button_submit_all', locale, "Submit All Ratings")

    ratings, comments = _collect_current_answers(
        label_to_value=scale_label_to_value_localized,
        base_ratings=draft_ratings, base_comments=draft_comments
    )
    priorities = db.get_development_priorities(rater_info['leader_id']) if is_self else []
    priorities_by_rank = {p['rank']: p for p in priorities}

    edit_clicked = {}

    with st.container(key="compass_survey_form"), st.form("feedback_form_page"):
        st.markdown(f'<div class="dimension-header">{review_heading}</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <p style="color: #4D4D4D; font-size: 0.95rem; margin-bottom: 1.5rem; font-style: italic;">
            {review_intro}
        </p>
        """, unsafe_allow_html=True)

        for page_idx, (page_type, page_arg) in enumerate(pages[:-1]):
            if page_type == 'dimension':
                dim_name = page_arg
                slug = dimension_slug(dim_name)
                dim_display_name = _t(db, f'dimension_{slug}_name', locale, dim_name)
                start, end = DIMENSIONS[dim_name]

                col_h, col_e = st.columns([5, 1])
                with col_h:
                    st.markdown(f'<div class="dimension-header">{dim_display_name}</div>', unsafe_allow_html=True)
                with col_e:
                    st.markdown('<div style="height: 1.5rem;"></div>', unsafe_allow_html=True)
                    edit_clicked[page_idx] = st.form_submit_button(edit_label, key=f"edit_{page_idx}")

                for item_num in range(start, end + 1):
                    fallback_item_text = get_item_text(item_num, relationship)
                    item_key = f"item_{item_num}_{'self' if relationship == 'Self' else 'other'}"
                    item_text = _t(db, item_key, locale, fallback_item_text)
                    stored_code = ratings.get(item_num, "")
                    try:
                        rating_label = scale_labels_by_code.get(int(stored_code), "")
                    except (TypeError, ValueError):
                        rating_label = ""
                    st.markdown(f"""
                    <div class="review-item-row">
                        <div class="review-item-question">
                            <span style="color: #999; font-size: 0.85rem;">Q{item_num}.</span>
                            <span class="item-text">{item_text}</span>
                        </div>
                        <div class="review-item-rating">{rating_label}</div>
                    </div>
                    """, unsafe_allow_html=True)

                comment_val = comments.get(dim_name, "")
                if comment_val and comment_val.strip():
                    st.markdown(f"""
                    <p style="margin: 0.5rem 0 0.5rem 0; color: #555; font-style: italic;">"{comment_val}"</p>
                    """, unsafe_allow_html=True)

                st.markdown("<hr style='margin: 1.5rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)

            elif page_type == 'overall':
                col_h, col_e = st.columns([5, 1])
                with col_h:
                    header = _t(db, 'ui_overall_feedback_header', locale, "Overall Feedback")
                    st.markdown(f'<div class="dimension-header">{header}</div>', unsafe_allow_html=True)
                with col_e:
                    st.markdown('<div style="height: 1.5rem;"></div>', unsafe_allow_html=True)
                    edit_clicked[page_idx] = st.form_submit_button(edit_label, key=f"edit_{page_idx}")

                keep_val = comments.get('keep', '')
                change_val = comments.get('change', '')
                if keep_val and keep_val.strip():
                    keep_form = 'self' if is_self else 'other'
                    st.markdown(f"<p><strong>{_t(db, f'prompt_keep_{keep_form}', locale, get_prompt_text('keep', relationship))}</strong></p>", unsafe_allow_html=True)
                    st.markdown(f'<p style="font-style: italic;">"{keep_val}"</p>', unsafe_allow_html=True)
                if change_val and change_val.strip():
                    keep_form = 'self' if is_self else 'other'
                    st.markdown(f"<p><strong>{_t(db, f'prompt_change_{keep_form}', locale, get_prompt_text('change', relationship))}</strong></p>", unsafe_allow_html=True)
                    st.markdown(f'<p style="font-style: italic;">"{change_val}"</p>', unsafe_allow_html=True)

                st.markdown("<hr style='margin: 1.5rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)

            elif page_type == 'priorities':
                col_h, col_e = st.columns([5, 1])
                with col_h:
                    header = _t(db, 'ui_priorities_header', locale, "Your Development Priorities")
                    st.markdown(f'<div class="dimension-header">{header}</div>', unsafe_allow_html=True)
                with col_e:
                    st.markdown('<div style="height: 1.5rem;"></div>', unsafe_allow_html=True)
                    edit_clicked[page_idx] = st.form_submit_button(edit_label, key=f"edit_{page_idx}")

                priority_label_template = _t(db, 'ui_priority_label', locale, "Priority {rank}")
                for rank in range(1, DEVELOPMENT_PRIORITY_COUNT + 1):
                    saved = priorities_by_rank.get(rank, {})
                    dim = saved.get('dimension') or ""
                    actions = saved.get('actions') or ""
                    if not dim:
                        continue
                    dim_display = _t(db, f'dimension_{dimension_slug(dim)}_name', locale, dim)
                    st.markdown(f"""
                    <p style="margin-top: 0.8rem; margin-bottom: 0.2rem;"><strong>{priority_label_template.format(rank=rank)}: {dim_display}</strong></p>
                    <p style="font-style: italic; margin: 0;">{actions}</p>
                    """, unsafe_allow_html=True)

                st.markdown("<hr style='margin: 1.5rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        submit_all_clicked = st.form_submit_button(
            submit_all_label, icon=":material/check_circle:", use_container_width=True, type="primary"
        )

    for page_idx, clicked in edit_clicked.items():
        if clicked:
            st.session_state['return_to_review'] = True
            st.session_state.form_page_idx = page_idx
            st.rerun()

    if submit_all_clicked:
        # ratings, comments, and priorities were already computed at the top
        # of this function from reliable sources (the merged draft, and the
        # database respectively) - not re-collected from session_state here,
        # since by this point several pages' worth of widgets are no longer
        # instantiated and would read back empty.

        # Defensive final check - every section already validated itself on
        # its own Continue click, so this should never actually fire. Kept as
        # a safety net, not the primary gate, in case of any inconsistency
        # (e.g. browser back-button use) between pages.
        missing = [n for n in range(1, TOTAL_ITEMS + 1) if n not in ratings or ratings[n] == ""]
        duplicate_dims = _duplicate_priority_dimensions(priorities) if is_self else []
        chosen_priorities = [p for p in priorities if p.get('dimension')]
        too_few_priorities = is_self and len(chosen_priorities) < DEVELOPMENT_PRIORITY_MINIMUM
        priorities_without_actions = _priorities_missing_actions(priorities) if is_self else []

        if missing or duplicate_dims or too_few_priorities or priorities_without_actions:
            try:
                db.save_draft(rater_id, ratings, comments)
                if is_self:
                    db.save_development_priorities(rater_info['leader_id'], priorities)
            except Exception:
                pass
            st.error(_t(db, 'ui_error_review_incomplete', locale,
                        "Something on an earlier page needs attention before this can be submitted. "
                        "Please use Edit above to check each section."))
        else:
            processed_ratings = {n: int(v) for n, v in ratings.items() if v != ""}
            processed_comments = {k: v for k, v in comments.items() if v and v.strip()}
            try:
                if is_self:
                    db.save_development_priorities(rater_info['leader_id'], priorities)
                db.submit_feedback(rater_id, processed_ratings, processed_comments)

                # Admin milestone notifications - self-assessment completion is
                # a one-off per leader (there's no rater-facing way to resubmit;
                # app.py's routing sends a completed rater straight to the
                # thank-you page instead of back into this form), so it needs
                # no extra guard beyond "this is a Self rater". The Full 360
                # case genuinely can fire from more than one completion in
                # quick succession, so it goes through try_claim_full_360_
                # notification's atomic claim instead of a plain if-check.
                # Failures here must never surface to the rater - this is
                # purely a side effect of a successful submission that has
                # already happened.
                try:
                    if ADMIN_NOTIFICATIONS_AVAILABLE:
                        leader_id = rater_info['leader_id']
                        leader_name = rater_info['leader_name']
                        if is_self:
                            send_admin_notification(
                                subject=f"Self-Assessment Complete: {leader_name} — Bentley Compass 360",
                                leader_name=leader_name,
                                milestone_type='self_assessment_ready',
                                db=db,
                                leader_id=leader_id
                            )
                        elif db.is_full_360_report_ready(leader_id) and db.try_claim_full_360_notification(leader_id):
                            send_admin_notification(
                                subject=f"Full 360 Ready: {leader_name} — Bentley Compass 360",
                                leader_name=leader_name,
                                milestone_type='full_360_ready',
                                db=db,
                                leader_id=leader_id
                            )
                except Exception:
                    pass

                st.success(_t(db, 'ui_success_submitted', locale, "Thank you! Your feedback has been submitted successfully."))
                st.balloons()

                st.query_params["submitted"] = "true"
                st.rerun()
            except Exception as e:
                st.error(_t(db, 'ui_submit_error', locale,
                            "An error occurred while submitting your feedback. Please try again. ({detail})"
                            ).format(detail=str(e)))


def render_feedback_form(db, rater_info):
    """Render the feedback form for a rater, one page at a time."""

    # Injected before the locale/consent gates below (not after), so the
    # Bentley typeface applies to those too, not just the paginated survey
    # proper - both are reached through this same function and return early.
    st.markdown(_BENTLEY_TYPEFACE_CSS, unsafe_allow_html=True)

    # --- Locale gate: shown once, before any survey content, until the rater
    # has picked a language (raters.locale is set either on their row already
    # or, on the very run they just picked, in session_state). Returning
    # raters never see this again because get_rater_by_token() re-fetches
    # rater_info fresh on every page load, already carrying whatever they
    # chose last time.
    if rater_info.get('locale') is None and st.session_state.get('rater_locale') is None:
        render_locale_picker(db, rater_info)
        return

    locale = _active_locale(rater_info)

    # --- Consent gate: shown once, after locale selection and before any
    # survey content, until the rater has given consent. Same durability
    # pattern as the locale gate above - checked from the database on every
    # visit, not session state, so a rater who closes the tab before
    # consenting sees it again, and one who has already consented never does.
    if not rater_info.get('consent_given') and not st.session_state.get('rater_consent_given'):
        render_consent_gate(db, rater_info, locale)
        return

    leader_name = rater_info['leader_name']
    relationship = rater_info['relationship']
    is_self = relationship == 'Self'
    rater_id = rater_info['id']

    st.session_state.db = db
    st.session_state.rater_id = rater_id

    draft_ratings, draft_comments, draft_saved_at = db.get_draft(rater_id)
    has_draft = draft_ratings is not None

    pages = _build_pages(is_self)

    just_resumed = 'form_page_idx' not in st.session_state
    if just_resumed:
        st.session_state.form_page_idx = _resume_page_index(pages, draft_ratings)

    if has_draft and 'draft_loaded' not in st.session_state:
        st.session_state.draft_loaded = True
        st.session_state.draft_saved_at = draft_saved_at

    page_idx = st.session_state.form_page_idx
    page_type, page_arg = pages[page_idx]

    _render_rtl_css(locale)
    _render_header(db, locale, rater_info, is_self, leader_name, relationship, show_instructions=(page_idx == 0))

    if has_draft and draft_saved_at and just_resumed:
        st.info(
            _t(db, 'ui_resume_banner', locale,
               "**Welcome back!** Your previous answers have been restored. "
               "You can continue from where you left off."),
            icon=":material/history:"
        )

    _render_progress_bar(db, locale, draft_ratings)

    scale_labels_by_code = {
        code: _t(db, f'ui_rating_{SCALE_KEY_SUFFIX[code]}', locale, SCALE_FREQUENCY[code])
        for code in (1, 2, 3, 4, 5)
    }
    # "No opportunity to observe" doesn't fit a leader rating themselves - they
    # were there for their own behaviour, so the gap is opportunity to
    # demonstrate it, not to observe it. Self/other therefore get distinct
    # keys (and fallbacks) for this one option, unlike the other five which
    # read the same either way.
    no_opportunity_key = 'ui_rating_no_opportunity_self' if is_self else 'ui_rating_no_opportunity_other'
    no_opportunity_fallback = "No opportunity to demonstrate" if is_self else "No opportunity to observe"
    scale_labels_by_code[0] = _t(db, no_opportunity_key, locale, no_opportunity_fallback)
    scale_options_localized = [scale_labels_by_code[c] for c in (1, 2, 3, 4, 5, 0)]
    scale_label_to_value_localized = {v: str(k) for k, v in scale_labels_by_code.items()}

    if page_type == 'dimension':
        _render_dimension_page(
            db, rater_info, page_arg, page_idx, pages, locale, is_self, relationship,
            leader_name, rater_id, has_draft, draft_ratings, draft_comments,
            scale_labels_by_code, scale_options_localized, scale_label_to_value_localized
        )
    elif page_type == 'overall':
        _render_overall_page(
            db, rater_info, page_idx, pages, locale, is_self, relationship, rater_id,
            has_draft, draft_ratings, draft_comments, scale_label_to_value_localized
        )
    elif page_type == 'priorities':
        _render_priorities_page(
            db, rater_info, page_idx, pages, locale, rater_id,
            draft_ratings, draft_comments, scale_label_to_value_localized
        )
    elif page_type == 'review':
        _render_review_page(
            db, rater_info, pages, locale, is_self, relationship, leader_name, rater_id,
            draft_ratings, draft_comments, scale_labels_by_code, scale_label_to_value_localized
        )

    # --- Save-time indicator in sidebar ---
    with st.sidebar:
        if st.session_state.get('last_saved'):
            last_saved_text = _t(db, 'ui_last_saved', locale, "Last saved: {time}").format(time=st.session_state.last_saved)
            st.markdown(f"<p style='color: #999; font-size: 0.8rem;'>{last_saved_text}</p>",
                       unsafe_allow_html=True)
        elif has_draft and draft_saved_at:
            draft_from_text = _t(db, 'ui_draft_from', locale, "Draft from: {time}").format(time=str(draft_saved_at)[:16])
            st.markdown(f"<p style='color: #999; font-size: 0.8rem;'>{draft_from_text}</p>",
                       unsafe_allow_html=True)


def render_thank_you():
    """Render thank you page after submission."""
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; background: white; border-radius: 12px;
                border: 1px solid #E2E0D8; max-width: 600px; margin: 2rem auto;">
        <div style="font-size: 4rem; margin-bottom: 1rem;">✓</div>
        <h2 style="color: #183319; margin-bottom: 1rem;">Thank You</h2>
        <p style="color: #666; font-size: 1.1rem; line-height: 1.8;">
            Your feedback has been successfully submitted and will help support this leader's development.
        </p>
        <p style="color: #999; margin-top: 2rem;">
            You may now close this window.
        </p>
    </div>
    """, unsafe_allow_html=True)
