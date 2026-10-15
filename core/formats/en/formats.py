"""
Project-level format overrides for language "en" / "en-us".
Forces 12-hour with UPPERCASE AM/PM (Indian convention) instead of
Django's default 12-hour "a.m./p.m." (en locale uses "P" strftime).
"""
# Example: "2:30 PM"
TIME_FORMAT = "g:i A"

# Datetime formats (kept consistent with TIME_FORMAT).
DATETIME_FORMAT = "N j, Y, g:i A"
SHORT_DATETIME_FORMAT = "j M Y, g:i A"
