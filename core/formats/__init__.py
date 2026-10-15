"""
Project-level format overrides.

Django's `en` locale sets TIME_FORMAT to "P" (lowercase "a.m./p.m." with periods).
We override here to force the project convention: 12-hour with UPPERCASE AM/PM
matching Indian usage. Without this, settings.TIME_FORMAT is shadowed by the
locale file when USE_L10N=True.
"""
# 12-hour, no leading zero on hour, minutes with leading zero, uppercase AM/PM.
# Example: "2:30 PM"
TIME_FORMAT = "g:i A"

# Match the convention for any datetime that includes a time component.
DATETIME_FORMAT = "N j, Y, g:i A"
SHORT_DATETIME_FORMAT = "j M Y, g:i A"
