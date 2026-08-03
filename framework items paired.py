# ============================================================================
# Compass 360 — paired item set (self / other), frequency scale, open prompts
# Drop-in replacement for the ITEMS block in framework.py, plus additions.
#
# What changed from the current framework.py:
#  - ITEMS values are now (dimension, {"self": "...", "other": "..."}) instead
#    of (dimension, "single string"). Serve the right form by rater type.
#  - 9 items reworded for the frequency scale (marked below).
#  - Added SCALE_FREQUENCY, OPEN_PROMPTS, get_item_text(), get_prompt_text().
#
# CALLER CHANGES NEEDED (flagged, not yet made):
#  - Anywhere that read ITEMS[n][1] as a string must now call
#    get_item_text(n, relationship) instead.
#  - Items 46-47 (old overall-effectiveness ratings) are REMOVED from ITEMS
#    and replaced by OPEN_PROMPTS (open text, routed to comments, not scored).
#  - Report averaging must treat a 0 ("No opportunity") as excluded from the
#    mean, not as a low score.
# ============================================================================

ITEMS = {
    # Leading Self (Q1-5)
    1: ("Leading Self", {"self": "I manage my own emotions effectively, even under pressure", "other": "They manage their own emotions effectively, even under pressure"}),
    2: ("Leading Self", {"self": "I acknowledge my strengths and development areas openly", "other": "They acknowledge their strengths and development areas openly"}),  # reworded for frequency scale
    3: ("Leading Self", {"self": "I stay composed when situations get difficult", "other": "They stay composed when situations get difficult"}),  # reworded for frequency scale
    4: ("Leading Self", {"self": "I take responsibility for my mistakes and learn from them", "other": "They take responsibility for their mistakes and learn from them"}),
    5: ("Leading Self", {"self": "I act in line with my stated values, even when it's costly to do so", "other": "They act in line with their stated values, even when it's costly to do so"}),  # reworded for frequency scale

    # Developing Others (Q6-10)
    6: ("Developing Others", {"self": "I provide constructive feedback to help others improve", "other": "They provide constructive feedback to help others improve"}),
    7: ("Developing Others", {"self": "I create opportunities for people to develop new skills", "other": "They create opportunities for people to develop new skills"}),
    8: ("Developing Others", {"self": "I take interest in the career aspirations of my team", "other": "They take interest in the career aspirations of their team"}),
    9: ("Developing Others", {"self": "I coach people to solve problems rather than providing solutions", "other": "They coach people to solve problems rather than providing solutions"}),
    10: ("Developing Others", {"self": "I identify high-potential talent and nurture future leaders", "other": "They identify high-potential talent and nurture future leaders"}),

    # Building High-Performing Teams (Q11-15)
    11: ("Building High-Performing Teams", {"self": "I respond to mistakes and bad news without blame", "other": "They respond to mistakes and bad news without blame"}),  # reworded for frequency scale
    12: ("Building High-Performing Teams", {"self": "I foster collaboration and shared ownership within the team", "other": "They foster collaboration and shared ownership within the team"}),
    13: ("Building High-Performing Teams", {"self": "I tackle disagreements in the team early, before they fester", "other": "They tackle disagreements in the team early, before they fester"}),  # reworded for frequency scale
    14: ("Building High-Performing Teams", {"self": "I celebrate team successes and recognise contributions", "other": "They celebrate team successes and recognise contributions"}),
    15: ("Building High-Performing Teams", {"self": "I build team capability and ensure knowledge sharing", "other": "They build team capability and ensure knowledge sharing"}),

    # Driving Results (Q16-20)
    16: ("Driving Results", {"self": "I set clear, ambitious, and measurable goals", "other": "They set clear, ambitious, and measurable goals"}),
    17: ("Driving Results", {"self": "I establish clear accountability for results", "other": "They establish clear accountability for results"}),
    18: ("Driving Results", {"self": "I monitor progress regularly and adjust plans when needed", "other": "They monitor progress regularly and adjust plans when needed"}),
    19: ("Driving Results", {"self": "I push the team to deliver business results consistently", "other": "They push the team to deliver business results consistently"}),
    20: ("Driving Results", {"self": "I balance short-term delivery with sustainable, long-term performance", "other": "They balance short-term delivery with sustainable, long-term performance"}),

    # Leading Change (Q21-25)
    21: ("Leading Change", {"self": "I identify the need for change and initiate it proactively", "other": "They identify the need for change and initiate it proactively"}),
    22: ("Leading Change", {"self": "I create a compelling vision for change that inspires people", "other": "They create a compelling vision for change that inspires people"}),
    23: ("Leading Change", {"self": "I help people understand and adapt to change", "other": "They help people understand and adapt to change"}),
    24: ("Leading Change", {"self": "I keep the team steady when things are uncertain", "other": "They keep the team steady when things are uncertain"}),  # reworded for frequency scale
    25: ("Leading Change", {"self": "I build momentum and sustain change through to completion", "other": "They build momentum and sustain change through to completion"}),

    # Communicating and Influencing (Q26-30)
    26: ("Communicating and Influencing", {"self": "I articulate ideas clearly and ensure understanding", "other": "They articulate ideas clearly and ensure understanding"}),
    27: ("Communicating and Influencing", {"self": "I adapt my communication style to different audiences", "other": "They adapt their communication style to different audiences"}),
    28: ("Communicating and Influencing", {"self": "I listen actively and consider others' perspectives", "other": "They listen actively and consider others' perspectives"}),
    29: ("Communicating and Influencing", {"self": "I influence others effectively to achieve outcomes", "other": "They influence others effectively to achieve outcomes"}),
    30: ("Communicating and Influencing", {"self": "I communicate with confidence and authority", "other": "They communicate with confidence and authority"}),

    # Building Trust (Q31-35)
    31: ("Building Trust", {"self": "I follow through on my commitments and promises", "other": "They follow through on their commitments and promises"}),
    32: ("Building Trust", {"self": "I share information openly, including when it's difficult", "other": "They share information openly, including when it's difficult"}),  # reworded for frequency scale
    33: ("Building Trust", {"self": "I give people a fair hearing before reaching a view", "other": "They give people a fair hearing before reaching a view"}),  # reworded for frequency scale
    34: ("Building Trust", {"self": "I stay fair to everyone involved when handling disagreements", "other": "They stay fair to everyone involved when handling disagreements"}),  # reworded for frequency scale
    35: ("Building Trust", {"self": "I build strong relationships based on mutual respect", "other": "They build strong relationships based on mutual respect"}),

    # Thinking Strategically (Q36-40)
    36: ("Thinking Strategically", {"self": "I think about broader business implications of decisions", "other": "They think about broader business implications of decisions"}),
    37: ("Thinking Strategically", {"self": "I anticipate market trends and competitive threats", "other": "They anticipate market trends and competitive threats"}),
    38: ("Thinking Strategically", {"self": "I see connections between different parts of the business", "other": "They see connections between different parts of the business"}),
    39: ("Thinking Strategically", {"self": "I consider long-term consequences in my decision-making", "other": "They consider long-term consequences in their decision-making"}),
    40: ("Thinking Strategically", {"self": "I challenge assumptions and explore multiple perspectives", "other": "They challenge assumptions and explore multiple perspectives"}),

    # Performance Excellence (Q41-45)
    41: ("Performance Excellence", {"self": "I apply structured approaches to solve complex problems", "other": "They apply structured approaches to solve complex problems"}),
    42: ("Performance Excellence", {"self": "I systematically analyse problems before taking action", "other": "They systematically analyse problems before taking action"}),
    43: ("Performance Excellence", {"self": "I drive continuous improvement in processes and systems", "other": "They drive continuous improvement in processes and systems"}),
    44: ("Performance Excellence", {"self": "I use data and evidence to inform decisions", "other": "They use data and evidence to inform decisions"}),
    45: ("Performance Excellence", {"self": "I embed quality and excellence into everything we do", "other": "They embed quality and excellence into everything they do"}),

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
    dimension, forms = ITEMS[item_number]
    return forms["self" if relationship == "Self" else "other"]

def get_prompt_text(prompt_key, relationship):
    return OPEN_PROMPTS[prompt_key]["self" if relationship == "Self" else "other"]
