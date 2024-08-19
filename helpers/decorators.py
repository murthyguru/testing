"""
helpers.decorators
~~~~~~~~~~~~~~~~~~

This module contains decorators that can be used in any module, not just
`flask` related modules.

:copyright: (c) 2023 Aderis Energy, LLC
"""

# module's wildcard import list 
__all__ = (
    'fsdecode_file_path',
    'fsdecode_pathlike',
    'StrOrBytesPath',
)


# type hinting imports
from typing import Callable, TypeVar, Union
from typing_extensions import ParamSpec

# python imports
import functools
import os




#                                                               Module Constants

_FLAG = object()
""" Internal sentinel for cases where `None` is a valid value. """


#                                                         Generic Type Variables

_R = TypeVar('_R')
""" Internal type variable.

A generic return type for callables.
"""

_P = ParamSpec('_P')
""" Internal type variable.

Used for retaining decorated callable type hints.
"""


#                                                                   Type Aliases

StrOrBytesPath = Union[str, bytes, os.PathLike]
""" Type alias: `Union[str, bytes, os.PathLike]`.

Almost identitical to the `os` typeshed's `StrOrBytesPath`.
"""
StrOrPathLike = Union[str, os.PathLike]


#                                                         os.fsdecode Decorators

def fsdecode_pathlike(*, idx:Union[int, None]=0, kw:Union[str, None]=None):
    """
    Decorator that ensures a function, taking a `str`, `bytes` or `os.PathLike`
    parameter as a positional or keyword argument, is called with that argument
    converted to a `str` using `os.fsdecode(arg)`.

    Args
    ----
      * This function takes no positional arguments.

      idx: int | None, default 0
        The 0-indexed position of the argument, can be negative or None.
      kw: str | None, default None
        The name of the parameter, or None.


    If the decorated function, `fn`, is invoked with `<kw>=...`, then `fn` will
    be invoked in a similar manner to:
    
    ```python
        if kw and isinstance(kwargs[kw], (str, bytes, os.PathLike)):
            kwargs[kw] = os.fsdecode(kwargs[kw])
        return fn(*args, **kwargs)
    ```
    
    If the decorated function is invoked without `<kw>=...`, then if it was
    invoked with positional args, the positional arg at index `idx` (default 0),
    will be used (if `idx` is not `None`), in a similar manner to:
    
    ```python
        if idx is not None and isinstance(args[idx], (str, bytes, os.PathLike)):
            args = args[:idx] + (os.fsdecode(args[idx]), ) + args[idx+1:]
        return fn(*args, **kwargs)
    ```
    
    If the decorated function is invoked without `<kw>=...` (or `kw` is `None`)
    and no positional args (or `idx` is `None`), then the following happens:
    
    ```python
        if not kw or not kw in kwargs:
            if idx is None or not args:
                return fn(*args, **kwargs)
    ```

    
    Examples
    --------
    ```python
    
        import os
        from helpers.decorators import fsdecode_pathlike

        class HomePath(os.PathLike):
            def __fspath__(self):
                return os.path.expanduser('~')

        home_str = os.path.expanduser('~')
        home_bytes = os.fsencode(home_str)
        home_path = HomePath()

        
        @fsdecode_pathlike()
        def test_stuff_1(path:StrOrBytesPath, foo, bar):
            return path if isinstance(path, str)

        test_stuff_1(home_str)              # str -> str
        test_stuff_1(home_bytes)            # bytes -> str
        test_stuff_1(home_path)             # os.PathLike -> str

        
        @fsdecode_pathlike(idx=2)
        def test_stuff_2(foo, bar, path:StrOrBytesPath):
            return path if isinstance(path, str)

        test_stuff_2(0, 0, home_str)        # str -> str

        
        @fsdecode_pathlike(kw='path')
        def test_stuff_3(foo, path:StrOrBytesPath, bar=None):
            return path if isinstance(path, str)

        test_stuff_3(0, path=home_path)     # os.PathLike -> str

        
        @fsdecode_pathlike(kw='path', idx=1)
        def test_stuff_4(foo, path:StrOrBytesPath):
            return path if isinstance(path, str)
        
        test_stuff_4(0, home_bytes)         # bytes -> str
        test_stuff_4(path=home_str, foo=0)  # str -> str
    ```

    See
    ---
      - `helpers.decorators.fsdecode_file_path`
    """

    # static checks - make dev's lives a litter easier
    assert idx is None or isinstance(idx, int), \
            "idx must be an int or None, got type %s" % (type(idx).__name__,)
    assert kw is None or isinstance(kw, str), \
            "kw must be a str or None, got type %s" % (type(kw).__name__,)


    def decorator_fsdecode(fn:Callable[_P, _R]) -> Callable[_P, _R]:

        assert callable(fn), 'decorated object must be callable, i.e. a function'

        @functools.wraps(fn)
        def wrapper_fsdecode(*args:_P.args, **kwargs:_P.kwargs):
            arg = kwarg = val = _FLAG
            
            if kw is not None:
                val = kwarg = kwargs.get(kw, _FLAG)
            
            if val is _FLAG:
                if idx is not None and len(args) > idx:
                    val = arg = args[idx]

            if val is not _FLAG:
                # we don't need to do anything if val is a str
                #
                # let the wrapped function raise if val is not a str, bytes
                # or os.PathLike
                if isinstance(val, (os.PathLike, bytes)):
                    val = os.fsdecode(val)

                if kwarg is not _FLAG:
                    kwargs[kw] = val

                elif arg is not _FLAG:
                    args = args[:idx] + (val, ) + args[idx+1:]
            
            return fn(*args, **kwargs)

        return wrapper_fsdecode
    return decorator_fsdecode


def fsdecode_file_path(fn:Callable[_P, _R]) -> Callable[_P, _R]:
    """
    Decorator that ensures a function, taking a `str`, `bytes` or `os.PathLike`
    parameter (optionally named `file_path`) as its first positional argument,
    is called with `file_path` being a `str` from `os.fsdecode(file_path)`.

    If the decorated function is invoked with `file_path=...`, then `fn` will
    be invoked in a similar manner to:
    
    ```python
        kwargs['file_path'] = os.fsdecode(kwargs['file_path'])
        return fn(*args, **kwargs)
    ```
    
    If the decorated function is invoked without `file_path=...`, then the first
    positional arg, if any, will be used, in a similar manner to:
    
    ```python
        if args:
            file_path = os.fsdecode(args[0])
            return fn(file_path, *args[1:], **kwargs)
    ```
    
    If the decorated function is invoked without `file_path=...` and no
    positional args, then the following happens:
    
    ```python
        if 'file_path' not in kwargs and not args:
            return fn(*args, **kwargs)
    ```
    
    Examples
    --------
    ```python
    
    import os
    from helpers.common import fsdecode_file_path
    
    @fsdecode_file_path
    def file_lock(file_path:Union[str, os.PathLike], raise_fnf:bool=True):
        
        # If file_lock was invoked with a str, bytes or os.PathLike file_path,
        # then file_path will be a str at this point 
        
        if not os.path.exists(file_path) and raise_fnf:
            raise FileNotFoundError("cannot get lock, file_path does not exist")
        return fasteners.InterProcessLock(file_path)
    ```

    See
    ---
    - `helpers.decorators.fsdecode_pathlike`
    """

    return fsdecode_pathlike(idx=0, kw='file_path')(fn)



