"""Design system for the Persian audit deck (16:9, RTL)."""

from pptx.util import Inches, Pt

# ---------------------------------------------------------------- palette
NAVY_DEEP = "081A2A"
NAVY = "0F2A42"
NAVY_2 = "163D5C"
STEEL = "2F6285"
STEEL_LIGHT = "6E93AB"
GOLD = "C39A47"
GOLD_DEEP = "9A7626"
GOLD_LIGHT = "EBD9B4"
TEAL = "1B6E68"
RED = "9E3B3B"
GREEN = "2C6B4F"
TEXT = "14283A"
MUTED = "5C7488"
MUTED_LIGHT = "8CA0B0"
LINE = "CCD9E3"
LINE_SOFT = "E3EBF2"
BG_SOFT = "F4F7FA"
BG_TINT = "EDF2F7"
WHITE = "FFFFFF"

FONT = "Tahoma"

# ---------------------------------------------------------------- geometry (inches)
SW, SH = 13.333, 7.5
ML, MR = 0.62, 0.62
CW = SW - ML - MR                 # 12.093
HEADER_KICKER_Y = 0.44
HEADER_TITLE_Y = 0.70
HEADER_RULE_Y = 1.42
BODY_TOP = 1.66
BODY_BOTTOM = 6.66
FOOTER_RULE_Y = 6.92
FOOTER_TEXT_Y = 7.00

# ---------------------------------------------------------------- type scale
T_TITLE = 27
T_KICKER = 11.5
T_LEAD = 17
T_BODY = 15
T_SMALL = 13
T_TABLE = 12
T_TINY = 10.5
T_BIG_NUM = 30


def hexcolor(h: str):
    from pptx.dml.color import RGBColor
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
