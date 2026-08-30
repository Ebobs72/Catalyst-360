#!/usr/bin/env python3
"""
Leader Portal for Bentley Compass 360.

Allows leaders to:
- View their assessment status
- Nominate their raters (Boss, Peers, DRs, Others)
- Track rater response progress
- Send reminders to raters

REDESIGN 2026-08-26: three screens (Overview, Nominate Raters, Guidelines)
rebuilt to the visual language in assets/Bentley Compass 360 — *.html, per
the design-principles work captured in CLAUDE.md ("Leader Portal Redesign").
Two constraints from that document drive real logic here, not just look:

1. ANONYMITY RULE: nothing on any screen in this file may show a named
   rater's own response status (opened the link / responded / close to
   finishing). Only the leader's own actions (invited, nominated, category)
   may be shown per-name. Response counts/rates ARE aggregate-only (no
   per-category or per-person breakdown) - but the bare aggregate count
   itself (e.g. "12 invited, 10 responded") is NOT gated or suppressed at
   any threshold, including outstanding == 1. CORRECTED 2026-08-27: an
   earlier version of this file suppressed the aggregate at low totals and
   at outstanding == 1, borrowing the anonymity pattern from where it
   genuinely applies (content/identity tied to a person) and applying it
   somewhere that threat model doesn't reach - a bare completion count
   names no one and reveals no feedback content. It also didn't actually
   work: a leader who saw real numbers a moment earlier and then watched
   them vanish learned exactly what the gating tried to hide, just via the
   disappearance instead of a stated number. See CLAUDE.md, "Correction:
   Remove the Your Progress Gating Entirely".
2. REMINDER ACCURACY: the "Send reminders" control must reflect real
   reminder_sent_at cooldown state, and its result message must say what
   actually happened (sent / still-throttled counts), not a blanket claim.
   See _reminder_cooldown_state and _send_reminders_and_report.
"""

import html
import textwrap
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from framework import (
    ANONYMITY_THRESHOLD, RATER_REQUIREMENTS, RELATIONSHIP_TYPES,
    RELATIONSHIP_INPUT_HELP, normalise_relationship, get_logo_data_uri,
    get_bentley_font_face_css, BENTLEY_FONT_STACK,
    get_bentley_logotype_face_css
)
# Leaders have no locale column (i18n is rater-only, see CLAUDE.md section 5),
# so every _t() call in this file passes locale=None and gets the English
# fallback - reusing feedback_form's helper keeps the routing consistent with
# the rest of the app instead of duplicating it here.
from feedback_form import _t

# Import email functionality if available
try:
    from email_sender import (
        is_email_configured,
        send_rater_invitation,
        send_bulk_reminders,
        send_invitation_failure_notice,
        get_app_base_url,
        REMINDER_THROTTLE_HOURS,
    )
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    REMINDER_THROTTLE_HOURS = 48

    def get_app_base_url():
        """Fallback when email_sender is unavailable; links are display-only then."""
        return ""


def _esc(value):
    """html.escape for interpolation into unsafe_allow_html blocks. Names,
    emails, dealership and cohort are all leader/admin-entered text, so this
    is worth doing even though nothing here is public-facing input."""
    return html.escape(str(value)) if value is not None else ""


def _html(fragment):
    """
    textwrap.dedent + strip for every multi-line HTML fragment in this file.

    REAL BUG THIS FIXES, found live in browser testing: a triple-quoted
    f-string written with the function body's own indentation (4+ leading
    spaces per line) gets passed through Streamlit's markdown-to-HTML step,
    which runs CommonMark rules BEFORE honouring unsafe_allow_html - and 4+
    leading spaces on a line is CommonMark's own syntax for a fenced code
    block. The result wasn't broken HTML, it was correctly-parsed Markdown
    that turned the whole card into literal escaped text on the page. Every
    multi-line HTML string in this file must be dedented before it reaches
    st.markdown, including ones returned from a helper and embedded inside
    another f-string later - the embedding string's own indentation doesn't
    matter, but the fragment's OWN internal indentation does.
    """
    return textwrap.dedent(fragment).strip()


def _md(fragment):
    """st.markdown(_html(fragment), unsafe_allow_html=True, anchors=False) -
    the single call site every top-level HTML block in this file should go
    through, including every h1-h3 in this file (confirmed by grep - none
    render via a separate raw st.markdown() call).

    anchors=False disables Streamlit's automatic heading-anchor-link icon
    (the small link glyph that appears on hover, with a matching #id added
    to the heading and jumped-to on click). Confirmed live: Streamlit
    applies this to ANY h1-h6 tag rendered through st.markdown, including
    raw HTML passed via unsafe_allow_html - not just headings created via
    its own Markdown '#' syntax or st.header()/st.subheader(). It's
    stray default chrome here, not a deliberate feature: this app has no
    in-page anchor navigation for these headings to serve. There is no
    global/config.toml equivalent (checked the installed Streamlit 1.60.0
    source directly - anchors is a per-call keyword on st.markdown only,
    nothing in config.py), so fixing it once here, at this file's single
    HTML-rendering choke point, is the actual global fix available."""
    st.markdown(_html(fragment), unsafe_allow_html=True, anchors=False)


def _icon(name, size=20, color=None):
    """
    A Material Symbols glyph for use inside raw HTML (unsafe_allow_html)
    blocks - NOT the :material/name: shortcode, which only expands inside
    Streamlit's own markdown-rendered widget text, not arbitrary HTML
    strings (see the RTL note elsewhere in this app for the same
    constraint). Confirmed live: Streamlit already loads the "Material
    Symbols Rounded" icon font globally for its own icon= parameters (this
    file's Edit button uses one), so a plain <span> naming the icon in that
    font renders correctly anywhere on the same page, raw HTML included -
    no separate font load needed.

    Replaces the raw emoji/unicode glyphs (checkmarks, clock, warning
    triangle) the first pass of this redesign used, which didn't match the
    Material icon set already established everywhere else in this app.
    `name` is a Material Symbols icon name, e.g. "check_circle", "schedule".
    """
    # font-family moved OUT of this inline style and into a real CSS class
    # (.cp-icon-glyph, see PORTAL_CSS) 2026-08-27, after a two-step failure
    # while adding the "every text instance" Bentley rollout's broad
    # `.stApp * { font-family: ... !important; }` rule:
    #   1. An inline style WITHOUT !important loses to an external rule
    #      WITH !important, regardless of the inline style's normally-
    #      higher specificity - confirmed live via screenshot, "check"/
    #      "schedule" rendering as literal readable text instead of a
    #      checkmark/clock glyph.
    #   2. The obvious fix - add !important to this inline declaration too
    #      - does NOT work: confirmed live via outerHTML that Streamlit's
    #      own HTML rendering strips !important out of inline style
    #      attributes entirely (the font-family declaration was completely
    #      absent from the rendered span, not merely losing the cascade
    #      fight), even under unsafe_allow_html=True. Not documented
    #      anywhere found; discovered by inspecting the actual served DOM
    #      after the !important fix visibly didn't work.
    # A real class sidesteps the whole inline-vs-external precedence
    # question: PORTAL_CSS's `.cp-icon-glyph` rule is a normal external
    # !important declaration, exactly like the [data-testid="stIconMaterial"]
    # exception already used for Streamlit's own native icon= parameter -
    # same mechanism, same specificity tier, same "declared after the
    # broad rule so source order wins the tie" reasoning.
    #
    # Single quotes around the font name in the style string below,
    # deliberately - this whole attribute is double-quoted, and a
    # double-quoted CSS value here would terminate it early. Confirmed
    # live: this exact bug shipped once already - the browser parsed
    # style="font-family:"Material Symbols Rounded"..." as style="font-
    # family:" followed by two bogus boolean attributes (material=""
    # symbols=""), so the icon rendered as literal text ("check") instead
    # of the glyph. No longer applicable to font-family specifically (it's
    # not in this string any more), but the file-size/line-height/etc.
    # properties below don't need quoting either way.
    style = (
        f"font-size:{size}px;"
        f'font-weight:400;line-height:1;display:inline-flex;'
        f'align-items:center;justify-content:center;'
    )
    if color:
        style += f'color:{color};'
    return f'<span class="cp-icon-glyph" style="{style}" translate="no">{name}</span>'


def _initials(name):
    """'Jordan Reeves' -> 'JR'. Falls back to the first two characters of
    whatever's there rather than crashing on an unusual name."""
    parts = [p for p in str(name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _progress_stats_safe(completed, total):
    """
    Numbers for the Full 360 status pill and the Your Progress stats strip.
    Always real numbers, at any total or outstanding count, including
    outstanding == 1 and totals below ANONYMITY_THRESHOLD.

    CORRECTED 2026-08-27 (previously named _progress_stats_safe when it DID
    gate/suppress at those points - kept the name since every caller already
    refers to it, but the suppression itself is gone, not just relocated).
    Two reasons, not one:
    1. It didn't even achieve what it was trying to. Suppressing only at
       outstanding == 1 doesn't hide that fact from someone who saw the
       real numbers a moment earlier (e.g. outstanding == 2) and then
       watched them go blank after one more response came in - the
       disappearance itself states "outstanding is now exactly 1" just as
       plainly as a digit would have.
    2. The deeper issue: this was never actually anonymity-sensitive to
       begin with. The real protections in this system (category-level
       score/comment thresholds in reports, the Nominate Raters table
       showing only invited/not-sent - never response status) all exist to
       stop content or identity being tied to a specific person. A bare
       completion count ("12 invited, 10 responded") names no one, breaks
       down by no category, and reveals not a word of anyone's feedback -
       it's the same category of information as a delivery tracker showing
       "3 of 5 delivered". The leader also already knows exactly who's
       outstanding regardless of what this number shows, since they
       nominated these people by name themselves; the system was never
       trying to (and shouldn't try to) prevent that. Applying the
       anonymity-gating pattern here borrowed a protection from where it
       genuinely matters and put it somewhere its threat model doesn't
       reach. See CLAUDE.md for the full correction.

    The `total < ANONYMITY_THRESHOLD` condition was reconsidered
    separately, not just dropped along with the outstanding==1 one - same
    reasoning applies (no identity/content revealed at low totals either,
    and no other genuine non-anonymity-derived reason was found to keep
    it), so it's gone too.
    """
    outstanding = total - completed
    if total == 0:
        return {'invited': 0, 'responded': 0, 'rate': 0, 'outstanding': 0}
    rate = round(100 * completed / total)
    return {
        'invited': total, 'responded': completed, 'rate': rate,
        'outstanding': outstanding,
    }


def _format_completion_date(raw_timestamp):
    """
    'Completed on {date}' per the CLAUDE.md decision (2026-08-26): completion
    date, not send date, since there's no "sent" timestamp anywhere in the
    system today. Source MUST be raters.completed_at on the leader's own
    Self-relationship row (passed in here directly), never a computed
    self_completed count - that's a 0/1, not a date.

    Returns None if there's no real timestamp to show, so the caller can
    fall back rather than print something wrong.
    """
    if not raw_timestamp:
        return None
    try:
        dt = datetime.fromisoformat(str(raw_timestamp).replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
    return f"{dt.day} {dt.strftime('%B')}"


def _ring_dashoffset(count, target):
    """
    SVG stroke-dashoffset for the category progress rings (r=24,
    circumference 2*pi*24 ≈ 150.8). Sized up from the concept mockup's
    original r=19/119.4 on 2026-08-27, alongside moving the ring to
    always sit on its own line below the category label (see
    .cp-card-top) - freed from squeezing beside label text at every
    width, there was room to make it a bit bigger and more legible.

    Ring shows NOMINATED count toward the category's suggested number (or,
    for Others, toward min_if_any once anyone's been added) - never response
    status. This is the leader's own action (who have I nominated), which is
    explicitly fine under the anonymity rule; it is deliberately NOT a
    response-progress ring, which would put per-category response data on a
    screen the anonymity rule doesn't clearly license it for.
    """
    circumference = 150.8
    if target <= 0:
        fraction = 1.0 if count > 0 else 0.0
    else:
        fraction = min(count / target, 1.0)
    return round(circumference * (1 - fraction), 1)


def _reminder_cooldown_state(incomplete_raters):
    """
    Real cooldown state for the Send reminders button, computed from
    reminder_sent_at - not just "does the throttle logic exist somewhere",
    which is the bug this build closes (see CLAUDE.md's Leader Portal
    Redesign section 4, "Send reminders control" finding).

    Returns (any_eligible: bool, hours_until_next: float | None).
    any_eligible is True if clicking now would actually remind someone
    (never reminded, or past REMINDER_THROTTLE_HOURS). hours_until_next is
    the time until the EARLIEST currently-throttled rater clears their
    window - i.e. when the button would next have someone to remind - None
    if there's nobody throttled (either everyone's eligible or the list is
    empty).
    """
    if not incomplete_raters:
        return False, None

    now = datetime.now()
    any_eligible = False
    soonest_clear = None

    for rater in incomplete_raters:
        if not rater.get('email'):
            continue
        last_sent = rater.get('reminder_sent_at')
        if not last_sent:
            any_eligible = True
            continue
        try:
            last_sent_dt = datetime.fromisoformat(
                str(last_sent).replace('Z', '+00:00')
            ).replace(tzinfo=None)
        except (ValueError, TypeError):
            any_eligible = True
            continue
        clears_at = last_sent_dt + timedelta(hours=REMINDER_THROTTLE_HOURS)
        if now >= clears_at:
            any_eligible = True
        else:
            if soonest_clear is None or clears_at < soonest_clear:
                soonest_clear = clears_at

    hours_until_next = None
    if soonest_clear is not None:
        hours_until_next = max((soonest_clear - now).total_seconds() / 3600, 0)

    return any_eligible, hours_until_next


def _send_reminders_and_report(db, leader_info, incomplete_raters, base_url):
    """
    Send reminders and return an ACCURATE result message.

    THE BUG THIS REPLACES: render_progress_section used to call
    send_rater_reminder in a loop, discard its (success, message) return
    value entirely, and always show "Reminders sent to anyone who hasn't
    responded yet" - even when every incomplete rater was inside their 48h
    cooldown and literally zero emails went out. Found while documenting the
    redesign (CLAUDE.md, 2026-08-26), fixed here as part of the build per
    that document's section 2.

    Uses the same send_bulk_reminders(sent, throttled, failed, results)
    tally as the admin dashboard's equivalent fix, so both portals report
    reminders with the same accuracy standard and neither drifts from the
    other independently.

    Reports real counts unconditionally - a brief period 2026-08-27 had
    this take a `reveal_counts` flag and go generic at outstanding == 1,
    matching the stats strip's own gating at the time. Removed along with
    that gating: see _progress_stats_safe for the full correction (a bare
    completion count was never actually anonymity-sensitive).
    """
    emailed = [r for r in incomplete_raters if r.get('email')]
    if not emailed:
        return "Nobody to remind."

    sent, throttled, failed, _results = send_bulk_reminders(
        emailed, leader_info['name'], base_url, db
    )

    parts = []
    if sent:
        parts.append(f"Reminded {sent} rater{'s' if sent != 1 else ''}.")
    if throttled:
        if sent:
            parts.append(
                f"{throttled} {'are' if throttled != 1 else 'is'} still within "
                f"their 48-hour window and weren't reminded again."
            )
        else:
            _any_eligible, hours = _reminder_cooldown_state(incomplete_raters)
            when = f" Try again in about {round(hours)}h." if hours else ""
            parts.append(
                f"All {throttled} rater{'s' if throttled != 1 else ''} still "
                f"within their 48-hour window — no reminders were sent.{when}"
            )
    if failed:
        parts.append(
            f"{failed} failed to send — check back or contact your "
            f"programme coordinator."
        )
    return " ".join(parts) if parts else "Nobody to remind."


# Rater requirements - MOVED to framework.py 2026-08-29 so email_sender.py's
# invitation template can share the exact same numbers instead of carrying
# its own hardcoded, driftable copy (see framework.py's own comment on
# RATER_REQUIREMENTS for the full reasoning). Imported above alongside
# ANONYMITY_THRESHOLD. 'Others' is optional, but ALL OR NOTHING above the
# anonymity threshold: nominate none, or nominate at least
# ANONYMITY_THRESHOLD. One or two "Others" is still worth avoiding: their
# responses don't get dropped (a thin Others group folds into whichever of
# Peers/DRs is large enough — see database.py's get_leader_feedback_data),
# but they lose their own voice in the report, showing up as part of that
# group rather than as Others. `min_if_any` captures the practical
# recommendation.

# Category caption/label pairs and requirement blurbs for the Overview ring
# cards, matching the concept mockup's two-line card header (small caption,
# then the real category name) and .req line. Numbers are pulled from
# RATER_REQUIREMENTS above rather than hardcoded twice, so a future change to
# the actual business rule can't silently drift out of sync with this copy.
CATEGORY_CAPTION = {'Boss': 'Line Manager', 'Peers': 'Colleagues', 'DRs': 'Your Team', 'Others': 'Optional'}
CATEGORY_REQ_TEXT = {
    'Boss': f"Minimum <b>{RATER_REQUIREMENTS['Boss']['min']}</b>, max {RATER_REQUIREMENTS['Boss']['max']} if matrix reporting",
    'Peers': (f"Minimum <b>{RATER_REQUIREMENTS['Peers']['min']}</b>, suggested {RATER_REQUIREMENTS['Peers']['suggested']}, "
               f"up to {RATER_REQUIREMENTS['Peers']['max']} if needed"),
    'DRs': (f"Minimum <b>{RATER_REQUIREMENTS['DRs']['min']}</b>, suggested {RATER_REQUIREMENTS['DRs']['suggested']}, "
            f"up to {RATER_REQUIREMENTS['DRs']['max']} if needed"),
    # Deliberately NOT the same flat "suggested 5" pattern as Peers/DRs -
    # Others typically draws from a smaller, more constrained pool (named
    # stakeholders/customers), so the softer "4 or 5 if you have them"
    # sets more honest expectations. The cap (10) is genuinely the same
    # number as Peers/DRs though, confirmed identical and confirmed safe
    # to state - see the nomination-cap diagnostic in the history above.
    'Others': (f"Minimum <b>{RATER_REQUIREMENTS['Others']['min_if_any']}</b>, ideally 4 or 5 if you have them, "
               f"up to {RATER_REQUIREMENTS['Others']['max']} if needed"),
}
CATEGORY_ACCENT = {'Boss': '#183319', 'Peers': '#183319', 'DRs': '#6b7a63', 'Others': '#DCD8C0'}

# Fuller per-category guidance for the Guidelines screen — copy taken from the
# concept mockup (assets/Bentley Compass 360 — Guidelines Concept.html),
# which was supplied as reference material binding for this build.
GUIDELINE_CATEGORIES = [
    {
        'key': 'Boss', 'title': 'Boss (Line Manager)', 'badge': '1 required, max 2',
        'body': (
            "Your direct line manager, the person you report to day-to-day. If you have "
            "matrix reporting into two managers, you can add a second, but one is enough "
            "in most cases."
        ),
        'tip_label': 'Why it matters:',
        'tip_body': (
            "your manager sees things your peers and reports often don't, how you represent "
            "your team upward and how you handle pressure from above."
        ),
    },
    {
        'key': 'Peers', 'title': 'Peers',
        'badge': (f"Minimum {RATER_REQUIREMENTS['Peers']['min']}, suggested {RATER_REQUIREMENTS['Peers']['suggested']}, "
                  f"up to {RATER_REQUIREMENTS['Peers']['max']} if needed"),
        'body': (
            "Colleagues at a similar level who see your day-to-day work, ideally from more "
            "than one part of the business, not just people on your immediate team."
        ),
        'tip_label': 'Tip:',
        'tip_body': (
            "a mix of peers who work closely with you and some who only see you occasionally "
            "(in meetings, on projects) gives a more rounded picture than five people who see "
            "the same slice of your week."
        ),
    },
    {
        'key': 'DRs', 'title': 'Direct Reports',
        'badge': (f"Minimum {RATER_REQUIREMENTS['DRs']['min']}, suggested {RATER_REQUIREMENTS['DRs']['suggested']}, "
                  f"up to {RATER_REQUIREMENTS['DRs']['max']} if needed"),
        'body': (
            "People who report to you. Aim for a range, someone who's been in your team for "
            "years, someone newer, someone from a different function if your team spans more "
            "than one."
        ),
        'tip_label': 'Why it matters:',
        'tip_body': (
            "this is the group with the clearest, most frequent view of how you actually "
            "lead, day to day. Don't only nominate your strongest supporters."
        ),
    },
    {
        'key': 'Others', 'title': 'Others',
        'badge': (f"Minimum {RATER_REQUIREMENTS['Others']['min_if_any']}, ideally 4 or 5 if you have them, "
                  f"up to {RATER_REQUIREMENTS['Others']['max']} if needed"),
        'body': (
            "Stakeholders, customers, or colleagues from outside your direct chain, if "
            "relevant to your role. Only use this category if you have genuinely relevant "
            "people to add; leave it empty otherwise."
        ),
        'tip_label': 'Note:',
        'tip_body': (
            "if you add anyone here, add at least three. A category with one or two people "
            "can't be shown separately without risking that person being identifiable, so it "
            "needs the same minimum as any other category."
        ),
    },
]

# Begin Here / Help screen content — copy taken from the concept mockup
# (assets/Bentley Compass 360 — Begin Here Concept.html), supplied as
# reference material binding for this build.
BEGIN_HERE_STEPS = [
    {
        'title': 'Add each rater, one at a time, or all at once from a spreadsheet',
        'body': (
            "Go to <strong>Nominate Raters</strong> and enter their name, email, and category "
            "(Boss, Peer, Direct Report, or Other). Click <strong>Add</strong>. This only saves "
            "the record, nothing is sent to them yet."
        ),
        'sub_note': (
            "Adding several people? Use <b>Upload a CSV instead</b> on the same page to add "
            "your whole list in one go, rather than typing each one in separately."
        ),
    },
    {
        'title': 'Repeat until your list is complete',
        'body': (
            "Add as many people as you need across each category before sending anything. "
            "There's no limit on how many times you can come back and add more later, but "
            "it's easiest to build the full list first."
        ),
        'sub_note': None,
    },
    {
        'title': "Check you've met each category's minimum",
        'body': (
            'Your rater cards on Overview will show "Requirement met" once each category has '
            'enough people. If a category still shows "more needed," add more before sending, '
            "or leave that category empty entirely if it doesn't apply (Others is optional)."
        ),
        'sub_note': None,
    },
    {
        'title': 'Click Send Invitations',
        'body': (
            "One click sends every pending invitation at once. This is the only point anyone "
            "actually receives an email, nothing goes out before this."
        ),
        'sub_note': None,
    },
    {
        'title': 'Send reminders later, if needed',
        'body': (
            'Once responses start coming in, a <strong>Send Reminders</strong> button appears '
            "next to Your Progress. It nudges everyone who hasn't responded yet in one go, no "
            "need to chase people individually, and it's limited to once every 48 hours."
        ),
        'sub_note': None,
    },
]

# Order matches the mockup: the two most likely practical questions after a
# leader's first session (editing a mistake, adding someone later) come
# first, ahead of the more explanatory cards.
BEGIN_HERE_WATCH_CARDS = [
    {
        'title': "Got someone's details wrong? Fix it anytime",
        'items': [
            "Typo'd an email address, or nominated someone under the wrong category? Click "
            "<strong>Edit</strong> next to their name on <strong>Nominate Raters</strong> to "
            "correct it, this works whether or not their invitation's already been sent.",
        ],
    },
    {
        'title': 'Forgot someone? Add them anytime',
        'items': [
            "You're not locked to your original list. Come back to <strong>Nominate Raters</strong> "
            "whenever you like and add anyone you missed. Clicking <strong>Send Invitations</strong> "
            "again only sends to whoever's still pending, everyone already invited stays exactly "
            "as they are, they won't be emailed a second time.",
        ],
    },
    {
        'title': 'Why the category minimums exist',
        'items': [
            "It's not arbitrary, it's what keeps individual feedback anonymous. A category of one "
            "or two people is too easy to trace back to a single person, so each one needs enough "
            "responses before it can be shown at all.",
        ],
        # A real button, not the mockup's inline <a href="#"> - a raw anchor
        # here would reintroduce the exact new-tab navigation bug just fixed
        # elsewhere in this file (see _go_to_view's docstring). Rendered as
        # a small link-styled control after the card text rather than
        # inline mid-sentence, since a Streamlit button can't sit inside a
        # markdown paragraph's own flow.
        'link_to': ('guidelines', 'See Guidelines for help deciding who to choose'),
    },
    {
        'title': "What your rater list does and doesn't show",
        'items': [
            "You'll see whether someone's been <strong>invited</strong>. You will never see "
            "whether they've personally <strong>responded</strong>, that's deliberate, not a "
            "missing feature. Response progress only ever shows as an overall total across "
            "everyone invited, never broken down by category or by name.",
        ],
    },
    {
        'title': 'What to check if something looks off',
        'items': [
            "Someone says they never received their invitation? Double-check their email address "
            "in your rater list first, a typo means it goes nowhere, silently.",
            'A category still shows "more needed" after you\'re sure everyone\'s replied? It '
            "usually just means responses genuinely haven't come in yet, not that anything's broken.",
            "Reminder button greyed out? You're inside the 48-hour window, it'll show exactly "
            "when it's available again.",
        ],
    },
    {
        # Added 2026-08-30, Ian's own instruction: nominating raters and
        # watching responses come in genuinely happens over days or weeks,
        # so this portal is worth being able to find again easily.
        'title': 'Worth bookmarking this page',
        'items': [
            "You'll likely be back here more than once as responses come in. Bookmark your "
            "portal page, or keep your invitation email handy, so you can find your way "
            "straight back whenever you need to.",
        ],
    },
]

# ==========================================================================
# CSS — namespaced "cp-" (Compass Portal) throughout so nothing here collides
# with app.py's global stylesheet or the admin dashboard's own rules, which
# are explicitly out of scope for this build. Adapted directly from the three
# concept mockups (assets/Bentley Compass 360 — *.html) rather than
# reinterpreted, so the class names and values below match that reference
# material as closely as Streamlit's own widget markup allows.
# ==========================================================================
PORTAL_CSS = """
<style>
  /* Topbar is now a real st.container(key="cp_topbar") wrapping brand/nav/
     account columns, not one raw HTML div - nav items had to become real
     st.button() calls (see _go_to_view's docstring: Streamlit force-adds
     target="_blank" to every <a> rendered via unsafe_allow_html, breaking
     in-tab navigation).

     FULL-BLEED WIDTH, NOT A NEGATIVE-MARGIN GUESS: a first version used
     margin:-1rem -1rem 0 -1rem to cancel Streamlit's own page padding -
     confirmed live (screenshots at several widths, then root-caused via
     the DOM chain) that this only ever cancelled the LEFT side. This
     element is a flex item (display:flex, flex-grow:0, flex-basis:auto)
     inside Streamlit's own layout, and - same underlying mechanism as the
     guide-card alignment bug elsewhere in this file - a negative margin
     on a flex item can shift its start edge but does not reliably force
     its own computed width to expand past what flex-basis already fixed;
     here that showed up as the box's LEFT edge reaching x:0 correctly
     while its RIGHT edge stayed pinned to the padded parent's inner edge,
     a consistent ~32px shortfall (Streamlit's 16px side padding x2)
     regardless of viewport width - so it wasn't a "wrong number", the
     mechanism itself couldn't work here.

     Fixed with the standard full-bleed breakout instead, which escapes a
     padded/centred parent by positioning relative to the VIEWPORT rather
     than fighting the parent's own box model: left:50%, pulled back by
     -50vw, width:100vw. This doesn't care what the parent's padding
     value is at any given width, so it can't drift out of sync with it
     again the way a hardcoded margin guess already has once. */
  div[class*="st-key-cp_topbar"] > div{
    background:#183319 !important;position:relative !important;left:50% !important;
    width:100vw !important;max-width:100vw !important;margin-left:-50vw !important;
    margin-top:-1rem !important;padding:14px 40px !important;box-sizing:border-box !important;
  }
  div[class*="st-key-cp_topbar"] div[data-testid="stHorizontalBlock"]{
    align-items:center;
  }
  .cp-topbar-row1{display:flex;align-items:center;justify-content:space-between;}
  /* Row 2 (nav) sits directly under row 1 (brand/account) - a visible
     divider line reads more deliberate than bare vertical spacing, and
     costs nothing since both rows already share the same green
     background. */
  div[class*="st-key-cp_topbar_row2"]{
    margin-top:14px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.14);
  }
  .cp-brand{display:flex;align-items:center;gap:14px;}
  /* Real Bentley wing mark sitting directly on the green topbar - no
     circle/badge behind it. Sized off the mockup's original 34px badge
     footprint so the header's overall proportions don't shift, but as a
     plain image, not a contained shape. */
  .cp-brand-mark{display:flex;align-items:center;flex-shrink:0;}
  .cp-brand-mark img{height:34px;width:auto;display:block;}
  .cp-brand-text{line-height:1.15;}
  .cp-brand-text .cp-b1{font-size:11px;letter-spacing:2px;color:#DCD8C0;font-weight:600;text-transform:uppercase;}
  .cp-brand-text .cp-b2{font-size:18px;font-weight:700;color:#FFFFFF;}
  .cp-account{display:flex;align-items:center;gap:12px;justify-content:flex-end;}
  .cp-avatar{width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.16);
    display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#FFFFFF;flex-shrink:0;}
  .cp-account .cp-name{font-size:13.5px;color:#FFFFFF;font-weight:500;}

  /* Nav buttons (Overview / Nominate Raters / Guidelines) - real
     st.button()s reskinned to read as plain text links on the green bar,
     not boxed buttons. cp_nav_active_ is the current page: white text,
     underline. cp_nav_ (inactive) is dimmer with no underline, matching
     the mockup's nav a / nav a.active split exactly, just driven by two
     container-key variants instead of a CSS class toggle. */
  div[class*="st-key-cp_nav_"] button,
  div[class*="st-key-cp_nav_"] button *{
    color:rgba(255,255,255,0.78) !important;
  }
  div[class*="st-key-cp_nav_"] button{
    background:none !important;border:none !important;border-radius:0 !important;
    border-bottom:2px solid transparent !important;font-weight:500 !important;
    font-size:13.5px !important;padding:6px 2px !important;white-space:nowrap !important;
  }
  div[class*="st-key-cp_nav_"] button p{white-space:nowrap !important;}
  div[class*="st-key-cp_nav_active_"] button,
  div[class*="st-key-cp_nav_active_"] button *{
    color:#FFFFFF !important;
  }
  div[class*="st-key-cp_nav_active_"] button{
    border-bottom:2px solid #DCD8C0 !important;font-weight:700 !important;
  }

  .cp-page-head{margin:34px 0 8px;}
  .cp-page-head h1{font-size:30px;margin:0 0 6px;color:#040404;font-weight:700;letter-spacing:-0.3px;}
  .cp-page-head p{margin:0;color:#6B6B6B;font-size:14.5px;max-width:680px;line-height:1.5;}

  .cp-section-label{font-size:12px;font-weight:700;letter-spacing:1.6px;text-transform:uppercase;
    color:#183319;margin:34px 0 14px;}

  /* status strip: self-assessment + full 360 readiness */
  .cp-status-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:22px;}
  .cp-status-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;
    padding:22px 24px;display:flex;align-items:center;justify-content:space-between;}
  .cp-status-card.cp-done{background:#183319;border-color:#183319;}
  .cp-status-left{display:flex;align-items:center;gap:16px;}
  .cp-status-icon{width:42px;height:42px;border-radius:50%;background:#e7ebe3;
    display:flex;align-items:center;justify-content:center;font-size:19px;color:#183319;flex-shrink:0;}
  .cp-status-card.cp-done .cp-status-icon{background:rgba(255,255,255,0.16);color:#FFFFFF;}
  .cp-status-text b{display:block;font-size:15.5px;color:#040404;margin-bottom:3px;}
  .cp-status-card.cp-done .cp-status-text b{color:#FFFFFF;}
  .cp-status-text span{font-size:12.5px;color:#6B6B6B;}
  .cp-status-card.cp-done .cp-status-text span{color:#DCD8C0;}
  .cp-pill{font-size:11.5px;font-weight:700;padding:5px 12px;border-radius:20px;
    background:#f1efe4;color:#183319;white-space:nowrap;}
  .cp-status-card.cp-done .cp-pill{background:rgba(255,255,255,0.16);color:#FFFFFF;}

  /* rater category cards - laid out with real st.columns(4) now (each
     card needed a real "Nominate" button under it, issue: cards were
     display-only), not a single raw .cp-grid div - Streamlit's own column
     stacking handles the mobile collapse, so no grid-template-columns
     override is needed in the mobile block below either. */
  /* REAL BUG FOUND LIVE (confirmed via screenshot, then reproduced by
     narrowing the viewport): the row's stHorizontalBlock already has
     align-items:stretch (Streamlit's own flex default), which stretches
     each st.column's OUTER box to match the tallest sibling - confirmed
     via getBoundingClientRect. But .cp-card is a plain block div sitting
     INSIDE that stretched column, with no height rule of its own, so it
     just took its own intrinsic content height and overflowed past the
     stretched column box whenever its description wrapped to a second
     line (Line Manager's "Minimum 1, max 2 if matrix reporting" and
     Others' "Add at least 3 if you use this category" wrap sooner than
     Peers/Direct Reports' shorter text, at plausible real widths - not a
     contrived edge case). Fixed by making the card itself fill 100% of
     its (already-stretched) column and lay out as a flex column, with the
     status chip pushed to the bottom via margin-top:auto on
     .cp-card-foot - so cards match height AND their chips sit on a
     common baseline regardless of how many lines the description above
     them took. */
  /* height:100% on .cp-card alone wasn't enough - confirmed live via a
     getComputedStyle chain walk: Streamlit wraps each card's raw-HTML
     markdown in its own stElementContainer > stMarkdown > (unnamed flex
     div) > stMarkdownContainer chain, and every one of those wrappers is
     height:auto (sized to its own content) except the outermost
     stVerticalBlock, which IS correctly stretched to match its tallest
     sibling column. A percentage height only resolves against the
     nearest ancestor with a DEFINITE (non-auto) height, so .cp-card's
     height:100% was resolving against its own auto-height immediate
     parent and just falling back to its own content height - the four
     cards measured 264/244/264/244px, not equal, despite this rule.
     Fixed by explicitly giving every wrapper level in that chain
     height:100% too, so the definite height on the real stretched column
     actually propagates all the way down to .cp-card.

     SUPERSEDED 2026-08-29 - the whole height:100% chain above is REMOVED,
     found live during a leader-portal walkthrough's "pill cramped against
     the card's bottom edge" report. Root-caused via a full ancestor chain
     measurement (getBoundingClientRect at every level, not assumed): on
     Overview, each card's column contains a SECOND flex item below it -
     the "Nominate" button (stLayoutWrapper, ~55px) - and stElementContainer
     is a flex item (flex-basis:auto, flex-shrink:1 by default) inside that
     column's own flex-column layout. Giving it height:100% sets its
     flex-basis to the column's full height, but default shrink then
     compresses it back down to (column height - button's own footprint)
     to make room for that sibling - confirmed measured at 357px, 16px
     short of the card's own true content height (min-height reservations
     + padding + gaps = 371px scrollHeight), and overflow:hidden was
     silently clipping that 16px, eating almost all of the intended bottom
     padding and leaving the status chip only ~5px from the card's edge.
     Trimming the card's own internal spacing (tried first, see the
     padding/margin values above) didn't fix it: shrinking the card's own
     natural content proportionally shrank what "the tallest natural
     content in the row" resolves to as well, so the deficit persisted at
     the same ~16px regardless of how much was trimmed - the two numbers
     move together, chasing a fixed target that isn't actually independent.
     THE ACTUAL FIX: the four categories' min-height floors (on the label,
     h3, and description - added 2026-08-27, tuned to the worst-case text
     length across all four categories at the narrowest multi-column
     width) are now IDENTICAL regardless of category, which means the four
     cards are ALREADY guaranteed equal natural height on their own,
     without needing any explicit height-matching machinery at all -
     confirmed live by setting height:auto on the whole chain and
     re-measuring: all four cards still matched exactly (373px each), no
     clipping (scrollHeight == clientHeight), and the chip-to-edge gap
     returned to a comfortable 21px. Removing the chain fixes the real bug
     as a side effect of removing a now-redundant mechanism, rather than
     chasing the symptom with more spacing tweaks - the same "stop trying
     to force it, remove the constraint" reasoning already used once before
     in this exact card (see the ring-placement fix above). If a future
     content change ever makes the four categories' text lengths genuinely
     asymmetric again (not just differently-worded at the same reserved
     floor), re-verify this holds - the floors are what guarantee equality
     now, not an explicit height rule. */
  .cp-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;
    padding:20px 20px 16px;position:relative;overflow:hidden;
    display:flex;flex-direction:column;box-sizing:border-box;}
  .cp-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
    background:var(--cp-accent,#183319);}
  /* "Nominate" link button under each card. REAL BUG FIXED, confirmed via
     screenshot: the previous version pulled the button up flush against
     the card with a bottom-corner-matching radius, sized to the exact
     same full column width as the card above it - visually correct in
     principle, but its own left/right edges then sat exactly where the
     card's own edges (and the card's ::before accent bar, a 4px strip
     pinned to left:0) sit, so the button's text/icon rendered as if
     bleeding into the accent bar rather than reading as a contained
     control. Fixed by dropping the flush/joined treatment entirely and
     using the SAME cp_secondary_ button styling already established
     everywhere else in this design system (white fill, green text,
     bordered, fully rounded) with normal positive spacing below the card,
     not overlapping it - "a proper button", not a bare link fused to the
     card's edge. */
  div[class*="st-key-cp_secondary_cat_link_"]{margin-top:10px;}
  /* REAL BUG FOUND LIVE 2026-08-27 (the human spotted it in a screenshot
     at a width none of the prior sweeps happened to land on): with the
     label and ring side by side, the ring got pushed past the card's
     own right edge at a narrow band of widths between the 4-column
     layout's collapse point and where everything comfortably fits
     (~640-700px, confirmed via getBoundingClientRect). Root cause: the
     ring is a fixed 48px with flex-shrink:0 (an SVG ring can't usefully
     shrink), and the category label is sometimes a single unbreakable
     word ("COLLEAGUES", "OPTIONAL") with no space to wrap at, so when
     both items' combined natural width exceeded the row's,
     justify-content:space-between had no spare space to remove and the
     ring just overflowed with nothing to stop it. A first fix
     (flex-wrap, letting the ring drop to its own line only when it
     didn't fit) stopped the overflow but traded it for a DIFFERENT
     problem: whether the ring wrapped now depended on each card's own
     label text length, so at some widths (e.g. 768-902px) two cards
     showed the ring beside the label and the other two showed it below
     - a row of four cards that no longer matched each other, confirmed
     via the same measurements.
     FIX (the human's own suggestion, simpler than either attempt
     above): stop trying to fit them side by side at all. The ring
     always sits on its own line below the label now, at every width -
     removes the whole category of "does this fit today" bug rather
     than chasing it, and every card is now guaranteed identical
     regardless of width or label length. Freed from squeezing beside
     label text, the ring also grew (48px -> 60px, r 19 -> 24) - see
     _ring_dashoffset and the SVG markup in _category_card_html. */
  .cp-card-top{display:flex;flex-direction:column;align-items:flex-start;gap:12px;margin-bottom:12px;}
  /* REAL BUG FOUND LIVE, confirmed via getBoundingClientRect at a range of
     widths, not visible in any single screenshot on its own: the pill's
     margin-top:auto anchors it to the bottom of the (equal-height) card,
     but only correctly when every card's own label+description content
     needs the SAME amount of room. At in-between widths a category with a
     longer description wraps to more lines than its neighbours in the same
     row (e.g. at 1000px: Boss and Others wrap their description to 2
     lines, Peers and Direct Reports stay on 1) - the shorter cards then
     have real slack for margin-top:auto to absorb, but the taller ones
     don't, so their content pushes the pill 16px further down than its
     row-mates. Swept the full multi-column range (the layout collapses to
     a single stacked column below ~630px, where this doesn't apply) and
     found the worst real case at ~650-710px width: the category label can
     wrap to 2 lines ("LINE MANAGER" -> "LINE" / "MANAGER"), the h3 title
     can wrap to 2 lines too ("Line Manager"/"Direct Reports" wrap, "Peers"/
     "Others" don't - a SECOND, separate source of the same mismatch, only
     found by re-measuring after the first fix below still didn't align
     everything), and the description to 3. Fixed by reserving that
     worst-case space with min-height on the label, the h3, and the
     description, rather than letting each card's box shrink to fit however
     many lines ITS OWN text happens to need at whatever width the viewer
     has - so the label, the h3 title, and the pill all sit at the
     identical vertical offset in every card at every width, not just
     within one row at one width. */
  .cp-cat-label{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6B6B6B;
    display:block;min-height:36px;}
  .cp-ring{position:relative;width:60px;height:60px;flex-shrink:0;}
  .cp-ring svg{transform:rotate(-90deg);}
  .cp-ring-track{stroke:#f1efe4;}
  .cp-ring-progress{stroke:#183319;stroke-linecap:round;}
  .cp-ring-label{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    font-size:13px;font-weight:700;color:#183319;}
  .cp-card h3{font-size:16.5px;margin:2px 0 4px;color:#040404;font-weight:700;min-height:68px;}
  /* min-height bumped 58px -> 98px 2026-08-27: the "Final Category
     Guidance Copy" pass lengthened all three non-Boss descriptions
     (added ", up to 10 if needed"; Others' own text grew further still,
     from "...if you have them" to that plus the same suffix). Re-swept
     the same worst-case width range this reservation was originally
     tuned against (630-710px, the narrowest multi-column squeeze before
     Streamlit's own native column-stacking takes over) and found Others'
     longer text now needs up to 5 lines (96px) there, not the 3 lines
     (58px) the old copy needed - confirmed via a natural-height probe
     (an off-screen clone at the real column width, bypassing the
     flex-shrink that was otherwise silently clipping the visible text
     to less than it needed). Re-verify this number again if any of
     these three strings changes length again. */
  .cp-card .cp-req{font-size:12px;color:#6B6B6B;margin-bottom:14px;min-height:98px;}
  .cp-card .cp-req b{color:#040404;}
  /* REAL BUG FOUND LIVE, a THIRD source of the same footTop mismatch,
     found only after the label/h3/description reservations above still
     left one card out of alignment: the status chip itself
     ("Requirement met" vs "Nominated" vs "N more needed") wraps to 2
     lines at the same ~650-710px squeeze where everything else wraps,
     and a longer chip label wraps while a shorter one doesn't - the
     foot's own box then grows to fit whichever chip it holds, varying
     the total reserved-content height per card even though everything
     above it is now fixed. Reserved on the FOOT container (min-height,
     content-box - padding-top is separate) rather than on the chip
     itself, so the pill's own visible size stays its normal compact
     shape and just sits vertically centred (align-items:center, already
     set) within the taller reserved row - reserving on the chip directly
     was tried first and rejected, it made every pill look like an
     oversized button even when its text fit on one line. */
  .cp-card-foot{display:flex;justify-content:space-between;align-items:center;margin-top:auto;
    padding-top:14px;min-height:45px;box-sizing:border-box;}
  .cp-status-chip{font-size:11.5px;font-weight:700;padding:4px 10px;border-radius:14px;display:inline-block;}
  .cp-status-chip.cp-met{background:#e7ebe3;color:#183319;}
  .cp-status-chip.cp-pending{background:#f1efe4;color:#8a7a4a;}

  .cp-stats-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:0;
    background:#183319;border-radius:14px;margin-top:14px;overflow:hidden;}
  .cp-stat-block{padding:26px 28px;border-right:1px solid rgba(255,255,255,0.14);}
  .cp-stat-block:last-child{border-right:none;}
  .cp-stat-block .cp-num{font-size:32px;font-weight:700;color:#FFFFFF;line-height:1;}
  .cp-stat-block .cp-lbl{font-size:12.5px;color:#DCD8C0;margin-top:8px;letter-spacing:0.3px;}

  /* Real st.container(key="cp_guide_card") now, not a raw div (the "Open
     full guidelines" control had to become a button - see _go_to_view).

     NO HORIZONTAL PADDING HERE, deliberately - see the guide-items-row
     comment below for why. Vertical padding + background/border/radius
     only; the heading row (title + button) carries its OWN horizontal
     inset instead, via cp_guide_heading_row. */
  div[class*="st-key-cp_guide_card"] > div{
    margin-top:34px;background:#f1efe4;border:1px solid #DCD8C0;
    border-radius:12px;padding:24px 0;
  }
  div[class*="st-key-cp_guide_heading_row"]{padding:0 26px;margin-bottom:14px;}
  .cp-g-head-title{font-size:15.5px;color:#040404;}
  /* Guide items are laid out with real st.columns(4, gap="medium") now,
     not a raw HTML grid - see the call site's comment (render_portal_
     overview) for why a CSS-grid approach kept drifting out of alignment
     with the category cards below whenever their own layout mechanism
     changed.

     THIS ROW DELIBERATELY HAS NO SIDE PADDING OR MARGIN AT ALL, unlike an
     earlier attempt that tried to cancel the card's padding with a
     negative margin. Confirmed live that doesn't work: this row is a flex
     item inside Streamlit's own stVerticalBlock (display:flex,
     flex-grow:1, flex-basis:0%), and a flex item's MAIN-AXIS SIZE is
     computed by the flex algorithm against its own parent's content-box
     width before margins are applied - a negative margin on a flex item
     shifts/overlaps visually but does not retroactively enlarge the size
     st.columns() inside it actually laid out against, unlike a plain
     block-level div where negative margins reliably expand the box. No
     amount of margin tuning fixed it (row stayed 688px against the card
     row's 742px regardless of -26px vs -27px vs targeting the key element
     itself instead of a child of it). The robust fix was to stop trying to
     escape the parent's padding after the fact, and instead give the
     guide CARD no horizontal padding in the first place (above), moving
     that inset onto only the content that still needs it (the heading
     row). This row and the un-padded category-card row below it now
     genuinely share the same available width with nothing to cancel -
     re-verified live: both rows measured 742px wide with the same x
     origin, and per-column drift dropped from an accumulating
     13/26/40px to sub-pixel rounding. */
  .cp-guide-item{padding:0 26px;}
  .cp-guide-item b{display:block;font-size:13.5px;color:#040404;margin-bottom:3px;}
  .cp-guide-item span{font-size:12px;color:#6B6B6B;}

  /* Top spacing now lives on the row container (cp_progress_row) so it
     applies evenly to both columns - see that container's own comment at
     the call site for why margin only on this label wasn't enough. */
  div[class*="st-key-cp_progress_row"] > div{margin-top:34px;}
  .cp-progress-head{display:flex;align-items:center;justify-content:space-between;margin:0;}
  .cp-progress-head .cp-section-label{margin:0;}
  .cp-reminder-note{font-size:11.5px;color:#6B6B6B;margin-top:6px;text-align:right;}

  /* Nominate Raters: add-card + nominated list */
  .cp-add-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;padding:24px 26px;}
  .cp-csv-row{display:flex;align-items:center;gap:10px;margin-top:14px;padding-top:14px;
    border-top:1px solid #f1efe4;font-size:13px;color:#6B6B6B;}
  .cp-list-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;overflow:hidden;}
  /* Header alignment MUST match content alignment - found via live report:
     headers read as centred against the actually-left-aligned row content
     below them. Root cause wasn't a stray text-align:center rule (there
     wasn't one to find) but the header/content mismatch was real
     regardless, so text-align:left is set explicitly here rather than
     left to inherit from nothing in particular. */
  .cp-list-head{display:grid;grid-template-columns:1.4fr 1.8fr 1fr 1fr;gap:16px;
    background:#f1efe4;font-size:11px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;
    color:#6B6B6B;padding:12px 22px;text-align:left;}
  /* The Edit column previously had no header label at all - this is its
     header, in its own st.columns cell (matching the [9, 1] split every
     content row already uses for its Edit button) rather than a 5th track
     inside the 4-column grid above, since that grid's own width only ever
     matched the 9-fraction content column, not the Edit button's column. */
  .cp-list-head-edit{background:#f1efe4;font-size:11px;font-weight:700;letter-spacing:0.8px;
    text-transform:uppercase;color:#6B6B6B;padding:12px 22px;text-align:left;height:100%;
    display:flex;align-items:center;}
  .cp-list-row-html{display:grid;grid-template-columns:1.4fr 1.8fr 1fr 1fr;gap:16px;align-items:center;
    padding:14px 22px;border-bottom:1px solid #f1efe4;}
  /* Field labels (Name/Email/Category/Status) exist in the markup for the
     mobile stacked-card layout below, where .cp-list-head's column headers
     no longer apply. On desktop the grid header already labels each column,
     so the inline label would just duplicate it next to every value -
     hidden here by default, switched back on for the mobile breakpoint. */
  .cp-field-label{display:none;}
  .cp-rname{font-weight:700;color:#040404;font-size:14px;}
  .cp-remail{color:#6B6B6B;font-size:13px;overflow-wrap:anywhere;}
  .cp-cat-chip{display:inline-block;font-size:11.5px;font-weight:700;padding:4px 10px;border-radius:14px;
    background:#e7ebe3;color:#183319;width:fit-content;}
  .cp-invited{background:#e7ebe3;color:#183319;}
  .cp-notsent{background:#f0f0ee;color:#6B6B6B;}
  .cp-send-bar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;
    background:#f1efe4;border:1px solid #DCD8C0;border-radius:12px;padding:16px 22px;margin-top:18px;}
  .cp-send-bar .cp-msg{font-size:14px;color:#040404;}
  .cp-send-bar .cp-msg b{color:#183319;}

  /* Guidelines */
  .cp-cat-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;
    padding:26px 28px;margin-bottom:18px;position:relative;overflow:hidden;}
  .cp-cat-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
    background:var(--cp-accent,#183319);}
  /* flex-wrap added 2026-08-27: the badge text grew considerably in the
     "Final Category Guidance Copy" pass (e.g. Others' badge went from
     "Minimum 3, ideally 4 or 5" to "...up to 10 if needed" appended), and
     at narrow widths the row no longer had room for both the title and
     the (white-space:nowrap) badge on one line. Confirmed live at 430px:
     the badge's own measured right edge sat past the card's right edge
     despite the card's overflow:hidden, while the title got squeezed
     into an unreadable "Ot/he/rs" - a flex row with no wrap forces BOTH
     children to fight for space when together they exceed it, and a
     nowrap child can't shrink to help. Wrapping lets the badge drop to
     its own line below the title instead, so neither is squeezed. */
  .cp-cat-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;gap:12px;
    flex-wrap:wrap;}
  .cp-cat-top h2{font-size:18px;margin:0;color:#040404;font-weight:700;}
  /* white-space:nowrap dropped 2026-08-27: at 360px even the badge ALONE
     on its own row (after the cp-cat-top flex-wrap fix above) was still
     wider than the card - Others' longest badge text has nowhere left to
     shrink to if it can't wrap internally too. Plain wrapping (the
     default) still renders as a single line whenever there's room, so
     this doesn't change how the shorter Boss/Peers/DRs badges look at
     any width that already worked. */
  .cp-req-badge{font-size:12px;font-weight:700;padding:5px 12px;border-radius:20px;
    background:#e7ebe3;color:#183319;max-width:100%;}
  .cp-cat-card p{font-size:14px;line-height:1.6;color:#3D3D3D;margin:0 0 12px;}
  .cp-cat-card .cp-tip{font-size:13px;color:#6B6B6B;background:#f1efe4;border-radius:8px;
    padding:10px 14px;margin-top:8px;}
  .cp-cat-card .cp-tip b{color:#040404;}
  .cp-note-card{margin-top:26px;background:#183319;border-radius:12px;padding:24px 28px;color:#FFFFFF;}
  .cp-note-card b{display:block;font-size:15px;margin-bottom:8px;}
  .cp-note-card p{font-size:13.5px;line-height:1.6;color:#DCD8C0;margin:0;}

  /* Begin Here / Help */
  .cp-eyebrow{font-size:12px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;
    color:#183319;margin-bottom:10px;}
  .cp-page-head.cp-begin-here p{max-width:600px;}
  .cp-step{display:flex;gap:20px;margin-bottom:28px;}
  .cp-step-num{flex-shrink:0;width:34px;height:34px;border-radius:50%;background:#183319;color:#FFFFFF;
    display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;}
  /* Direct-child combinator, deliberately - a descendant selector here
     (.cp-step-body b) would also match the <b> nested inside .cp-sub-note
     below (sub-note sits inside .cp-step-body too), forcing THAT bold text
     onto its own block line and breaking its sentence out of the
     surrounding paragraph flow. Found live: "Upload a CSV instead" was
     rendering as an isolated bold line instead of inline mid-sentence. */
  .cp-step-body > b{display:block;font-size:15.5px;color:#040404;margin-bottom:6px;}
  .cp-step-body p{margin:0;font-size:14px;line-height:1.65;color:#3D3D3D;}
  .cp-sub-note{margin-top:10px;font-size:13px;color:#6B6B6B;background:#f1efe4;
    border-radius:8px;padding:10px 14px;line-height:1.5;}
  .cp-sub-note b{display:inline;color:#040404;}
  .cp-inline-link{color:#183319;font-weight:700;text-decoration:none;}
  .cp-divider{height:1px;background:#DCD8C0;margin:36px 0;}
  .cp-watch-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;
    padding:24px 26px;margin-bottom:16px;}
  .cp-watch-card b{display:block;font-size:15px;color:#040404;margin-bottom:14px;}
  .cp-watch-item{display:flex;gap:12px;margin-bottom:12px;font-size:13.5px;line-height:1.55;color:#3D3D3D;}
  .cp-watch-item:last-child{margin-bottom:0;}
  .cp-dot{flex-shrink:0;width:6px;height:6px;border-radius:50%;background:#183319;margin-top:7px;}
  .cp-closing{margin-top:40px;background:#183319;border-radius:12px;padding:22px 26px;color:#FFFFFF;
    font-size:13.5px;line-height:1.6;}
  .cp-closing b{color:#DCD8C0;}

  /* Streamlit buttons reskinned to match the mockups' .btn family. Two
     namespaces via container key, same pattern already established
     elsewhere in this app (see app.py's button-contrast section): never
     set colour without background, per that section's rule.

     REAL BUG FOUND LIVE: setting `color` on the <button> element alone
     wasn't enough - the button's own theme colour (Bentley green) is set
     explicitly on the inner <p> Streamlit wraps the label in
     (stMarkdownContainer p), not just inherited from the button, so it
     beat the button-level override regardless of !important (inheritance
     always loses to an explicit rule on the element itself, !important or
     not). "Send pending invitations" rendered as dark-green-on-dark-green,
     invisible. Fixed the same way app.py's segmented-control fix already
     does it elsewhere in this app: also target `button *` explicitly, not
     just `button`. */
  div[class*="st-key-cp_primary_"] button,
  div[class*="st-key-cp_primary_"] button *{
    color:#FFFFFF !important;
  }
  div[class*="st-key-cp_primary_"] button{
    background:#183319 !important;border:none !important;
    border-radius:8px !important;font-weight:600 !important;
  }
  div[class*="st-key-cp_primary_"] button:disabled,
  div[class*="st-key-cp_primary_"] button:disabled *{
    color:#F0F0EE !important;
  }
  div[class*="st-key-cp_primary_"] button:disabled{
    background:#9AA79B !important;
  }
  div[class*="st-key-cp_secondary_"] button,
  div[class*="st-key-cp_secondary_"] button *{
    color:#183319 !important;
  }
  div[class*="st-key-cp_secondary_"] button{
    background:#FFFFFF !important;border:1.5px solid #DCD8C0 !important;
    border-radius:8px !important;font-weight:600 !important;
  }
  div[class*="st-key-cp_secondary_"] button:disabled,
  div[class*="st-key-cp_secondary_"] button:disabled *{
    color:#9A9A9A !important;
  }
  div[class*="st-key-cp_secondary_"] button:disabled{
    background:#F5F4EE !important;border-color:#E5E3D8 !important;
  }
  div[class*="st-key-cp_ghost_"] button,
  div[class*="st-key-cp_ghost_"] button *{
    color:#183319 !important;
  }
  div[class*="st-key-cp_ghost_"] button{
    background:none !important;border:none !important;font-weight:700 !important;
  }

  /* Add-a-rater form fields, restyled to the card look above (same pattern
     already used in app.py for this form's old layout, reapplied here since
     this file now owns its own scoped stylesheet for the redesign). */
  div[class*="st-key-cp_add_card"] div[data-testid="stTextInputRootElement"],
  div[class*="st-key-cp_add_card"] div[data-testid="stTextInputRootElement"] div{
    background-color:#FFFFFF;
  }
  div[class*="st-key-cp_add_card"] div[data-testid="stTextInputRootElement"]{
    border:1px solid #DCD8C0;
  }
  div[class*="st-key-cp_add_card"] div[data-baseweb="select"] > div,
  div[class*="st-key-cp_add_card"] [data-testid="stSelectbox"] [role="group"]{
    background-color:#FFFFFF;
  }

  /* ===================== MOBILE ======================
     Same real-width-sweep discipline as the feedback form's rating-scale
     fix (see app.py) - checked at ~360/430/600px, not assumed. Card grids
     collapse to a single column; the nominated-raters list (the highest-
     risk element per CLAUDE.md's redesign notes - a 4-column row can't
     realistically stay one row on a phone) switches from a CSS grid table
     to stacked cards with visible field labels, never a horizontal scroll
     or truncated columns. */
  @media (max-width: 700px){
    /* Topbar row 1 (brand/account) is plain flex HTML, not st.columns, so
       it needs its own explicit stacking rule at mobile widths - unlike
       row 2 (nav), which is still real st.columns and Streamlit stacks
       that vertically on its own below its internal breakpoint. This just
       tightens the padding/margins on both so neither inherits the
       desktop bar's wide side padding. */
    div[class*="st-key-cp_topbar"] > div{padding:14px 16px;}
    .cp-topbar-row1{flex-direction:column;align-items:flex-start;gap:10px;}
    div[class*="st-key-cp_topbar_row2"]{margin-top:10px;padding-top:10px;}
    div[class*="st-key-cp_nav_"] button{justify-content:center !important;}
    .cp-account{justify-content:flex-start;}
    .cp-status-grid{grid-template-columns:1fr;}
    .cp-stats-strip{grid-template-columns:1fr 1fr;}
    .cp-stat-block{border-right:none !important;border-bottom:1px solid rgba(255,255,255,0.14);}
    .cp-progress-head{flex-direction:column;align-items:flex-start;gap:10px;}
    .cp-reminder-note{text-align:left;}

    /* Nominated list: grid -> stacked cards. Each row becomes its own
       bordered block with labelled fields instead of a 4-column row. */
    .cp-list-head{display:none;}
    .cp-list-row-html{
      display:block;padding:14px 16px;border-bottom:8px solid #F7F6F1;background:#FFFFFF;
    }
    .cp-list-row-html > *{display:block;margin-bottom:6px;}
    .cp-list-row-html .cp-field-label{
      display:block;font-size:10px;font-weight:700;letter-spacing:0.6px;text-transform:uppercase;
      color:#9A9A9A;margin-bottom:2px;
    }
  }
</style>
"""

# Bentley typeface, prepended here rather than interpolated into the huge
# constant above. PORTAL_CSS above is a PLAIN (non-f) string, deliberately -
# it's ~1500 lines of CSS full of {..} rule braces, and turning it into an
# f-string to splice this in would mean escaping every single one of them,
# fragile and easy to get wrong for no real benefit. This block is small
# and built fresh instead, then concatenated on front.
#
# Scope: font-face declarations (see get_bentley_font_face_css - only Light
# 300/Regular 400 exist as real cuts, no 700 declared, see that function's
# docstring for why that matters) plus overriding font-family on the same
# selectors app.py's global stylesheet sets 'Source Sans Pro' on for this
# app's headings/buttons (bare h1-h3, the four button-variant testids).
# Matching those exact selectors, adding !important, and relying on this
# <style> block landing LATER in the page than app.py's (app.py's runs at
# import time, before render_leader_portal is ever called) is what makes
# this win without touching app.py's shared rule at all - which the Admin
# Dashboard also depends on, and is explicitly out of scope here. Because
# this only ever gets injected from within render_leader_portal, Admin
# Dashboard page loads (which never call into this file) never receive
# this stylesheet regardless of how broad these selectors look in
# isolation - there's no DOM-level scoping trick needed, just never
# rendering it there.
PORTAL_CSS = f"""
<style>
{get_bentley_font_face_css()}
{get_bentley_logotype_face_css()}
/* EVERY TEXT INSTANCE, 2026-08-27 - widened from an earlier pass that only
   targeted h1-h3, the button testids, and a hand-picked "cp-*" wildcard.
   Caught live: a Streamlit BUTTON element picking up font-family:Bentley
   (from the old button[data-testid=...] rule) does NOT mean its own label
   text does too - Streamlit renders that label as a <p> inside a nested
   <div data-testid="stMarkdownContainer">, and font-family only inherits
   DOWN through ancestors that don't set their own value; Streamlit's own
   built-in stylesheet sets an explicit (non-!important) font-family
   directly on that inner <p>, which breaks the inheritance chain from the
   button. Same story for widget labels, captions, input/textarea text,
   checkbox/radio/segmented-control option text - none of it is h1-h3, a
   button element itself, or a "cp-*" class, so none of it was ever
   actually reached by the earlier pass, confirmed live via
   getComputedStyle showing "Source Sans" (Streamlit's own built-in default,
   a different font from the Google-Fonts "Source Sans Pro" app.py imports
   for its own classes) on a button's inner <p> despite the button itself
   correctly showing Bentley.
   Fixed properly this time with a genuinely universal rule instead of
   hand-listing selectors again (the exact trap the "cp-*" wildcard was
   already trying to avoid, just scoped too narrowly): `.stApp *` reaches
   every descendant of Streamlit's own root app container, so nothing new
   Streamlit renders internally (a fresh widget type, a nested markdown
   <p>) can silently fall outside it the way individual selectors already
   have twice. `!important` wins regardless of specificity against any
   Streamlit default that doesn't also use !important (framework defaults
   essentially never do), so this reliably overrides built-in widget
   styling without needing to out-specify it selector by selector.
   ONE REQUIRED EXCEPTION, checked before shipping this broadly: Material
   Symbols icons (every st.button(..., icon=":material/name:") call in
   this file - 6 of them) render by putting the literal icon NAME as text
   ("arrow_forward", "edit", "check_circle"...) inside a
   [data-testid="stIconMaterial"] span and mapping it to a glyph via the
   "Material Symbols Rounded" icon font specifically. A blanket
   font-family override would replace that icon font too, and the result
   is not a missing icon - it's the literal icon name rendering as
   readable text next to the button label (confirmed by reasoning through
   the actual DOM structure, matching the exact bug already documented and
   fixed once for this file's OWN _icon() helper's inline-style version -
   this is the same failure mode reaching a different, non-inline code
   path). The exception rule below restores the icon font specifically;
   it's declared AFTER the broad rule and matches it on specificity
   (a single attribute selector, same tier as ".stApp *"), so later-wins
   source order is what makes it take effect, not higher specificity.
   A THIRD instance of the SAME failure mode, found 2026-08-28 via a real
   screenshot (Ian spotted stray "histor" text bleeding into the "Welcome
   back!" resume banner in feedback_form.py, reproduced and traced here
   too since this file's st.info/st.warning/st.success/st.error calls hit
   the identical code path): Streamlit's own built-in alert icon (the one
   shown automatically next to st.info/st.warning/st.success/st.error, not
   an icon= parameter this file passes explicitly) renders the same way,
   inside [data-testid="stAlertDynamicIcon"] - a fourth Streamlit-internal
   icon element type this file's own icon audit hadn't enumerated, since
   it isn't created by an icon= call site to grep for. Added to the same
   exception rule below. */
.stApp, .stApp * {{
  font-family: {BENTLEY_FONT_STACK} !important;
}}
[data-testid="stIconMaterial"],
[data-testid="stAlertDynamicIcon"],
.cp-icon-glyph {{
  font-family: 'Material Symbols Rounded' !important;
}}
.cp-brand-text .cp-b1 {{
  font-family: 'Bentley Logotype', {BENTLEY_FONT_STACK} !important;
}}
</style>
""" + PORTAL_CSS


def _go_to_view(view):
    """
    Navigate within the same tab - the fix for the reported "every nav
    click opens a new tab" bug.

    ROOT CAUSE, confirmed live, not assumed: this file's own source never
    set target="_blank" anywhere - inspecting the actual rendered DOM
    showed Streamlit's markdown renderer force-injects
    target="_blank" rel="noopener noreferrer" onto EVERY <a> tag it
    renders through unsafe_allow_html, even a plain same-origin
    query-string link like href="?portal=...&view=...". A <script>-tag
    workaround (find those links and strip the attribute, or attach a
    same-tab click handler) was tried and confirmed NOT to work either -
    script tags inside unsafe_allow_html content never execute, which is
    standard browser behaviour for HTML injected via innerHTML, not a
    Streamlit-specific bug.

    The robust fix: stop using <a> tags for in-app navigation entirely.
    Every nav control in this file (topbar links, quick-action links,
    category-card links) now calls this instead of rendering a raw href -
    a real Streamlit rerun over the existing connection, which was never
    capable of opening a new tab in the first place.
    """
    st.query_params['view'] = view
    st.rerun()


def _scroll_to_top_if_view_changed(view):
    """Scroll the browser to the top of the viewport, but ONLY when the
    portal's active view has genuinely changed since the last time this ran
    - never on a rerun caused by something else on the same page (e.g. a
    widget interaction within Overview/Nominate that doesn't go through
    _go_to_view). ADDED 2026-08-29, extending the same fix already built for
    the feedback form's dimension-page pagination (see
    _scroll_to_top_if_page_changed in feedback_form.py) to this file - found
    live during a leader-portal walkthrough that every navigation action
    here (Begin Here -> Overview, into Guidelines, any topbar nav item)
    left scroll position wherever it was on the previous page instead of
    landing at the top of the new one.

    Reuses the exact mechanism already proven correct in feedback_form.py,
    including the two real bugs found getting it working there (see that
    function's own docstring for the full story - not re-explained here):
    - Uses `el.scrollTop = 0`, not `el.scrollTo({...})`, since the options-
      object form was confirmed unreliable in this cross-frame context.
    - Embeds `view` into the iframe's HTML content (as a comment) so the
      content genuinely differs on every real navigation - Streamlit
      otherwise treats a repeated st.iframe call with byte-identical
      content as the same element and never reloads it, so the <script>
      would only ever execute on its first mount in a browser session.
    - Targets `[data-testid="stMain"]`, this app's real scrollable
      container, not `window`.

    Call this AFTER the new view's own content has rendered, not before -
    the feedback-form version of this fix caused a genuine, reproducible
    server crash when it fired ahead of the page's own dispatch block, on
    a specific page-to-page transition. render_leader_portal's dispatch
    already renders each view's content before this is called, so the same
    ordering is preserved here.
    """
    if st.session_state.get('_scrolled_to_view') == view:
        return
    st.session_state['_scrolled_to_view'] = view
    st.iframe(
        f"""<!-- view {view} -->
        <script>
        function scrollMainToTop() {{
            var el = window.parent.document.querySelector('[data-testid="stMain"]');
            if (el) {{ el.scrollTop = 0; el.scrollLeft = 0; }}
        }}
        scrollMainToTop();
        [50, 100, 150].forEach(function(delay) {{
            setTimeout(scrollMainToTop, delay);
        }});
        </script>""",
        height=1,
    )


def _render_portal_topbar(leader_info, active_view=None, show_nav=True):
    """
    Shared header for every portal screen (and, without nav, the consent
    gate) - dark green bar, Bentley wing mark, page nav, account badge.

    TWO ROWS, not one - changed 2026-08-27 at the human's suggestion, to
    fix a real bug: with brand/nav/account sharing one row (a 3-column
    split, nav getting only the middle 5.4/8.6 of the width), nav buttons
    had comfortable room at the ~902px width the row was tuned against,
    but at ~650-750px - a window Streamlit's own native column-stacking
    breakpoint (~640px) doesn't yet cover - the nav column shrank enough
    that "Nominate Raters" (white-space:nowrap, per the 4th-nav-item fix
    below) visibly overflowed its own button and collided with the next
    one. Splitting removes the actual constraint rather than relocating
    it: nav now gets the row to itself, so it has roughly 1.6x the room
    at any given width and never needs to compress in that gap. Row 1
    (brand left, account right) is plain flex HTML, not st.columns -
    neither element is interactive, so there was no need for real
    Streamlit columns there at all. Bonus fix that came free with this:
    the brand text ("Bentley Compass 360 / Your Leadership Portal") no
    longer competes with nav+account for row width, so it stops wrapping
    to three lines at 768-902px (flagged but not fixed in the prior pass).

    Nav items are real st.button() calls wired to _go_to_view, not <a>
    tags (see that function's docstring for why) - styled via the
    cp_nav_/cp_nav_active_ container-key CSS below to read as plain text
    links inside the green bar, not boxed buttons.

    The mockup's plain green-circle "B" badge is replaced with the real
    Bentley wing mark per the human's instruction, negative (white) variant
    since it sits on the dark green bar - the positive variant would be
    invisible there.
    """
    logo_uri = get_logo_data_uri(negative=True)
    # Fallback only fires if the logo asset is genuinely missing from disk -
    # styled to stay legible on its own (no circle to lean on any more)
    # rather than a bare unstyled "B".
    mark_inner = (f'<img src="{logo_uri}" alt="">' if logo_uri
                  else '<span style="color:#DCD8C0;font-weight:700;font-size:22px;">B</span>')

    account_html = ""
    if show_nav:
        account_html = f"""
          <div class="cp-account">
            <div class="cp-avatar">{_esc(_initials(leader_info.get('name')))}</div>
            <div class="cp-name">{_esc(leader_info.get('name'))}</div>
          </div>
        """

    with st.container(key="cp_topbar"):
        with st.container(key="cp_topbar_row1"):
            _md(f"""
            <div class="cp-topbar-row1">
              <div class="cp-brand">
                <div class="cp-brand-mark">{mark_inner}</div>
                <div class="cp-brand-text">
                  <div class="cp-b1">Bentley Compass 360</div>
                  <div class="cp-b2">Your Leadership Portal</div>
                </div>
              </div>
              {account_html}
            </div>
            """)

        if show_nav:
            views = [('overview', 'Overview'), ('nominate', 'Nominate Raters'),
                     ('guidelines', 'Guidelines'), ('help', 'Help')]
            with st.container(key="cp_topbar_row2"):
                nav_cols = st.columns(len(views), gap="small", vertical_alignment="center")
                for (key, label), col in zip(views, nav_cols):
                    with col:
                        active = key == active_view
                        with st.container(key=f"cp_nav_{'active_' if active else ''}{key}"):
                            if st.button(label, key=f"cp_nav_btn_{key}", use_container_width=True):
                                _go_to_view(key)


def render_leader_consent_gate(db, leader_info):
    """One-time data-protection consent screen, shown on the leader's first
    portal visit, before their welcome/status header or any nomination tab.
    Gated on leaders.consent_given, checked from the database on every visit
    (never session state alone), so it is asked once and never again once
    given - same durability pattern as the rater-facing consent gate in
    feedback_form.py. Ticking the box is a distinct, deliberate action:
    portal entry is blocked until it's ticked, not just discouraged.

    Content differs from the rater version: the leader is consenting to
    their OWN assessment data and to raters being contacted on their behalf,
    not to submitting a single response, so it also covers their
    responsibility for nominating raters appropriately.
    """
    st.markdown(PORTAL_CSS, unsafe_allow_html=True)
    _render_portal_topbar(leader_info, show_nav=False)

    heading = _t(db, 'ui_leader_consent_heading', None, "Before you begin")
    own_data_explainer = _t(
        db, 'ui_consent_leader_body_1', None,
        "Your own Self-Assessment and Full 360 data is visible only to you, the programme "
        "administrator, and your coach, unless you choose to share your report further."
    )
    nomination_responsibility = _t(
        db, 'ui_consent_leader_body_2', None,
        "When you nominate raters, you're responsible for choosing people who can give you "
        "meaningful feedback (see the Guidelines tab for guidance on each category)."
    )
    rater_scrubbing_explainer = _t(
        db, 'ui_consent_leader_body_3', None,
        "Once your raters submit their feedback, their name and email are permanently scrubbed "
        "from the system, this can't be undone. You're welcome to tell them this directly when "
        "you send their invitations."
    )
    comments_warning = _t(
        db, 'ui_consent_leader_body_4', None,
        "Their comments are shown to you grouped with others' in the same category, word-for-word. "
        "Comments aren't protected by the anonymity threshold the way scores are, so anything "
        "specific or identifying a rater writes may be recognisable to you, even where their "
        "scores aren't."
    )
    # Softened 2026-08-23: the literal "[Retention statement to be
    # confirmed]" read as a bug during real GM self-assessment testing.
    # Still a placeholder pending the actual DPA-informed decision, just one
    # that doesn't look broken while it's pending.
    retention_note = _t(
        db, 'ui_consent_retention', None,
        "We're still finalising our data retention timeline with Bentley."
    )

    _md(f"""
    <div style="max-width:1240px; margin:32px auto 0; padding:0 40px;">
    <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #E2E0D8; margin-bottom: 1.5rem;">
        <h3 style="margin: 0 0 0.8rem 0; color: #183319;">{heading}</h3>
        <ul style="margin: 0; padding-left: 1.2rem; color: #333; line-height: 1.7;">
            <li>{own_data_explainer}</li>
            <li>{nomination_responsibility}</li>
            <li>{rater_scrubbing_explainer}</li>
            <li>{comments_warning}</li>
        </ul>
        <p style="margin: 0.9rem 0 0 0; color: #B45309; font-style: italic; font-size: 0.85rem;">
            {retention_note}
        </p>
    </div>
    </div>
    """)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        checkbox_label = _t(
            db, 'ui_leader_consent_checkbox_label', None,
            "I understand how my feedback and my raters' feedback will be used and stored."
        )
        consented = st.checkbox(checkbox_label, value=False, key="leader_consent_checkbox")

        if st.button(
            _t(db, 'ui_button_continue', None, "Continue"),
            type="primary", icon=":material/arrow_forward:", use_container_width=True,
            disabled=not consented,
        ):
            db.set_leader_consent(leader_info['id'])
            st.session_state['leader_consent_given'] = True
            st.rerun()


def render_leader_portal(db, leader_info):
    """Route to the three portal screens by ?view=, after two one-time
    gates: consent, then Begin Here. Each screen is its own full render
    (matching the concept mockups, which are three separate HTML pages),
    not a client-side tab switch - simpler and avoids extra state
    machinery for what's fundamentally page navigation.

    Gate order is consent first, then Begin Here (the human's explicit
    call 2026-08-27: consent is the more important of the two). Both are
    checked from the database, never session state alone, so each is
    shown once and never forced again - same durability discipline as the
    locale picker and the rater-facing consent gate in feedback_form.py.
    """

    leader_id = leader_info['id']

    if not leader_info.get('consent_given') and not st.session_state.get('leader_consent_given'):
        render_leader_consent_gate(db, leader_info)
        return

    st.markdown(PORTAL_CSS, unsafe_allow_html=True)

    # Begin Here shown once, immediately after consent, before whatever
    # view the leader was actually headed for - deliberately unconditional
    # on the `view` query param (a leader landing on a deep link they
    # hadn't visited before still needs the onboarding first, same as
    # consent does). Marked seen the moment it's shown, not gated behind a
    # specific button click - unlike consent there's nothing to actively
    # agree to here, so "shown once" is the whole requirement. Reachable
    # afterwards, indefinitely, via Help in the nav (render_portal_begin_here
    # itself is unchanged - this reuses it, it doesn't duplicate it).
    if not leader_info.get('begin_here_seen_at') and not st.session_state.get('leader_begin_here_seen'):
        db.set_leader_begin_here_seen(leader_id)
        st.session_state['leader_begin_here_seen'] = True
        _render_portal_topbar(leader_info, active_view='help', show_nav=True)
        st.markdown('<div style="max-width:1240px; margin:0 auto; padding:0 40px 60px;">',
                    unsafe_allow_html=True)
        render_portal_begin_here()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    view = st.query_params.get('view', 'overview')
    if view not in ('overview', 'nominate', 'guidelines', 'help'):
        view = 'overview'

    _render_portal_topbar(leader_info, active_view=view, show_nav=True)

    raters = db.get_raters_for_leader(leader_id)
    self_rater = next((r for r in raters if r['relationship'] == 'Self'), None)
    other_raters = [r for r in raters if r['relationship'] != 'Self']

    st.markdown('<div style="max-width:1240px; margin:0 auto; padding:0 40px 60px;">', unsafe_allow_html=True)

    if view == 'nominate':
        render_portal_nominate(db, leader_info, other_raters)
    elif view == 'guidelines':
        render_portal_guidelines()
    elif view == 'help':
        render_portal_begin_here()
    else:
        render_portal_overview(db, leader_info, self_rater, other_raters)

    st.markdown('</div>', unsafe_allow_html=True)

    # Fires after the view's own content above, not before - see
    # _scroll_to_top_if_view_changed's own docstring for why (the identical
    # ordering mistake caused a real crash the first time this pattern was
    # built, in feedback_form.py).
    _scroll_to_top_if_view_changed(view)


def render_portal_overview(db, leader_info, self_rater, other_raters):
    """Overview screen: status cards, "who to nominate" teaser, category
    ring cards, and the Your Progress stats strip + reminders control."""

    base_url = st.session_state.get('portal_base_url', get_app_base_url())

    # Computed once, here, and threaded through every element on this page
    # that touches response counts (the Full 360 status card, the reminder
    # note, the Send Reminders result, the stats strip) - a single source
    # of truth for the real numbers, so none of them can ever show a
    # different figure than another. This used to also be a single source
    # of truth for whether to SUPPRESS those numbers; that gating is gone
    # (see _progress_stats_safe), but the shared-computation architecture
    # stayed, since it's the right way to keep multiple UI elements in
    # agreement regardless of what they're agreeing ON.
    overview_stats = _progress_stats_safe(
        sum(1 for r in other_raters if r.get('completed')), len(other_raters)
    )

    head_col, add_col, send_col = st.columns([3, 1, 1.3])
    with head_col:
        _md(f"""
        <div class="cp-page-head">
          <h1>Welcome, {_esc(leader_info['name'])}</h1>
          <p>{_esc(leader_info.get('dealership', ''))} &middot; {_esc(leader_info.get('cohort', ''))}</p>
        </div>
        """)
    with add_col:
        st.markdown('<div style="margin-top:38px;"></div>', unsafe_allow_html=True)
        with st.container(key="cp_secondary_add_rater_link"):
            if st.button("+ Add a rater", use_container_width=True, key="cp_add_rater_link_btn"):
                _go_to_view('nominate')
    with send_col:
        st.markdown('<div style="margin-top:38px;"></div>', unsafe_allow_html=True)
        pending = db.get_raters_pending_invitation(leader_info['id']) if EMAIL_AVAILABLE else []
        with st.container(key="cp_primary_send_pending"):
            if st.button(f"Send pending invitations ({len(pending)})" if pending else "Send pending invitations",
                         disabled=not pending, use_container_width=True, key="cp_send_pending_btn"):
                _do_send_pending_invitations(db, leader_info, pending, base_url)
                st.rerun()

    # --- Status cards -----------------------------------------------------
    self_html = _self_status_card_html(self_rater)
    full360_html = _full360_status_card_html(other_raters, overview_stats)
    st.markdown(f'<div class="cp-status-grid">{self_html}{full360_html}</div>', unsafe_allow_html=True)

    # --- Who should you nominate? teaser -----------------------------------
    with st.container(key="cp_guide_card"):
        # This heading row carries its own horizontal padding
        # (cp_guide_heading_row) - the card itself no longer has any, so
        # the item row below shares the exact same width as the un-padded
        # category cards beneath it. See that row's CSS comment for why.
        with st.container(key="cp_guide_heading_row"):
            g_head_col, g_btn_col = st.columns([4, 1.5], vertical_alignment="center")
            with g_head_col:
                st.markdown('<b class="cp-g-head-title">Who should you nominate?</b>', unsafe_allow_html=True)
            with g_btn_col:
                with st.container(key="cp_secondary_open_guidelines"):
                    if st.button("Open full guidelines", use_container_width=True, key="cp_open_guidelines_btn"):
                        _go_to_view('guidelines')

        # REAL BUG FOUND LIVE, re-checked rather than assumed fixed: this
        # used to be a raw HTML grid (.cp-guide-list) with a hand-picked gap
        # matching what the category cards below USED to use before they
        # became real st.columns (a separate fix, for the clickable-card
        # requirement). Streamlit's own column gap ("medium") turned out to
        # be 32px, not the 18px this was still assuming - confirmed via
        # getBoundingClientRect on the live page, showing a growing drift
        # (1px/3px/7px/11px) across the four columns, not the clean
        # column-for-column alignment it looked like it should have. Fixed
        # by using the SAME st.columns(4, gap="medium") mechanism here as
        # the cards below use, so both rows are laid out by the identical
        # code path and can't silently drift apart again if Streamlit's own
        # gap value ever changes.
        #
        # No wrapping container/padding-cancellation trick needed here any
        # more - see the .cp-guide-item CSS comment for why an earlier
        # negative-margin attempt didn't work on a flex item, and why
        # removing the card's own horizontal padding (instead of fighting
        # it after the fact) is what actually fixed the alignment.
        guide_cols = st.columns(4, gap="medium")
        guide_items = [
            ("Boss", "Your direct line manager. One is enough."),
            ("Peers", "Colleagues at a similar level who see your day-to-day work."),
            ("Direct Reports", "People who report to you. Aim for a range of tenure."),
            ("Others", "Stakeholders or customers, if relevant to your role."),
        ]
        for (title, desc), col in zip(guide_items, guide_cols):
            with col:
                _md(f'<div class="cp-guide-item"><b>{_esc(title)}</b><span>{_esc(desc)}</span></div>')

    # --- Category ring cards ------------------------------------------------
    rater_counts = {'Boss': 0, 'Peers': 0, 'DRs': 0, 'Others': 0}
    for r in other_raters:
        if r['relationship'] in rater_counts:
            rater_counts[r['relationship']] += 1

    st.markdown('<div class="cp-section-label">Your raters, by category</div>', unsafe_allow_html=True)
    # Each card is a real link to Nominate Raters (issue: cards were
    # display-only with no way to act on a "3 more needed" chip). A plain
    # link to the page is the baseline shipped here - NOT deep-linked to
    # pre-select this category in the add-rater form, because that
    # dropdown deliberately has no default (see render_portal_nominate's
    # docstring: a leftover selection once caused a leader to add too many
    # Bosses) - pre-filling a category would undo that already-reasoned
    # safety choice, so the plain link is the right scope here, not a
    # corner cut for time.
    _render_category_cards_row(rater_counts, clickable=True)

    # --- Your Progress + Send reminders -------------------------------------
    incomplete = [r for r in other_raters if not r.get('completed')]
    any_eligible, hours_until_next = _reminder_cooldown_state(incomplete)
    email_configured = EMAIL_AVAILABLE and is_email_configured()

    # Wrapped in one container so the top margin applies to the WHOLE row,
    # not just prog_col1's own HTML - found live: margin-top on
    # .cp-progress-head only pushed the "Your progress" label down inside
    # its own column, while prog_col2's Send reminders button (a real
    # widget with no equivalent margin of its own) stayed flush against
    # the category cards above, so the row looked unevenly spaced/squashed
    # on desktop specifically (columns stack with normal gaps on mobile,
    # which is why this only showed up at desktop widths).
    with st.container(key="cp_progress_row"):
        prog_col1, prog_col2 = st.columns([3, 1.6])
        with prog_col1:
            st.markdown('<div class="cp-progress-head"><div class="cp-section-label">Your progress</div></div>',
                         unsafe_allow_html=True)
        with prog_col2:
            if other_raters and email_configured:
                disabled = not any_eligible
                with st.container(key="cp_secondary_send_reminders"):
                    if st.button("Send reminders", disabled=disabled, use_container_width=True,
                                 key="cp_send_reminders_btn"):
                        msg = _send_reminders_and_report(db, leader_info, incomplete, base_url)
                        st.session_state['cp_reminder_result'] = msg
                        st.rerun()
                if disabled and hours_until_next:
                    note = f"Available again in {round(hours_until_next)}h."
                elif incomplete:
                    note = f"Nudges the {len(incomplete)} who haven't responded yet."
                else:
                    note = "Everyone has responded."
                st.markdown(f'<div class="cp-reminder-note">{_esc(note)}</div>', unsafe_allow_html=True)

    if st.session_state.get('cp_reminder_result'):
        st.info(st.session_state.pop('cp_reminder_result'))

    stats = overview_stats
    if not other_raters:
        # Real zeros still render below (per the "always show the numbers,
        # don't hide them behind placeholder text" rule) - this is just a
        # short explanatory line alongside them, not a substitute for them.
        st.caption("Nominate your raters to start tracking responses.")
    _md(f"""
    <div class="cp-stats-strip">
      <div class="cp-stat-block"><div class="cp-num">{stats['invited']}</div><div class="cp-lbl">Raters invited</div></div>
      <div class="cp-stat-block"><div class="cp-num">{stats['responded']}</div><div class="cp-lbl">Responded</div></div>
      <div class="cp-stat-block"><div class="cp-num">{stats['rate']}%</div><div class="cp-lbl">Response rate</div></div>
      <div class="cp-stat-block"><div class="cp-num">{stats['outstanding']}</div><div class="cp-lbl">Still to respond</div></div>
    </div>
    """)


def _self_status_card_html(self_rater):
    if self_rater and self_rater.get('completed'):
        date_text = _format_completion_date(self_rater.get('completed_at'))
        subtitle = (f"Completed on {_esc(date_text)}, discussed at your Module 1 coaching session"
                    if date_text else "Discussed at your Module 1 coaching session")
        return _html(f"""
        <div class="cp-status-card cp-done">
          <div class="cp-status-left">
            <div class="cp-status-icon">{_icon('check', size=22)}</div>
            <div class="cp-status-text"><b>Self-Assessment complete</b><span>{subtitle}</span></div>
          </div>
        </div>
        """)
    return _html(f"""
    <div class="cp-status-card">
      <div class="cp-status-left">
        <div class="cp-status-icon">{_icon('radio_button_unchecked', size=22)}</div>
        <div class="cp-status-text"><b>Self-Assessment pending</b><span>Not yet completed</span></div>
      </div>
    </div>
    """)


def _full360_status_card_html(other_raters, stats):
    """`stats` is `_progress_stats_safe(...)`, computed ONCE by the caller
    (render_portal_overview) and threaded through here rather than
    recomputed - see that function's `overview_stats` for why: every
    response-count element on the page reads off the same value so none
    of them can independently drift out of sync with the others."""
    completed = sum(1 for r in other_raters if r.get('completed'))
    total = len(other_raters)
    if total == 0:
        return _html(f"""
        <div class="cp-status-card">
          <div class="cp-status-left">
            <div class="cp-status-icon">{_icon('schedule', size=22)}</div>
            <div class="cp-status-text"><b>Full 360 not started</b><span>Nominate your raters to begin</span></div>
          </div>
        </div>
        """)
    if completed == total:
        return _html(f"""
        <div class="cp-status-card cp-done">
          <div class="cp-status-left">
            <div class="cp-status-icon">{_icon('check', size=22)}</div>
            <div class="cp-status-text"><b>Full 360 complete</b><span>All responses received</span></div>
          </div>
        </div>
        """)
    subtitle = f"{stats['responded']} of {stats['invited']} responses received"
    pill = f'<span class="cp-pill">{stats["rate"]}%</span>'
    return _html(f"""
    <div class="cp-status-card">
      <div class="cp-status-left">
        <div class="cp-status-icon">{_icon('schedule', size=22)}</div>
        <div class="cp-status-text"><b>Full 360 in progress</b><span>{_esc(subtitle)}</span></div>
      </div>
      {pill}
    </div>
    """)


def _category_card_html(cat, count):
    req = RATER_REQUIREMENTS[cat]
    min_if_any = req.get('min_if_any')
    # REAL BUG FOUND while confirming this against a constructed 6-nominated
    # test (per the human's logic-check request 2026-08-27): the target used
    # to be hardcoded to the suggested/min_if_any/min number alone, with no
    # regard for whether the leader had actually gone past it - "suggested"
    # is not a cap (nothing stops nominating more, confirmed separately in
    # the add-rater form and CSV import, both of which check against the
    # real 'max', never 'suggested'), but the ring's own denominator didn't
    # know that. _ring_dashoffset already clamps the ARC itself to a full
    # circle past 100%, so the ring never visually overflowed - but the
    # LABEL still showed the stale target, e.g. "6/5" for 6 nominated Peers,
    # which reads as broken/capped even though the underlying data isn't.
    # Fixed by taking whichever is larger: a leader who goes past the
    # suggested number sees "6/6" (a correctly full, correctly labelled
    # ring), not "6/5".
    base_target = req.get('ring_target') or req['suggested'] or min_if_any or req['min'] or 1
    target = max(base_target, count)
    offset = _ring_dashoffset(count, target)

    if min_if_any and 0 < count < min_if_any:
        chip_cls, chip_text = 'cp-pending', f"{min_if_any - count} more needed"
    elif not req.get('required_nomination', True):
        chip_cls, chip_text = 'cp-met', ("Nominated" if count > 0 else "Not in use")
    elif count >= req['min']:
        chip_cls, chip_text = 'cp-met', "Requirement met"
    else:
        chip_cls, chip_text = 'cp-pending', f"{req['min'] - count} more needed"

    return _html(f"""
    <div class="cp-card" style="--cp-accent:{CATEGORY_ACCENT[cat]}">
      <div class="cp-card-top">
        <span class="cp-cat-label">{_esc(CATEGORY_CAPTION[cat])}</span>
        <div class="cp-ring">
          <svg width="60" height="60">
            <circle class="cp-ring-track" cx="30" cy="30" r="24" stroke-width="6" fill="none"/>
            <circle class="cp-ring-progress" cx="30" cy="30" r="24" stroke-width="6" fill="none"
              stroke-dasharray="150.8" stroke-dashoffset="{offset}"/>
          </svg>
          <div class="cp-ring-label">{count}{f"/{target}" if req['suggested'] or (min_if_any and count) else ""}</div>
        </div>
      </div>
      <h3>{_esc(RELATIONSHIP_TYPES.get(cat, cat))}</h3>
      <div class="cp-req">{CATEGORY_REQ_TEXT[cat]}</div>
      <div class="cp-card-foot"><span class="cp-status-chip {chip_cls}">{_esc(chip_text)}</span></div>
    </div>
    """)


def _render_category_cards_row(rater_counts, clickable):
    """
    The four rater-category cards, shared between Overview (clickable, its
    original home) and the top of Nominate Raters (read-only - added so a
    leader mid-nomination doesn't have to bounce back to Overview just to
    check category progress). Same data, same visual treatment; the
    difference is entirely the `clickable` flag, not two copies of this
    markup drifting apart from each other over time.

    Uses real st.columns(4, gap="medium") rather than a raw HTML grid -
    each card needed a real "Nominate" button under it (making the cards
    clickable was a separate fix), and that button has to be a real
    Streamlit widget, which can't live inside a markdown string.
    """
    cols = st.columns(4, gap="medium")
    for cat, col in zip(['Boss', 'Peers', 'DRs', 'Others'], cols):
        with col:
            _md(_category_card_html(cat, rater_counts[cat]))
            if clickable:
                with st.container(key=f"cp_secondary_cat_link_{cat}"):
                    if st.button("Nominate", icon=":material/arrow_forward:", use_container_width=True,
                                 key=f"cp_cat_link_btn_{cat}"):
                        _go_to_view('nominate')


def _do_send_pending_invitations(db, leader_info, pending, base_url):
    """Shared by the Overview quick-action button and the Nominate Raters
    send-bar - same action, same accuracy standard, so both entry points
    behave identically rather than drifting apart."""
    if not pending:
        return
    if not is_email_configured():
        st.session_state['cp_invite_result'] = (
            "error", "Email isn't configured for this deployment - invitations can't be sent right now."
        )
        return
    sent, failed_entries = 0, []
    for rater in pending:
        success, _ = send_rater_invitation(rater, leader_info['name'], base_url, db)
        if success:
            sent += 1
        else:
            failed_entries.append({'name': rater.get('name'), 'email': rater.get('email')})

    if failed_entries:
        failed = len(failed_entries)
        st.session_state['cp_invite_result'] = (
            "warning",
            f"Sent {sent} invitation{'s' if sent != 1 else ''}. {failed} failed to send - "
            f"check back or contact your programme coordinator."
        )
        send_invitation_failure_notice(leader_info, failed_entries, base_url, db)
    else:
        st.session_state['cp_invite_result'] = ("success", f"Sent {sent} invitation{'s' if sent != 1 else ''}.")


def _normalise_name(name):
    """Case-insensitive, trimmed comparison key for duplicate-name matching -
    the one definition both the manual add form and the CSV importer use
    below, so the two can't quietly drift on what counts as "the same
    name"."""
    return (name or '').strip().lower()


def _find_duplicate_name(raters, name):
    """Return the first rater dict in `raters` whose name matches `name`
    (case-insensitive, trimmed), across ANY category.

    ORIGINALLY same-category only (a Peer and a Direct Report sharing a
    name was treated as more likely two real people than a duplicate).
    REVERSED 2026-08-29, Ian's own call after seeing the feature live: a
    name reused under a DIFFERENT category might mean someone changed
    their mind about which group a nominee belongs in, or picked the wrong
    one the first time - worth a nudge too, not silently ignored. The
    caller (render_portal_nominate's submit handler, and
    _parse_rater_csv below) is responsible for comparing the match's own
    `relationship` against the new entry's to choose same-category vs
    cross-category wording - this function just finds the match.

    Severed raters (name/email nulled on completion) never match, since
    their normalised name is always the empty string.
    """
    target = _normalise_name(name)
    if not target:
        return None
    for r in raters:
        if _normalise_name(r.get('name')) == target:
            return r
    return None


def render_portal_nominate(db, leader_info, existing_raters):
    """Nominate Raters screen: add form + CSV import (functionally unchanged
    from before this redesign), then the nominated list and send-invitations
    bar in the new visual language.

    ONE DELIBERATE DEVIATION FROM THE CONCEPT MOCKUP: the mockup's list rows
    include a "Remove" action. This app does not offer self-serve removal
    (see CLAUDE.md, "Leader portal: sending an invitation is a separate,
    deliberate action..." section) - removing a non-responder changes no
    score or count, so a working Remove button here would just be a
    plausible-looking control with no real backing, and re-adding it
    contradicts a deliberate, already-reasoned decision this build wasn't
    asked to revisit. Only Edit (correct email/relationship) is offered,
    matching what the app has always allowed.
    """
    leader_id = leader_info['id']
    # The duplicate-name check (both here and inside CSV import) matches
    # against the ROSTER, not `existing_raters` - found live while testing:
    # every rater who has already responded is severed (name/email nulled),
    # so `existing_raters` alone goes blind to exactly the people most
    # likely to be "final" nominees. The roster survives severing by design
    # (see get_nomination_roster's own docstring) and is the same source
    # "People You've Nominated" already reads from for the identical reason.
    nomination_roster = db.get_nomination_roster(leader_id)
    base_url = st.session_state.get('portal_base_url', get_app_base_url())

    _md("""
    <div class="cp-page-head">
      <h1>Nominate Your Raters</h1>
      <p>Add the people you'd like feedback from. Nothing is sent until you're ready, review the
      full list below and click Send Invitations when it's complete.</p>
    </div>
    """)

    if inv_result := st.session_state.pop('cp_invite_result', None):
        level, msg = inv_result
        getattr(st, level)(msg)

    rater_counts = {'Boss': 0, 'Peers': 0, 'DRs': 0, 'Others': 0}
    for r in existing_raters:
        if r['relationship'] in rater_counts:
            rater_counts[r['relationship']] += 1

    # Read-only category cards, same data/treatment as Overview's - added so
    # a leader actively nominating doesn't have to bounce back to Overview
    # just to check category progress. NO "Nominate" link on these (unlike
    # Overview's): a self-referential link back to the page you're already
    # standing on adds nothing.
    st.markdown('<div class="cp-section-label">Your raters, by category</div>', unsafe_allow_html=True)
    _render_category_cards_row(rater_counts, clickable=False)

    _render_nomination_warnings(rater_counts)

    st.markdown('<div class="cp-section-label">Add a rater</div>', unsafe_allow_html=True)

    # Clears the add-rater form's own widgets on the run AFTER a genuine add
    # completes (either directly below, or via "Add anyway" further down) -
    # has to happen HERE, before those widgets are instantiated, since
    # Streamlit refuses to set a widget's session_state value once that
    # widget has already been created in the same run. clear_on_submit is
    # deliberately NOT used on the form any more (added 2026-08-29 for the
    # duplicate-name warning below): it would also clear the fields on a
    # duplicate-triggered submit, and Cancel needs those fields to still
    # show exactly what was typed, so a leader fixing a typo (e.g. the
    # email) doesn't have to retype the rest from scratch.
    if st.session_state.pop('_clear_add_rater_form', False):
        for key in ('add_rater_name', 'add_rater_email', 'add_rater_relationship'):
            st.session_state.pop(key, None)

    with st.container(key="cp_add_card"):
        with st.form("add_rater_form", clear_on_submit=False):
            col1, col2, col3, col4 = st.columns([1.3, 1.3, 1, 0.7])
            with col1:
                rater_name = st.text_input("Full name", key="add_rater_name", placeholder="e.g. Priya Anand")
            with col2:
                rater_email = st.text_input("Email address", key="add_rater_email", placeholder="e.g. priya.anand@bentley...")
            with col3:
                relationship = st.selectbox(
                    "Relationship", options=['Boss', 'Peers', 'DRs', 'Others'],
                    index=None, placeholder="Choose category...", key="add_rater_relationship",
                    format_func=lambda x: {
                        'Boss': 'Boss (Line Manager)', 'Peers': 'Peer',
                        'DRs': 'Direct Report', 'Others': 'Other'
                    }.get(x, x)
                )
            at_max = relationship is not None and rater_counts.get(relationship, 0) >= RATER_REQUIREMENTS[relationship]['max']
            with col4:
                st.markdown('<div style="height:1.6rem;"></div>', unsafe_allow_html=True)
                with st.container(key="cp_primary_add_rater"):
                    submitted = st.form_submit_button("+ Add", disabled=at_max, use_container_width=True)

            if at_max:
                st.caption(f"Maximum {RATER_REQUIREMENTS[relationship]['max']} {RELATIONSHIP_TYPES.get(relationship, relationship)} raters reached")

            if submitted:
                if not rater_name or not rater_email:
                    st.error("Please enter both name and email")
                elif '@' not in rater_email:
                    st.error("Please enter a valid email address")
                elif not relationship:
                    st.error("Please select a relationship")
                else:
                    duplicate = _find_duplicate_name(nomination_roster, rater_name)
                    if duplicate:
                        # PAUSE, DON'T BLOCK: hold the add for one explicit
                        # confirmation rather than refusing it outright - two
                        # genuinely different people can share a name, and a
                        # leader who's sure it's fine shouldn't be prevented
                        # from proceeding. Checks across ALL categories now
                        # (Ian's own reversal, 2026-08-29, of the original
                        # same-category-only design) - see
                        # _find_duplicate_name's own docstring for why.
                        st.session_state['pending_duplicate_add'] = {
                            'name': rater_name, 'email': rater_email, 'relationship': relationship,
                            'existing_relationship': duplicate.get('relationship'),
                        }
                    else:
                        db.add_rater(leader_id, relationship, rater_name, rater_email)
                        db.add_to_nomination_roster(leader_id, rater_name, rater_email, relationship)
                        st.session_state.pop('pending_duplicate_add', None)
                        st.session_state['_clear_add_rater_form'] = True
                        st.success(f"Added {rater_name}. Check the details below, then send their invitation when you're ready.")
                        st.rerun()

        pending = st.session_state.get('pending_duplicate_add')
        if pending:
            # Same-category and cross-category collisions get different
            # copy (added 2026-08-29 alongside the cross-category check
            # itself): a same-category repeat is most likely a genuine
            # accidental re-add, but a cross-category match more often
            # means the leader changed their mind about which group a
            # nominee belongs in, or picked the wrong one first time - so
            # it points at the Edit flow on the existing entry instead of
            # assuming a new person is intended.
            existing_label = RELATIONSHIP_TYPES.get(
                pending['existing_relationship'], pending['existing_relationship']
            )
            same_category = pending['existing_relationship'] == pending['relationship']
            if same_category:
                warning_text = (
                    f"There's already a {existing_label} called {pending['name']} on your "
                    f"list. Add this one anyway?"
                )
            else:
                warning_text = (
                    f"There's already a {existing_label} called {pending['name']} on your "
                    f"list, under a different category. If this is the same person but you "
                    f"need to change their category, you can edit them in People You've "
                    f"Nominated below instead of adding a new entry. Add this one anyway?"
                )
            with st.container(key="cp_duplicate_warning"):
                st.warning(warning_text)
                wcol1, wcol2 = st.columns(2)
                with wcol1:
                    if st.button("Add anyway", key="confirm_duplicate_add", type="primary", use_container_width=True):
                        db.add_rater(leader_id, pending['relationship'], pending['name'], pending['email'])
                        db.add_to_nomination_roster(leader_id, pending['name'], pending['email'], pending['relationship'])
                        st.session_state.pop('pending_duplicate_add', None)
                        st.session_state['_clear_add_rater_form'] = True
                        st.success(f"Added {pending['name']}. Check the details below, then send their invitation when you're ready.")
                        st.rerun()
                with wcol2:
                    # Deliberately does NOT clear add_rater_name/email/
                    # relationship - the whole point of Cancel is that someone
                    # can fix a typo (e.g. the email) without retyping
                    # everything from scratch.
                    if st.button("Cancel", key="cancel_duplicate_add", use_container_width=True):
                        st.session_state.pop('pending_duplicate_add', None)
                        st.rerun()

        show_csv = st.session_state.get('cp_show_csv', False)
        with st.container(key="cp_ghost_csv_toggle"):
            if st.button(("Hide CSV upload" if show_csv else "Adding several at once? Upload a CSV instead"),
                         icon=":material/description:", key="cp_csv_toggle_btn"):
                st.session_state['cp_show_csv'] = not show_csv
                st.rerun()

        if show_csv:
            _render_csv_import(db, leader_id, existing_raters, nomination_roster)

    st.markdown('<div class="cp-section-label">People you\'ve nominated</div>', unsafe_allow_html=True)
    _render_nominated_list_new(db, leader_info, base_url)


def _render_nomination_warnings(rater_counts):
    """Thin-group and at-risk-group guidance, kept from the pre-redesign
    version — the concept mockup doesn't show these states, but they're
    real, already-reasoned anonymity guidance (see CLAUDE.md's "thin-Others
    hole" section) that belongs where a leader can act on it: while they're
    actively nominating, not just on Overview's summary cards."""
    thin_optional_groups = []
    at_risk_groups = []
    for cat in ['Boss', 'Peers', 'DRs', 'Others']:
        req = RATER_REQUIREMENTS[cat]
        count = rater_counts[cat]
        min_if_any = req.get('min_if_any')
        if min_if_any and 0 < count < min_if_any:
            thin_optional_groups.append((cat, count, min_if_any))
        elif req.get('required_nomination', True) and count >= req['min']:
            if cat in ('Peers', 'DRs') and count == ANONYMITY_THRESHOLD:
                at_risk_groups.append((cat, count))
        elif not req.get('required_nomination', True) and min_if_any and count == min_if_any:
            at_risk_groups.append((cat, count))

    for cat, count, needed in thin_optional_groups:
        label = RELATIONSHIP_TYPES.get(cat, cat)
        st.warning(
            f"You've nominated {count} under **{label}**, which isn't enough to "
            f"report as its own group. Their responses won't be lost — with fewer "
            f"than {needed}, a thin {label} group gets folded into your Peers or "
            f"Direct Reports group instead, so nobody's individual view stands out. "
            f"But it does mean their perspective as {label} won't show up on its "
            f"own in the report. Either take it to {needed} or more, or remove "
            f"them and use whichever other category genuinely fits."
        )

    fold_target_text = {'Peers': 'Others', 'DRs': 'Others', 'Others': 'Peers or Direct Reports'}
    for cat, count in at_risk_groups:
        label = RELATIONSHIP_TYPES.get(cat, cat)
        fold_target = fold_target_text.get(cat, 'another group')
        if cat == 'Others':
            # Others' upfront copy (CATEGORY_REQ_TEXT, GUIDELINE_CATEGORIES)
            # already says "Minimum 3, ideally 4 or 5 if you have them, up
            # to 10 if needed" - this warning fires at exactly 3, so it
            # must read as a REMINDER
            # of that, not as new information sprung on the leader right
            # after they did what they were told. See the human's logic
            # check 2026-08-27: the old wording (shared with Peers/DRs
            # below) presented the buffer suggestion as if for the first
            # time, which read as a gotcha against Others' old "Add at
            # least 3" copy that never mentioned one.
            st.info(
                f"You've nominated exactly {count} under **Others** — as mentioned "
                f"when you were adding raters, it's worth having one or two more as "
                f"cover if you can. That's because if even one of them doesn't "
                f"respond, the group drops below the minimum needed to report "
                f"Others on its own; their responses won't be lost, but they'd get "
                f"folded into your Peers or Direct Reports group instead."
            )
        else:
            st.info(
                f"You've nominated exactly {count} under **{label}**, which is the "
                f"minimum needed to report that group on its own. If even one of them "
                f"doesn't respond it drops below the minimum — their responses won't "
                f"be lost, but they'd get folded into your {fold_target} "
                f"group rather than showing up as {label} in their own right. Worth "
                f"adding one or two more as cover."
            )


def _render_csv_import(db, leader_id, existing_raters, nomination_roster):
    template_df = pd.DataFrame({
        'name': ['Jane Smith', 'Tom Brown', 'Sarah Jones', 'Raj Patel'],
        'email': ['jane@company.com', 'tom@company.com', 'sarah@company.com', 'raj@company.com'],
        'relationship': ['Line Manager', 'Peer', 'Direct Report', 'Other'],
    })
    st.download_button("Download Template", template_df.to_csv(index=False), "rater_template.csv", "text/csv")
    st.caption(f"Columns: name, email, relationship. Relationship accepts {RELATIONSHIP_INPUT_HELP} — capitalisation doesn't matter.")

    csv_uploader_key = f"rater_csv_uploader_{st.session_state.get('rater_csv_upload_count', 0)}"
    uploaded_file = st.file_uploader("Upload CSV", type="csv", key=csv_uploader_key)

    if uploaded_file:
        try:
            import_df = pd.read_csv(uploaded_file)
            rows, problems, warnings = _parse_rater_csv(import_df, existing_raters, nomination_roster)
            for problem in problems:
                st.error(problem)
            if rows:
                preview = pd.DataFrame([
                    {'name': r['name'], 'email': r['email'],
                     'relationship': RELATIONSHIP_TYPES.get(r['relationship'], r['relationship'])}
                    for r in rows
                ])
                st.success(f"Ready to import {len(rows)} {'person' if len(rows) == 1 else 'people'}")
                st.dataframe(preview, use_container_width=True, hide_index=True)
                # Non-blocking: these are duplicate-name-within-category
                # nudges (see _parse_rater_csv's own docstring), never a
                # reason to withhold the import - Import All below stays
                # fully enabled regardless of how many of these show.
                for warning in warnings:
                    st.warning(warning)
                with st.container(key="cp_primary_import_csv"):
                    if st.button("Import All", use_container_width=True, key="cp_import_csv_btn"):
                        for r in rows:
                            db.add_rater(leader_id, r['relationship'], r['name'], r['email'])
                            db.add_to_nomination_roster(leader_id, r['name'], r['email'], r['relationship'])
                        st.success(f"Imported {len(rows)} {'person' if len(rows) == 1 else 'people'}. "
                                   f"Check the details below, then send invitations when you're ready.")
                        st.session_state['rater_csv_upload_count'] = st.session_state.get('rater_csv_upload_count', 0) + 1
                        st.session_state['cp_show_csv'] = False
                        st.rerun()
            elif not problems:
                st.warning("That file didn't contain any rows to import.")
        except Exception as e:
            st.error(f"Could not read that CSV: {str(e)}")


def _render_nominated_list_new(db, leader_info, base_url):
    """
    List who the leader has nominated, restyled to the concept mockup's list
    layout. Reads from leaders.nomination_roster, not `raters` — see the
    original render_nominated_list's docstring (preserved in spirit here):
    identity severing nulls raters.name/email at submission, so sourcing
    from `raters` would blank out exactly the people who responded.

    STATUS COLUMN IS "Invited" / "Not yet sent" ONLY — this is the anonymity
    rule from CLAUDE.md section 1, applied here as actual logic, not just a
    style choice. It reflects the LEADER's own action (have they sent the
    invitation), sourced from get_raters_pending_invitation, never whether
    the rater has responded.
    """
    roster = db.get_nomination_roster(leader_info['id'])
    if not roster:
        st.info("You haven't nominated any raters yet.")
        return

    st.caption(
        "This shows who you've invited, not who has responded — individual response status "
        "is kept confidential to protect anonymity. See your category progress on the "
        "Overview page for response counts. If you've got someone's email address wrong, or "
        "nominated them under the wrong relationship, correct it below with Edit."
    )

    if EMAIL_AVAILABLE:
        pending_raters = db.get_raters_pending_invitation(leader_info['id'])
        pending_emails = {(r.get('email') or '').strip().lower() for r in pending_raters}
    else:
        pending_emails = None  # can't confirm invited status without email — treat as not sent

    failed_emails = db.get_failed_invitation_emails(leader_info['id']) if EMAIL_AVAILABLE else set()

    live_raters = [r for r in db.get_raters_for_leader(leader_info['id']) if r['relationship'] != 'Self']
    counts = {rel: 0 for rel in RATER_REQUIREMENTS}
    for r in live_raters:
        if r['relationship'] in counts:
            counts[r['relationship']] += 1

    relationship_options = ['Boss', 'Peers', 'DRs', 'Others']

    with st.container(key="cp_list_card"):
        st.markdown('<div class="cp-list-card">', unsafe_allow_html=True)
        # Split into the same [9, 1] columns as each content row below, so
        # the "Edit" header lands directly above the actual Edit buttons
        # rather than the 4-column header row silently having no label at
        # all for that fifth, unlabelled column.
        hcol1, hcol2 = st.columns([9, 1])
        with hcol1:
            st.markdown(
                '<div class="cp-list-head"><div>Name</div><div>Email</div><div>Category</div><div>Status</div></div>',
                unsafe_allow_html=True
            )
        with hcol2:
            st.markdown('<div class="cp-list-head cp-list-head-edit">Edit</div>', unsafe_allow_html=True)

        for idx, entry in enumerate(roster):
            rel = entry.get('relationship')
            current_email = entry.get('email') or ""
            editing_key = f"edit_nominee_{idx}"

            if st.session_state.get(editing_key):
                ecol1, ecol2, ecol3, ecol4 = st.columns([2, 2.4, 1.8, 0.8])
                with ecol1:
                    st.write(entry.get('name') or "Unknown")
                with ecol2:
                    new_email = st.text_input("Corrected email", value=current_email,
                                               key=f"email_input_{idx}", label_visibility="collapsed",
                                               placeholder="Correct email address")
                with ecol3:
                    new_rel = st.selectbox(
                        "Relationship", options=relationship_options,
                        index=relationship_options.index(rel) if rel in relationship_options else 0,
                        format_func=lambda x: RELATIONSHIP_TYPES.get(x, x),
                        key=f"rel_input_{idx}", label_visibility="collapsed"
                    )
                with ecol4:
                    if st.button("Save", key=f"save_nominee_{idx}"):
                        error = _validate_nomination_change(rel, new_rel, new_email, counts)
                        if error:
                            st.error(error)
                        else:
                            _apply_nomination_correction(db, leader_info, base_url, current_email, new_email, new_rel)
                            st.session_state[editing_key] = False
                            st.toast("Nomination updated.")
                            st.rerun()
            else:
                status = "Invited" if (pending_emails is not None and current_email.strip().lower() not in pending_emails) else "Not yet sent"
                status_cls = "cp-invited" if status == "Invited" else "cp-notsent"
                failed = current_email.strip().lower() in failed_emails
                warn_html = (
                    f'<span title="Invitation failed to send" style="margin-left:6px;">'
                    f'{_icon("warning", size=16, color="#B00020")}</span>'
                ) if failed else ""

                rcol1, rcol2 = st.columns([9, 1])
                with rcol1:
                    _md(f"""
                    <div class="cp-list-row-html">
                      <div><span class="cp-field-label">Name</span><span class="cp-rname">{_esc(entry.get('name') or 'Unknown')}</span></div>
                      <div><span class="cp-field-label">Email</span><span class="cp-remail">{_esc(current_email or 'No email address')}{warn_html}</span></div>
                      <div><span class="cp-field-label">Category</span><span class="cp-cat-chip">{_esc(RELATIONSHIP_TYPES.get(rel, rel))}</span></div>
                      <div><span class="cp-field-label">Status</span><span class="cp-status-chip {status_cls}">{status}</span></div>
                    </div>
                    """)
                with rcol2:
                    st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
                    if st.button("", icon=":material/edit:", key=f"edit_{idx}", help="Correct this person's email or relationship"):
                        st.session_state[editing_key] = True
                        st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    pending = db.get_raters_pending_invitation(leader_info['id']) if EMAIL_AVAILABLE else []
    if pending:
        _md(f"""
        <div class="cp-send-bar">
          <div class="cp-msg"><b>{len(pending)} invitation{'s' if len(pending) != 1 else ''}</b> {'are' if len(pending) != 1 else 'is'} ready to send.</div>
        </div>
        """)
        with st.container(key="cp_primary_send_invitations"):
            if st.button(f"Send Invitation{'s' if len(pending) != 1 else ''}", use_container_width=True, key="cp_send_invitations_btn"):
                _do_send_pending_invitations(db, leader_info, pending, base_url)
                st.rerun()


def _parse_rater_csv(import_df, existing_raters, nomination_roster):
    """
    Turn an uploaded CSV into rows ready to import, plus human-readable problems.

    Returns (rows, problems, warnings). `rows` are dicts of name/email/relationship
    with the relationship already normalised to its internal code. `problems` are
    messages naming the offending spreadsheet row, so the leader can go and fix
    that line rather than being told the whole file is wrong.

    Nothing is imported if there are problems: a partial import of a nominee list
    is worse than none, because the leader cannot easily tell what landed.

    `warnings` (added 2026-08-29) are the non-blocking duplicate-name nudges
    - unlike `problems`, these never suppress the import. Checked against
    BOTH the existing list and other rows already seen in this same CSV
    (`seen_by_name` is seeded from `nomination_roster`, NOT `existing_raters`
    - a rater who has already responded is severed, name nulled, so
    `existing_raters` alone goes blind to exactly the people most likely to
    be a genuine duplicate target; the roster survives severing by design -
    then grows as rows are processed, mirroring the existing `seen_emails`
    pattern below), so two rows in one upload that collide with each other
    are caught too, not just a row colliding with someone already on the
    list. Whichever row of a collision is processed SECOND gets the warning
    - the same convention `seen_emails` already uses for its own (blocking)
    duplicate check.

    Checks ACROSS ALL CATEGORIES, not just the same one (Ian's own reversal,
    2026-08-29, of the original same-category-only design - see
    _find_duplicate_name's own docstring for why). `seen_by_name` maps each
    normalised name to the SET of categories already seen for it, so a row
    can be told apart as a same-category repeat (gets the "second entry"
    wording) versus a cross-category reuse (gets wording pointing at the
    Edit flow instead, since that more often means a leader meant to correct
    someone's category, not add a new person).
    """
    required = ['name', 'email', 'relationship']
    missing_cols = [c for c in required if c not in import_df.columns]
    if missing_cols:
        return [], [
            f"Your CSV is missing the {', '.join(missing_cols)} "
            f"column{'s' if len(missing_cols) > 1 else ''}. "
            f"It needs: name, email, relationship."
        ], []

    rows = []
    problems = []
    warnings = []
    seen_emails = {
        (r.get('email') or '').strip().lower()
        for r in existing_raters if r.get('email')
    }
    seen_by_name = {}
    for r in nomination_roster:
        nm = _normalise_name(r.get('name'))
        if nm:
            seen_by_name.setdefault(nm, set()).add(r['relationship'])
    counts = {rel: 0 for rel in RATER_REQUIREMENTS}
    for r in existing_raters:
        if r['relationship'] in counts:
            counts[r['relationship']] += 1

    for position, (_, row) in enumerate(import_df.iterrows(), start=2):
        # start=2 because row 1 of the spreadsheet is the header
        name = str(row['name']).strip() if pd.notna(row['name']) else ''
        email = str(row['email']).strip() if pd.notna(row['email']) else ''
        raw_rel = row['relationship'] if pd.notna(row['relationship']) else None
        relationship = normalise_relationship(raw_rel)

        if not name and not email and raw_rel is None:
            continue  # blank line, ignore silently

        if not name:
            problems.append(f"Row {position}: no name given.")
            continue
        if not email or '@' not in email:
            problems.append(f"Row {position} ({name}): '{email}' isn't a valid email address.")
            continue
        if relationship is None:
            shown = str(raw_rel).strip() if raw_rel is not None else '(blank)'
            problems.append(
                f"Row {position} ({name}): '{shown}' isn't a relationship we "
                f"recognise. Use {RELATIONSHIP_INPUT_HELP}."
            )
            continue
        if relationship == 'Self':
            problems.append(
                f"Row {position} ({name}): your own self-assessment is handled "
                f"separately, so don't include yourself here. Use "
                f"{RELATIONSHIP_INPUT_HELP}."
            )
            continue

        if email.lower() in seen_emails:
            problems.append(
                f"Row {position} ({name}): {email} is already on your list."
            )
            continue
        seen_emails.add(email.lower())

        counts[relationship] += 1
        limit = RATER_REQUIREMENTS.get(relationship, {}).get('max')
        if limit is not None and counts[relationship] > limit:
            label = RELATIONSHIP_TYPES.get(relationship, relationship)
            problems.append(
                f"Row {position} ({name}): this would give you more than the "
                f"maximum of {limit} for {label}."
            )
            continue

        name_norm = _normalise_name(name)
        prior_categories = seen_by_name.get(name_norm, set())
        if relationship in prior_categories:
            label = RELATIONSHIP_TYPES.get(relationship, relationship)
            warnings.append(
                f"Row {position} ({name}): there's already a {label} called "
                f"{name} on your list. This will add a second entry."
            )
        elif prior_categories:
            existing_rel = next(iter(prior_categories))
            existing_label = RELATIONSHIP_TYPES.get(existing_rel, existing_rel)
            warnings.append(
                f"Row {position} ({name}): there's already a {existing_label} "
                f"called {name} on your list, under a different category. If "
                f"this is the same person, correct their category from People "
                f"You've Nominated after importing, rather than importing a "
                f"new entry."
            )
        seen_by_name.setdefault(name_norm, set()).add(relationship)

        rows.append({'name': name, 'email': email, 'relationship': relationship})

    if problems:
        # Do not import a partial list
        return [], problems, []

    return rows, problems, warnings


def _validate_nomination_change(current_rel, new_rel, new_email, counts):
    """Return an error message if the requested change isn't allowed, else None."""
    if not new_email or '@' not in new_email:
        return "Please enter a valid email address."

    if new_rel != current_rel:
        limit = RATER_REQUIREMENTS.get(new_rel, {}).get('max')
        if limit is not None and counts.get(new_rel, 0) >= limit:
            label = RELATIONSHIP_TYPES.get(new_rel, new_rel)
            return (
                f"You already have the maximum of {limit} for {label}. "
                f"Move or remove one of those first."
            )
    return None


def _apply_nomination_correction(db, leader_info, base_url,
                                 old_email, new_email, new_relationship):
    """
    Update a nominee's email and relationship on the roster, and on their rater
    row if they haven't yet responded.

    The roster is ALWAYS updated, so the visible outcome is identical for
    everyone. That is what stops the result revealing who has responded.

    The rater row is only touched when `get_unsevered_rater_by_email` finds it,
    which by definition means they have not submitted. Two reasons that is right
    on substance, not just a privacy dodge:
      - Writing an address onto a severed row would re-identify an anonymous
        response.
      - Someone who has already answered did so in the context of the
        relationship they were invited under, so their answers belong in that
        group. Recategorising them afterwards would misrepresent their input, and
        moving anonymous responses between groups would let someone work out
        which group a response sits in by watching the averages shift.
    """
    db.update_nomination_entry(
        leader_info['id'], old_email,
        new_email=new_email, new_relationship=new_relationship
    )

    rater = db.get_unsevered_rater_by_email(leader_info['id'], old_email)
    if rater is None or rater.get('completed'):
        return

    email_changed = new_email != old_email
    db.update_rater(rater['id'], email=new_email, relationship=new_relationship)

    # Only re-invite when the address actually changed. A relationship tweak does
    # not alter the invitation copy, so re-sending would just be noise.
    if email_changed and EMAIL_AVAILABLE and is_email_configured():
        updated = db.get_rater(rater['id'])
        if updated:
            send_rater_invitation(updated, leader_info['name'], base_url, db)


def render_portal_guidelines():
    """Guidelines screen: per-category cards with fuller guidance, plus the
    anonymity explanation card, matching the concept mockup exactly."""

    _md("""
    <div class="cp-page-head">
      <h1>360 Feedback Guidelines</h1>
      <p>The quality of your feedback depends on choosing raters who can give you meaningful,
      honest insight into your leadership. Here's guidance on each category.</p>
    </div>
    """)

    # Added 2026-08-30, Ian's own instruction: nominating raters and
    # watching responses come in happens over days or weeks, not one
    # sitting, so this is worth being able to find again easily.
    _md("""
    <div class="cp-sub-note">
      You'll likely visit this portal more than once as your raters respond. Bookmark it, or
      keep your invitation email handy, so you can find your way straight back.
    </div>
    """)

    for cat in GUIDELINE_CATEGORIES:
        _md(f"""
        <div class="cp-cat-card" style="--cp-accent:{CATEGORY_ACCENT[cat['key']]}">
          <div class="cp-cat-top">
            <h2>{_esc(cat['title'])}</h2>
            <span class="cp-req-badge">{_esc(cat['badge'])}</span>
          </div>
          <p>{_esc(cat['body'])}</p>
          <div class="cp-tip"><b>{_esc(cat['tip_label'])}</b> {_esc(cat['tip_body'])}</div>
        </div>
        """)

    _md("""
    <div class="cp-note-card">
      <b>A note on anonymity</b>
      <p>Individual scores are never shown to you alone, only combined with others in the same
      category once enough people have responded - except your Line Manager, whose feedback is
      always shown attributably, since that category can never reach the same threshold on its
      own. This is exactly why the minimums above matter: they're what keeps individual feedback
      protected. Comments are shown to you word-for-word, though, so anything specific a rater
      writes may still be recognisable, even where their scores aren't.</p>
    </div>
    """)


def render_portal_begin_here():
    """Begin Here / Help screen: how-to steps for nominating raters, plus
    the "Good to know" reference cards. Shown TWICE in the portal's
    lifecycle, same content both times, no branching in this function:
    once automatically, as the one-time onboarding gate render_leader_portal
    shows right after consent (see that function), and every time after
    that on demand via Help in the top nav (see _render_portal_topbar) -
    the closing note on this page says as much, so a leader who reads this
    once doesn't need to remember it, just that Help exists.

    CONTENT SOURCE: assets/Bentley Compass 360 — Begin Here Concept.html,
    supplied as reference material binding for this build. Two watch-cards
    (editing mistakes, adding someone later) are deliberately first, per
    that document - the two most likely practical questions after a
    leader's first session.
    """
    _md("""
    <div class="cp-page-head cp-begin-here">
      <div class="cp-eyebrow">Begin Here</div>
      <h1>Before you nominate your raters</h1>
      <p>Your Self-Assessment is done, so this is the next stage. Here's exactly how to
      nominate your raters, followed by a few things worth knowing before you start.</p>
    </div>
    """)

    st.markdown('<div class="cp-section-label" style="margin-top:0;">How to nominate your raters</div>',
                unsafe_allow_html=True)

    for i, step in enumerate(BEGIN_HERE_STEPS, start=1):
        sub_note_html = (f'<div class="cp-sub-note">{step["sub_note"]}</div>'
                          if step.get('sub_note') else '')
        _md(f"""
        <div class="cp-step">
          <div class="cp-step-num">{i}</div>
          <div class="cp-step-body">
            <b>{step['title']}</b>
            <p>{step['body']}</p>
            {sub_note_html}
          </div>
        </div>
        """)

    st.markdown('<div class="cp-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="cp-section-label" style="margin-top:0;">Good to know</div>',
                unsafe_allow_html=True)

    for card in BEGIN_HERE_WATCH_CARDS:
        items_html = "".join(
            f'<div class="cp-watch-item"><span class="cp-dot"></span><span>{item}</span></div>'
            for item in card['items']
        )
        _md(f"""
        <div class="cp-watch-card">
          <b>{card['title']}</b>
          {items_html}
        </div>
        """)
        if card.get('link_to'):
            view, label = card['link_to']
            with st.container(key=f"cp_ghost_begin_here_link_{view}"):
                if st.button(label, icon=":material/arrow_forward:", key=f"cp_begin_here_link_btn_{view}"):
                    _go_to_view(view)

    _md("""
    <div class="cp-closing">
      You won't need to find this page again to remember any of this, it's always here
      under <b>Help</b> in the menu above whenever you need it.
    </div>
    """)

    st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
    cta_col1, cta_col2 = st.columns([3, 1.3])
    with cta_col2:
        with st.container(key="cp_primary_begin_here_cta"):
            if st.button("Go to Overview", icon=":material/arrow_forward:", use_container_width=True,
                         key="cp_begin_here_cta_btn"):
                _go_to_view('overview')
