"""
helpers.jinja.filters.common
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module contains jinja2 `template_filters` with pretty common use cases.
Most of the template filteres in this module were migrated from `app.py`.

:copyright: (c) 2023 Aderis Energy
"""

# import all list (i.e. from _ import *)
__all__ = (
    'datetime_fmt',
    'datetime_fmt_string',
    'time_24hr',
    'weekday_fmt',
)


# type hinting imports
from typing import Sequence, Union

# python imports
import datetime
import dateutil.parser


#                                               Module Register Filters Function

# this import is just for type hinting
try:
    import flask as _flask
except: pass


# called from './__init__.py'
def _register_filters(app:_flask.Flask):
    """ Internal function used by `helpers.jinja.filters.__init__.py`.
    
    This function should not be imported or used.
    """

    # register jinja filters migrated from app.py
    app.add_template_filter(f=datetime_fmt, name='datetime')
    app.add_template_filter(f=datetime_fmt_string, name='datetime_string')
    app.add_template_filter(f=weekday_fmt, name='weekday')
    app.add_template_filter(f=time_24hr, name='time24')

    # TODO: register other common jinja filters




#                                                   Filters Migrated from app.py

# some custom Jinja2 template filters

def datetime_fmt(value:datetime.datetime, fmt:str='%a, %d %b %Y %H:%M:%S'):
    """
    Returns `'N/A'` if `value` is not a `datetime.datetime` or it does not have
    a `strftime` attribute.
    """
    try:
        return value.strftime(fmt)
    except AttributeError:
        return 'N/A'


def datetime_fmt_string(value:str, fmt:str='%Y-%m-%d %H:%M:%S'):
    """
    Returns `'-'` if `value` is `None`, otherwise parses `value` to a
    `datetime.datetime`, if it's not a `datetime.datetime`, and returns
    `value.strftime(fmt)`.
    """
    if value is None:
        return "-"
    # dateutil.parser doesn't check if arg is a datetime, so we do
    if not isinstance(value, datetime.datetime):
        value = dateutil.parser.parse(value)
    return value.strftime(fmt)


# lookup tuple used by the 'weekday_fmt' function
__WEEKDAY_LOOKUP = (
    ("Mon", "Monday"),
    ("Tues", "Tuesday"),
    ("Wed", "Wednesday"),
    ("Thurs", "Thursday"),
    ("Fri", "Friday"),
    ("Sat", "Saturday"),
    ("Sun", "Sunday")
)

def weekday_fmt(value:Union[int, Sequence[int]], long:bool=True) -> str:
    """
    If `long` is truthy, the default, then long format weekday(s) will be
    returned (i.e. `'Monday'`), otherwise short format weekday(s) will be
    returned (i.e. `'Mon'`).
    """
    idx = 1 if long else 0
    
    if isinstance(value, int):
        # return 1 weekday str mapped to the given int value
        return __WEEKDAY_LOOKUP[value][idx]
    
    else:
        # value might be a sequence, return space separated weekdays
        if isinstance(value, tuple):
            value = list(value)
        try:
            value.sort()
        except (ValueError, AttributeError):
            return 'N/A'
        
        return ''.join(__WEEKDAY_LOOKUP[v][idx] for v in value)


def time_24hr(value:datetime.time, fmt:str="%H:%M") -> str:
    """ Returns `value.strftime(fmt)`. """
    return value.strftime(fmt)



#                                                  Other Common Template Filters

# TODO: add other common jinja filters


