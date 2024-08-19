"""
helpers.jinja.filters
~~~~~~~~~~~~~~~~~~~~~

The `filters` subpackage contains modules related to jinja2 template filters.

:copyright: (c) 2023 Aderis Energy, LLC
"""

# no import all list, keep 'register_jinja_filters' out of 'from _ import *'
__all__ = ()


#                                               app.py Register Filters Function

# this import is just for type hinting
try:
    import flask as _flask
except: pass

def register_jinja_filters(app:_flask.Flask):
    """ Internal function used by `app.py`.
    
    This function should not be imported or used.
    """

    import helpers.jinja.filters.common as _common
    import helpers.jinja.filters.cache_bust as _cache_bust

    # register jinja filters defined in submodules
    _common._register_filters(app=app)
    _cache_bust._register_filters(app=app)


