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
    1: {"self": "I manage my own emotions effectively, even under pressure", "other": "They manage their own emotions effectively, even under pressure"},
    2: {"self": "I acknowledge my strengths and development areas openly", "other": "They acknowledge their strengths and development areas openly"},
    3: {"self": "I stay composed when situations get difficult", "other": "They stay composed when situations get difficult"},
    4: {"self": "I take responsibility for my mistakes and learn from them", "other": "They take responsibility for their mistakes and learn from them"},
    5: {"self": "I act in line with my stated values, even when it's costly to do so", "other": "They act in line with their stated values, even when it's costly to do so"},

    # Developing Others (6-10)
    6: {"self": "I provide constructive feedback to help others improve", "other": "They provide constructive feedback to help others improve"},
    7: {"self": "I create opportunities for people to develop new skills", "other": "They create opportunities for people to develop new skills"},
    8: {"self": "I take interest in the career aspirations of my team", "other": "They take interest in the career aspirations of their team"},
    9: {"self": "I coach people to solve problems rather than providing solutions", "other": "They coach people to solve problems rather than providing solutions"},
    10: {"self": "I identify high-potential talent and nurture future leaders", "other": "They identify high-potential talent and nurture future leaders"},

    # Building High-Performing Teams (11-15)
    11: {"self": "I respond to mistakes and bad news without blame", "other": "They respond to mistakes and bad news without blame"},
    12: {"self": "I foster collaboration and shared ownership within the team", "other": "They foster collaboration and shared ownership within the team"},
    13: {"self": "I tackle disagreements in the team early, before they fester", "other": "They tackle disagreements in the team early, before they fester"},
    14: {"self": "I celebrate team successes and recognise contributions", "other": "They celebrate team successes and recognise contributions"},
    15: {"self": "I build team capability and ensure knowledge sharing", "other": "They build team capability and ensure knowledge sharing"},

    # Driving Results (16-20)
    16: {"self": "I set clear, ambitious, and measurable goals", "other": "They set clear, ambitious, and measurable goals"},
    17: {"self": "I establish clear accountability for results", "other": "They establish clear accountability for results"},
    18: {"self": "I monitor progress regularly and adjust plans when needed", "other": "They monitor progress regularly and adjust plans when needed"},
    19: {"self": "I push the team to deliver business results consistently", "other": "They push the team to deliver business results consistently"},
    20: {"self": "I balance short-term delivery with sustainable, long-term performance", "other": "They balance short-term delivery with sustainable, long-term performance"},

    # Leading Change (21-25)
    21: {"self": "I identify the need for change and initiate it proactively", "other": "They identify the need for change and initiate it proactively"},
    22: {"self": "I create a compelling vision for change that inspires people", "other": "They create a compelling vision for change that inspires people"},
    23: {"self": "I help people understand and adapt to change", "other": "They help people understand and adapt to change"},
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
    36: {"self": "I think about broader business implications of decisions", "other": "They think about broader business implications of decisions"},
    37: {"self": "I anticipate market trends and competitive threats", "other": "They anticipate market trends and competitive threats"},
    38: {"self": "I see connections between different parts of the business", "other": "They see connections between different parts of the business"},
    39: {"self": "I consider long-term consequences in my decision-making", "other": "They consider long-term consequences in their decision-making"},
    40: {"self": "I challenge assumptions and explore multiple perspectives", "other": "They challenge assumptions and explore multiple perspectives"},

    # Performance Excellence (41-45)
    41: {"self": "I apply structured approaches to solve complex problems", "other": "They apply structured approaches to solve complex problems"},
    42: {"self": "I systematically analyse problems before taking action", "other": "They systematically analyse problems before taking action"},
    43: {"self": "I drive continuous improvement in processes and systems", "other": "They drive continuous improvement in processes and systems"},
    44: {"self": "I use data and evidence to inform decisions", "other": "They use data and evidence to inform decisions"},
    45: {"self": "I embed quality and excellence into everything we do", "other": "They embed quality and excellence into everything they do"},
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
    'charcoal': '#4D4D4F',           # Radar chart All Raters line/markers only
                                      # (see 'radar_all_raters' below) - no
                                      # longer the bar-chart All Raters colour
                                      # as of 2026-08-08, see 'heritage_white'.
    'charcoal_grey': '#5F5E5A',      # Potential Blind Spots header
    'radar_all_raters': '#B2B2B2',   # All Raters FILL on the OVERVIEW RADAR
                                      # ONLY, not the bar charts. Confirmed
                                      # Bentley brand value, lighter than
                                      # 'charcoal' on purpose: the radar's two
                                      # series have semi-transparent fills that
                                      # overlap, and a charcoal fill sat too
                                      # close to bentley_green's fill in tonal
                                      # value - the blended overlap read as
                                      # indistinct from either series alone.
                                      # Bar charts don't stack fills like this,
                                      # so they don't need this split.
    'heritage_white': '#DCD8C0',     # All Raters bar colour (item bar charts,
                                      # self-only bar) AND, separately, the
                                      # Development Areas PAPU-NANU header -
                                      # same hex value serving two different
                                      # concepts, flagged 2026-08-08 and
                                      # confirmed intentional by the human:
                                      # it's a real colour in the confirmed
                                      # palette, so reusing it is fine.
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
    'good_news_tint_pale': '#DCE0DC', # Executive Summary "under-rating"
                                      # (self scores below All Raters, the
                                      # same direction as Good News) gap cell -
                                      # an 85% tint of bentley_green, pale
                                      # enough for the cell's dark body text,
                                      # calibrated to a similar lightness to
                                      # the arbitrary Excel green it replaces.
    'blind_spot_tint_pale': '#EFEFEE', # Executive Summary "over-rating" (self
                                      # scores above All Raters, the same
                                      # direction as Potential Blind Spots) gap
                                      # cell - a 90% tint of charcoal_grey
                                      # (the Blind Spots header colour), same
                                      # logic as good_news_tint_pale above:
                                      # the gap direction that already has a
                                      # PAPU-NANU identity elsewhere in the
                                      # report reuses that identity here too,
                                      # rather than an arbitrary unrelated hue.
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
# (GROUP_DISPLAY['Combined']) is 'heritage_white' on bar charts and 'charcoal'
# / 'radar_all_raters' on the radar - not a GROUP_COLOURS entry since it isn't
# a rater group.
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
# The Bentley typeface is proprietary ("BENTLEY TYPE is a trademark of BENTLEY"),
# so its font files must NOT be committed to this repository to make the cloud
# case work. That would need a licensing decision, not a code change.
REPORT_FONT = 'Bentley'

# Tried in order when rendering charts, first one actually installed wins.
CHART_FONT_PREFERENCE = ['Bentley', 'Bentley TT', 'Helvetica Neue', 'Arial', 'DejaVu Sans']

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
