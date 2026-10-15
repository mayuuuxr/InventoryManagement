"""Template filters for stock quantities (whole numbers in this industry)."""
from django import template

from entries.utils import fmt_qty

register = template.Library()


@register.filter(name="whole")
def whole(value):
    """160.00 -> "160". See entries.utils.fmt_qty."""
    return fmt_qty(value)
