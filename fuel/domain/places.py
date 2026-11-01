"""Place-name rules shared by data loading and request parsing."""

import re

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
    "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)

_ABBREVIATIONS = [("saint ", "st "), ("st. ", "st "), ("sainte ", "ste "), ("fort ", "ft "), ("mount ", "mt ")]


def normalize_place_name(name: str) -> str:
    """'St. Louis' and 'Saint Louis' both become 'stlouis'."""
    name = name.strip().lower() + " "
    for long, short in _ABBREVIATIONS:
        name = name.replace(long, short)
    return re.sub(r"[^a-z0-9]", "", name)
