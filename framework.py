#!/usr/bin/env python3
"""
Framework configuration for Bentley Compass 360.

Contains all dimensions, items, and display configuration.
"""

import re
import base64
from pathlib import Path

# ============================================
# DIMENSION STRUCTURE
# ============================================

DIMENSIONS = {
    'Leading Self': (1, 5),
    'Developing Others': (6, 10),
    'Building High-Performing Teams': (11, 15),
    'Driving Results': (16, 20),
    'Leading Change': (21, 25),
    'Communicating & Influencing': (26, 30),
    'Building Trust': (31, 35),
    'Thinking Strategically': (36, 40),
    'Performance Excellence': (41, 45),
}

# ============================================
# ALL 45 ITEMS — paired self/other forms, frequency scale
# ============================================

ITEMS = {
    # Leading Self (1-5)
    1: {"self": "I stay calm and manage my emotions effectively, even under pressure", "other": "They stay calm and manage their emotions effectively, even under pressure"},
    2: {"self": "I acknowledge my strengths and development areas openly", "other": "They acknowledge their strengths and development areas openly"},
    3: {"self": "I delegate appropriately rather than taking on too much myself", "other": "They delegate appropriately rather than taking on too much themselves"},
    4: {"self": "I take responsibility for my mistakes and learn from them", "other": "They take responsibility for their mistakes and learn from them"},
    5: {"self": "I manage my time effectively, focusing on high-value activities rather than firefighting", "other": "They manage their time effectively, focusing on high-value activities rather than firefighting"},

    # Developing Others (6-10)
    6: {"self": "I provide constructive feedback to help others improve", "other": "They provide constructive feedback to help others improve"},
    7: {"self": "I create opportunities for people to develop new skills", "other": "They create opportunities for people to develop new skills"},
    8: {"self": "I take interest in the career aspirations of my team", "other": "They take interest in the career aspirations of their team"},
    9: {"self": "I coach people to solve problems rather than providing solutions", "other": "They coach people to solve problems rather than providing solutions"},
    10: {"self": "I identify high-potential talent and nurture future leaders", "other": "They identify high-potential talent and nurture future leaders"},

    # Building High-Performing Teams (11-15)
    11: {"self": "I create a team environment where people feel safe to raise mistakes and disagreements early", "other": "They create a team environment where people feel safe to raise mistakes and disagreements early"},
    12: {"self": "I foster collaboration and shared ownership within the team", "other": "They foster collaboration and shared ownership within the team"},
    13: {"self": "I adapt my leadership style to what different team members need", "other": "They adapt their leadership style to what different team members need"},
    14: {"self": "I celebrate team successes and recognise contributions", "other": "They celebrate team successes and recognise contributions"},
    15: {"self": "I build team capability and ensure knowledge sharing", "other": "They build team capability and ensure knowledge sharing"},

    # Driving Results (16-20)
    16: {"self": "I set clear, ambitious, and measurable goals", "other": "They set clear, ambitious, and measurable goals"},
    17: {"self": "I establish clear accountability for results", "other": "They establish clear accountability for results"},
    18: {"self": "I monitor progress regularly and adjust plans when needed", "other": "They monitor progress regularly and adjust plans when needed"},
    19: {"self": "I push the team to deliver business results consistently", "other": "They push the team to deliver business results consistently"},
    20: {"self": "I make timely decisions rather than delaying unnecessarily", "other": "They make timely decisions rather than delaying unnecessarily"},

    # Leading Change (21-25)
    21: {"self": "I identify the need for change and initiate it proactively", "other": "They identify the need for change and initiate it proactively"},
    22: {"self": "I create a compelling vision for change that helps people understand and adapt", "other": "They create a compelling vision for change that helps people understand and adapt"},
    23: {"self": "I encourage new ideas and ways of working, not just maintaining the status quo", "other": "They encourage new ideas and ways of working, not just maintaining the status quo"},
    24: {"self": "I keep the team steady when things are uncertain", "other": "They keep the team steady when things are uncertain"},
    25: {"self": "I build momentum and sustain change through to completion", "other": "They build momentum and sustain change through to completion"},

    # Communicating & Influencing (26-30)
    26: {"self": "I articulate ideas clearly and ensure understanding", "other": "They articulate ideas clearly and ensure understanding"},
    27: {"self": "I adapt my communication style to different audiences", "other": "They adapt their communication style to different audiences"},
    28: {"self": "I listen actively and consider others' perspectives", "other": "They listen actively and consider others' perspectives"},
    29: {"self": "I influence others effectively to achieve outcomes", "other": "They influence others effectively to achieve outcomes"},
    30: {"self": "I communicate with confidence and authority", "other": "They communicate with confidence and authority"},

    # Building Trust (31-35)
    31: {"self": "I follow through on my commitments and promises", "other": "They follow through on their commitments and promises"},
    32: {"self": "I share information openly, including when it's difficult", "other": "They share information openly, including when it's difficult"},
    33: {"self": "I give people a fair hearing before reaching a view", "other": "They give people a fair hearing before reaching a view"},
    34: {"self": "I stay fair to everyone involved when handling disagreements", "other": "They stay fair to everyone involved when handling disagreements"},
    35: {"self": "I build strong relationships based on mutual respect", "other": "They build strong relationships based on mutual respect"},

    # Thinking Strategically (36-40)
    36: {"self": "I think about how my decisions affect other parts of the business, not just my own area", "other": "They think about how decisions affect other parts of the business, not just their own area"},
    37: {"self": "I anticipate market trends and risks before they become problems", "other": "They anticipate market trends and risks before they become problems"},
    38: {"self": "I build effective relationships with key stakeholders across the business", "other": "They build effective relationships with key stakeholders across the business"},
    39: {"self": "I consider long-term consequences in my decision-making", "other": "They consider long-term consequences in their decision-making"},
    40: {"self": "I challenge assumptions and explore multiple perspectives", "other": "They challenge assumptions and explore multiple perspectives"},

    # Performance Excellence (41-45)
    41: {"self": "I use the Performance Excellence framework to prioritise opportunities based on data rather than instinct", "other": "They use the Performance Excellence framework to prioritise opportunities based on data rather than instinct"},
    42: {"self": "I clearly define problem statements before jumping into solutions", "other": "They clearly define problem statements before jumping into solutions"},
    43: {"self": "I break larger issues into structured, manageable stages to solve problems at the right level", "other": "They break larger issues into structured, manageable stages to solve problems at the right level"},
    44: {"self": "I engage the right people at each stage of the funnel to validate assumptions and strengthen solutions", "other": "They engage the right people at each stage of the funnel to validate assumptions and strengthen solutions"},
    45: {"self": "I follow through on improvement actions and track impact to ensure benefits are realised and sustained", "other": "They follow through on improvement actions and track impact to ensure benefits are realised and sustained"},
}

# ==========================================
# FREQUENCY SCALE (behaviour-based)
# ==========================================
SCALE_FREQUENCY = {
    1: "Rarely or never",
    2: "Occasionally",
    3: "Sometimes",
    4: "Often",
    5: "Consistently",
    0: "No opportunity to observe",   # excluded from averages, not a low score
}

# ==========================================
# OPEN CLOSING PROMPTS (not scored — routed to comments by section)
# ==========================================
OPEN_PROMPTS = {
    "keep": {"self": "What do you want to keep doing?",
             "other": "What should this person keep doing?"},
    "change": {"self": "What one change would make the biggest difference to your leadership?",
               "other": "What one change would make the biggest difference to their leadership?"},
}

def get_item_text(item_number, relationship):
    """Correctly-phrased item text for a rater relationship.
    'Self' gets the I-form; everyone else gets the They-form."""
    forms = ITEMS[item_number]
    return forms["self" if relationship == "Self" else "other"]

def get_prompt_text(prompt_key, relationship):
    """Correctly-phrased open-prompt text for a rater relationship."""
    return OPEN_PROMPTS[prompt_key]["self" if relationship == "Self" else "other"]

# ============================================
# i18n FOUNDATION (round-two rater nomination, October cohort)
# ============================================
# Locale codes stored on raters.locale and used as the `locale` argument to
# db.get_translation(). None/NULL and 'en' are both treated as English at
# every read site - 'en' is what's stored when a rater actively picks English
# on the locale screen, None is a rater who hasn't picked anything yet.
# Traditional (not Simplified) Chinese, per the Taipei dealership in the
# October cohort - 'zh-Hant' names the script, not a region, deliberately,
# since a rater's working language isn't inferable from where their
# dealership sits (see the build instructions this was speced against).
SUPPORTED_LOCALES = {
    'en': 'English',
    'ar': 'العربية',
    'de': 'Deutsch',
    'fr': 'Français',
    'nl': 'Nederlands',
    'vi': 'Tiếng Việt',
    'zh-Hant': '繁體中文',
}

RTL_LOCALES = {'ar'}


def dimension_slug(dim_name):
    """Stable, human-readable slug for a dimension name, e.g. 'Leading Self'
    -> 'leading_self', used to build translations string_keys
    (dimension_{slug}_name / dimension_{slug}_desc). Derived from the name
    itself rather than hand-maintained per dimension, so a renamed or added
    dimension can't silently drift out of sync with its own slug."""
    return re.sub(r'[^a-z0-9]+', '_', dim_name.lower()).strip('_')

# ============================================
# DIMENSION DESCRIPTIONS
# ============================================

DIMENSION_DESCRIPTIONS = {
    'Leading Self': "Personal effectiveness, self-management, and leading by example. Leaders strong in this area manage their time and energy well, stay composed under pressure, and continuously work on their own development.",
    
    'Developing Others': "Growing capability in individuals and teams. Leaders strong in this area invest in development conversations, create learning opportunities, and build their team's ability to operate independently.",
    
    'Building High-Performing Teams': "Creating the conditions for teams to thrive. Leaders strong in this area build collaborative teams, address dysfunction, and adapt their style to get the best from different people.",
    
    'Driving Results': "Delivering performance through others. Leaders strong in this area set clear expectations, hold people accountable fairly, make timely decisions, and maintain focus on what matters most.",
    
    'Leading Change': "Navigating teams through uncertainty and transformation. Leaders strong in this area help people understand and commit to change, support them through transitions, and encourage innovation.",
    
    'Communicating & Influencing': "Connecting with others and getting buy-in. Leaders strong in this area listen well, communicate clearly, keep people informed, and can influence without relying on authority.",
    
    'Building Trust': "Creating psychological safety and credibility. Leaders strong in this area keep their commitments, share information openly, are honest even when difficult, and create an environment where people feel safe to speak up.",
    
    'Thinking Strategically': "Seeing the bigger picture and planning ahead. Leaders strong in this area think beyond their immediate area, balance short and long-term priorities, build stakeholder relationships, and manage risks proactively.",
    
    'Performance Excellence': "Driving business performance through structured problem-solving. Leaders strong in this area use data to prioritise, define problems clearly, break issues into manageable stages, engage the right people, and track impact of improvement actions.",
}

# ============================================
# RELATIONSHIP TYPES
# ============================================

RELATIONSHIP_TYPES = {
    'Self': 'Self',
    'Boss': 'Line Manager',
    'Peers': 'Peers',
    'DRs': 'Direct Reports',
    'Others': 'Others',
}

GROUP_DISPLAY = {
    'Self': 'Self',
    'Boss': 'Line Manager',
    'Peers': 'Peers',
    'DRs': 'Direct Reports',
    'Others': 'Others',
    'Combined': 'All Raters'
}

# ============================================
# RELATIONSHIP PARSING FOR CSV IMPORT
# ============================================
#
# The internal codes ('Boss', 'DRs') are jargon, and expecting anyone filling in a
# spreadsheet to match them exactly, including capitalisation, is a trap. A CSV
# that failed because someone typed "others" instead of "Others" is a bad
# experience and the leader's own fault only in the narrowest sense.
#
# `normalise_relationship` accepts what people actually type: any case, extra
# whitespace, hyphens or underscores, and the plain-English labels as well as the
# internal codes. Both CSV import paths (leader portal and admin dashboard) go
# through it, so they can never diverge.
RELATIONSHIP_SYNONYMS = {
    # 'Self' is recognised so the ADMIN importer can use it, but the leader portal
    # rejects it explicitly: a leader's own self-assessment row is created with
    # their assessment, never bulk-uploaded alongside their raters.
    'Self': ['self', 'me', 'myself', 'self assessment', 'self-assessment'],
    'Boss': [
        'boss', 'bosses', 'line manager', 'linemanager', 'manager', 'lm',
        'supervisor', 'my manager', 'my line manager', 'head of', 'reports to',
    ],
    'Peers': [
        'peer', 'peers', 'colleague', 'colleagues', 'peer group', 'my peers',
        'same level', 'equivalent',
    ],
    'DRs': [
        'dr', 'drs', 'direct report', 'direct reports', 'directreport',
        'directreports', 'report', 'reports', 'team member', 'team members',
        'my team', 'subordinate', 'subordinates',
    ],
    'Others': [
        'other', 'others', 'stakeholder', 'stakeholders', 'matrix',
        'internal customer', 'internal customers', 'customer', 'customers',
        'supplier', 'suppliers', 'wider stakeholder', 'wider stakeholders',
    ],
}


def normalise_relationship(value):
    """
    Map a free-text relationship to its internal code, or None if unrecognised.

    Tolerant of case, surrounding whitespace, and hyphens/underscores/dots/slashes
    used as separators. Returns one of 'Boss', 'Peers', 'DRs', 'Others'.
    """
    if value is None:
        return None

    text = str(value).strip().lower()
    if not text or text in ('nan', 'none'):
        return None

    # Treat common separators as spaces, then collapse runs of whitespace
    text = re.sub(r'[-_./\\]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    for canonical, variants in RELATIONSHIP_SYNONYMS.items():
        if text == canonical.lower() or text in variants:
            return canonical

    return None


# Shown to users as the accepted values. The plain-English labels, since those are
# what the template supplies and what people would naturally write.
RELATIONSHIP_INPUT_HELP = "Line Manager, Peer, Direct Report, or Other"

# Characters that read as a plain space/quote/hyphen on screen but are a
# different byte underneath - exactly the class of bug that produced two
# separate "Self Assessment Test August 2026" cohort cards from what looked
# like one identical cohort name (2026-08-23). Not exhaustive, targets the
# specific sources named at the time: a non-breaking space or zero-width
# character picked up from a copy-paste source (Word, a browser address bar,
# an email), or a smart quote/dash from autocorrect.
_COHORT_LOOKALIKE_CHARS = {
    ' ': ' ',   # non-breaking space
    '​': '',    # zero-width space
    '‌': '',    # zero-width non-joiner
    '‍': '',    # zero-width joiner
    '﻿': '',    # zero-width no-break space / BOM
    '‘': "'", '’': "'",   # smart single quotes
    '“': '"', '”': '"',   # smart double quotes
    '–': '-', '—': '-',   # en dash, em dash
}


def normalise_cohort_text(value):
    """
    Canonicalise a free-text cohort name so a stray invisible or lookalike
    character can't create a silent near-duplicate of an existing cohort.

    Replaces known lookalike characters (non-breaking/zero-width spaces,
    smart quotes, en/em dashes - see _COHORT_LOOKALIKE_CHARS) with their
    plain-ASCII equivalents, then collapses whitespace and trims. This is
    deliberately not exhaustive of every possible invisible character, only
    the sources already known to have caused this - the actual anti-
    duplicate protection is the caller comparing the normalised result
    against existing cohorts (case-insensitively) before treating it as new,
    not this function alone. Returns '' for None/blank input, never None,
    so callers can treat the result as a plain string throughout.
    """
    if value is None:
        return ''

    text = str(value)
    for lookalike, replacement in _COHORT_LOOKALIKE_CHARS.items():
        text = text.replace(lookalike, replacement)

    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ============================================
# COLOURS - Bentley Brand Palette
# ============================================

COLOURS = {
    'bentley_green': '#183319',      # Official Bentley Green - Self ONLY, sole
                                      # ownership, unique, not shared or diluted
                                      # anywhere else in the document. Also
                                      # Agreed Strengths header (a PAPU-NANU
                                      # quadrant colour, a separate decision -
                                      # see the note below the PAPU-NANU calls).
    'grey_dark': '#3D3D3D',           # Line Manager
    'grey_mid': '#6B6B6B',            # Peers
    'grey_light': '#9A9A9A',          # Direct Reports
    'grey_lightest': '#C4C4C4',       # Others
    'charcoal': '#4D4D4F',           # No longer used for "All Raters" - kept
                                      # only as a general-purpose dark grey,
                                      # not tied to any one meaning.
    'charcoal_grey': '#5F5E5A',      # Potential Blind Spots header
    'heritage_white': '#DCD8C0',     # All Raters bar colour (item bar charts,
                                      # self-only bar), the radar chart's All
                                      # Raters FILL, AND, separately, the
                                      # Development Areas PAPU-NANU header -
                                      # same hex value serving multiple
                                      # concepts, flagged 2026-08-08 and
                                      # confirmed intentional by the human:
                                      # it's a real colour in the confirmed
                                      # palette, so reusing it is fine.
    'heritage_white_deep': '#BBB8A3', # Radar chart's All Raters LINE/markers
                                      # only - a deepened variant of
                                      # heritage_white (also used, coincidentally
                                      # via the same hex, as 'gap_over_rating'
                                      # in the Executive Summary - kept as a
                                      # separate named constant so the two can
                                      # vary independently later, not coupled
                                      # just because they share a value today).
                                      # heritage_white itself is far too light
                                      # to use at full opacity for a thin line:
                                      # tested at only 1.44:1 contrast against
                                      # the white chart background (this
                                      # deepened version reaches 2.0:1) - still
                                      # short of the ~3:1 WCAG guideline for
                                      # graphical elements, but the human's
                                      # explicit call is that matching the All
                                      # Raters bar identity matters more here
                                      # than maximising line contrast, given
                                      # the FILL (a much larger, more legible
                                      # area) already carries genuine
                                      # heritage_white and is what most
                                      # visibly makes that identity match.
    'good_news_tint': '#5D705E',      # Good News PAPU-NANU header - a genuine
                                      # 30% tint of bentley_green (blended
                                      # toward white), not just "some other
                                      # green". Replaces the old #5C7F63
                                      # (formerly 'green_soft', retired below)
                                      # which was a similar-looking muted green
                                      # but not mathematically derived from
                                      # bentley_green at all. Contrast with
                                      # white header text: 5.31:1, comfortably
                                      # past the WCAG AA 4.5:1 minimum (the old
                                      # value was 4.5:1 exactly - right on the
                                      # edge).
    'gap_under_rating': '#BAC2BA',    # Executive Summary "under-rating" gap
                                      # cell ONLY (self scores below All
                                      # Raters, i.e. by_dimension['Gap'] < 0 -
                                      # confirmed against database.py, Gap =
                                      # Self - Combined, so negative genuinely
                                      # means self rated lower). A 70% tint of
                                      # bentley_green. Isolated from the
                                      # PAPU-NANU system deliberately - Good
                                      # News represents the same gap direction
                                      # but is a separate colour decision (see
                                      # 'good_news_tint' above); this table is
                                      # scanned quickly in a live coaching
                                      # conversation, so 2026-08-08 moved it
                                      # from an 85% tint (too subtle to read
                                      # at a glance) to this more present 70%.
    'gap_over_rating': '#BBB8A3',     # Executive Summary "over-rating" gap
                                      # cell ONLY (Gap > 0, self rated higher).
                                      # A deepened variant of heritage_white
                                      # (scaled darker, not the base value
                                      # used elsewhere for All Raters bars/
                                      # Development Areas), same 2026-08-08
                                      # reasoning as gap_under_rating - more
                                      # presence for a quickly-scanned table.
                                      # Earlier passes tried the base
                                      # heritage_white value, and before that
                                      # a pale tint of charcoal_grey tying it
                                      # to Potential Blind Spots' identity -
                                      # both superseded, not a PAPU-NANU
                                      # colour despite representing the same
                                      # gap direction as that quadrant.
    'bentley_cream': '#F5F5DC',      # Bentley cream
    'bentley_charcoal': '#2C2C2C',   # Bentley charcoal
    'light_grey': '#F5F5F5',
    'dark_grey': '#333333',
}
# NB: the fixed report palette above is the only palette report_generator.py
# is allowed to use, per the confirmed brand book correction 2026-08-06.
# #024731 was an estimate made before the real brand book was available -
# #183319 is the confirmed official Bentley Green. Tan, leather and gold tones
# (previously 'leather_tan' #9C6148, 'tan_tint' #c9a692, and 'bentley_gold'
# #B8860B before that) are retired entirely - none of them are in Bentley's
# confirmed palette. The green-tint respondent-group family ('green_mid'
# #3D5F44, 'green_soft' #5C7F63, 'green_pale' #7FA087, 'green_lightest'
# #A8C2AC) is ALSO retired as of 2026-08-08, per client feedback: those four
# groups moved to a dark-to-light greyscale progression instead, so that Self
# is the only thing on the page reading as green at all. #5C7F63 (the old
# 'green_soft') no longer appears anywhere - the Good News PAPU-NANU header
# that used to hardcode it directly now uses 'good_news_tint' instead, a
# genuine tint of bentley_green rather than a similar-looking but unrelated
# green. The Executive Summary's gap-highlighting colours (previously generic
# Excel defaults #FFF2CC/#C6EFCE, not part of any confirmed palette at all)
# are retired the same day for the same reason - see 'good_news_tint_pale'
# and 'blind_spot_tint_pale' above.

# Group colours for report bar charts and comment labels - fixed brand
# palette, not to be extended. Self is the only one in the green family, full
# strength, exclusive to Self. The four individual rater groups are a
# dark-to-light greyscale progression as of 2026-08-08 (client feedback -
# green tints previously used here are retired). "All Raters"
# (GROUP_DISPLAY['Combined']) is 'heritage_white' everywhere it appears (item
# bar charts and the radar chart's fill; the radar's line/markers use the
# deepened 'heritage_white_deep' for visibility) - not a GROUP_COLOURS entry
# since it isn't a rater group.
GROUP_COLOURS = {
    'Self': COLOURS['bentley_green'],
    'Boss': COLOURS['grey_dark'],
    'Peers': COLOURS['grey_mid'],
    'DRs': COLOURS['grey_light'],
    'Others': COLOURS['grey_lightest'],
}

# ============================================
# LOGO
# ============================================

# The official Bentley "Simplified" lockup (wings + wordmark) - Positive is
# dark-on-light for white/light backgrounds, Negative is white-on-transparent
# for dark backgrounds (the email header banners, which use the dark green or
# charcoal fill). Single source of truth for both asset paths -
# report_generator.py, the Streamlit pages, and the email templates all read
# the same files rather than each keeping their own copy of the path.
LOGO_PATH = Path("assets/bentley-logo-simplified-positive.png")
LOGO_NEGATIVE_PATH = Path("assets/bentley-logo-simplified-negative.png")


def get_logo_data_uri(negative=False):
    """Base64 data: URI for the logo, for embedding directly in HTML.

    Pass negative=True for the white-on-transparent variant, needed on dark
    backgrounds (e.g. the email header banners) - the dark-on-light default
    would be nearly invisible there.

    Used in Streamlit pages (unsafe_allow_html blocks) and email templates,
    where there's no "file on disk" the browser/email client can load from -
    only a string of HTML. Returns None if the asset is missing so callers
    can degrade gracefully rather than show a broken image.

    NB for email specifically: base64 data: URIs render fine in Gmail, Apple
    Mail, and mobile clients, but Outlook desktop has a long history of NOT
    rendering inline base64 images reliably. If dealership recipients are
    mostly on Outlook, the email logo may not always show - a real image URL
    hosted somewhere reachable would be the robust fix, which is
    infrastructure this project doesn't have yet.
    """
    path = LOGO_NEGATIVE_PATH if negative else LOGO_PATH
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f"data:image/png;base64,{encoded}"

# ============================================
# REPORT TYPOGRAPHY
# ============================================

# Font for generated Word reports.
#
# TWO DIFFERENT MECHANISMS, and they fail differently:
#
# 1. DOCUMENT TEXT — a .docx stores only the font NAME. Word resolves it when the
#    file is opened, so this works on any machine that has the font installed and
#    substitutes on any machine that does not. No font file is needed where the
#    report is generated.
#
# 2. CHART IMAGES — the radar and bar charts are rasterised to PNG by matplotlib
#    at generation time, so the font must be installed ON THE GENERATING MACHINE.
#    Streamlit Cloud does not have the Bentley typeface, so reports generated
#    there will have chart text in the fallback while the document text still
#    says Bentley. Generate client-facing reports locally to keep them
#    consistent, or accept the mismatch.
#
# LICENSING, UPDATED 2026-08-27: Ian has explicit permission from Xiao
# (Bentley brand hub) to use this typeface in client-facing, non-public-access
# situations - this covers the Leader Portal and the feedback forms (see
# BENTLEY_FONT_STACK below), which is why those font files now DO sit in
# assets/ and ARE committed. It does NOT cover the chart-image mechanism
# below - a different, separate permission - but the actual scope (Leader
# Portal + feedback forms) is unaffected by that distinction.
REPORT_FONT = 'Bentley'

# CHART FONT, REWORKED 2026-08-27 - see report_generator.py's resolve_chart_*
# functions for the actual implementation. Previously this was a NAME-based
# preference list, tried against whatever happens to be installed on the
# generating machine (CHART_FONT_PREFERENCE - Ian's own Mac has the real
# Bentley OTF family installed system-wide, Streamlit Cloud/Render never
# did, so chart text was consistent locally and fell back to Helvetica/Arial/
# DejaVu Sans wherever reports were generated remotely - the "generate
# client-facing reports locally to keep them consistent" caution elsewhere
# in this codebase exists because of exactly that gap).
#
# Genuinely closed now, not just documented around: three TTF files licensed
# specifically for this (Bentley-Regular_web.ttf, Bentley-Light_web.ttf,
# Bentley-Expanded Bold_web.ttf) are committed to assets/ and referenced
# DIRECTLY BY FILE PATH via matplotlib's FontProperties(fname=...), which
# works identically on every machine regardless of what's installed there -
# no name-based lookup, no per-environment inconsistency, no more local-vs-
# remote generation gap for chart text specifically.
#
# NOT name-based on purpose, not just historically: inspected with fontTools,
# these three TTF files carry a CORRECT family name ("Bentley", "Bentley
# Light", "Bentley Expanded Bold") on their Macintosh (platform 1) name-table
# entries, but every Windows-platform (platform 3, the one matplotlib/
# freetype actually reads for name-based lookup on any non-Mac machine,
# i.e. Render) name field - family, full name, PostScript name - is the
# literal DEL control character (U+007F), not a font bug but very likely a
# deliberate anti-extraction measure from the foundry on this specific "_web"
# file set. Confirmed live: fm.fontManager.addfont() on these files registers
# them under that garbled name, not "Bentley" - a name-based rcParams
# approach (the old CHART_FONT_PREFERENCE mechanism) would silently never
# match them on Render. fname= bypasses name resolution entirely and loads
# the font file's own glyph/outline data directly, unaffected by the
# corrupted name-table entries (confirmed by comparing this TTF's 'B' glyph
# outline - bounding box and contour count - byte-for-byte against the
# ALREADY-verified-genuine Bentley-Regular.woff used on the web pages: they
# matched exactly, proving this is the real typeface despite the name-table
# corruption, not a substituted placeholder).
BENTLEY_CHART_REGULAR_PATH = Path("assets/Bentley-Regular_web.ttf")
BENTLEY_CHART_LIGHT_PATH = Path("assets/Bentley-Light_web.ttf")
BENTLEY_CHART_EXPANDED_BOLD_PATH = Path("assets/Bentley-Expanded Bold_web.ttf")

# Legacy name-based fallback, kept ONLY for resolve_chart_font()'s "did a
# real Bentley family somehow get installed on this machine anyway" check -
# not the primary mechanism any more, see report_generator.py.
CHART_FONT_PREFERENCE = ['Bentley', 'Bentley TT', 'Helvetica Neue', 'Arial', 'DejaVu Sans']

# ============================================
# UI TYPEFACE (Leader Portal + feedback forms only)
# ============================================
#
# Separate from REPORT_FONT/CHART_FONT_PREFERENCE above, which are about the
# Word reports and their charts - genuinely different code paths with
# genuinely different constraints (a .docx just stores a font NAME; a
# browser needs the actual font FILE). Scope here is deliberately narrower
# than "everywhere Bentley Compass 360 renders": the Admin Dashboard is
# explicitly excluded (internal tool, Ian's own call, not part of the
# licensed client-facing scope) and so are the generated reports (see the
# REPORT_FONT comment above - not the same problem, not addressed here).
#
# Only Light (300) and Regular (400) exist as real "normal-width" cuts -
# there is no true bold IN THIS WIDTH. Declaring ANY face at a given weight
# tells the browser that weight is covered, which suppresses its own
# synthetic-bold fallback (font-synthesis) for that family - so mislabelling
# Regular as 700 doesn't make text bolder, it makes requesting bold text
# FAIL to synthesise anything, silently rendering as plain Regular. Real
# mistake made once already while testing the live A/B comparison this
# section exists to support - worth remembering if this ever gets touched
# again.
#
# GENUINE BOLD, DECIDED 2026-08-27 (see the "Genuine Bold Rollout" task in
# CLAUDE.md): the comparison above resolved in favour of the real Expanded
# Bold face over browser-synthesised bold - bold is used sparingly here
# (card titles, chips, stat numbers, section headings), never in running
# body text, so the wider Expanded design reads as a deliberate accent
# rather than a constant width-mismatch. BENTLEY_EXPANDED_BOLD_PATH is
# registered as weight:700 under the SAME 'Bentley' family name (not a
# separate family) below, specifically so every element that already
# resolves to family 'Bentley' at weight:700 - h1-h3 (browsers bold
# headings by default), and every explicit font-weight:700 rule already
# using BENTLEY_FONT_STACK - picks up the genuine face automatically, with
# no need to hunt down and individually retarget each selector. This is
# safe/correct CSS font-matching, not the same mistake as above: that
# warning was about mislabelling Regular (no true bold exists for IT);
# Expanded Bold IS a true, deliberately heavier-and-wider cut, so labelling
# it 700 is accurate, not a mislabel.
BENTLEY_LIGHT_PATH = Path("assets/Bentley-Light.woff")
BENTLEY_REGULAR_PATH = Path("assets/Bentley-Regular.woff")
BENTLEY_EXPANDED_BOLD_PATH = Path("assets/Bentley-Expanded Bold.woff")

# Font stack for use in Streamlit unsafe_allow_html CSS: 'Bentley' first,
# falling back to the same system-font stack already used across this app's
# UI CSS if the font ever fails to load, so nothing breaks visually either
# way.
BENTLEY_FONT_STACK = (
    "'Bentley', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
)


def font_face_css(family, path, weight=400, style='normal'):
    """One base64-embedded @font-face block for `path`, under `family`/`weight`.

    Base64-embedded (not a plain url() path to the file on disk) for the same
    reason get_logo_data_uri above embeds images rather than linking them:
    there's no guarantee a given Streamlit deployment target serves a static
    assets folder over HTTP at all, so a browser-fetchable path can't be
    relied on - embedding the bytes directly works identically everywhere.
    Returns '' if the file is missing, so callers can compose several of
    these and degrade gracefully (the font stack's own fallback still
    applies) rather than crash on a missing asset.
    """
    if not path.exists():
        return ''
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return (
        f"@font-face {{font-family:'{family}';"
        f"src:url(data:font/woff;base64,{encoded}) format('woff');"
        f"font-weight:{weight};font-style:{style};font-display:swap;}}\n"
    )


def get_bentley_font_face_css():
    """@font-face declarations for the three cuts of the Bentley typeface
    used across the UI, all under the shared 'Bentley' family name so
    BENTLEY_FONT_STACK's font-weight rules resolve to the correct file:
    Light (300), Regular (400), and - decided 2026-08-27 - Expanded Bold
    (700), the genuine bold face. See the module comment above for why
    700 is a real, deliberate face here (not the earlier mislabelling
    mistake it looks superficially similar to)."""
    return (
        font_face_css('Bentley', BENTLEY_LIGHT_PATH, weight=300)
        + font_face_css('Bentley', BENTLEY_REGULAR_PATH, weight=400)
        + font_face_css('Bentley', BENTLEY_EXPANDED_BOLD_PATH, weight=700)
    )


# Logotype face - the "BENTLEY COMPASS 360" wordmark specifically, NOT a
# general body/UI font. Confirmed with Ian 2026-08-27 for the topbar lockup
# (leader portal brand text, feedback form headers) - do not apply this
# family anywhere else without checking with him first, since a display
# logotype face is not guaranteed to carry full, evenly-weighted Latin
# glyph coverage the way Regular/Light do.
BENTLEY_LOGOTYPE_PATH = Path("assets/Bentley-Logotype.woff")


def get_bentley_logotype_face_css():
    """@font-face for the Bentley Logotype face, under its own family name
    (deliberately NOT folded into 'Bentley'/BENTLEY_FONT_STACK - this face
    is for the brand wordmark only, callers must opt in per-element)."""
    return font_face_css('Bentley Logotype', BENTLEY_LOGOTYPE_PATH, weight=400)

# ============================================
# THRESHOLDS
# ============================================

HIGH_SCORE_THRESHOLD = 4.0
SIGNIFICANT_GAP = 0.5
MIN_RESPONSES_FOR_REPORT = 5

# Anonymity threshold - groups with fewer responses than this
# will have their scores folded into "Others" category
# Boss is exempt (always shown with n=1)
# Self is exempt (always shown)
ANONYMITY_THRESHOLD = 3

# Nomination category requirements - the single source of truth for the
# min/suggested/max numbers shown to a leader when nominating raters.
# MOVED HERE from leader_portal.py 2026-08-29: the invitation email
# (email_sender.py) had its own hardcoded copy of these numbers and had
# drifted out of sync with the portal's own copy after a wording update -
# a real bug found during a leader-portal walkthrough. Both leader_portal.py
# (which builds the portal's own HTML-formatted CATEGORY_REQ_TEXT from this)
# and email_sender.py (which builds its own plain-text guidance lines from
# it) now import this same dict, so the underlying numbers - the part
# actually likely to change - can't silently diverge between them again.
# The exact wording template is still written once per caller (the portal
# bolds the minimum number; the email doesn't), since the two contexts
# render differently, but both are built from these same figures.
#
# 'suggested' is deliberately 0 for Others, not 5 - Others has no flat
# target the way Peers/DRs do (see each caller's own guidance text).
# 'ring_target' is a SEPARATE number the leader portal uses only for its
# progress ring's geometry/label, so it can give a full ring at 5 (matching
# the other three categories visually) without implying a flat "5" target
# in the copy, which would misstate a category that often can't realistically
# reach it - this doesn't touch the portal's chip logic, which reads
# 'min_if_any' directly, never 'suggested' or 'ring_target'.
RATER_REQUIREMENTS = {
    'Boss': {'min': 1, 'max': 2, 'suggested': 1, 'required_nomination': True, 'show_minimum': True},
    'Peers': {'min': 3, 'max': 10, 'suggested': 5, 'required_nomination': True, 'show_minimum': True},
    'DRs': {'min': 3, 'max': 10, 'suggested': 5, 'required_nomination': True, 'show_minimum': True},
    'Others': {'min': 0, 'max': 10, 'suggested': 0, 'required_nomination': False,
               'show_minimum': False, 'min_if_any': ANONYMITY_THRESHOLD, 'ring_target': 5}
}

# ============================================
# COMMENT SECTIONS
# ============================================

COMMENT_SECTIONS = list(DIMENSIONS.keys()) + ['keep', 'change']

# ============================================
# SELF-IDENTIFIED DEVELOPMENT PRIORITIES
# ============================================

# The leader ranks up to this many priorities at self-assessment. Each is chosen
# from DIMENSIONS, with free text used to name the specific behaviours and actions
# they intend to work on within that dimension.
DEVELOPMENT_PRIORITY_COUNT = 3

# At least this many must be chosen before the self-assessment can be submitted.
# Set to 1 on the human's instruction (2026-08-04): the leader must commit to at
# least one area to work on, but naming a second and third stays optional.
DEVELOPMENT_PRIORITY_MINIMUM = 1

# Whenever a dimension IS chosen, its actions text is required. A dimension with
# no actions is close to useless in a coaching conversation, and it lets someone
# pick three areas and submit having said nothing about any of them. The minimum
# length is deliberately low: it blocks "." and "n/a" without picking a fight
# with anyone writing a genuinely terse but real answer.
DEVELOPMENT_PRIORITY_ACTION_MIN_CHARS = 10

DEVELOPMENT_PRIORITY_INTRO = (
    "Before you finish, name the areas you most want to develop, in priority "
    "order. Choose the dimension, then be specific about the behaviours you want "
    "to change and what you intend to do differently. Priority 1 is required; "
    "the second and third are optional. If it helps, look back at what you wrote "
    "in the closing questions above and build on that. These become the starting "
    "point for your coaching conversation."
)

DEVELOPMENT_PRIORITY_PROMPT = (
    "What specifically will you work on in {dimension}? Name the behaviours and "
    "the actions you intend to take."
)

# Helper to get dimension for an item
def get_dimension_for_item(item_num):
    """Return the dimension name for a given item number."""
    for dim_name, (start, end) in DIMENSIONS.items():
        if start <= item_num <= end:
            return dim_name
    return None
