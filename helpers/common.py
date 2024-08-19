# type hinting imports
from typing import Any, Dict, List, NamedTuple, TextIO, Tuple, Union

# python imports
import fasteners
import gzip
import inspect
import json
import os
import pytz
import sys
import threading
import time
import traceback
from zipfile import ZIP_DEFLATED, ZipFile, BadZipFile

from datetime import datetime

from email import generator
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# app imports
from helpers.decorators import fsdecode_file_path, fsdecode_pathlike
from helpers.globalconstants import CONFIG_INTERNAL, SOS_CONFIG

PTIME_FORMAT = "%Y-%m-%d %H:%M:%S"
EML_FOLDER = "/sos_data/todo_emails"


class QueryFileLocation(NamedTuple):
    exists: bool
    folder_path: str
    filename: str
    is_zipped: bool

#                                                   Module Internal Path Helpers

def _norm_path_suffix(file_path:str, suffix:str, normpath:bool=True) -> str:
    """ Internal function subject to change. """
    if normpath:
        file_path = os.path.normpath(file_path)

    if file_path[-len(suffix):].lower() != suffix.lower():
        return f"{file_path}{suffix}"
    
    return file_path

def _norm_json_config_path(file_path:str, start:str) -> str:
    """ Internal function subject to change. """
    file_path = os.path.normpath(file_path)
    if not file_path.startswith(start):
        file_path = os.path.join(start, file_path.lstrip(os.path.sep))
    return _norm_path_suffix(file_path, '.json', normpath=False)


class setInterval :
    def __init__(self,interval,action) :
        self.interval=interval
        self.action=action
        self.stopEvent=threading.Event()
        thread=threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self) :
        nextTime=time.time()+self.interval
        while not self.stopEvent.wait(nextTime-time.time()) :
            nextTime+=self.interval
            self.action()

    def cancel(self) :
        self.stopEvent.set()

def _norm_json_config_internal_path(file_path:str) -> str:
    """ Internal function subject to change. """
    return _norm_json_config_path(file_path, start=CONFIG_INTERNAL)


def _norm_json_sos_config_path(file_path:str) -> str:
    """ Internal function subject to change. """
    return _norm_json_config_path(file_path, start=SOS_CONFIG)

#                                                              File Lock Helpers

#@fsdecode_file_path
def file_lock(file_path:Union[str, os.PathLike], raise_fnf:bool=True) -> fasteners.InterProcessLock:
    """ Gets an unacquired `fasteners.InterProcessLock` on the given file path.

    Args
    ----
      file_path: str|os.PathLike
        Path to the the file to lock.
      raise_fnf: bool, default True
        Raise a FileNotFoundError if the file path does not exist.
    
    Raises
    ------
      FileNotFoundError:
        If raise_fnf is True, the default, and the file does not exist.
    """
    if not os.path.exists(file_path) and raise_fnf:
        # in Linux, errno.ENOENT (Error NO ENTity) == 2
        raise FileNotFoundError(2, "cannot lock file, file_path does not exist", f"{file_path}")
    
    return fasteners.InterProcessLock(file_path)


#@fsdecode_file_path
def json_lock(file_path:Union[str, os.PathLike], config:bool=True, internal:bool=False, raise_fnf:bool=True) -> fasteners.InterProcessLock:
    """
    Gets an unacquired `fasteners.InterProcessLock` on the given json file path.

    Args
    ----
      file_path: str|os.PathLike
        Path to the the file to lock.
      config: bool, default True
        True if file is in /sos-config, otherwise False.
      internal: bool, default False
        True if file is in /opt/flask_app/config_internal, otherwise False.
      raise_fnf: bool, default True
        Raise a FileNotFoundError if the file path does not exist.
    
    Returns
    -------
      fasteners.InterProcessLock:
        An unacquired lock on the given file path.

    Raises
    ------
      FileNotFoundError:
        If raise_fnf is True, the default, and the file does not exist.
    """
    file_path = os.fsdecode(file_path)
    if config:
        file_path = _norm_json_sos_config_path(file_path)
    elif internal:
        file_path = _norm_json_config_internal_path(file_path)

    return file_lock(file_path, raise_fnf=raise_fnf)

#                                                              json File Helpers

def _get_json_lock(file_path:str, config:bool=True, internal:bool=False) -> Union[dict, list]:
    """ Internal helper, subject to change.
    
    Use `get_json_lock` instead.
    """
    # import pdb;pdb.set_trace()
    # 'C:\\Desktop-WireTap\\sos-config\\background.json'

    # os.path.exists('C:\\Desktop-WireTap\\sos-config\\background.json')
    # if config:
    #     file_path = _norm_json_sos_config_path(file_path)
    # elif internal:
    #     file_path = _norm_json_config_internal_path(file_path)
    # import pdb;pdb.set_trace()
    # os.path.dirname(os.path.dirname(__file__)) 
    # os.path.join(os.getcwd(),_norm_json_sos_config_path(file_path))
    # file_path = _norm_json_sos_config_path(file_path)

    # os.path.dirname(__file__)


    file_path = str(os.getcwd()) + str(_norm_json_sos_config_path(file_path))
    # os.path.join(os.path.dirname(__file__),'..','pv.json')
    # file_path = _norm_json_sos_config_path(file_path)
    # file_path= os.path.normpath(file_path)
    print("\n\n==file_path====")
    print(file_path +"\n\n")
    try:
        # with file_lock(file_path):
        with open(file_path) as fp:
            return json.load(fp)
            
  
    except (json.decoder.JSONDecodeError, FileNotFoundError):
        
        with file_lock(file_path):
                with open(file_path, "r") as f:
                     content = f.read()
                new_content = content[:-60]
                return json.loads(new_content)
               


#@fsdecode_file_path
def get_json_config(file_path:Union[str, os.PathLike], config:bool=True) -> Union[dict, list]:
    """ Deprecated
    ---

    Use `get_json_lock`.

    Args
    ----
      file_path: str|os.PathLike
        Path to the the json file to deserialize.
      config: bool, default True
        True if file is in /sos-config, otherwise False.
    """
    return _get_json_lock(file_path, config=config)


#@fsdecode_file_path
def get_json_lock(file_path:Union[str, os.PathLike], config:bool=True, internal:bool=False, search_depth:int=2) -> Union[dict, list]:
    """ Gets json data from a file, file is locked while being deserialized.
    
    Args
    ----
      file_path: str | os.PathLike
        Path to the the file to open
      config: bool, default True
        True if file is in /sos-config, otherwise False.
      internal: bool, default False
        True if file is in /opt/flask_app/config_internal, otherwise False.
      search_depth: int, default 2
        How far up the path to search for a zip archive containing the filename.
    
    Returns
    -------
      dict | list:
        A dict or list deserialized from the json file.
    """
    try:
        with open(file_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"\n\n Exception while reading json file {file_path} - {e}")
        return {}

    return data
    if config or internal:
        # we don't need to search for a zip file if we're getting a sos-config
        # or config_internal file
        return _get_json_lock(file_path, config=config, internal=internal)
    
    
    file_path = _norm_path_suffix(file_path, '.json')
    
    try:
        # file_lock raises FileNotFoundError if file_path does not exist
        with file_lock(file_path):
            with open(file_path) as f:
                data = json.load(f)

    except (json.decoder.JSONDecodeError, FileNotFoundError):
        # We'll only search for a zip file if we're not looking for a config
        # or internal config file.
        if search_depth:
            zip_path, filename = os.path.split(file_path)
            #printd("%s not found, trying %s: %s" %(file_path, zip_path, filename))
            return get_json_zip(zip_path, filename, search_depth=search_depth)
        else:
            #printd("Nothing more to search for")
             with file_lock(file_path):
                with open(file_path) as f:
                    data = json.load(f[:-73])
    # except Exception as e:
    #     #print_exc(e, msg="exception in 'get_json_lock'")

    # NOTE: JHenly 2023-06-20
    # not sure if this can ever be reached, but it will raise a ReferenceError
    return data

@fsdecode_pathlike(kw='filepath')
def file_query(filepath:Union[os.PathLike, str], search_depth:int=2) -> QueryFileLocation:
    if os.path.isfile(filepath):
        folder, fname = os.path.split(filepath)
        if  os.stat(filepath).st_size > 0:
            return QueryFileLocation(True, folder, fname, False)
        else:
            return QueryFileLocation(False, folder, fname, False)
    
    if search_depth > 0:
        zip_path, zip_fname = os.path.split(filepath)
        return zip_file_query(zip_path, zip_fname, search_depth)


@fsdecode_pathlike(kw='zip_path')
def zip_file_query(zip_path:Union[str, os.PathLike],
                   filename:Union[str, os.PathLike],
                   search_depth:int=2
                   ) -> QueryFileLocation:
    
    zip_path = _norm_path_suffix(zip_path, '.zip')

    try:
        # file_lock raises FileNotFoundError if zip_path does not exist
        with file_lock(zip_path):
            with ZipFile(zip_path) as zf:
                for fn in zf.namelist():
                    if fn.endswith(filename):
                        return QueryFileLocation(True, zip_path, filename, True)

        # raise if filename is not in zip archive
        raise FileNotFoundError
    
    except (FileNotFoundError, BadZipFile) as e:
        if search_depth:
            new_zip_path, file_path = os.path.split(zip_path)
            new_filename = os.path.join(os.path.splitext(file_path)[0], filename)
            # printd("%s not found, trying %s: %s"
            #     % (filename, new_zip_path, new_filename)
            # )
            return zip_file_query(new_zip_path, new_filename, search_depth - 1)
        else:
            # printd("Maximum depth reached")
            return QueryFileLocation(False, None, None, False)

@fsdecode_pathlike(kw='zip_path')
def get_json_zip(zip_path:Union[str, os.PathLike], filename:str, search_depth:int=2) -> Union[dict, list]:
    """ Retrieves the contents of a json file in a compressed zip archive.

    Args:
        zip_path (str, os.PathLike): Absolute path to the zip file
        filename (str): Relative location of the file to load in
            the zip archive.
        search_depth (int, optional): How far up the path to search for a zip
            archive containing the filename. Defaults to 2.
    Raises:
        FileNotFoundError: If the maximum search depth is reached and the file
            does not exist.
    Returns:
        dict | list: A dict or list deserialized from the json file.
    """
    zip_path = _norm_path_suffix(zip_path, '.zip')

    #printd("%s: %s %s" %(search_depth, zip_path, filename))
    try:
        # file_lock raises FileNotFoundError if zip_path does not exist
        with file_lock(zip_path):
            with ZipFile(zip_path) as zf:
                for fn in zf.namelist():
                    if fn.endswith(filename):
                        with zf.open(fn) as f:
                            return json.load(f)

        # raise if filename is not in zip archive
        raise FileNotFoundError

    except (json.JSONDecodeError, FileNotFoundError, BadZipFile) as e:
        if search_depth:
            new_zip_path, file_path = os.path.split(zip_path)
            new_filename = os.path.join(os.path.splitext(file_path)[0], filename)
            # printd("%s not found, trying %s: %s"
            #     % (filename, new_zip_path, new_filename)
            # )
            return get_json_zip(new_zip_path, new_filename, search_depth - 1)
        else:
            # printd("Maximum depth reached")
            raise FileNotFoundError from e
    
    # NOTE - JHenly 2023-05-24  (see the 1st note above)
    # what should we return? None will cause a hard to find bug
    raise FileNotFoundError(filename)

def get_json_gzip(file_path, config=True, internal=False):
    """Returns json data from a file. File is locked while in use.
    File is a gzipped (.gz) archive

    If config is set to true, file path will automatically start in 
    /sos-config/, else the full relative path is expected.

    Args:
        file_path (str): path to the the file to open
        config (bool, optional): True if file is in /sos-config, otherwise
            False. Defaults to True.

    Returns:
        dict: Dictionary containing information parsed from the json file.
    """
    if config:
        file_path = "/sos-config/" + file_path + ".json"
    elif internal:
        file_path = "config_internal/" + file_path + ".json"
    with fasteners.InterProcessLock(f"{file_path}.gz"):
        with gzip.open(f"{file_path}.gz", 'rb') as file:
            content = file.read().decode('utf-8')
            data = json.loads(content)
    return data

#@fsdecode_file_path
def get_json_gzip(file_path:Union[str, os.PathLike], config:bool=True, internal:bool=False) -> Union[dict, list]:
    """Returns json data from a file. File is locked while in use.
    File is a gzipped (.gz) archive

    If config is set to true, file path will automatically start in 
    /sos-config/, else the full relative path is expected.

    Args:
        file_path (str, os.PathLike): path to the the file to open
        config (bool, optional): True if file is in /sos-config, otherwise
            False. Defaults to True.

    Returns:
        dict | list: A dict or list deserialized from the json file.
    """
    if config:
        file_path = _norm_json_sos_config_path(file_path)
    elif internal:
        file_path = _norm_json_config_internal_path(file_path)
    
    file_path = _norm_path_suffix(file_path, '.gz')
    with file_lock(file_path):
        with gzip.open(file_path, 'rb') as file:
            content = file.read().decode('utf-8')
            return json.loads(content)
        
#@fsdecode_file_path
def save_json_gzip_lock(file_path:Union[str, os.PathLike], new_data:Union[dict, list], compressionLevel:int=5):
    """ Saves a JSON file, compressed using gzip module.

    Args:
        file_path (str, os.PathLike): Name of the json file to save
                         configuration to.
                         Provide only the file name if in /sos-config,
                         else give the full path name.
        new_data (dict, list): Data to be saved into the JSON file.
        compressionLevel (int, optional): specified compression file, 0 to 9, to
                                          zip the json file to. Default 5.
    """
    file_path = _norm_path_suffix(file_path, '.gz')
    with file_lock(file_path, raise_fnf=False):
        new_data = json.dumps(obj=new_data, indent=None, separators=(',', ':')).encode(encoding='UTF-8')
        with gzip.open(file_path, "wb", compressionLevel) as file:
            file.write(new_data)

#@fsdecode_file_path
def save_json_config(file_path:Union[str, os.PathLike], new_data:Union[dict, list], config:bool=True, internal:bool=False):
    """ Saves a JSON configuration file.

    Args:
        file_path (str, os.PathLike): Name of the json file to save
                         configuration to.
                         Provide only the file name if in /sos-config,
                         else give the full path name.
        new_data (dict, list): Data to be saved into the JSON file.
        config (bool, optional): True if the file is in /sos-config,
                        else False. Defaults to True.
        internal (bool, optional): True if the file is in 
                        /opt/flask_app/config_internal, else False. Defaults to
                        False.
    """
    # if config:
    #     file_path = _norm_json_sos_config_path(file_path)
    # elif internal:
    #     file_path = _norm_json_config_internal_path(file_path)
    # serialize to a string before truncating the file, in case of errors
    new_data = json.dumps(obj=new_data, indent=None, separators=(',', ':'))
    # print(new_data)
    # with file_lock(file_path, raise_fnf=False):
    with open(file_path, "w+") as file:
        file.write(new_data)

# Delete or Swap out when data_retentionUnified is merged to master
#@fsdecode_file_path
def compress(file_path:Union[str, os.PathLike], config:bool=True):
    if config:
        file_path = _norm_json_sos_config_path(file_path)
    
    zip = _norm_path_suffix(file_path, '.zip')
    arcname = file_path.split("/")[-1]

    ZipFile(zip, 'w', compression=ZIP_DEFLATED).write(filename=file_path, arcname=arcname)


#@fsdecode_file_path
def extractZip(file_path:Union[str, os.PathLike], save_path:str, config:bool=True):
    if config:
        file_path = _norm_json_sos_config_path(file_path)
    
    with ZipFile(file_path, 'r') as zipObj:
        zipObj.extractall(save_path)

def send_email(msgto:str, subject:str, msgtext:str, msghtml:str="", msgfrom:str=""):
    """ Simply creates an email message and puts it in the folder for
    the smtp handler to send.

    Args:
        msgto (string): email address of the recipient
        subject (string): email subject
        msgtext (string): plaintext version of the email
        msghtml (string, optional): html version of the message
        msgfrom (string, optional): sender email address. If none provided,
                will attempt to use the smtp email in the plant configuration
    """

    message = MIMEMultipart('alternative')
    message["Subject"] = subject
    message["To"] = msgto
    if msgfrom:
        message["From"] = msgfrom
    else:
        message["From"] = get_json_lock("plant_config")["smtp"]["email"]
    
    part1 = MIMEText(msgtext, 'plain')
    message.attach(part1)
    
    if msghtml:
        part2 = MIMEText(msghtml, 'html')
        message.attach(part2)

    eml_file = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f.eml")

    if not os.path.exists(EML_FOLDER):
        os.mkdir(path=EML_FOLDER)

    with open(os.path.join(EML_FOLDER, eml_file), "w+") as f:
        gen = generator.Generator(f)
        gen.flatten(message)

#                                                                Logging Helpers

def _iso_now(sep:str=' ', timespec='milliseconds') -> str:
    """ Internal helper, subject to change. """
    return datetime.now().isoformat(sep=sep, timespec=timespec)


def _caller_filename(depth:int=2) -> str:
    """ Internal helper, subject to change. """
    return os.path.split(inspect.stack()[depth].filename)[-1]

def _get_print_kwargs_or_defaults(kwargs:dict) -> Tuple[str, str]:
    """ Internal function subject to change.
    
    Updates `kwargs` in place, i.e. alters the passed in `dict`.
    """
    now = kwargs.pop('now', False) or _iso_now()
    caller = kwargs.pop('caller', False) or _caller_filename(depth=3)
    return now, caller


def printd(*args, **kwargs):
    """
    print function that includes diagnostic data (timestamp and name of the
    calling file) and prints to `stdout`, use just like normal print.
    """
    #import pdb;pdb.set_trace()
    kwargs.setdefault('file', sys.stdout)
    now, caller = _get_print_kwargs_or_defaults(kwargs)

    if args and isinstance(args[0], BaseException):
        print_exc(exc=args[0], *args[1:], now=now, caller=caller, **kwargs)
        return

    print("[%s] %s: " % (now, caller), *args, **kwargs)


def printe(*args, **kwargs):
    """
    Print function that includes diagnostic data (timestamp and name of the
    calling file) and prints to `stderr`, use just like normal print
    """
    kwargs.setdefault('file', sys.stderr)
    now, caller = _get_print_kwargs_or_defaults(kwargs)

    if args and isinstance(args[0], BaseException):
        print_exc(exc=args[0], *args[1:], now=now, caller=caller, **kwargs)
        return

    print("[%s] %s: " % (now, caller), *args, **kwargs)

def _update_print_kwargs(kwargs:dict):
    """ Internal function subject to change.
    
    Updates `kwargs` in place, i.e. alters the passed in `dict`.
    """
    if 'now' not in kwargs:
        kwargs['now'] = _iso_now()
    if 'caller' not in kwargs:
        kwargs['caller'] = _caller_filename(depth=3)


def printb(*args, **kwargs):
    """
    Print function that includes diagnostic data (timestamp and name of the
    calling file) and prints to `stdout` and `stderr`, use just like normal
    print.
    """
    # add 'now' and 'caller' if not in kwargs
    _update_print_kwargs(kwargs)

    printd(*args, **kwargs)
    printe(*args, **kwargs)


def print_exc(exc:BaseException, *args, msg:str=None, **kwargs):
    """
    Print function that includes diagnostic data (timestamp and name of the
    calling file) and prints to `stderr`, first argument must be an exception
    but other than that use just like normal print
    """
    # add 'now' and 'caller' if not in kwargs
    _update_print_kwargs(kwargs)

    if isinstance(exc, BaseException):
        trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
        printe(''.join(trace), **kwargs)
    
    msg and printe(msg, **kwargs)
    args and printe(*args, **kwargs)


#                                                      Object Metadata Functions

def _class_name(obj:type) -> str:
    """ Internal `class_name` helper function, subject to change. """
    try:
        name = obj.__name__
    except:
        return ''
    return name if isinstance(name, str) else ''


def class_name(obj) -> str:
    """
    Returns the class name of the given object, if the given object has no class
    name then `''` will be returned.

    This function has a no-raise guarantee.
    """
    return _class_name(obj if isinstance(obj, type) else type(obj))


def _qual_name(obj:type) -> str:
    """ Internal `qual_name` helper function, subject to change. """
    try:
        fqn = obj.__qualname__
        if isinstance(fqn, str):
            return fqn
    except:
        pass
    return _class_name(obj)


def qual_name(obj) -> str:
    """
    Returns the qualified class name of the given object, if the given object
    has no qualified class name then the class name will be returned or `''`.

    This function has a no-raise guarantee.
    """
    return _qual_name(obj if isinstance(obj, type) else type(obj))


def _module_name(obj:type) -> str:
    """ Internal `module_name` helper function, subject to change. """
    try:
        mod = obj.__module__
        # we don't need to prepend 'builtins.' to standard types like 'str'
        if isinstance(mod, str) and mod != 'builtins':
            return mod
    except:
        pass
    return ''


def module_name(obj) -> str:
    """
    Returns the name of the given object's associated module, if the object has
    no associated module then `''` will be returned.

    This function has a no-raise guarantee.
    """
    return _module_name(obj if isinstance(obj, type) else type(obj))


def module_qual_name(obj) -> str:
    """
    Returns the given object's module name, if any, and its fully qualified
    class name or just its class name.

    The following scheme describes the returned `str`'s format:

    `[module_name][.]<class_fqn | class_name>`
    
    Note if the given object has both a module name and a class name, then they
    will be separated by a `.`, otherwise no `.` will be added.

    This function has a no-raise guarantee.
    """
    obj = obj if isinstance(obj, type) else type(obj)
    mod, fqn = _module_name(obj), _qual_name(obj)
    if mod and fqn:
        mod += '.'
    return f"{mod}{fqn}"
