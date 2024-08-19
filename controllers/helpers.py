
# type hinting imports
from typing import List, Union

# python imports
from datetime import datetime, timedelta, date
from flask import Markup, make_response
from werkzeug.utils import get_content_type
import csv
import dateutil.parser
import fasteners 
import gzip
import json
import math
import os
import sqlite3
import requests
from collections import namedtuple
import time
import pathlib
import pytz
from wtforms import StringField, SubmitField
from wtforms.widgets import Input

# app imports
from helpers.common import (
    get_json_config, get_json_lock, printd, save_json_config, printe, json_lock
)



iconography = {}
gray_link_icon = Markup("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"gray\" d=\"M17 7h-3c-.55 0-1 .45-1 1s.45 1 1 1h3c1.65 0 3 1.35 3 3s-1.35 3-3 3h-3c-.55 0-1 .45-1 1s.45 1 1 1h3c2.76 0 5-2.24 5-5s-2.24-5-5-5zm-9 5c0 .55.45 1 1 1h6c.55 0 1-.45 1-1s-.45-1-1-1H9c-.55 0-1 .45-1 1zm2 3H7c-1.65 0-3-1.35-3-3s1.35-3 3-3h3c.55 0 1-.45 1-1s-.45-1-1-1H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h3c.55 0 1-.45 1-1s-.45-1-1-1z\"/></svg>")
red_link_off_icon = Markup("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"red\" d=\"M21.94 11.23C21.57 8.76 19.32 7 16.82 7h-2.87c-.52 0-.95.43-.95.95s.43.95.95.95h2.9c1.6 0 3.04 1.14 3.22 2.73.17 1.43-.64 2.69-1.85 3.22l1.4 1.4c1.63-1.02 2.64-2.91 2.32-5.02zM4.12 3.56c-.39-.39-1.02-.39-1.41 0s-.39 1.02 0 1.41l2.4 2.4c-1.94.8-3.27 2.77-3.09 5.04C2.23 15.05 4.59 17 7.23 17h2.82c.52 0 .95-.43.95-.95s-.43-.95-.95-.95H7.16c-1.63 0-3.1-1.19-3.25-2.82-.15-1.72 1.11-3.17 2.75-3.35l2.1 2.1c-.43.09-.76.46-.76.92v.1c0 .52.43.95.95.95h1.78L13 15.27V17h1.73l3.3 3.3c.39.39 1.02.39 1.41 0 .39-.39.39-1.02 0-1.41L4.12 3.56zM16 11.95c0-.52-.43-.95-.95-.95h-.66l1.49 1.49c.07-.13.12-.28.12-.44v-.1z\"/></svg>")
white_refresh_icon = Markup("<svg width=\"30\" height=\"30\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M.01 0h24v24h-24V0z\"/><path fill=\"white\" d=\"M12 4V2.21c0-.45-.54-.67-.85-.35l-2.8 2.79c-.2.2-.2.51 0 .71l2.79 2.79c.32.31.86.09.86-.36V6c3.31 0 6 2.69 6 6 0 .79-.15 1.56-.44 2.25-.15.36-.04.77.23 1.04.51.51 1.37.33 1.64-.34.37-.91.57-1.91.57-2.95 0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-.79.15-1.56.44-2.25.15-.36.04-.77-.23-1.04-.51-.51-1.37-.33-1.64.34C4.2 9.96 4 10.96 4 12c0 4.42 3.58 8 8 8v1.79c0 .45.54.67.85.35l2.79-2.79c.2-.2.2-.51 0-.71l-2.79-2.79c-.31-.31-.85-.09-.85.36V18z\"/></svg>")
white_settings_icon = Markup("<svg width=\"20\" height=\"20\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"white\" d=\"M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z\"/></svg>")
gray_settings_icon = Markup("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path class=\"rollover_black\" fill=\"gray\" d=\"M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z\"/></svg>")
red_exit_icon = Markup("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"red\" d=\"M18.3 5.71c-.39-.39-1.02-.39-1.41 0L12 10.59 7.11 5.7c-.39-.39-1.02-.39-1.41 0-.39.39-.39 1.02 0 1.41L10.59 12 5.7 16.89c-.39.39-.39 1.02 0 1.41.39.39 1.02.39 1.41 0L12 13.41l4.89 4.89c.39.39 1.02.39 1.41 0 .39-.39.39-1.02 0-1.41L13.41 12l4.89-4.89c.38-.38.38-1.02 0-1.4z\"/></svg>")
gray_trash_icon = Markup("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path class=\"rollover_black\" fill=\"gray\" d=\"M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2H8c-1.1 0-2 .9-2 2v10zM18 4h-2.5l-.71-.71c-.18-.18-.44-.29-.7-.29H9.91c-.26 0-.52.11-.7.29L8.5 4H6c-.55 0-1 .45-1 1s.45 1 1 1h12c.55 0 1-.45 1-1s-.45-1-1-1z\"/></svg>")
white_user_icon = Markup("<svg width=\"34\" height=\"34\" viewBox=\"0 0 24 24\"><path fill=\"white\" d=\"M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z\"/><path d=\"M0 0h24v24H0z\" fill=\"none\"/></svg>")
smoke_list_icon = Markup("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"gray\" d=\"M11 7h6v2h-6zm0 4h6v2h-6zm0 4h6v2h-6zM7 7h2v2H7zm0 4h2v2H7zm0 4h2v2H7zM20.1 3H3.9c-.5 0-.9.4-.9.9v16.2c0 .4.4.9.9.9h16.2c.4 0 .9-.5.9-.9V3.9c0-.5-.5-.9-.9-.9zM19 19H5V5h14v14z\"/></svg>")
smoke_library_icon = Markup("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"gray\" d=\"M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H8V4h12v12zM10 9h8v2h-8zm0 3h4v2h-4zm0-6h8v2h-8z\"/></svg>")
smoke_add_icon = Markup("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"gray\" d=\"M19 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zm-8-2h2v-4h4v-2h-4V7h-2v4H7v2h4z\"/></svg>")
gray_swap_vert = Markup("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path d=\"M16 17.01V10h-2v7.01h-3L15 21l4-3.99h-3zM9 3L5 6.99h3V14h2V6.99h3L9 3zm7 14.01V10h-2v7.01h-3L15 21l4-3.99h-3zM9 3L5 6.99h3V14h2V6.99h3L9 3z\"/></svg>")
white_swap_vert = Markup("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path fill=\"none\" d=\"M0 0h24v24H0V0z\"/><path fill=\"white\" d=\"M16 17.01V10h-2v7.01h-3L15 21l4-3.99h-3zM9 3L5 6.99h3V14h2V6.99h3L9 3zm7 14.01V10h-2v7.01h-3L15 21l4-3.99h-3zM9 3L5 6.99h3V14h2V6.99h3L9 3z\"/></svg>")
smoke_cloud_download = Markup("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\"><path d=\"M0 0h24v24H0z\" fill=\"none\"/><path d=\"M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM17 13l-5 5-5-5h3V9h4v4h3z\"/></svg>")
gray_screen = Markup("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"gray\" width=\"24\" height=\"24\"><path d=\"M0 0h24v24H0z\" fill=\"none\"/><path d=\"M21 2H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h7v2H8v2h8v-2h-2v-2h7c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H3V4h18v12z\"/></svg>")


iconography['gray_swap_vert'] = gray_swap_vert
iconography['white_swap_vert'] = white_swap_vert
iconography['smoke_add_icon'] = smoke_add_icon
iconography['smoke_library_icon'] = smoke_library_icon
iconography['smoke_list_icon'] = smoke_list_icon
iconography["gray_link"] = gray_link_icon
iconography["red_link_off"] = red_link_off_icon
iconography["white_refresh"] = white_refresh_icon
iconography["white_settings"] = white_settings_icon
iconography["gray_settings"] = gray_settings_icon
iconography["red_exit"] = red_exit_icon
iconography["gray_trash"] = gray_trash_icon
iconography["white_user"] = white_user_icon
iconography["smoke_cloud_download"] = smoke_cloud_download
iconography["gray_screen"] = gray_screen



def get_uid_index(nobject:str) -> int:
    """
    Gets the next unique ID for a given index in `indexes.json`, then adds one
    to the entry in `indexes.json` and saves it.

    Currently supported values for `nobject` include:
     - `"devices"` - Device's `dev_daq` in `site_devices.json`.
     - `"reports"` - Report's `id` in `reports.json`.
     - `"templates"` - Device template's `template_id` in `device_templates.json`

    Args
    ----
      nobject: str
        The name of the index in indexes.json.

    """
    with fasteners.InterProcessLock("/sos-config/indexes.json"):
        indexes = get_json_config(file_path='indexes', config=True)

        next_index = int(indexes.get(nobject, 1))
        indexes[nobject] = next_index + 1
        save_json_config('indexes', indexes)
    
    return next_index




allowed_extensions = {
    'all': ['xlsx', 'csv', 'jpg', 'jpeg', 'png'],
    'import': ['csv', 'json', 'zip'],
    'photos': ['png', 'jpg', 'jpeg'],
}
""" Mapping of file category to list of allowed upload file extensions.

 - `'all': ['xlsx', 'csv', 'jpg', 'jpeg', 'png']`
 - `'import': ['csv', 'json', 'zip']`
 - `'photos': ['png', 'jpg', 'jpeg']`
"""

allowed_import_extensions = ['csv', 'json', 'zip']
ALLOWED_IMPORT_FILES = ['sos_templates']


def allowed_file(filename:Union[str, os.PathLike], file_category:str='all') -> bool:
    """
    Checks whether a filename's extension is in a list of allowed upload file
    extensions.

    The value of `file_category` must be a key in this module's
    `allowed_extensions` mapping, otherwise this function will return `False`.

    Args
    ----
      filename: str | os.PathLike
        The filename to check.
      file_category: str, default 'all':
        The category of file to be uploaded.

    Returns
    -------
      bool:
        True if the file is allowed, otherwise False.
    """
    # the '.' is included by pathlib.Path#suffix so we need to shift by 1
    return pathlib.Path(filename).suffix[1:] in allowed_extensions.get(file_category, [])



# DEPRECATED you should just use allowed_file above with the 'import' type instead
def allowed_import_file(filename:Union[str, os.PathLike]) -> bool:
    """ DEPRECATED
    ---
    Use `allowed_file(<filename>, file_category='import')` instead, that's what
    this function does.
    
    Returns `True` if a file is allowed to be imported using the import
    tool (must be an accepted file type and accepted filename).

    Args
    ----
      filename: str | os.PathLike
        Name of file attempting to import, including extension.

    Returns
    -------
      bool:
        True if the file is allowed, otherwise False.
    """
    return allowed_file(filename=filename, file_category='import')
    #filename, extension = filename.rsplit('.', 1)
    #printd(filename, extension)
    #return extension in allowed_import_extensions


def time_ago(time):
    """Returns a tuple of an X ago string, and the timeout of
    the class of the ago, in seconds.

    Args:
        time (datetime): object to compare the current time to

    Returns:
        tuple (x ago string, class timeout)
    """
    now = pytz.utc.localize(datetime.utcnow())
    diff = now - time
    sec_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if sec_diff < 10:
            return ('Just now', 60)
        if sec_diff < 60:
            return ("{} seconds ago".format(math.floor(sec_diff)), 60)
        if sec_diff < 120:
            return ("A minute ago")
        if sec_diff < 3600:
            return ("{} minutes ago".format(math.floor(sec_diff/60)), 60)
        if sec_diff < 86400:
            return ("{} hours ago".format(math.floor(sec_diff/3600)), 3600)

    if day_diff == 1:
        return ("Yesterday", 86400)
    if day_diff < 7:
        return ("{} days ago".format(day_diff), 86400)
    if day_diff < 31:
        return ("{} weeks ago".format(math.floor(day_diff/7)), 86400)
    if day_diff < 365:
        return ("{} months ago".format(math.floor(day_diff/30)), 86400)
    return ("{} years ago".format(math.floor(day_diff/365)), 86400)




# # Global Functions
# def getSosTemplate(daq_template):
#     with open("/sos-config/template_associations.json") as f:
#         fcntl.flock(f, fcntl.LOCK_EX)
#         associ = json.load(f)
#         fcntl.flock(f, fcntl.LOCK_UN)
#     for i in associ:
#         if i['daq_template'] == daq_template:
#             return i['sos_template']
#     return None

def query_database(device_map: dict):
    """
        Returns data directly from the sqlite3 moddata database.
        Args:
            device_map (dict): dictionary that maps daq_names of devices to lists of tags
        Returns:
            return_tags: dict of device_daq to tag_name to value mappings (if device is not None),
                         or tag_name to value mappings
    """
    return_tags = {}
    Measure = namedtuple('Measure', ['value', 'unit', 'time'])
    
    modcurs, dbconn = None, None
    try:
        dbconn = sqlite3.connect('/opt/moddata.db', timeout=20)
        with dbconn:
            modcurs = dbconn.cursor()

            for dev, dev_tags in device_map.items():
                return_tags[dev] = {}
                
                if isinstance( dev_tags, (tuple, list) ):
                    t_list = ["("]
                    t_list.extend(["measure_name = ?" if idx == 0 else " OR measure_name = ?" for idx, dev in enumerate(dev_tags)])
                    t_list.append(") AND device = ?")
                    dev_command = []
                    dev_command.extend(dev_tags)
                    dev_command.append(dev)
                    
                    mname_query = "".join(t_list)
                    modcurs.execute(f'''
                        SELECT device, measure_name, measure_value, destination_unit, last_updated FROM modvalues WHERE {mname_query}
                    ''', tuple(dev_command))
                    query_result = modcurs.fetchall()
                    for tag_result in query_result:                
                        if len(tag_result) > 0:
                            return_tags[tag_result[0]][tag_result[1]] = Measure(value=tag_result[2], unit=tag_result[3], time=tag_result[4])
                        else:
                            # no results
                            return_tags[tag_result[0]][tag_result[1]] = Measure(value=None, unit=None, time=datetime.now().isoformat())
                    
    finally:
        modcurs and modcurs.close()
        dbconn and dbconn.close()

    return return_tags

def order_registers(registers, function_code, request_limit):
    groups = []
    currstart = None
    currend = None
    tag_group = []

    for atag in registers:
        if currstart == None:
            currstart = atag['address']
            currend = currstart + (atag['quantity'] - 1)
        elif atag['address'] <= currend:
            #duplicate address tag
            continue
        else:
            if (atag['address'] > (1 + currend)) or (((currend - currstart + 1) + atag['quantity']) > request_limit):
                curr_quantity = (currend - currstart) + 1
                groups.append({"address": currstart, "quantity": curr_quantity, "function": function_code})
                currstart = atag['address']
                currend = currstart + (atag['quantity'] - 1)
            else:
                currend = currend + (atag['quantity'])
    curr_quantity = (currend - currstart) + 1
    groups.append({"address": currstart, "quantity": curr_quantity, "function": function_code})

    return groups

#auto-generate call groups (simple grouping)
def auto_gen_call_groups_simple(device_type, template, request_limit=100):
    modbus_call_groups = get_json_lock("modbus_call_groups")
    sos_templates_modbus = get_json_lock("sos_templates_modbus")
    modbus_map = sos_templates_modbus[device_type][template]

    if (request_limit == None) or (request_limit < 1) or (request_limit > 123):
        request_limit = 100

    if device_type not in modbus_call_groups:
        modbus_call_groups[device_type] = {}

    modbus_call_groups[device_type][template] = []

    device_tag_list = sorted(modbus_map, key=lambda i: i['address'])

    holding_registers = []
    discrete_inputs = []
    input_registers = []
    coils = []

    for tag in device_tag_list:
        if tag['function'] == 'read-holding-registers':
            holding_registers.append(tag)
        elif tag['function'] == 'read-discrete-inputs':
            discrete_inputs.append(tag)
        elif tag['function'] == 'read-input-registers':
            input_registers.append(tag)
        elif tag['function'] == 'read-coils':
            coils.append(tag)

    device_tag_call_groups = []

    if holding_registers != []:
        device_tag_call_groups = device_tag_call_groups + order_registers(holding_registers, 'read-holding-registers', request_limit)
    if discrete_inputs != []:
        device_tag_call_groups = device_tag_call_groups + order_registers(discrete_inputs, 'read-discrete-inputs', request_limit)
    if input_registers != []:
        device_tag_call_groups = device_tag_call_groups + order_registers(input_registers, 'read-input-registers', request_limit)
    if coils != []:
        device_tag_call_groups = device_tag_call_groups + order_registers(coils, 'read-coils', request_limit)


    modbus_call_groups[device_type][template] = device_tag_call_groups

    with json_lock('modbus_call_groups'):
        save_json_config('modbus_call_groups', modbus_call_groups)

    return device_tag_call_groups

def query_dnp3(device_map: dict):
    """
        Returns data directly from the device communicating via DNP3
        Args:
            device_map (dict): dictionary that maps daq_names of devices to lists of tags
        Returns:
            dict: mapping of tag_name to value, quality mappings
    """
    
    request_body = []
    return_data = {}
    for dev, tags in device_map.items():
        return_data[dev] = {}
        request_body.extend([{"device": dev, "point": tag} for tag in tags])
    
    Measure = namedtuple('Measure', ['value', 'quality', 'time'])
    dnp3_agent_config = get_json_lock("dnp3_agent_config")
    # print("Attempting to query DNP3")
    post_url = f"http://{dnp3_agent_config['web']['endpoint']}:{dnp3_agent_config['web']['port']}/measurement/current"
    try:
        post_response = requests.post(post_url, json=request_body)
    except Exception as e:
        print(e)
        return None
    if not (post_response.status_code == 200):
        print(f"Posted {post_url} threw error status of {post_response.status_code}")
        # should probably still return a json response similar to below
        return None
    for tag_response in post_response.json():
        try:
            
            # DNP3 can have null, convert to 0's
            return_val = 0
            val = tag_response["current"]["value"]
            if val.get("analog", None) != None:
                return_val = val.get("analog")
            elif val.get("binary", None) != None:
                return_val = val.get("binary")
            
            return_data[tag_response["id"]["device"]][tag_response["id"]["point"]] = Measure(value=return_val, quality=tag_response["current"]["quality"][0], time=tag_response["current"]["sample_time"])
        except Exception as e:
            print("error when attempting to grab dnp3 tag")
            print(e)
            
            return_data[tag_response["id"]["device"]][tag_response["id"]["point"]] = Measure(value=None, quality="COMM_LOST", time=datetime.now().isoformat())
            continue

    return return_data

def watch_commit(device_map: dict, dt: datetime, db_type: str, expiry: int, save_interval: int = 30):
    """
        Generates a .CSV document based on a passed device map (daq_name => measures).
        Use as a method in a ThreadPoolExecutor

    Args:
        device_map (dict): Maps daq_names to lists of measures
        dt (datetime): Right now datetime, in datetime class
        db_type (str): database / dnp3 / snmp
        expiry (int): number in minutes for watching a set of tags, range 1 to 15 minutes
        save_interval (int, optional): Interval to write the data to. Defaults to 30.
    """
    
    # Stretch: Gzip / Zip .csv
    
    print("I have been called....")
    time_limit_seconds = expiry * 60
    if not (time_limit_seconds in range(1, 901)):
        return
    
    # Expiry = use to prevent creating multiple threads
    # See datapi /save_ppc_schedule for example.
    
    fname = f"{dt.strftime('%m-%d-%y_%H-%M-%S')}_expiry{expiry}"
    fp = f"/sos_data/live_data/ppc/{fname}.csv"
    p = pathlib.Path(fp)
    p.touch()
    
    ret_csv = ""
    t_list = ["timestamp"]
    for dev_tags in device_map.values():
        t_list.extend(dev_tags)
    t_len = len(t_list)
    ret_csv = "".join([f"{measure}\n" if idx == t_len - 1 else f"{measure}," for idx, measure in enumerate(t_list)])
    
    with p.open("w+") as fp:
        fp.write(ret_csv)
        ret_csv = ""
        
    i = 1
    while (i <= time_limit_seconds):
        data = globals()[f"query_{db_type}"](device_map)
        
        dt_now = datetime.now().astimezone(pytz.timezone('UTC')).isoformat()
        t_list = [ret_csv, dt_now, ","]
        
        Measure_Value = namedtuple('Measure_Value', ['value'])
        
        for dev, dev_tags in device_map.items():
            if dev in data:
                t_list.extend([f"{data[dev].get(tag, Measure_Value(value=None)).value}," for tag in dev_tags])
        
        t_list.append("\n")
        
        ret_csv = "".join(t_list)
        
        # Every 30 seconds
        if i % save_interval == 0:
            print(f'Data Commit ({fname}): saving...')
            # save
            with p.open("a+") as fp:
                fp.write(ret_csv)
                ret_csv = ""
        i += 1
        time.sleep(1)

#given json file name, opens it from sos-config folder
# def get_json_config(file_path, config=True):
#     if config:
#         file_path = "/sos-config/" + file_path + ".json"
#     with open(file_path) as file:
#         data = json.load(file)
#     return data

# #returns json data from config file, if you want to use a non config file set config false
# def get_json_lock(file_path, config=True, internal=False):
#     """Returns json data from a file. File is locked while in use.

#     If config is set to true, file path will automatically start in 
#     /sos-config/, else the full relative path is expected.

#     Args:
#         file_path (str): path to the the file to open
#         config (bool, optional): True if file is in /sos-config, otherwise
#             False. Defaults to True.

#     Returns:
#         dict: Dictionary containing information parsed from the json file.
#     """
#     if config:
#         file_path = "/sos-config/" + file_path + ".json"
#     elif internal:
#         file_path = "config_internal/" + file_path + ".json"
#     with fasteners.InterProcessLock(file_path):
#         with open(file_path) as file:
#             data = json.load(file)
#     return data

# #given json file name and new data, writes new data to sos-config folder
# def save_json_config(file_path, new_data, config=True):
#     """Saves a JSON configuration file.

#     Args:
#         file_path (str): Name of the json file to save configuration to.
#                          Provide only the file name if in /sos-config,
#                          else give the full path name.
#         new_data (dict): Data to be saved into the JSON file.
#         config (bool, optional): True if the file is in /sos-config,
#                         else False. Defaults to True.
#     """
#     if config:
#         file_path = "/sos-config/" + file_path + ".json"
#     with open(file_path, "w+") as file:
#         json.dump(new_data, file)


def get_alarm_name(alarm_id:str) -> str:
    """ Given `alarm_id`, return `disp_name`. """
    alarms = get_json_lock("alarms")
    if alarm_id in alarms['user_alarms']:
        return alarms['user_alarms'][alarm_id]['disp_name']
    else:
        return alarm_id

def daq_name_to_sos( daq_name:str, site_devices: dict={} ) -> str:
    """ Returns the sos_name, given a daq_name. Optionally can pass site_devices entry

    Args:
        daq_name (str): Unique device identifier
        site_devices (dict, optional): dict containing the site's devices. Optional, Defaults to None.

    Returns:
        str: sos_name of the requested daq
    """
    if not site_devices:
        site_devices = get_json_lock("site_devices")
        
    for device_cat in site_devices:
        for device in site_devices[device_cat]:
            if device['daq_name'] == daq_name:
                return device['sos_name']
    return daq_name

def get_device_info(daq_name:str, site_devices:dict={}) -> Union[dict, None]:
    """ Given device `daq_name`, loads its dictionary from `site_devices.json`.

    Args:
        daq_name (str): Unique device identifier
        site_devices (dict, optional): Copy of site_devices entry. Defaults to None.

    Returns:
        Union[dict, None]: Either None for no device found, or a dict entry for the requested device.
    """
    
    if not site_devices:
        site_devices = get_json_lock("site_devices")
    for device_cat in site_devices:
        for device in site_devices[device_cat]:
            if device['daq_name'] == daq_name:
                return device
    return None

def get_device_template_info(daq_name:str) -> Union[dict, None]:
    """
    Given device template's `template_id`, loads its dictionary from
    `device_templates.json`.
    """
    device_templates = get_json_lock('device_templates')
    for device_cat in device_templates:
        for device in device_templates[device_cat]:
            if device['template_id'] == daq_name:
                return device
    return None


def get_device_type_list() -> List[str]:
    """ Returns list of all device types in `asset_measures.json` """
    asset_measures = get_json_lock("asset_measures")
    return list(asset_measures.keys())


def get_modbus_maps_by_type() -> dict:
    """
    Returns mapping of device type to list of modbus maps from
    `sos_templates_modbus.json`.
    """
    modbus_taglist = get_json_lock("sos_templates_modbus")

    modbus_devices = {}

    for device_type in modbus_taglist:
        modbus_devices[device_type] = []
        for device in modbus_taglist[device_type]:
            modbus_devices[device_type].append(device)

    return modbus_devices
def get_snmp_maps_by_type() -> dict:
    """
    Returns mapping of device type to list of modbus maps from
    `sos_templates_modbus.json`.
    """
    snmp_taglist = get_json_lock("sos_templates_snmp")

    snmp_devices = {}

    for device_type in snmp_taglist:
        snmp_devices[device_type] = []
        for device in snmp_taglist[device_type]:
            snmp_devices[device_type].append(device)

    return snmp_devices

def get_rest_maps_by_type() -> dict:
    """
    Returns mapping of device type to list of modbus maps from
    `sos_templates_modbus.json`.
    """
    rest_taglist = get_json_lock("sos_templates_rest_api")

    rest_devices = {}

    for device_type in rest_taglist:
        rest_devices[device_type] = []
        for device in rest_taglist[device_type]:
            rest_devices[device_type].append(device)

    return rest_devices
def get_dnp_maps_by_type() -> dict:
    """
    Returns mapping of device type to list of modbus maps from
    `sos_templates_modbus.json`.
    """
    dnp_taglist = get_json_lock("sos_templates_dnp3")

    dnp_devices = {}

    for device_type in dnp_taglist:
        dnp_devices[device_type] = []
        for device in dnp_taglist[device_type]:
            dnp_devices[device_type].append(device)

    return dnp_devices

def get_dir_size(fromPath:Union[str, os.PathLike]='.') -> int:
    """ DEPRECATED
    ---
    Given a directory path, calculate and return its size, including any
    subdirectories.

    Args:
        fromPath (str, optional): Path to start from. Defaults to '.'
        (current directory)

    Returns:
        int: size of the directory in bytes
    """
    dir_size = 0
    for dirpath, dirnames, filenames in os.walk(fromPath):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                dir_size += os.path.getsize(fp)

    return dir_size

def toMiB(a:Union[float, int]):
    """ DEPRECATED
    ---
    Given a number of bytes, converts to megabytes (1024 bytes per kilobyte)

    Args
    ----
      a: float | int
        bytes to convert to megabytes

    Returns
    -------
        int: Input converted into megabytes.
    """
    return int(a // (1024 * 1024))

def get_formatted_download_string(className:str, format:str):
    """
    Given a tile's `class_name`, `className`, and a file extension, `format`,
    this function returns a formatted \ 
    `'<site_id>_<tile_display_name>_<timestamp>.<format>'` string.

    Example
    -------
    ```
    >>> # For the Data Query tile on site Montgomery
    ... # On June 16th, 2022 at 9:25 AM
    ... 
    >>> get_formatted_download_string('MeasuresQuery', 'csv')
    'MONT1_Data_Query_06_16_22_09_25_17.csv'
    ```

    Args
    ----
      className: str
        The class_name of the tile.
      format:
        The file extension to add to the download string.

    Returns
    -------
      str: A formatted file download string.
    """
    dashboard_tiles_opt = get_json_lock("dashboard_tiles")
    for tile in dashboard_tiles_opt:
        if tile['class_name'] == className:
            display_name = tile['display_name'].replace(" ", "_")
    config = get_json_lock("plant_config")
    site_code = config['site_id']
    dt = datetime.now()
    dt_format = str(dt.strftime("%x_%H_%M_%S")).replace("/", "-")
    return site_code + "_" + display_name + "_" + dt_format + "." + format


def generate_8760_csv(dest: os.PathLike="/sos-config/current_template.csv"):
    """Generates an 8760 csv file based on the current model data in
    model_data.json.

    Args:
        dest (os.PathLike, optional): Path of csv file to write. Defaults to
            "/sos-config/current_template.csv".
    """
    plant_config = get_json_lock("plant_config")
    model_data = get_json_lock("model_data")

    try:

        if (plant_config["module_type"] == "bifacial"):

            csv_headers = [
                'Month', 'Day', 'Hour Beginning', 'E_Grid', 'GlobInc', 'TArray', 'Windvel', 'GlobHor', 'Tamb', 'FShdBm', 'GlobBak'
            ]
            csv_units = ['', '', '', 'W', 'W/m2', 'C', 'm/s', 'W/m2', 'C', '', 'W/m2']

        else:

            csv_headers = [
                'Month', 'Day', 'Hour Beginning', 'E_Grid', 'GlobInc', 'TArray', 'Windvel', 'GlobHor', 'Tamb', 'FShdBm'
            ]
            csv_units = ['', '', '', 'W', 'W/m2', 'C', 'm/s', 'W/m2', 'C', '']

    except:

        csv_headers = [
            'Month', 'Day', 'Hour Beginning', 'E_Grid', 'GlobInc', 'TArray', 'Windvel', 'GlobHor', 'Tamb', 'FShdBm'
        ]
        csv_units = ['', '', '', 'W', 'W/m2', 'C', 'm/s', 'W/m2', 'C', '']

    with open(dest, "w", newline="") as csvfile:
        unit_write = csv.writer(csvfile)
        unit_write.writerow(csv_units)
        cwrite = csv.DictWriter(csvfile, csv_headers)
        cwrite.writeheader()
        for model_time, model_params in model_data['hour_data'].items():
            model_time = dateutil.parser.parse(model_time[5:])

            try:

                if (plant_config["module_type"] == "bifacial"):

                    cwrite.writerow({

                        "Month": model_time.month,
                        "Day": model_time.day,
                        "Hour Beginning": model_time.hour,
                        "E_Grid": model_params['e_grid'],
                        "GlobInc": model_params['globinc'],
                        "TArray": model_params['tarray'],
                        "Windvel": model_params['windvel'],
                        "GlobHor": model_params['globhor'],
                        "Tamb": model_params['tamb'],
                        "FShdBm": model_params['fshdbm'],
                        "GlobBak": model_params['globbak']

                    })

                else:

                    cwrite.writerow({

                        "Month": model_time.month,
                        "Day": model_time.day,
                        "Hour Beginning": model_time.hour,
                        "E_Grid": model_params['e_grid'],
                        "GlobInc": model_params['globinc'],
                        "TArray": model_params['tarray'],
                        "Windvel": model_params['windvel'],
                        "GlobHor": model_params['globhor'],
                        "Tamb": model_params['tamb'],
                        "FShdBm": model_params['fshdbm']

                    })

            except:

                cwrite.writerow({

                    "Month": model_time.month,
                    "Day": model_time.day,
                    "Hour Beginning": model_time.hour,
                    "E_Grid": model_params['e_grid'],
                    "GlobInc": model_params['globinc'],
                    "TArray": model_params['tarray'],
                    "Windvel": model_params['windvel'],
                    "GlobHor": model_params['globhor'],
                    "Tamb": model_params['tamb'],
                    "FShdBm": model_params['fshdbm']

                })

def get_date_times(start_time: Union[str, datetime], end_time: Union[str, datetime]) -> dict:
    """ For the given time range, returns a dict of dates to their included timestamps.
        Agnostic of timezone

    Args:
        start_time (Union[str, datetime]): isoformat string or datetime for begin of range
        end_time (Union[str, datetime]): isoformat string or datetime for end of range

    Returns:
        dict: maps dates to lists of included timestamps
    """
    
    # TODO - Consider using orderedDict instead of .sort on keys
    
    start_d = start_time
    end_d = end_time
    
    if isinstance(start_time, str):
        start_d = dateutil.parser.parse(start_time).replace(second=0, microsecond=0)
    if isinstance(end_time, str):
        end_d = dateutil.parser.parse(end_time).replace(second=0, microsecond=0)
    
    times_array = []
    times_map = {}
    
    while start_d != (end_d + timedelta(minutes=1)):
        times_array.append(start_d)
        start_d = start_d + timedelta(minutes=1)
        
    for i in times_array:
        if i.date() in times_map:
            times_map[i.date()].append(i)
        else:
            times_map[i.date()] = []
            times_map[i.date()].append(i)
    
    return times_map

def get_time_stretch(start_time: Union[str, datetime], end_time: Union[str, datetime], return_string:bool=True) -> List[Union[str, datetime]]:
    """ Given a requested start_time and end_time, returns a list
        of isoformat strings in the requested range.

    Args:
        start_time (Union[str, datetime]): isoformat string or datetime for begin of range
        end_time (Union[str, datetime]): isoformat string or datetime for end of range
        return_string (bool): If true, will return a list of str rather than datetime objects

    Returns:
        list[str]: contains isoformat strings between requested start and end times.
    """
    start_d = start_time
    end_d = end_time
    
    if isinstance(start_time, str):
        start_d = dateutil.parser.parse(start_time).replace(second=0, microsecond=0) 
    if isinstance(end_time, str):
        end_d = dateutil.parser.parse(end_time).replace(second=0, microsecond=0)
    
    times_array = []
    while start_d != (end_d + timedelta(minutes=1)):
        if return_string:
            times_array.append(start_d.isoformat())
        else:
            times_array.append(start_d)
        start_d = start_d + timedelta(minutes=1)
    return times_array

def get_full_day_time_stretch(day: Union[date, datetime, str]) -> List[str]:
    """ Returns a list of isoformat strings for the UTC begin 
        and end of the requested day.

    Args:
        day (Union[date, datetime, str]): Either string or date format day identifier

    Returns:
        list[str]: contains isoformat strings between requested start and end times.
    """
    
    if isinstance(day, str):
        # Raises (ParserError, OverflowError) on invalid
        day = dateutil.parser.parse(day)
    elif isinstance(day, date):
        day = datetime(year=day.year, month=day.month, day=day.day)
    
    start_d = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end_d = day.replace(hour=23, minute=59, second=0, microsecond=0)
    
    # UTC
    start_d = pytz.utc.localize(start_d)
    end_d = pytz.utc.localize(end_d)
    
    return get_time_stretch(start_d, end_d)
    

def get_local_midnight(input_date:str, input_timezone:str, start_end:str):
    """ Converts an inputted date into utc iso format

    Args:
        input_date (string): inputted date to change to utc
        input_timezone: local timezone of input_date
        start_end: String to specify whether or not the date needs to be rolled-over

    Returns:
        input localized to utc format
    """
    input_parsed = dateutil.parser.parse(input_date)
    printd('parsed input: ')
    printd(input_parsed)

    if start_end == 'end':
        printd('adding a day')
        input_parsed = input_parsed + timedelta(days=1)
        printd(input_parsed)

    local_tz = pytz.timezone(input_timezone)
    input_localized = local_tz.localize(input_parsed)
    printd('localized: ')
    printd(input_localized)

    utc_tz = pytz.timezone('utc')
    input_utc_localized = input_localized.astimezone(utc_tz)
    printd('utc localized: ')
    printd(input_utc_localized)

    return input_utc_localized.isoformat()

def make_compressed_response(data:Union[dict, list, tuple, str, bytes], mimetype:str='text/html', charset:str='utf-8', compress_level:int=5):
    """
    Just like `make_response` but uses gzip to compress the data and adds the
    `Content-Length`, `Content-Encoding` and `Content-Type` headers to tell the
    browser to decompress the response's data into the proper format.

    All browsers automagically support decompressing gzipped data so there's no
    headache on the front-end.

    If data is a `dict`, `list` or `tuple` then it will be converted to a `str`
    via `json.dumps` and then to `bytes` via `encode(charset)`.

    If data is a `str` then it will be converted to `bytes` via
    `encode(charset)`.

    Parameters
    ----------
    data: dict, list, tuple, str, bytes
        The data to compress and add to the response.

    mimetype: str
        Optional, what to set the 'Content-Type' response header to, i.e.
        `'application/json'`, `'text/html'`, `'text/css'`, etc., the default is
        `'text/html'`.

    charset: str
        Optional, the content type encoding, i.e. the `'charset=utf-8'` portion
        of the content type `'text/html; charset=utf-8'`, the default is
        `'utf-8'`.

    compress_level: int
        Optional, an integer ranging from `0` to `9`, the lower the number the
        faster the compression, the higher the number the greater the
        compression, the default is `5`.

    Returns
    -------
        An HTTP response with compressed data and the proper headers.

    Examples
    --------
    ```
        @bp_datapi.route('/get_huge_dict', methods=['GET'])
        def get_huge_dict():
            huge_dict = {f"{i}": i for i in range(0, 1_000_000)}
            return make_compressed_response(data=huge_dict)

        @bp_datapi.route('/get_huge_dict_as_json', methods=['GET'])
        def get_huge_dict_as_json():
            huge_dict = {f"{i}": i for i in range(0, 1_000_000)}
            return make_compressed_response(data=huge_dict, mimetype='application/json')

        @bp_datapi.route('/get_huge_dict_fast_but_big', methods=['GET'])
        def get_huge_dict_fast_but_big():
            huge_dict = {f"{i}": i for i in range(0, 1_000_000)}
            # fastest but with negligible compression
            return make_compressed_response(data=huge_dict, compress_level=0)

        @bp_datapi.route('/get_huge_dict_slow_but_small', methods=['GET'])
        def get_huge_dict_slow_but_small():
            huge_dict = {f"{i}": i for i in range(0, 1_000_000)}
            # slowest but with the most compression
            return make_compressed_response(data=huge_dict, compress_level=9)
    ```
    """
    mimetype = mimetype.strip()
    charset = charset.strip()
    compress_level = int(compress_level)

    if isinstance(data, (dict, list, tuple)):
        data = json.dumps(obj=data, indent=None, separators=(',', ':')).encode(encoding=charset)
    elif isinstance(data, str):
        data = data.encode(encoding=charset)

    content = gzip.compress(data=data, compresslevel=compress_level)

    response = make_response(content)
    response.headers['Content-Length'] = len(content)
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Type'] = get_content_type(mimetype, charset)

    return response


# Helper Class Definitions

# WTForm render widgets
class SubmitRenderButton(Input):
    """
    Changes the rendering of a input type="submit" element
    to utilize an actual button.
    """
    input_type = 'submit'

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        button_html = '<button {params}>{label}</button>'.format(
            params=self.html_params(name=field.name, **kwargs),
            label=field.label.text
        )
        return Markup(button_html)

class SubmitRenderButtonIcon(Input):
    """
    Changes the rendering of an input type="submit" element
    to utilize an actual button. Renders a requested <i> icon
    element in place of the button. The icon's styles and classes
    can be customized with icon_class and icon_options, respectively.
    """
    input_type = 'submit'

    def __init__(self, icon_class: str ='', icon_options: dict ={}, **kwargs):
        self.icon_class = icon_class
        self.style_string = ''.join( f"{key}: {value}; " for key, value in icon_options.items())
        super().__init__(**kwargs)

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        # Hard-coded style for invisible button.
        button_html = '<button style="border: 0; background: none; cursor: pointer; {styles}" {params}><i class="{icon}"></i></button>'.format(
            styles=self.style_string,
            params=self.html_params(name=field.name, **kwargs),
            icon=self.icon_class
        )
        return Markup(button_html)