from datetime import datetime
import json
from numbers import Real
import os
import requests
import sys
import time
from typing import Union

from helpers.common import printd, printe

if sys.platform == 'linux':
    DOWNLOAD_FOLDER = os.path.abspath("/var/tmp")
else:
    DOWNLOAD_FOLDER = os.path.abspath(os.path.expanduser("~/Downloads"))

CHUNK_SIZE = 1024 * 1024  # 1 MiB

class FileDownloadError(Exception):
    """Failed to download the requested file."""
    pass


def _get_error_message(e: Exception) -> str:
    """Returns a human readable error message based on the types of errors
    that the file downloader might enconuter.

    Args:
        e (Exception): Exception that was raised by the file download function.
    
    Returns:
        str: Message based on the exception that was passed
    """

    if isinstance(e, requests.exceptions.ConnectionError):
        return "A connection error occurred."
    elif isinstance(e, requests.exceptions.ConnectTimeout):
        return 'The request timed out while trying to connect to the remote server.'
    elif isinstance(e, requests.exceptions.RequestException):
        return "An error occurred while handling the request."
    elif isinstance(e, FileDownloadError):
        return str(e)
    else:
        return 'An unknown error occurred.'


def get_filename_from_response(response: requests.Response) -> (str, str):
    """Attempts to parse a downloaded file's filename from a Response object

    Args:
        response (requests.Response): HTTP response after requesting a file

    Returns:
        (tuple): 0 (str): parsed filename,
                 1 (str): encoding or None
                 Or None if the filename could not be parsed
    """
    # File responses from Focus should have the filename encoded in the
    # 'content-disposition' header with a value of, e.g.
    # "attachment; filename=mypviq_1.0.0.txt; filename*=UTF-8''mypviq_1.0.0.txt"
    # from which we need to parse the filename. This attempts to return the bit
    # we're asking about.
    content_disposition = response.headers.get("Content-Disposition").lower()
    if not content_disposition:
        return None
    
    # Each argument in the disposition is separated by a ;, so let's split the
    # string based on that separator, and trim any whitespace
    args = [x.strip() for x in content_disposition.split(";") if "filename" in x]

    # According to MDN, a filename key can be succeeded by an encoding, which
    # should be preferred over a normal filename. We'll try to parse that here,
    # only worrying about the first entry.
    f_enc = next((x for x in args if "*=" in x), None)
    if f_enc:
        f_enc = f_enc.replace("filename*=", '').split("''")
        # This should just contain 2 entries, but I'll only get the first 2 to
        # avoid ValueErrors if there's more than 2, then rearrange so that
        # the filename is first
        fname = f_enc[1]
        encoding = f_enc[0]
        return (fname, encoding)
    else:
        # If it didn't have an encoding, just get the next normal match
        f_enc = next((x for x in args if "=" in x), None)
        if f_enc:
            return (f_enc.replace("filename=", ''), None)

        return None


def fetch_file(url: str,
               dest: Union[os.PathLike, str] = DOWNLOAD_FOLDER,
               chunk_timeout: Real = 15,
               **kwargs) -> str:
    """Fetches the file from url as a GET request, then saves the file in
    the specified destination folder.
    
    Any kwargs provided are passed directly to the requests.get function. It is
    strongly recommended to provide a timeout key for the request function. This
    timeout differs from chunk_timeout - refer to the requests Timeout section
    of the documentation
    https://2.python-requests.org/en/master/user/advanced/#id16
    If a timeout is not provided, a default is used (set to None for no timeout)

    Args:
        url (str): URL that the file will be fetched from
        dest (Union[os.PathLike, str], optional): Path to destination folder.
            Defaults to filedownloader.DOWNLOAD_FOLDER
        chunk_timeout (Real, optional): Maximum time to wait, in seconds,
            between filedownloader.CHUNK_SIZE chunks. Defaults to 15.

    Returns:
        (str): Path to saved file, or None

    Raises:
        requests.exceptions.RequestException: If the download failed.
        requests.exceptions.Timeout: If the download failed.
    """
    if 'timeout' not in kwargs:
        kwargs['timeout'] = (4, 27)

    printd("Fetching file from %s " % url)
    temp_filename = "download_%s" % datetime.now().timestamp()

    try:
        r = requests.get(url, stream=True, **kwargs)
        if r.status_code == 200:
            printd("Successful response.")
        else:
            err_msg = "Received unexpected response code: %s: %s" % (
                r.status_code, r.text
            )
            printe(err_msg)
            raise FileDownloadError(err_msg)

        # Keep some statistics about download time
        chunks = 0
        start_time = datetime.now()

        with open(os.path.join(dest, temp_filename), 'wb') as df:
            chunk_start = datetime.now()

            for chunk in r.iter_content(CHUNK_SIZE):
                chunks += 1
                print(".", flush=True, end="")
                df.write(chunk)

                chunk_end = datetime.now()
                time_diff = (chunk_end - chunk_start).seconds
                if time_diff > chunk_timeout:
                    raise FileDownloadError("Maximum chunk time exceeded.")

                chunk_start = chunk_end


        print()
        printd("Downloaded %d chunks in %d seconds"
            % (chunks, (datetime.now() - start_time).seconds)
        )
        
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.ConnectTimeout,
        requests.exceptions.RequestException,
        FileDownloadError
    ) as e:
        # If the download fails, print some info about that happening and
        # attempt to remove the temporary download file.
        printe("File download failed")
        errmsg = _get_error_message(e)
        try:
            os.remove(os.path.join(dest, temp_filename))
        except FileNotFoundError:
            pass

        raise FileDownloadError(errmsg) from e

    filename, _ = get_filename_from_response(r)
    if filename is None:
        printe("Could not parse filename from download attempt.")
        printe("Response: %s" % json.dumps(r.headers))
        filename = temp_filename

    dest_file = os.path.join(dest, filename)
    os.rename(os.path.join(dest, temp_filename), dest_file)

    return dest_file
