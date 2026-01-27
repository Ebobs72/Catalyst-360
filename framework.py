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
}

# ============================================
# ALL 42 ITEMS
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
    17: "Holds people accountable for their commitments",
    18: "Makes timely decisions rather than delaying unnecessarily",
    19: "Follows through on agreed actions and expects others to do the same",
    20: "Delivers results consistently",
    
    # Leading Change (21-25)
    21: "Prepares their team well when change is coming",
    22: "Helps people understand the reasons behind change, not just what's changing",
    23: "Addresses resistance to change constructively rather than ignoring it",
    24: "Maintains momentum through the difficult middle stages of change",
    25: "Looks for opportunities to improve and innovate, not just maintain the status quo",
    
    # Communicating & Influencing (26-30)
    26: "Listens genuinely rather than just waiting to speak",
    27: "Communicates clearly so people understand what's expected",
    28: "Gives feedback that is timely, specific, and constructive",
    29: "Adapts their communication style to different people and situations",
    30: "Influences through engagement rather than just telling people what to do",
    
    # Building Trust (31-35)
    31: "Does what they say they will do",
    32: "Admits mistakes and takes responsibility when things go wrong",
    33: "Shares information openly rather than keeping people in the dark",
    34: "Acknowledges and celebrates good work",
    35: "Creates an environment where people feel safe to speak up",
    
    # Thinking Strategically (36-40)
    36: "Thinks beyond their immediate area to consider wider organisational impact",
    37: "Balances short-term pressures with longer-term priorities",
    38: "Builds effective relationships with key stakeholders across the business",
    39: "Involves their team in shaping direction rather than dictating it",
    40: "Identifies and manages risks before they become problems",
    
    # Overall Effectiveness (41-42)
    41: "Overall, is an effective leader",
    42: "I would want to work with this person again",
}

# ============================================
# DIMENSION DESCRIPTIONS
# ============================================

DIMENSION_DESCRIPTIONS = {
    'Leading Self': "Personal effectiveness, self-management, and leading by example. Leaders strong in this area manage their time well, delegate appropriately, stay composed under pressure, and actively seek feedback to improve.",
    
    'Developing Others': "Growing capability in individuals and teams. Leaders strong in this area invest in development conversations, create learning environments, coach rather than direct, and build team independence.",
    
    'Building High-Performing Teams': "Creating the conditions for teams to thrive. Leaders strong in this area build collaborative teams, address dysfunction, bring energy, adapt their style, and balance challenge with care.",
    
    'Driving Results': "Delivering performance through others. Leaders strong in this area set clear expectations, hold people accountable, make timely decisions, follow through, and deliver consistently.",
    
    'Leading Change': "Navigating teams through uncertainty and transformation. Leaders strong in this area prepare people for change, explain the why, address resistance, maintain momentum, and seek innovation.",
    
    'Communicating & Influencing': "Connecting with others and getting buy-in. Leaders strong in this area listen well, communicate clearly, give constructive feedback, adapt their style, and influence through engagement.",
    
    'Building Trust': "Creating psychological safety and credibility. Leaders strong in this area keep promises, admit mistakes, share information, recognise good work, and create safety for speaking up.",
    
    'Thinking Strategically': "Seeing the bigger picture and planning ahead. Leaders strong in this area think beyond their area, balance short and long-term, build stakeholder relationships, involve others, and manage risk.",
}

# ============================================
# RATING SCALE
# ============================================

RATING_SCALE = {
    1: "Strongly Disagree",
    2: "Disagree", 
    3: "Neither Agree nor Disagree",
    4: "Agree",
    5: "Strongly Agree",
}

# ============================================
# RESPONDENT GROUPS
# ============================================

RELATIONSHIP_TYPES = {
    'Self': 'Self-Assessment',
    'Boss': 'Line Manager',
    'Peers': 'Peer',
    'DRs': 'Direct Report',
    'Others': 'Other Colleague',
}

GROUP_DISPLAY = {
    'Self': 'Self',
    'Boss': 'Line Manager',
    'Peers': 'Peers',
    'DRs': 'Direct Reports',
    'Others': 'Others',
}

# ============================================
# COLOURS
# ============================================

COLOURS = {
    'primary_blue': '#2F5496',
    'orange': '#C65911',
    'green': '#548235',
    'dark_green': '#375623',
    'purple': '#7030A0',
    'gold': '#BF9000',
    'grey': '#808080',
    'light_grey': '#B0B0B0',
    'bentley_green': '#024731',
}

GROUP_COLORS = {
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
