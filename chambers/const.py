"""
Chambers CONSTANTS
"""

# Events
OTHER = 0
CONVENE = 1
CONVENE_SCHEDULED = 2
RECONVENE = 3
ADJOURN = 4
RECESS_TIME = 5
RECESS_COC = 6
RECESS_15M = 7
MORNING_DEBATE = 10
DEBATE_BILL = 11
VOTE_VOICE = 21
VOTE_RECORDED = 22

# Event Groups
ALL_EVENTS = (CONVENE, RECONVENE, ADJOURN, RECESS_TIME, RECESS_COC, MORNING_DEBATE, DEBATE_BILL, VOTE_VOICE, VOTE_RECORDED)
RECESS = (RECESS_TIME, RECESS_COC)
VOTE = (VOTE_VOICE, VOTE_RECORDED)