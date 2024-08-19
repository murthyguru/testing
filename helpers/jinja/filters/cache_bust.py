"""
helpers.jinja.filters.cache_bust
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module contains jinja2 template filters related to user agent (web browser)
cache busting.

:copyright: (c) 2023 Aderis Energy, LLC
"""

# import all list (i.e. from _ import *)
__all__ = (
    'lmt_bust',
    'lmt_bust_cache'
)


# python imports
import os
import pathlib

# app imports
from helpers.common import printd, printe
from helpers.globalconstants import RUNNING_APP_DIR


#                                         Production/Development Filepath Helper

__FLASK_APP_PATH = pathlib.Path(RUNNING_APP_DIR).resolve()


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
    global lmt_bust_cache

    # let the user know where the app's root directory is during local dev
    if app.config.get('TESTING') is True or app.config.get('DEBUG') is True:
        printd(f"Flask Application Root Directory:\n  {str(RUNNING_APP_DIR)}")
        
        # do not cache during local dev
        lmt_bust_cache = lmt_bust

    # register file LMT cache busting jinja2 filters
    app.add_template_filter(f=lmt_bust, name='lmt_bust')
    app.add_template_filter(f=lmt_bust_cache, name='lmt_bust_cache')




#                                                 File LMT Cache Busting Helpers

def __to_flask_app_path(filepath:str) -> pathlib.Path:
    """ Internal helper function, subject to change.
    
    Used by the `lmt_bust` and `lmt_bust_cache` jinja2 template filters.
    """
    # turn any filepath into a path relative to the root app dir
    return __FLASK_APP_PATH.joinpath(filepath.lstrip(os.path.sep))


def __check_filepath(filter_name:str, filepath:str) -> str:
    """ Internal helper function, subject to change.
    
    Used by the `lmt_bust` and `lmt_bust_cache` jinja2 template filters.
    """
    try:
        _filepath = str(filepath).strip()
    except:
        raise ValueError(
            f"in jinja2 template filter '{filter_name}', could not convert the "
            f"given filepath to 'str', got '{filepath}' with type "
            f"'{type(filepath).__name__}'"
        ) from None
    
    if not _filepath:
        raise ValueError(
            f"in jinja2 template filter '{filter_name}', filepath is empty, "
            f"got '{filepath}'")
    
    return _filepath


def __not_a_file(filter_name:str, filepath:str, app_path:pathlib.Path) -> str:
    """ Internal helper function, subject to change.
    
    Used by the `lmt_bust` and `lmt_bust_cache` jinja2 template filters.
    """
    printe(f"in jinja2 template filter '{filter_name}', the given filepath is "
           "not a file")
    printe(f"  filepath: '{filepath}'")
    printe(f"  flask_app_path: '{str(app_path)}'")
    # just return the filepath with a -1 LMT
    return f"{filepath}?v=-1"



#                                                 File LMT Cache Busting Filters

def lmt_bust(filepath:str):
    """
    Cache busts web browsers by appending a file's last modified time as a query
    to the given filepath.

    Args
    ----
      filepath: str
        A filepath relative to the app's root directory, usually /opt/flask_app.

    Raises
    ------
      ValueError:
        If the given filepath cannot be converted to a str or it's empty.

    Examples
    --------
    Use in jinja templates like so:
    ```html
    <script src="{{ url_for('static', filename='js/foo.js') | lmt_bust }}">
    ```

    Result will be similar to:
    ```html
    <script src="/static/js/foo.js?v=0123456789">
    ```
    """
    filepath = __check_filepath('lmt_bust', filepath)

    flask_app_path = __to_flask_app_path(filepath)

    if not flask_app_path.is_file():
        return __not_a_file('lmt_bust', filepath, flask_app_path)

    # return the filepath, not the flask_app_path
    return f"{filepath}?v={int(flask_app_path.stat().st_mtime)}"



_lmt_cache = {}
""" Internal module variable.

Dict cache used by the `lmt_bust_cache` jinja2 template filter.
"""



def lmt_bust_cache(filepath:str):
    """
    Just like the `lmt_bust` template filter, but caches the generated bust
    strings.

    Args
    ----
      filepath: str
        A filepath relative to the app's root directory, usually /opt/flask_app.

    Raises
    ------
      ValueError:
        If the given filepath cannot be converted to a str or it's empty.

    Examples
    --------
    Use in jinja templates like so:
    ```html
    <script src="{{ url_for('static', filename='js/foo.js') | lmt_bust_cache }}">
    ```

    Result will be similar to:
    ```html
    <script src="/static/js/foo.js?v=0123456789">
    ```
    """
    filepath = __check_filepath('lmt_bust_cache', filepath)

    bust_str = _lmt_cache.get(filepath, None)

    # check cache for filepath and its bust string has not been gc'ed, else gen
    # and put its bust string in cache
    if bust_str is None:
        flask_app_path = __to_flask_app_path(filepath)

        if not flask_app_path.is_file():
            return __not_a_file('lmt_bust_cache', filepath, flask_app_path)

        # create bust string with filepath, not flask_app_path
        bust_str = f"{filepath}?v={int(flask_app_path.stat().st_mtime)}"
        _lmt_cache[filepath] = bust_str

    return bust_str


