from datetime import datetime, time
from django import template
from django.utils.timesince import timesince
from django.utils.formats import date_format

register = template.Library()


@register.filter("utc_timesince", is_safe=False)
def timesince_filter(value):
    """Formats a date as the time since that date (i.e. "4 days, 6 hours")."""
    if not value:
        return ''
    try:
        return timesince(value, datetime.utcnow())
    except (ValueError, TypeError, AttributeError):
        return ''


@register.filter("replace_hour")
def replace_hour(value, argv):
    if not value:
        return ''

    if isinstance(value, datetime):
        return datetime.combine(value.date(), time(hour=5, minute=0))
    else:
        return ''
