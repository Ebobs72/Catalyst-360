#!/usr/bin/env python3
"""
Framework configuration for the 360 Development Catalyst.

Contains all dimensions, items, and display configuration.
"""

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
# ALL 47 ITEMS
# ============================================

ITEMS = {
    # Leading Self (1-5)
    1: "Maintains a healthy balance between strategic leadership and day-to-day management",
    2: "Manages their time effectively, focusing on high-value activities rather than firefighting",
    3: "Delegates appropriately rather than taking on too much themselves",
    4: "Stays calm and composed under pressure",
    5: "Is open to feedback on their own leadership and actively works to improve",
    
    # Developing Others (6-10)
    6: "Invests time in developing their team members as individuals",
    7: "Has meaningful development conversations, not just operational catch-ups",
    8: "Creates an environment where people are encouraged to learn and grow",
    9: "Helps their people think through problems rather than simply providing answers",
    10: "Builds the capability of their team to operate more independently over time",
    
    # Building High-Performing Teams (11-15)
    11: "Builds teams that work well together and support each other",
    12: "Addresses dysfunctional team dynamics rather than ignoring them",
    13: "Brings positive energy to their team, even in challenging times",
    14: "Adapts their leadership style to what different team members need",
    15: "Challenges people to perform while genuinely caring about them as individuals",
    
    # Driving Results (16-20)
    16: "Sets clear expectations so people know what success looks like",
    17: "Holds people accountable for their commitments in a fair and consistent way",
    18: "Makes timely decisions rather than delaying unnecessarily",
    19: "Follows through on agreed actions and expects the same from others",
    20: "Maintains focus on priorities rather than being distracted by less important issues",
    
    # Leading Change (21-25)
    21: "Helps their team understand the reasons behind changes",
    22: "Supports their people through uncertainty rather than leaving them to cope alone",
    23: "Encourages new ideas and ways of working",
    24: "Adapts their approach when circumstances change rather than sticking rigidly to plans",
    25: "Builds commitment to change rather than just compliance",
    
    # Communicating & Influencing (26-30)
    26: "Listens well and considers different perspectives before reaching conclusions",
    27: "Communicates clearly so people understand what's expected",
    28: "Keeps people appropriately informed rather than leaving them guessing",
    29: "Adapts their communication style to different audiences",
    30: "Is able to influence others without relying on positional authority",
    
    # Building Trust (31-35)
    31: "Does what they say they will do",
    32: "Is honest even when the message is difficult",
    33: "Shares information openly rather than keeping people in the dark",
    34: "Acknowledges and celebrates good work",
    35: "Creates an environment where people feel safe to speak up",
    
    # Thinking Strategically (36-40)
    36: "Thinks beyond their immediate area to consider wider organisational impact",
    37: "Balances short-term pressures with longer-term priorities",
    38: "Builds effective relationships with key stakeholders across the business",
    39: "Involves their team in shaping direction rather than dictating it",
    40: "Identifies and manages risks before they become problems",
    
    # Performance Excellence (41-45)
    41: "Uses the Performance Excellence framework to prioritise opportunities based on data rather than instinct",
    42: "Clearly defines problem statements before jumping into solutions",
    43: "Breaks larger issues into structured, manageable stages to ensure problems are solved at the right level",
    44: "Engages the right people at each stage of the funnel to validate assumptions and strengthen solutions",
    45: "Follows through on improvement actions and tracks impact to ensure benefits are realised and sustained",
    
    # Overall Effectiveness (46-47)
    46: "Overall, is an effective leader",
    47: "I would want to work with this person again",
}

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
    'Combined': 'Combined Others'
}

# ============================================
# COLOURS
# ============================================

COLOURS = {
    'primary_green': '#024731',
    'primary_blue': '#1B365D',
    'orange': '#D35400',
    'green': '#27AE60',
    'purple': '#8E44AD',
    'gold': '#C5A028',
    'light_grey': '#F5F5F5',
    'dark_grey': '#333333',
}

GROUP_COLOURS = {
    'Self': COLOURS['primary_blue'],
    'Boss': COLOURS['orange'],
    'Peers': COLOURS['green'],
    'DRs': COLOURS['purple'],
    'Others': COLOURS['gold'],
}

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

COMMENT_SECTIONS = list(DIMENSIONS.keys()) + ['strengths', 'development']

# Helper to get dimension for an item
def get_dimension_for_item(item_num):
    """Return the dimension name for a given item number."""
    for dim_name, (start, end) in DIMENSIONS.items():
        if start <= item_num <= end:
            return dim_name
    return None
