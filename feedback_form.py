#!/usr/bin/env python3
"""
Feedback form for raters in Bentley Compass 360.

Provides a clean, branded experience for submitting 360 feedback.
Supports save & resume — raters can close the browser and return later.
"""

import streamlit as st
import json
from datetime import datetime
from framework import (
    DIMENSIONS, DIMENSION_DESCRIPTIONS,
    RELATIONSHIP_TYPES, GROUP_DISPLAY,
    SCALE_FREQUENCY, OPEN_PROMPTS,
    DEVELOPMENT_PRIORITY_COUNT, DEVELOPMENT_PRIORITY_INTRO,
    DEVELOPMENT_PRIORITY_PROMPT, DEVELOPMENT_PRIORITY_MINIMUM,
    DEVELOPMENT_PRIORITY_ACTION_MIN_CHARS,
    get_item_text, get_prompt_text, get_logo_data_uri,
    SUPPORTED_LOCALES, RTL_LOCALES, dimension_slug
)

TOTAL_ITEMS = 45

# Rating scale as a single row of 6 labelled buttons (st.segmented_control),
# not a dropdown. "No opportunity to observe" is functionally a different kind
# of answer to the 5 frequency options — not a 6th point on the scale — and is
# set apart visually via CSS (see the stSegmentedControl rules in app.py), but
# it stays one widget with the other five rather than a second, separately-
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


def _count_answered_ratings(draft_ratings=None):
    """How many of the 45 items have a rating selected right now.

    A widget instantiated with only `default=` (never yet clicked by the
    rater in this browser session) doesn't reliably show up in
    st.session_state on the same run it's restored from a draft, so items
    already present in draft_ratings are counted even when the widget's own
    session_state entry is still empty.
    """
    count = 0
    for item_num in range(1, TOTAL_ITEMS + 1):
        val = st.session_state.get(f"rating_{item_num}")
        if not val and draft_ratings and item_num in draft_ratings:
            val = draft_ratings[item_num]
        if val:
            count += 1
    return count


def _collect_current_answers(label_to_value=None):
    """Gather all current ratings and comments from session state.

    label_to_value maps the CURRENTLY DISPLAYED scale label back to its
    stored code ("0"-"5"). Defaults to the English map, but every real call
    site inside render_feedback_form passes the rater's locale-aware map
    instead: once the rating scale labels are translated, the widget's stored
    value IS the translated label, and the English-only default would fail to
    find it and silently drop the rating as "" rather than raise.
    """
    label_to_value = label_to_value or SCALE_LABEL_TO_VALUE
    ratings = {}
    comments = {}

    # Ratings (Q1-Q45). The widget's own session state holds the scale label
    # text (e.g. "Often"), converted back here to the stored code ("0"-"5")
    # so the draft/submission format is exactly what it was under the old
    # selectbox — only the widget changed, not what gets saved.
    for item_num in range(1, TOTAL_ITEMS + 1):
        label = st.session_state.get(f"rating_{item_num}")
        if label:
            ratings[item_num] = label_to_value.get(label, "")

    # Dimension comments
    for dim_name in DIMENSIONS.keys():
        val = st.session_state.get(f"comment_{dim_name}", "")
        if val and val.strip():
            comments[dim_name] = val

    # Closing open prompts
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


def _t(db, key, locale, fallback):
    """Shorthand for db.get_translation - returns fallback (the current
    English string, already hardcoded at every call site) until a real
    translation row exists for `locale`. Safe to call with locale=None."""
    return db.get_translation(key, locale, fallback_text=fallback)


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
        <h1 style="font-size: 1.8rem; margin-bottom: 0.3rem;">BENTLEY COMPASS 360</h1>
        <p style="font-size: 1.1rem; opacity: 0.9; margin: 0;">
            {'Self-Assessment' if is_self else f'Feedback for <strong>{leader_name}</strong>'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background: #F8F9FA; padding: 1.2rem; border-radius: 8px; margin: 1.5rem 0; border-left: 4px solid #183319;">
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


def render_feedback_form(db, rater_info):
    """Render the feedback form for a rater."""

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
    
    # RTL layout for Arabic - scoped to the form content area only. Numbers,
    # Q-numbering, and the 1-5 rating scale are force-kept LTR per the i18n
    # build instructions (section 5): mirroring those would misread as
    # different numbers, not just flip direction.
    if locale in RTL_LOCALES:
        st.markdown("""
        <style>
        div[data-testid="stForm"] { direction: rtl; text-align: right; }
        div[data-testid="stForm"] .item-container span:first-child {
            direction: ltr; unicode-bidi: embed; display: inline-block;
        }
        div[data-testid="stForm"] [data-testid="stButtonGroup"] {
            direction: ltr;
        }
        </style>
        """, unsafe_allow_html=True)

    # Header
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
        <h1 style="font-size: 1.8rem; margin-bottom: 0.3rem;">BENTLEY COMPASS 360</h1>
        <p style="font-size: 1.1rem; opacity: 0.9; margin: 0;">
            {self_label if is_self else feedback_for_label}
        </p>
        <p style="font-size: 0.9rem; opacity: 0.7; margin-top: 0.5rem;">
            {providing_as_label if not is_self else 'Bentley Compass Leadership Programme'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Resume banner
    if has_draft and draft_saved_at:
        st.info(
            _t(db, 'ui_resume_banner', locale,
               "**Welcome back!** Your previous answers have been restored. "
               "You can continue from where you left off."),
            icon=":material/history:"
        )

    # Instructions
    if is_self:
        instructions_self = _t(
            db, 'ui_instructions_self', locale,
            "<strong>About this self-assessment</strong><br>"
            "Please rate yourself honestly on each statement below. Your self-assessment will be compared "
            "with feedback from others to identify areas of alignment and potential blind spots. "
            "There are no right or wrong answers – the value comes from honest reflection."
        )
        st.markdown(f"""
        <div style="background: #F8F9FA; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #183319;">
            <p style="margin: 0; color: #333; line-height: 1.6;">
                {instructions_self}
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
            _t(db, 'ui_instructions_other_4', locale,
               "Any comments you make will be anonymised to the group title you respond from – "
               "<strong>unless you are the direct line manager of the individual.</strong>"),
            _t(db, 'ui_instructions_other_5', locale,
               "Rate how often you have observed each behaviour. If you have not had an opportunity to "
               "observe someone behaving in that way, please choose <strong>\"No opportunity to observe\"</strong> "
               "rather than guessing."),
            _t(db, 'ui_instructions_other_6', locale,
               "Your progress is saved automatically. You can close this window at any time "
               "and return to this link to continue where you left off."),
        ]
        st.markdown(f"""
        <div style="background: #F8F9FA; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #183319;">
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

    # Rating scale labels, translated. The segmented control's stored VALUE is
    # this label text, so the reverse map back to a stored code has to use
    # these SAME translated labels too (see _collect_current_answers) - built
    # once here and reused for every item below and at both the Save and
    # Submit handlers further down.
    scale_labels_by_code = {
        code: _t(db, f'ui_rating_{SCALE_KEY_SUFFIX[code]}', locale, SCALE_FREQUENCY[code])
        for code in (1, 2, 3, 4, 5, 0)
    }
    scale_options_localized = [scale_labels_by_code[c] for c in (1, 2, 3, 4, 5, 0)]
    scale_label_to_value_localized = {v: str(k) for k, v in scale_labels_by_code.items()}

    # --- FORM (using st.form for clean submission, with draft pre-population) ---
    # Note: We use st.form for the actual widgets, but auto-save happens via
    # a separate mechanism outside the form since on_change doesn't fire inside forms.

    with st.form("feedback_form"):
        # Iterate through dimensions
        for dim_name, (start_item, end_item) in DIMENSIONS.items():
            slug = dimension_slug(dim_name)
            # dim_name itself stays the English key used for session_state,
            # draft storage, and DB lookups throughout - only the DISPLAYED
            # heading/description text is translated.
            dim_display_name = _t(db, f'dimension_{slug}_name', locale, dim_name)
            dim_display_desc = _t(db, f'dimension_{slug}_desc', locale, DIMENSION_DESCRIPTIONS[dim_name])

            st.markdown(f'<div class="dimension-header">{dim_display_name}</div>', unsafe_allow_html=True)

            st.markdown(f"""
            <p style="color: #666; font-size: 0.95rem; margin-bottom: 1rem; font-style: italic;">
                {dim_display_desc}
            </p>
            """, unsafe_allow_html=True)

            for item_num in range(start_item, end_item + 1):
                fallback_item_text = get_item_text(item_num, relationship)
                item_key = f"item_{item_num}_{'self' if relationship == 'Self' else 'other'}"
                item_text = _t(db, item_key, locale, fallback_item_text)

                st.markdown(f"""
                <div class="item-container">
                    <span style="color: #999; font-size: 0.85rem;">Q{item_num}.</span>
                    <span class="item-text">{item_text}</span>
                </div>
                """, unsafe_allow_html=True)

                # Pre-populate from draft if available. draft_ratings holds the
                # stored code ("0"-"5"); the widget itself works in label text,
                # so look up the matching (locale-aware) label to preselect.
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

                # Slim inline progress readout, replacing the old sidebar panel
                answered = _count_answered_ratings(draft_ratings)
                pct = answered / TOTAL_ITEMS * 100
                progress_text = _t(db, 'ui_progress_of', locale, "{answered} of {total}").format(
                    answered=answered, total=TOTAL_ITEMS
                )
                st.markdown(f"""
                <div class="item-progress">
                    <div class="item-progress-track">
                        <div class="item-progress-fill" style="width: {pct:.1f}%;"></div>
                    </div>
                    <span class="item-progress-text">{progress_text}</span>
                </div>
                """, unsafe_allow_html=True)

            # Comment for this dimension
            comment_prompt_key = 'ui_dimension_comment_prompt_self' if is_self else 'ui_dimension_comment_prompt_other'
            comment_prompt_fallback = (
                "Optional: Any specific comments about yourself regarding {dimension}?" if is_self
                else "Optional: Any specific comments about {leader_name} regarding {dimension}?"
            )
            comment_prompt = _t(db, comment_prompt_key, locale, comment_prompt_fallback).format(
                dimension=dim_display_name, leader_name=leader_name
            )
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
            
            st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
        
        # Overall comments — two open prompts (not scored)
        overall_feedback_header = _t(db, 'ui_overall_feedback_header', locale, "Overall Feedback")
        st.markdown(f'<div class="dimension-header">{overall_feedback_header}</div>', unsafe_allow_html=True)

        keep_form = 'self' if is_self else 'other'
        keep_prompt = _t(db, f'prompt_keep_{keep_form}', locale, get_prompt_text('keep', relationship))
        st.markdown(f"""
        <p style="margin-top: 1rem; margin-bottom: 0.5rem; color: #333;">
            <strong>{keep_prompt}</strong>
        </p>
        """, unsafe_allow_html=True)

        default_keep = ""
        if has_draft and draft_comments and 'keep' in draft_comments:
            default_keep = draft_comments['keep']

        st.text_area(
            "Keep doing",
            value=default_keep,
            key="comment_keep",
            height=100,
            label_visibility="collapsed",
            placeholder=_t(db, 'ui_keep_placeholder', locale, "Describe the leadership qualities and behaviours that are most effective...")
        )

        change_prompt = _t(db, f'prompt_change_{keep_form}', locale, get_prompt_text('change', relationship))
        st.markdown(f"""
        <p style="margin-top: 1.5rem; margin-bottom: 0.5rem; color: #333;">
            <strong>{change_prompt}</strong>
        </p>
        """, unsafe_allow_html=True)

        default_change = ""
        if has_draft and draft_comments and 'change' in draft_comments:
            default_change = draft_comments['change']

        st.text_area(
            "One change",
            value=default_change,
            key="comment_change",
            height=100,
            label_visibility="collapsed",
            placeholder=_t(db, 'ui_change_placeholder', locale, "Suggest the one change that would make the biggest difference...")
        )

        # --- Development priorities (self-assessment only) ---
        # The leader ranks up to three dimensions and names the specific
        # behaviours and actions they intend to work on within each. Raters
        # never see this: it is the leader's own development intent.
        if is_self:
            st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
            priorities_header = _t(db, 'ui_priorities_header', locale, "Your Development Priorities")
            st.markdown(f'<div class="dimension-header">{priorities_header}</div>', unsafe_allow_html=True)

            priorities_intro = _t(db, 'ui_priorities_intro', locale, DEVELOPMENT_PRIORITY_INTRO)
            st.markdown(f"""
            <p style="margin-top: 1rem; margin-bottom: 1rem; color: #333; line-height: 1.6;">
                {priorities_intro}
            </p>
            """, unsafe_allow_html=True)

            existing_priorities = db.get_development_priorities(rater_info['leader_id'])
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
                    else f' <span style="color: #999; font-weight: 400;">{priority_optional_note}</span>'
                )
                st.markdown(f"""
                <p style="margin-top: 1.2rem; margin-bottom: 0.3rem; color: #183319; font-weight: 600;">
                    {priority_label_template.format(rank=rank)}{required_label}
                </p>
                """, unsafe_allow_html=True)

                default_idx = 0
                if saved.get('dimension') in dimension_options:
                    default_idx = dimension_options.index(saved['dimension'])

                # format_func only changes what's DISPLAYED - the option VALUE
                # stored in session_state (and later saved as the priority's
                # dimension) stays the English dim_name, since that's the key
                # DIMENSIONS/report_generator.py match against elsewhere.
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

        # --- Two buttons: Save & Continue Later, and Submit ---
        col_save, col_submit = st.columns(2)
        
        with col_save:
            save_clicked = st.form_submit_button(
                _t(db, 'ui_button_save', locale, "Save & Continue Later"),
                icon=":material/save:",
                use_container_width=True
            )

        with col_submit:
            submit_clicked = st.form_submit_button(
                _t(db, 'ui_button_submit', locale, "Submit Feedback"),
                icon=":material/check_circle:",
                use_container_width=True,
                type="primary"
            )

        # --- Handle Save & Continue Later ---
        if save_clicked:
            ratings, comments = _collect_current_answers(label_to_value=scale_label_to_value_localized)
            try:
                db.save_draft(rater_id, ratings, comments)
                # Priorities live on the leader row, not in the rater draft, so
                # they are saved directly rather than through save_draft
                if is_self:
                    db.save_development_priorities(
                        rater_info['leader_id'], _collect_priorities()
                    )
                answered = len(ratings)
                total = TOTAL_ITEMS
                st.success(
                    _t(db, 'ui_save_success', locale,
                       "**Progress saved!** ({answered} of {total} items answered)\n\n"
                       "You can safely close this window. When you're ready to continue, "
                       "just use the same link — your answers will be waiting for you."
                       ).format(answered=answered, total=total),
                    icon=":material/check_circle:"
                )
            except Exception as e:
                st.error(_t(db, 'ui_save_error_prefix', locale, "Could not save progress: {detail}").format(detail=str(e)))

        # --- Handle Submit ---
        if submit_clicked:
            # Collect all answers
            ratings, comments = _collect_current_answers(label_to_value=scale_label_to_value_localized)
            priorities = _collect_priorities() if is_self else []

            # Validate - check that all items have been rated
            missing = []
            for item_num in range(1, TOTAL_ITEMS + 1):
                if item_num not in ratings or ratings[item_num] == "":
                    missing.append(item_num)

            duplicate_dims = _duplicate_priority_dimensions(priorities)
            chosen_priorities = [p for p in priorities if p.get('dimension')]
            too_few_priorities = (
                is_self and len(chosen_priorities) < DEVELOPMENT_PRIORITY_MINIMUM
            )
            priorities_without_actions = (
                _priorities_missing_actions(priorities) if is_self else []
            )

            progress_saved_note = _t(db, 'ui_note_progress_saved', locale, "Your progress has been saved — you won't lose your answers.")

            if missing:
                # Save what they have so far even though submission failed
                try:
                    db.save_draft(rater_id, ratings, comments)
                    if is_self:
                        db.save_development_priorities(rater_info['leader_id'], priorities)
                except Exception:
                    pass

                missing_list = ', '.join(f"Q{n}" for n in missing[:5]) + ('...' if len(missing) > 5 else '')
                st.error(
                    _t(db, 'ui_error_missing_items', locale,
                       "Please provide a rating for all items before submitting. "
                       "Missing: {missing_list}").format(missing_list=missing_list)
                    + "\n\n" + progress_saved_note
                )
            elif too_few_priorities:
                # The leader must commit to at least one area to work on
                try:
                    db.save_draft(rater_id, ratings, comments)
                    db.save_development_priorities(rater_info['leader_id'], priorities)
                except Exception:
                    pass

                st.error(
                    _t(db, 'ui_error_too_few_priorities', locale,
                       "Please choose at least one development priority before "
                       "submitting. Pick the dimension you most want to work on and "
                       "say what you intend to do differently. If it helps, build on "
                       "what you wrote in the closing questions above.")
                    + "\n\n" + progress_saved_note
                )
            elif duplicate_dims:
                # Ranking the same dimension twice is meaningless, so block it
                try:
                    db.save_draft(rater_id, ratings, comments)
                    db.save_development_priorities(rater_info['leader_id'], priorities)
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
                    + "\n\n" + progress_saved_note
                )
            elif priorities_without_actions:
                # A chosen dimension with no actions carries nothing into the
                # coaching conversation, so require the pair
                try:
                    db.save_draft(rater_id, ratings, comments)
                    db.save_development_priorities(rater_info['leader_id'], priorities)
                except Exception:
                    pass

                # Pluralisation ("Priority"/"Priorities") is English-specific
                # grammar - a simple suffix swap doesn't generalise to most of
                # the six target languages. Left as-is for this foundation
                # pass (no translation content is being written yet); a real
                # translator will need to restructure this sentence for their
                # language rather than translate the {plural} token literally.
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
                    + "\n\n" + progress_saved_note
                )
            else:
                # Process ratings for final submission — values are "0" (no
                # opportunity to observe) through "5" on the frequency scale
                processed_ratings = {}
                for item_num, rating in ratings.items():
                    if rating != "":
                        processed_ratings[item_num] = int(rating)
                
                # Process comments
                processed_comments = {k: v for k, v in comments.items() if v and v.strip()}
                
                # Submit to database (this also clears the draft)
                try:
                    # Priorities first: submit_feedback severs identity, and the
                    # priorities belong to the leader either way, but saving them
                    # before the irreversible step means a failure there cannot
                    # lose what the leader typed
                    if is_self:
                        db.save_development_priorities(
                            rater_info['leader_id'], priorities
                        )

                    db.submit_feedback(rater_id, processed_ratings, processed_comments)

                    st.success(_t(db, 'ui_success_submitted', locale, "Thank you! Your feedback has been submitted successfully."))
                    st.balloons()

                    st.query_params["submitted"] = "true"
                    st.rerun()

                except Exception as e:
                    st.error(_t(db, 'ui_submit_error', locale,
                                "An error occurred while submitting your feedback. Please try again. ({detail})"
                                ).format(detail=str(e)))
    
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
    
    # --- Save-time indicator in sidebar ---
    # The running "X of 45" count now lives inline under each item (see the
    # form loop above), replacing the big progress panel that used to be here.
    # This keeps just the save/draft timestamp, which the inline bar doesn't show.
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
