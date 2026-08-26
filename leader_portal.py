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
   may be shown per-name. Response counts/rates are aggregate-only, and even
   in aggregate they stay behind the same gating _progress_summary_text
   already used - never resolving to one outstanding person by subtraction.
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
    ANONYMITY_THRESHOLD, RELATIONSHIP_TYPES,
    RELATIONSHIP_INPUT_HELP, normalise_relationship, get_logo_data_uri
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
    """st.markdown(_html(fragment), unsafe_allow_html=True) - the single
    call site every top-level HTML block in this file should go through."""
    st.markdown(_html(fragment), unsafe_allow_html=True)


def _initials(name):
    """'Jordan Reeves' -> 'JR'. Falls back to the first two characters of
    whatever's there rather than crashing on an unusual name."""
    parts = [p for p in str(name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _progress_summary_text(completed, total):
    """
    Total-level-only progress summary — never reveals a per-group or
    per-person breakdown, and never resolves to a single outstanding (or
    single respondent) individual by simple subtraction.
    """
    if total == 0:
        return "You haven't nominated any raters yet."

    outstanding = total - completed
    if outstanding == 0:
        return ":material/check_circle: All responses received."
    if total < ANONYMITY_THRESHOLD or outstanding == 1:
        return ":material/autorenew: Responses are coming in."
    return f":material/bar_chart: {completed} of {total} responses received."


def _progress_stats_safe(completed, total):
    """
    Numbers for the Full 360 status pill and the Your Progress stats strip.

    SAME GATING AS _progress_summary_text, applied to the numeric display
    rather than just the sentence: this is the anonymity hard floor from
    CLAUDE.md section 4 ("never show a group of one, or any count/coverage
    split that resolves to a single person by simple subtraction"). The
    concept mockup's stats strip shows raw numbers unconditionally - real
    data has to stay gated regardless of what the static mockup shows.

    Returns a dict:
      safe=True  -> invited, responded, rate, outstanding are real numbers
      safe=False -> those are None; use `text` (from _progress_summary_text)
                    instead of rendering the numeric strip/pill at all
    """
    outstanding = total - completed
    gated = total > 0 and (total < ANONYMITY_THRESHOLD or outstanding == 1)
    if total == 0 or gated:
        return {
            'safe': False,
            'text': _progress_summary_text(completed, total),
            'invited': None, 'responded': None, 'rate': None, 'outstanding': None,
        }
    rate = round(100 * completed / total) if total else 0
    return {
        'safe': True,
        'text': None,
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
    SVG stroke-dashoffset for the category progress rings (r=19,
    circumference 2*pi*19 ≈ 119.4, matching the concept mockup's markup
    exactly so the same ring geometry/CSS applies unchanged).

    Ring shows NOMINATED count toward the category's suggested number (or,
    for Others, toward min_if_any once anyone's been added) - never response
    status. This is the leader's own action (who have I nominated), which is
    explicitly fine under the anonymity rule; it is deliberately NOT a
    response-progress ring, which would put per-category response data on a
    screen the anonymity rule doesn't clearly license it for.
    """
    circumference = 119.4
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


# Rater requirements
# 'Others' is optional, but ALL OR NOTHING above the anonymity threshold:
# nominate none, or nominate at least ANONYMITY_THRESHOLD. One or two "Others" is
# still worth avoiding: their responses don't get dropped (a thin Others group
# folds into whichever of Peers/DRs is large enough — see database.py's
# get_leader_feedback_data), but they lose their own voice in the report, showing
# up as part of that group rather than as Others. `min_if_any` captures the
# practical recommendation.
RATER_REQUIREMENTS = {
    'Boss': {'min': 1, 'max': 2, 'suggested': 1, 'required_nomination': True, 'show_minimum': True},
    'Peers': {'min': 3, 'max': 10, 'suggested': 5, 'required_nomination': True, 'show_minimum': True},
    'DRs': {'min': 3, 'max': 10, 'suggested': 5, 'required_nomination': True, 'show_minimum': True},
    'Others': {'min': 0, 'max': 10, 'suggested': 0, 'required_nomination': False,
               'show_minimum': False, 'min_if_any': ANONYMITY_THRESHOLD}
}

# Category caption/label pairs and requirement blurbs for the Overview ring
# cards, matching the concept mockup's two-line card header (small caption,
# then the real category name) and .req line. Numbers are pulled from
# RATER_REQUIREMENTS above rather than hardcoded twice, so a future change to
# the actual business rule can't silently drift out of sync with this copy.
CATEGORY_CAPTION = {'Boss': 'Line Manager', 'Peers': 'Colleagues', 'DRs': 'Your Team', 'Others': 'Optional'}
CATEGORY_REQ_TEXT = {
    'Boss': f"Minimum <b>{RATER_REQUIREMENTS['Boss']['min']}</b>, max {RATER_REQUIREMENTS['Boss']['max']} if matrix reporting",
    'Peers': f"Minimum <b>{RATER_REQUIREMENTS['Peers']['min']}</b>, suggested {RATER_REQUIREMENTS['Peers']['suggested']}",
    'DRs': f"Minimum <b>{RATER_REQUIREMENTS['DRs']['min']}</b>, suggested {RATER_REQUIREMENTS['DRs']['suggested']}",
    'Others': f"Add at least {RATER_REQUIREMENTS['Others']['min_if_any']} if you use this category",
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
        'key': 'Peers', 'title': 'Peers', 'badge': 'Minimum 3, suggested 5',
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
        'key': 'DRs', 'title': 'Direct Reports', 'badge': 'Minimum 3, suggested 5',
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
        'key': 'Others', 'title': 'Others', 'badge': 'Optional, min 3 if used',
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
  .cp-topbar{background:#183319;color:#FFFFFF;display:flex;align-items:center;justify-content:space-between;
    padding:0 40px;height:76px;margin:-1rem -1rem 0 -1rem;border-radius:0;}
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
  .cp-nav{display:flex;gap:36px;}
  .cp-nav a{color:rgba(255,255,255,0.78);text-decoration:none;font-size:14.5px;font-weight:500;
    padding-bottom:6px;border-bottom:2px solid transparent;}
  .cp-nav a.cp-active{color:#FFFFFF;border-bottom-color:#DCD8C0;}
  .cp-account{display:flex;align-items:center;gap:12px;}
  .cp-avatar{width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.16);
    display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#FFFFFF;flex-shrink:0;}
  .cp-account .cp-name{font-size:13.5px;color:#FFFFFF;font-weight:500;}

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

  /* rater category cards */
  .cp-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;}
  .cp-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;
    padding:20px 20px 16px;position:relative;overflow:hidden;}
  .cp-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
    background:var(--cp-accent,#183319);}
  .cp-card-top{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;}
  .cp-cat-label{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6B6B6B;}
  .cp-ring{position:relative;width:48px;height:48px;flex-shrink:0;}
  .cp-ring svg{transform:rotate(-90deg);}
  .cp-ring-track{stroke:#f1efe4;}
  .cp-ring-progress{stroke:#183319;stroke-linecap:round;}
  .cp-ring-label{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    font-size:11px;font-weight:700;color:#183319;}
  .cp-card h3{font-size:16.5px;margin:2px 0 4px;color:#040404;font-weight:700;}
  .cp-card .cp-req{font-size:12px;color:#6B6B6B;margin-bottom:14px;}
  .cp-card .cp-req b{color:#040404;}
  .cp-card-foot{display:flex;justify-content:space-between;align-items:center;}
  .cp-status-chip{font-size:11.5px;font-weight:700;padding:4px 10px;border-radius:14px;display:inline-block;}
  .cp-status-chip.cp-met{background:#e7ebe3;color:#183319;}
  .cp-status-chip.cp-pending{background:#f1efe4;color:#8a7a4a;}

  .cp-stats-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:0;
    background:#183319;border-radius:14px;margin-top:14px;overflow:hidden;}
  .cp-stat-block{padding:26px 28px;border-right:1px solid rgba(255,255,255,0.14);}
  .cp-stat-block:last-child{border-right:none;}
  .cp-stat-block .cp-num{font-size:32px;font-weight:700;color:#FFFFFF;line-height:1;}
  .cp-stat-block .cp-lbl{font-size:12.5px;color:#DCD8C0;margin-top:8px;letter-spacing:0.3px;}
  .cp-stats-vague{background:#183319;border-radius:14px;margin-top:14px;padding:26px 28px;
    color:#FFFFFF;font-size:14.5px;}

  .cp-guide-card{margin-top:34px;background:#f1efe4;border:1px solid #DCD8C0;
    border-radius:12px;padding:24px 26px;}
  .cp-guide-card .cp-g-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
  .cp-guide-card .cp-g-head b{font-size:15.5px;color:#040404;}
  .cp-guide-list{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;}
  .cp-guide-item b{display:block;font-size:13.5px;color:#040404;margin-bottom:3px;}
  .cp-guide-item span{font-size:12px;color:#6B6B6B;}

  .cp-progress-head{display:flex;align-items:center;justify-content:space-between;margin:34px 0 0;}
  .cp-progress-head .cp-section-label{margin:0;}
  .cp-reminder-note{font-size:11.5px;color:#6B6B6B;margin-top:6px;text-align:right;}

  /* Nominate Raters: add-card + nominated list */
  .cp-add-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;padding:24px 26px;}
  .cp-csv-row{display:flex;align-items:center;gap:10px;margin-top:14px;padding-top:14px;
    border-top:1px solid #f1efe4;font-size:13px;color:#6B6B6B;}
  .cp-list-card{background:#FFFFFF;border:1px solid #DCD8C0;border-radius:12px;overflow:hidden;}
  .cp-list-head{display:grid;grid-template-columns:1.4fr 1.8fr 1fr 1fr;gap:16px;
    background:#f1efe4;font-size:11px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;
    color:#6B6B6B;padding:12px 22px;}
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
  .cp-cat-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;gap:12px;}
  .cp-cat-top h2{font-size:18px;margin:0;color:#040404;font-weight:700;}
  .cp-req-badge{font-size:12px;font-weight:700;padding:5px 12px;border-radius:20px;
    background:#e7ebe3;color:#183319;white-space:nowrap;}
  .cp-cat-card p{font-size:14px;line-height:1.6;color:#3D3D3D;margin:0 0 12px;}
  .cp-cat-card .cp-tip{font-size:13px;color:#6B6B6B;background:#f1efe4;border-radius:8px;
    padding:10px 14px;margin-top:8px;}
  .cp-cat-card .cp-tip b{color:#040404;}
  .cp-note-card{margin-top:26px;background:#183319;border-radius:12px;padding:24px 28px;color:#FFFFFF;}
  .cp-note-card b{display:block;font-size:15px;margin-bottom:8px;}
  .cp-note-card p{font-size:13.5px;line-height:1.6;color:#DCD8C0;margin:0;}

  /* Streamlit buttons reskinned to match the mockups' .btn family. Two
     namespaces via container key, same pattern already established
     elsewhere in this app (see app.py's button-contrast section): never
     set colour without background, per that section's rule. */
  div[class*="st-key-cp_primary_"] button{
    background:#183319 !important;color:#FFFFFF !important;border:none !important;
    border-radius:8px !important;font-weight:600 !important;
  }
  div[class*="st-key-cp_primary_"] button:disabled{
    background:#9AA79B !important;color:#F0F0EE !important;
  }
  div[class*="st-key-cp_secondary_"] button{
    background:#FFFFFF !important;color:#183319 !important;border:1.5px solid #DCD8C0 !important;
    border-radius:8px !important;font-weight:600 !important;
  }
  div[class*="st-key-cp_secondary_"] button:disabled{
    background:#F5F4EE !important;color:#9A9A9A !important;border-color:#E5E3D8 !important;
  }
  div[class*="st-key-cp_ghost_"] button{
    background:none !important;border:none !important;color:#183319 !important;font-weight:700 !important;
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
    .cp-topbar{padding:0 16px;height:auto;flex-wrap:wrap;row-gap:10px;padding-top:12px;padding-bottom:12px;}
    .cp-nav{gap:18px;order:3;width:100%;justify-content:center;}
    .cp-status-grid{grid-template-columns:1fr;}
    .cp-grid{grid-template-columns:1fr;}
    .cp-guide-list{grid-template-columns:1fr;}
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


def _render_portal_topbar(leader_info, active_view=None, show_nav=True):
    """
    Shared header for every portal screen (and, without nav, the consent
    gate) - dark green bar, Bentley wing mark, page nav, account badge.

    Nav links are plain <a href="?portal=...&view=..."> - a real browser
    navigation/rerun, not client-side state - which keeps this simple and
    avoids fragile CSS-over-widget tricks for something that's fundamentally
    just "which page am I on".

    The mockup's plain green-circle "B" badge is replaced with the real
    Bentley wing mark per the human's instruction, negative (white) variant
    since it sits on the dark green bar - the positive variant would be
    invisible there.
    """
    token = leader_info.get('portal_token', '')
    logo_uri = get_logo_data_uri(negative=True)
    # Fallback only fires if the logo asset is genuinely missing from disk -
    # styled to stay legible on its own (no circle to lean on any more)
    # rather than a bare unstyled "B".
    mark_inner = (f'<img src="{logo_uri}" alt="">' if logo_uri
                  else '<span style="color:#DCD8C0;font-weight:700;font-size:22px;">B</span>')

    nav_html = ""
    if show_nav:
        views = [('overview', 'Overview'), ('nominate', 'Nominate Raters'), ('guidelines', 'Guidelines')]
        links = []
        for key, label in views:
            cls = "cp-active" if key == active_view else ""
            links.append(f'<a class="{cls}" href="?portal={_esc(token)}&view={key}">{label}</a>')
        nav_html = f'<nav class="cp-nav">{"".join(links)}</nav>'

    account_html = ""
    if show_nav:
        account_html = _html(f"""
        <div class="cp-account">
          <div class="cp-avatar">{_esc(_initials(leader_info.get('name')))}</div>
          <div class="cp-name">{_esc(leader_info.get('name'))}</div>
        </div>
        """)

    _md(f"""
    <div class="cp-topbar">
      <div class="cp-brand">
        <div class="cp-brand-mark">{mark_inner}</div>
        <div class="cp-brand-text">
          <div class="cp-b1">Bentley Compass 360</div>
          <div class="cp-b2">Your Leadership Portal</div>
        </div>
      </div>
      {nav_html}
      {account_html}
    </div>
    """)


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
    """Route to the three portal screens by ?view=, after the one-time
    consent gate. Each screen is its own full render (matching the concept
    mockups, which are three separate HTML pages), not a client-side tab
    switch - simpler and avoids extra state machinery for what's
    fundamentally page navigation."""

    leader_id = leader_info['id']

    if not leader_info.get('consent_given') and not st.session_state.get('leader_consent_given'):
        render_leader_consent_gate(db, leader_info)
        return

    st.markdown(PORTAL_CSS, unsafe_allow_html=True)

    view = st.query_params.get('view', 'overview')
    if view not in ('overview', 'nominate', 'guidelines'):
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
    else:
        render_portal_overview(db, leader_info, self_rater, other_raters)

    st.markdown('</div>', unsafe_allow_html=True)


def render_portal_overview(db, leader_info, self_rater, other_raters):
    """Overview screen: status cards, "who to nominate" teaser, category
    ring cards, and the Your Progress stats strip + reminders control."""

    base_url = st.session_state.get('portal_base_url', get_app_base_url())

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
        token = leader_info.get('portal_token', '')
        st.markdown(
            f'<a href="?portal={_esc(token)}&view=nominate" style="display:block;text-align:center;'
            f'padding:11px 18px;border-radius:8px;border:1.5px solid #DCD8C0;background:#FFFFFF;'
            f'color:#183319;font-weight:600;font-size:14px;text-decoration:none;">+ Add a rater</a>',
            unsafe_allow_html=True
        )
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
    full360_html = _full360_status_card_html(other_raters)
    st.markdown(f'<div class="cp-status-grid">{self_html}{full360_html}</div>', unsafe_allow_html=True)

    # --- Who should you nominate? teaser -----------------------------------
    token = leader_info.get('portal_token', '')
    _md(f"""
    <div class="cp-guide-card">
      <div class="cp-g-head">
        <b>Who should you nominate?</b>
        <a href="?portal={_esc(token)}&view=guidelines" style="padding:9px 16px;border-radius:8px;
           border:1.5px solid #DCD8C0;background:#FFFFFF;color:#183319;font-weight:600;font-size:13px;
           text-decoration:none;">Open full guidelines</a>
      </div>
      <div class="cp-guide-list">
        <div class="cp-guide-item"><b>Boss</b><span>Your direct line manager. One is enough.</span></div>
        <div class="cp-guide-item"><b>Peers</b><span>Colleagues at a similar level who see your day-to-day work.</span></div>
        <div class="cp-guide-item"><b>Direct Reports</b><span>People who report to you. Aim for a range of tenure.</span></div>
        <div class="cp-guide-item"><b>Others</b><span>Stakeholders or customers, if relevant to your role.</span></div>
      </div>
    </div>
    """)

    # --- Category ring cards ------------------------------------------------
    rater_counts = {'Boss': 0, 'Peers': 0, 'DRs': 0, 'Others': 0}
    for r in other_raters:
        if r['relationship'] in rater_counts:
            rater_counts[r['relationship']] += 1

    st.markdown('<div class="cp-section-label">Your raters, by category</div>', unsafe_allow_html=True)
    cards_html = '<div class="cp-grid">'
    for cat in ['Boss', 'Peers', 'DRs', 'Others']:
        cards_html += _category_card_html(cat, rater_counts[cat])
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

    # --- Your Progress + Send reminders -------------------------------------
    incomplete = [r for r in other_raters if not r.get('completed')]
    any_eligible, hours_until_next = _reminder_cooldown_state(incomplete)
    email_configured = EMAIL_AVAILABLE and is_email_configured()

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

    stats = _progress_stats_safe(sum(1 for r in other_raters if r.get('completed')), len(other_raters))
    if stats['safe']:
        _md(f"""
        <div class="cp-stats-strip">
          <div class="cp-stat-block"><div class="cp-num">{stats['invited']}</div><div class="cp-lbl">Raters invited</div></div>
          <div class="cp-stat-block"><div class="cp-num">{stats['responded']}</div><div class="cp-lbl">Responded</div></div>
          <div class="cp-stat-block"><div class="cp-num">{stats['rate']}%</div><div class="cp-lbl">Response rate</div></div>
          <div class="cp-stat-block"><div class="cp-num">{stats['outstanding']}</div><div class="cp-lbl">Still to respond</div></div>
        </div>
        """)
    else:
        st.markdown(f'<div class="cp-stats-vague">{_esc(stats["text"].split(" ", 1)[-1] if stats["text"] else "")}'
                     f'</div>', unsafe_allow_html=True)


def _self_status_card_html(self_rater):
    if self_rater and self_rater.get('completed'):
        date_text = _format_completion_date(self_rater.get('completed_at'))
        subtitle = (f"Completed on {_esc(date_text)}, discussed at your Module 1 coaching session"
                    if date_text else "Discussed at your Module 1 coaching session")
        return _html(f"""
        <div class="cp-status-card cp-done">
          <div class="cp-status-left">
            <div class="cp-status-icon">&#10003;</div>
            <div class="cp-status-text"><b>Self-Assessment complete</b><span>{subtitle}</span></div>
          </div>
        </div>
        """)
    return _html("""
    <div class="cp-status-card">
      <div class="cp-status-left">
        <div class="cp-status-icon">&#9675;</div>
        <div class="cp-status-text"><b>Self-Assessment pending</b><span>Not yet completed</span></div>
      </div>
    </div>
    """)


def _full360_status_card_html(other_raters):
    completed = sum(1 for r in other_raters if r.get('completed'))
    total = len(other_raters)
    if total == 0:
        return _html("""
        <div class="cp-status-card">
          <div class="cp-status-left">
            <div class="cp-status-icon">&#128340;</div>
            <div class="cp-status-text"><b>Full 360 not started</b><span>Nominate your raters to begin</span></div>
          </div>
        </div>
        """)
    stats = _progress_stats_safe(completed, total)
    if completed == total:
        return _html("""
        <div class="cp-status-card cp-done">
          <div class="cp-status-left">
            <div class="cp-status-icon">&#10003;</div>
            <div class="cp-status-text"><b>Full 360 complete</b><span>All responses received</span></div>
          </div>
        </div>
        """)
    if stats['safe']:
        subtitle = f"{stats['responded']} of {stats['invited']} responses received"
        pill = f'<span class="cp-pill">{stats["rate"]}%</span>'
    else:
        subtitle = "Responses are coming in"
        pill = ""
    return _html(f"""
    <div class="cp-status-card">
      <div class="cp-status-left">
        <div class="cp-status-icon">&#128340;</div>
        <div class="cp-status-text"><b>Full 360 in progress</b><span>{_esc(subtitle)}</span></div>
      </div>
      {pill}
    </div>
    """)


def _category_card_html(cat, count):
    req = RATER_REQUIREMENTS[cat]
    min_if_any = req.get('min_if_any')
    target = req['suggested'] or min_if_any or req['min'] or 1
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
          <svg width="48" height="48">
            <circle class="cp-ring-track" cx="24" cy="24" r="19" stroke-width="5" fill="none"/>
            <circle class="cp-ring-progress" cx="24" cy="24" r="19" stroke-width="5" fill="none"
              stroke-dasharray="119.4" stroke-dashoffset="{offset}"/>
          </svg>
          <div class="cp-ring-label">{count}{f"/{target}" if req['suggested'] or (min_if_any and count) else ""}</div>
        </div>
      </div>
      <h3>{_esc(RELATIONSHIP_TYPES.get(cat, cat))}</h3>
      <div class="cp-req">{CATEGORY_REQ_TEXT[cat]}</div>
      <div class="cp-card-foot"><span class="cp-status-chip {chip_cls}">{_esc(chip_text)}</span></div>
    </div>
    """)


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

    _render_nomination_warnings(rater_counts)

    st.markdown('<div class="cp-section-label">Add a rater</div>', unsafe_allow_html=True)

    with st.container(key="cp_add_card"):
        with st.form("add_rater_form", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns([1.3, 1.3, 1, 0.7])
            with col1:
                rater_name = st.text_input("Full name", placeholder="e.g. Priya Anand")
            with col2:
                rater_email = st.text_input("Email address", placeholder="e.g. priya.anand@bentley...")
            with col3:
                relationship = st.selectbox(
                    "Relationship", options=['Boss', 'Peers', 'DRs', 'Others'],
                    index=None, placeholder="Choose category...",
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
                    db.add_rater(leader_id, relationship, rater_name, rater_email)
                    db.add_to_nomination_roster(leader_id, rater_name, rater_email, relationship)
                    st.success(f"Added {rater_name}. Check the details below, then send their invitation when you're ready.")
                    st.rerun()

        show_csv = st.session_state.get('cp_show_csv', False)
        with st.container(key="cp_ghost_csv_toggle"):
            if st.button(("Hide CSV upload" if show_csv else "📄 Adding several at once? Upload a CSV instead"),
                         key="cp_csv_toggle_btn"):
                st.session_state['cp_show_csv'] = not show_csv
                st.rerun()

        if show_csv:
            _render_csv_import(db, leader_id, existing_raters)

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
        st.info(
            f"You've nominated exactly {count} under **{label}**, which is the "
            f"minimum needed to report that group on its own. If even one of them "
            f"doesn't respond it drops below the minimum — their responses won't "
            f"be lost, but they'd get folded into your {fold_target} "
            f"group rather than showing up as {label} in their own right. Worth "
            f"adding one or two more as cover."
        )


def _render_csv_import(db, leader_id, existing_raters):
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
            rows, problems = _parse_rater_csv(import_df, existing_raters)
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
        st.markdown(
            '<div class="cp-list-head"><div>Name</div><div>Email</div><div>Category</div><div>Status</div></div>',
            unsafe_allow_html=True
        )

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
                warn_html = ('<span title="Invitation failed to send" style="color:#B00020;'
                              'margin-left:6px;">&#9888;</span>') if failed else ""

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


def _parse_rater_csv(import_df, existing_raters):
    """
    Turn an uploaded CSV into rows ready to import, plus human-readable problems.

    Returns (rows, problems). `rows` are dicts of name/email/relationship with the
    relationship already normalised to its internal code. `problems` are messages
    naming the offending spreadsheet row, so the leader can go and fix that line
    rather than being told the whole file is wrong.

    Nothing is imported if there are problems: a partial import of a nominee list
    is worse than none, because the leader cannot easily tell what landed.
    """
    required = ['name', 'email', 'relationship']
    missing_cols = [c for c in required if c not in import_df.columns]
    if missing_cols:
        return [], [
            f"Your CSV is missing the {', '.join(missing_cols)} "
            f"column{'s' if len(missing_cols) > 1 else ''}. "
            f"It needs: name, email, relationship."
        ]

    rows = []
    problems = []
    seen_emails = {
        (r.get('email') or '').strip().lower()
        for r in existing_raters if r.get('email')
    }
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

        rows.append({'name': name, 'email': email, 'relationship': relationship})

    if problems:
        # Do not import a partial list
        return [], problems

    return rows, problems


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
      category once enough people have responded. This is exactly why the minimums above matter:
      they're what keeps individual feedback protected. Comments are shown to you word-for-word,
      though, so anything specific a rater writes may still be recognisable, even where their
      scores aren't.</p>
    </div>
    """)
