from flask import Flask, Blueprint, session, render_template, Response, request, Markup, flash, redirect, url_for, send_from_directory, request, redirect, url_for, jsonify, make_response, abort
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField, HiddenField, PasswordField, BooleanField, SelectField, DateField, SelectMultipleField, IntegerField, FloatField, RadioField
from wtforms.validators import DataRequired, InputRequired, ValidationError, Email, EqualTo, Length, IPAddress, NumberRange
from flask_wtf.file import FileField, FileRequired, FileAllowed
from werkzeug.utils import secure_filename
from itsdangerous import JSONWebSignatureSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from copy import deepcopy
# from logger import add_to_log
from typing import List, Dict, Tuple
import shutil
# import fcntl
from pathlib import Path
import time
import random
import secrets
import json
import smtplib
import struct
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import generator
import requests
import os
import re
import subprocess
from datetime import datetime, timedelta
import datetime
import dateutil.parser
import zipfile
import csv
import pytz
import openpyxl
import fasteners
from waitress import serve
import sqlite3
import math
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.compat import iteritems
from pymodbus.exceptions import ConnectionException
import zipfile
import xml.etree.ElementTree as ET
import math
import sys
import psutil
import socket
import signal


from controllers.helpers import get_json_lock, save_json_config, auto_gen_call_groups_simple
from helpers.common import json_lock

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from controllers.mypv_devices import create_device, save_device, DeviceBaseForm
from pymodbus.client.sync import ModbusTcpClient

import serial
import serial.tools.list_ports

import logging
from shutil import which

import os
import logging

# Function to get the directory of the currently running script
def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))

# Get the directory of app.py
script_dir = get_script_dir()

# Navigate up the directory tree to the desired base path
script_base_path = os.path.dirname(os.path.dirname(script_dir))

# Define the directory for file operations within the base path
project_directory = os.path.join(script_base_path, 'python-screen-app')

# Define log path
log_path = os.path.join(os.getenv('USERPROFILE'), 'wiretap_files', 'logs', 'app_scan.log')

# Define log base path
log_base_path = os.path.join(os.getenv('USERPROFILE'), 'wiretap_files', 'logs')

# Create the logs directory if it doesn't exist
os.makedirs(os.path.dirname(log_path), exist_ok=True)

# Configure logging
logging.basicConfig(filename=log_path, level=logging.DEBUG)

# Define the base path for file operations within the home directory
base_path = os.path.join(os.getenv('USERPROFILE'), 'wiretap_files', 'python-screen-app')

# Create the base path directory if it doesn't exist
os.makedirs(base_path, exist_ok=True)

check_endtask = 0

python_executable_path = os.path.join(os.getenv('USERPROFILE'), 'wiretap_files', 'mac_venv', 'Scripts', 'python.exe')


# from tcp_probe import probe as probe_ip

try:

    from background.modbus_rtu_wiretap.datastore_v1 import WiretapStore as db, WiretapDTO
    
    wiretapDBExists = True
    db.copy_datastore_db_if_not_exists()

except:

    wiretapDBExists = False


bp_wiretap = Blueprint('bp_wiretap', __name__)

def eightDigit (num):

    number = str(num)

    for i in range(0, 8):

        if (len(number) < 8):

            number += "0"

        else:

            break

    return number

def get_float (hexarr, endianness):

    if not("bigByte" in endianness):

        hexarr = hexarr[2:] + hexarr[:2]

    if not("bigWord" in endianness):

        hexarr = [hexarr[1]] + [hexarr[0]] + [hexarr[3]] + [hexarr[2]]

    hexarr = "".join(hexarr)

    return '{:.2e}'.format(struct.unpack('!f', bytes.fromhex(hexarr))[0])

def twos_complement(hexstr, bits):

    value = int(hexstr,16)

    if value & (1 << (bits-1)):

        value -= 1 << bits

    return value

def get_device_form (dev_type, dev_template, dev_id, port):

    asset_params = get_json_lock("asset_parameters")
    fields = asset_params[dev_type]

    sos_templates = get_json_lock("sos_templates")
    daq_templates = list(sos_templates[dev_type].keys())
    daq_templates.append('-')
    #print(daq_templates)

    class dyna_asset(DeviceBaseForm):
        #pass
        daq_template = SelectField("Data Template", choices=[(dev_template, dev_template)], default = dev_template)

    unit_conversions = get_json_lock("unit_conversion")


    for dyna_field in fields:
        field_obj = fields[dyna_field]
        data_unit = unit_conversions[field_obj["unit"]]["data_type"]

        if "options" in field_obj:
            setattr(dyna_asset, dyna_field, SelectField(field_obj["label"], choices = [(choice, choice) for choice in field_obj["options"]]))
        elif data_unit == "float":
            setattr(dyna_asset, dyna_field, FloatField(field_obj["label"]))
        elif data_unit == "int":
            setattr(dyna_asset, dyna_field, IntegerField(field_obj["label"]))
        elif data_unit == "bool":
            setattr(dyna_asset, dyna_field, BooleanField(field_obj["label"]))
        elif data_unit == "string":
            setattr(dyna_asset, dyna_field, StringField(field_obj["label"]))
        elif data_unit == "date":
            setattr(dyna_asset, dyna_field, DateField(field_obj["label"]))
        # else:
        #   setattr(dyna_asset, dyna_field, StringField(field_obj["label"]))

        #setattr(dyna_asset, dyna_field, StringField(field_obj["label"]))

    setattr(dyna_asset, "comm_id", IntegerField("Comm. ID", validators=[validators.NumberRange(min = 1, max = 255)]))

    form = dyna_asset(prefix='device')

    form.device_type.data = dev_type
    form.comm_id.data = int(dev_id)
    form.manufacturer.data = "Aderis Energy LLC"
    form.model.data = "WireTap"
    form.monitored.data = True
    form.wiretapped.data = port
    form.network_type.data = "WireTap"
    form.virtual.data = False
    form.protocol.data = "WireTap"

    return form

@bp_wiretap.route('/new_device_partial', methods = ['POST', 'GET'])
def new_device_form_partial_wiretap ():

    asset_params = get_json_lock("asset_parameters")

    form = get_device_form(request.form['deviceType'], request.form['deviceTemplate'], request.form['id'], request.form['port'])

    #transfer device type, manufacturer, model, data temp, network, description
    #loop through asset params


    device_temps = get_json_lock("device_templates")

    for device_temp in device_temps[request.form['deviceType']]:

        if device_temp['template_id'] == request.form['deviceTemplate']:

            form.device_type.data = request.form['deviceType']
            form.network_type.data = device_temp['network']['type']

            if 'system' in device_temp:

                form.energy_system.data = device_temp['system']

            else:

                form.energy_system.data = "PV"

            form.protocol.data = device_temp['network']['params']['protocol']
            form.device_template.data = request.form['deviceTemplate']
            form.run_kpis.data = True

            if device_temp['daq_template'] == None:

                form.daq_template.data = "-"

            for param in asset_params[request.form['deviceType']]:

                if param == 'aggregate':

                    form['aggregate'].data = True

                else:

                    form[param].data = device_temp[param]

    return render_template("/devices/_edit_device_form.html",edit=False, form = form, device_params = asset_params[request.form['deviceType']])

@bp_wiretap.route('/wiretap_monitor_v1', methods = ['GET', 'POST'])
# #@login_required
def wiretap_monitor_v1():
    background = get_json_lock("background")
    assets = get_json_lock("asset_measures")
    unit_reference = get_json_lock('unit_reference')


    category_tuple_list = []

    for unit_category in unit_reference:

        unit_tuple_list = []

        for unit in unit_reference[unit_category]['conversions']:

            unit_tuple_list.append(tuple((unit, unit)))

        category_tuple_list.append(tuple((unit_category, tuple((unit_tuple_list)))))

    unit_choices = tuple((category_tuple_list))

    asset_measures = get_json_lock('asset_measures')
    measure_mappings = {device_type:[(x, asset_measures[device_type][x]["unit"]) for x in asset_measures[device_type]] for device_type in asset_measures}
    
    try:
    
        ports = background["modbus_rtu_wiretap"]["parameters"]["portRecieve"]
        
        if not(type(ports) == type([])):
            
            ports = [ports]
        
    except:
    
        ports = ["No Ports Found"]

    site_devices = get_json_lock("site_devices")

    device_templates = get_json_lock('sos_templates_modbus')
    device_templates_list = {}

    if (wiretapDBExists):

        wireTapped_Data = db.get_all()

    else:

        wireTapped_Data = None

    ids = []

    if not(wireTapped_Data is None):

        for dev_type in device_templates.keys():

            device_templates_list[dev_type] = []

            for dev_temp in device_templates[dev_type].keys():

                device_templates_list[dev_type].append(dev_temp)

        found = False

        tappedSerialPorts = background["modbus_rtu_wiretap"]["parameters"]["portRecieve"]

        if not(type(tappedSerialPorts) == type([])):
                    
            tappedSerialPorts = [tappedSerialPorts]

        for i in wireTapped_Data:

            found = False

            if (not(i.port in tappedSerialPorts)):

                continue

            for j in site_devices.keys():

                for k in site_devices[j]:

                    if (k["network"]["params"]["comm_id"] == int(f"{i.id}") and not((i.id, i.port) in [(x[1], x[2]) for x in ids]) and (k["wiretapped"] == True)):

                        ids.append((f"{i.id}{i.port}", i.id, i.port, (f"{i.port} - " + "{:03d}".format(int(f"{i.id}")) + f" ({k['sos_name']})"), True, k["device_type"], k["daq_template"]))

                        found = True

                        break

                if (found):

                    break

            if not(found) and not((i.id, i.port) in [(x[1], x[2]) for x in ids]) and (i.port in tappedSerialPorts):

                ids.append((f"{i.id}{i.port}", i.id, i.port, (f"{i.port} - " + "{:03d}".format(int(f"{i.id}"))), False))

        ids.sort(key = lambda x: x[3])

    if request.method == 'POST':

        asset_parameters = get_json_lock("asset_parameters")

        dev_type = request.form['device-device_type']
        device_template = request.form['device-daq_template']
        device_port = request.form['device-wiretapped']
        device_id = request.form['device-comm_id']

        form = get_device_form(dev_type, device_template, device_id, device_port)

        device_params = asset_parameters[dev_type]

        if form.submit.data:
            if form.validate_on_submit():

                if request.form['device-daq_name'] == "":

                    response = create_device(form)

                else:

                    response = save_device(form)

                site_devices = get_json_lock("site_devices")

                if not(wireTapped_Data is None):

                    ids = []

                    for dev_type in device_templates.keys():

                        device_templates_list[dev_type] = []

                        for dev_temp in device_templates[dev_type].keys():

                            device_templates_list[dev_type].append(dev_temp)

                    found = False

                    tappedSerialPorts = background["modbus_rtu_wiretap"]["parameters"]["portRecieve"]

                    if not(type(tappedSerialPorts) == type([])):
                                
                        tappedSerialPorts = [tappedSerialPorts]

                    for i in wireTapped_Data:

                        found = False

                        if (not(i.port in tappedSerialPorts)):

                            continue

                        for j in site_devices.keys():
                            
                            for k in site_devices[j]:

                                if (k["network"]["params"]["comm_id"] == int(f"{i.id}") and not((i.id, i.port) in [(x[1], x[2]) for x in ids]) and (k["wiretapped"] == True)):

                                    ids.append((f"{i.id}{i.port}", i.id, i.port, (f"{i.port} - " + "{:03d}".format(int(f"{i.id}")) + f" ({k['sos_name']})"), True, k["device_type"], k["daq_template"]))

                                    found = True

                                    break

                            if (found):

                                break

                        if not(found) and not((i.id, i.port) in [(x[1], x[2]) for x in ids]) and (i.port in tappedSerialPorts):

                            ids.append((f"{i.id}{i.port}", i.id, i.port, (f"{i.port} - " + "{:03d}".format(int(f"{i.id}"))), False))
                        
                    ids.sort(key = lambda x: x[3])

                return render_template('/wire_tap/monitor_v1.html', types = site_devices, templates = device_templates_list, devices = ids, dataFound = True, saved = response, ports = ports, assets = assets, unit_choices = unit_choices, measure_mappings = measure_mappings)

            else:

                return render_template('/wire_tap/monitor_v1.html', types = site_devices, templates = device_templates_list, devices = ids, form = form, dataFound = True, device_params = device_params, ports = ports, assets = assets, unit_choices = unit_choices, measure_mappings = measure_mappings)

    if (wireTapped_Data is None):

        return render_template('/wire_tap/monitor_v1.html', types = site_devices, templates = device_templates_list, devices = ids, dataFound = False, ports = ports, assets = assets, unit_choices = unit_choices, measure_mappings = measure_mappings)

    else:

        return render_template('/wire_tap/monitor_v1.html', types = site_devices, templates = device_templates_list, devices = ids, dataFound = True, ports = ports, assets = assets, unit_choices = unit_choices, measure_mappings = measure_mappings)

from flask import jsonify, Response, request
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
import math

#@bp_wiretap.route('/get_table_data_v1', methods = ['POST'])
#@login_required
# def get_table_data_v1 ():

#     if (str(request.form["id"]) == "None"):

#         return Response()

#     data = db.get_all_with_id_from_port(int(request.form["id"]), request.form["port"])

#     print('The data is :',data)

#     table = []

#     functionCodes = {

#         "read-coils": 0x01,
#         "read-discrete-inputs": 0x02,
#         "read-holding-registers": 0x03,
#         "read-input-registers": 0x04

#     }

#     for i in functionCodes.keys():

#         selectedData = [x for x in data if x[2] == functionCodes[i]]

#         for selection in selectedData:

#             response = selection[5].split(",")

#             if ((functionCodes[i] == 0x01) or (functionCodes[i] == 0x02)):

#                 addressRequestStart = int((selection[4].split(",")[0] + selection[4].split(",")[1]), 16)

#                 for j in range(0, len(response)):

#                     addressStart = addressRequestStart + j

#                     byteSelected = bin(int(response[int(math.floor(j / 8))], 16))[::-1]

#                     byteSelected = eightDigit(byteSelected[:-2])

#                     startingAddress = ((int((selection[4].split(',')[0] + selection[4].split(',')[1]), 16)) + (j * 8))

#                     table.append([startingAddress, f"<tr><td>{i}</td><td>Starting at {startingAddress}</td><td><pre>{response[int(math.floor(j / 8))]}</pre></td><td colspan = 5>{byteSelected}</td><td>{selection[6]}</td></tr>"])

#             else:

#                 for j in range(0, len(response), 2):

#                     adjustedAddress = ((int((selection[4].split(",")[0] + selection[4].split(",")[1]), 16)) * 2) + j

#                     int16 = 0
#                     int32 = 0
#                     uint16 = 0
#                     uint32 = 0

#                     wordOrder = Endian.Big
#                     byteOrder = Endian.Big

#                     try:

#                         decoder = BinaryPayloadDecoder.fromRegisters([int("".join(response[j : (j + 2)]), 16), int("".join(response[(j + 2) : (j + 4)]), 16)], byteorder = byteOrder, wordorder = wordOrder)

#                         registers = [int("".join(response[j : (j + 2)]), 16), int("".join(response[(j + 2) : (j + 4)]), 16)]

#                     except:

#                         decoder = BinaryPayloadDecoder.fromRegisters([int("".join(response[j : (j + 2)]), 16)], byteorder = byteOrder, wordorder = wordOrder)

#                         registers = [int("".join(response[j : (j + 2)]), 16)]

#                     try:

#                         int16 = decoder.decode_16bit_int()

#                     except:

#                         int16 = "-"

#                     decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder = byteOrder, wordorder = wordOrder)

#                     try:

#                         int32 = decoder.decode_32bit_int()

#                     except:

#                         int32 = "-"

#                     decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder = byteOrder, wordorder = wordOrder)

#                     try:

#                         uint16 = decoder.decode_16bit_uint()

#                     except:

#                         uint16 = "-"

#                     decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder = byteOrder, wordorder = wordOrder)

#                     try:

#                         uint32 = decoder.decode_32bit_uint()

#                     except:

#                         uint32 = "-"

#                     decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder = byteOrder, wordorder = wordOrder)

#                     try:

#                         float32 = decoder.decode_32bit_float()

#                     except:

#                         float32 = "-"

#                     try:

#                         hex = " ".join(response[j : (j + 4)]).upper()

#                     except:

#                         hex = " ".join(response[j : (j + 2)]).upper()

#                     table.append([int(adjustedAddress / 2), f"<tr><td>{i}</td><td>{int(adjustedAddress / 2)}</td><td><pre>{hex}</pre></td><td>{int16}</td><td>{uint16}</td><td>{int32}</td><td>{uint32}</td><td>{float32}</td><td>{selection[6]}</td></tr>"])

#     filtered = []

#     [filtered.append(x) for x in table if x not in filtered]

#     return jsonify(sorted(filtered, key = lambda x:x[0]))

@bp_wiretap.route('/get_table_data_v1', methods=['POST'])
def get_table_data_v1():
    if str(request.form["id"]) == "None":
        return Response()
    
    data = db.get_all_with_id_from_port(int(request.form["id"]), request.form["port"])
    functionCodes = {
        "read-coils": 0x01,
        "read-discrete-inputs": 0x02,
        "read-holding-registers": 0x03,
        "read-input-registers": 0x04
    }

    formattedData = {}

    for functionName, functionCode in functionCodes.items():
        selectedData = [x for x in data if x.call == functionCode]
        for selection in selectedData:
            response = selection.response.split(",")
            address = int(selection.request.split(",")[0] + selection.request.split(",")[1], 16)

            for i in range(0, len(response), 2):
                if i + 1 < len(response):  # Ensure there's at least two bytes to process
                    register = address + i // 2
                    hexValue = " ".join(response[i:i+2]).upper()
                    
                    try:
                        registers = [int(response[j], 16) for j in range(i, i+4, 2) if j < len(response)]
                    except ValueError:
                        registers = []

                    if functionName not in formattedData:
                        formattedData[functionName] = {}

                    # Initialize sums if not present
                    if str(register) not in formattedData[functionName]:
                        formattedData[functionName][str(register)] = {
                            "hex": hexValue,
                            "int16": {"BB": 0, "BL": 0, "LB": 0, "LL": 0},
                            "uint16": {"BB": 0, "BL": 0, "LB": 0, "LL": 0},
                            "int32": {"BB": 0, "BL": 0, "LB": 0, "LL": 0},
                            "uint32": {"BB": 0, "BL": 0, "LB": 0, "LL": 0},
                            "float32": {"BB": 0.0, "BL": 0.0, "LB": 0.0, "LL": 0.0}
                        }

                    try:
                        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
                        int16 = decoder.decode_16bit_int()
                        formattedData[functionName][str(register)]["int16"]["BB"] += int16
                    except:
                        pass
                    
                    try:
                        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
                        uint16 = decoder.decode_16bit_uint()
                        formattedData[functionName][str(register)]["uint16"]["BB"] += uint16
                    except:
                        pass
                    
                    try:
                        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
                        int32 = decoder.decode_32bit_int()
                        formattedData[functionName][str(register)]["int32"]["BB"] += int32
                    except:
                        pass
                    
                    try:
                        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
                        uint32 = decoder.decode_32bit_uint()
                        formattedData[functionName][str(register)]["uint32"]["BB"] += uint32
                    except:
                        pass
                    
                    try:
                        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
                        float32 = decoder.decode_32bit_float()
                        formattedData[functionName][str(register)]["float32"]["BB"] += float32
                    except:
                        pass

    return jsonify(formattedData)


@bp_wiretap.route('/new_wiretap_data', methods = ['POST'])
#@login_required
def new_wiretap_data ():

    workingDirectory = os.getcwd().replace("\\", "/")
        
    foundPairsFilePath = f'{log_base_path}/foundPairs.json'
    serialStreamsFilePath = f'{log_base_path}/serialStreams.json'
    logging.info(f'serialStreamsFilePath   %s',serialStreamsFilePath)
        
    new_data = {
                  "new_serial": None,
                  "new_found": None
               }
    
    new_data["new_serial"] = get_json_lock(serialStreamsFilePath, config = False)
    new_data["new_found"] = get_json_lock(foundPairsFilePath, config = False)
    logging.info(f'new data is %s',new_data)
                
    return jsonify(new_data)

# Function to find nmap dynamically
def find_nmap():
    # Use shutil.which to find nmap in the PATH
    nmap_path = shutil.which("nmap")
    if nmap_path:
        return nmap_path

    # Common locations for nmap on Windows
    common_paths = [
        r"C:\Program Files\Nmap\nmap.exe",
        r"C:\Program Files (x86)\Nmap\nmap.exe",
        r"C:\Nmap\nmap.exe"
    ]

    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path

    logging.error("nmap executable not found in PATH or common locations")
    raise FileNotFoundError("nmap executable not found in PATH or common locations")

@bp_wiretap.route('/ip_discovery', methods = ['POST'])
def ip_discovery ():
    
    # Get list of ips that the user entered
    # Get port the user entered

    data = json.loads(request.data.decode('utf-8'))

    ips = data["ips"]
    port = data["port"]

    ips = ips.replace(" ", "").split(",")

    ipsFiltered = []
    ipErrors = []
    
    global nmapSubprocess

    nmapSubprocess = None

    for ip in ips:

        if (re.search("^((25[0-5]|((2[0-4]|1\d|[1-9]|)\d))(-(25[0-5]|((2[0-4]|1\d|[1-9]|)\d)))?\.){3}((25[0-5]|((2[0-4]|1\d|[1-9]|)\d))(-(25[0-5]|((2[0-4]|1\d|[1-9]|)\d)))?){1}(\/(3[0-2]|((2|1|0)\d)))?$", ip)):

            ipsFiltered.append(ip)

        else:

            ipErrors.append(ip)

    if (len(ipErrors) > 0):

        errors = ", ".join(ipErrors)

        return {"started": False, "errors": errors}
    
    try:

        if ((int(port) > 65536) or (int(port) < 0)):

            return {"started": False, "errors": "badPort"}
        
    except:

        return {"started": False, "errors": "badPort"}
    
    else:
        scan_results_path = os.path.join(base_path, 'nmap_scan_results.xml')

        logging.info('XML path is : %s',scan_results_path)

        with fasteners.InterProcessLock(scan_results_path):

            with open(scan_results_path, 'w'): pass

        # Find nmap dynamically
        nmap_path = find_nmap()

        logging.info('nmap path in command : %s',nmap_path)

        if (not(port == "") and ((int(port) <= 65536) or (int(port) >= 0))):

            nmapSubprocess = subprocess.Popen([nmap_path, "-p", port, "-vv", "--stats-every", "1s", "-oX", scan_results_path] + ipsFiltered, stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)

        else:

            nmapSubprocess = subprocess.Popen([nmap_path, "--stats-every", "1s", "-vv", "-oX", scan_results_path] + ipsFiltered, stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)

        return {"started": True}

@bp_wiretap.route('/kill_ip_discovery', methods = ['POST'])
#@login_required
def kill_ip_discovery ():

    try:

        global nmapSubprocess

        if (not(nmapSubprocess == None)):

            nmapSubprocess.kill()

            nmapSubprocess = None

        return ("Success")
    
    except Exception as e:

        logging.info('kill_ip_discover Error is : %s',e)

        return ("Failed")
    
@bp_wiretap.route('/ip_discovery_status', methods = ['POST'])
#@login_required
def ip_discovery_status ():

    global check_endtask

    status = None

    scan_results_path = os.path.join(base_path, 'nmap_scan_results.xml')

    if (scan_results_path):

        # with fasteners.InterProcessLock("/sos-config/modbus_tcp_info/nmap_scan_results.xml"):

        with open(scan_results_path, "r") as f:
            
            status = f.read()

        statusLines = status.split("\n")

        hosts = {}
        endedTasks = []
        currentStatus = "Processing"
        error = None

        activeTag = ""
        activeSubTag = ""

        itemDescription = {}
        address = None

        for line in statusLines:

            if (("<host>" in line) or ("<host " in line) or ("<hosthint>" in line)):

                activeTag = "host"

            if (("</host>" in line) or ("</hosthint>" in line)):

                activeTag = ""

                if (("status" in itemDescription) and not("status" in hosts[address])):
                
                    hosts[address]["status"] = itemDescription["status"]

                if (("port" in itemDescription) and not("port" in hosts[address])):
                
                    hosts[address]["port"] = itemDescription["port"]

                itemDescription = {}
                address = None

            if (activeTag == "host"):

                if ("<status " in line):

                    lineCopy = line.split("state=\"")[1]

                    endOfData = lineCopy.index("\"")

                    itemDescription["status"] = lineCopy[0:endOfData]

                    if not(address == None):

                        hosts[address]["status"] = lineCopy[0:endOfData]

                if (("<address " in line) and ("addrtype=\"ipv4\"" in line)):

                    lineCopy = line.split("addr=\"")[1]

                    endOfData = lineCopy.index("\"")

                    address = lineCopy[0:endOfData]

                    hosts[address] = {}

                if ("<ports>" in line):

                    activeSubTag = "ports"

                if ("</ports>" in line):

                    activeSubTag = ""

                if (activeSubTag == "ports"):

                    if ("<state " in line):

                        lineCopy = line.split("state=\"")[1]

                        endOfData = lineCopy.index("\"")

                        itemDescription["port"] = lineCopy[0:endOfData]

                        if not(address == None):

                            hosts[address]["port"] = lineCopy[0:endOfData]

            if ("<taskbegin " in line):

                lineCopy = line.split("task=\"")[1]

                endOfData = lineCopy.index("\"")

                currentStatus = {"task": lineCopy[0:endOfData], "percent": 50}

            if ("<taskend " in line):

                lineCopy = line.split("task=\"")[1]

                endOfData = lineCopy.index("\"")

                if check_endtask in (0,1):
                    currentStatus = {"task": lineCopy[0:endOfData], "percent": 100}
                    check_endtask += 1
                elif check_endtask == 2:
                    endedTasks.append(lineCopy[0:endOfData])

            if ("<taskprogress " in line):

                lineCopy = line.split("task=\"")[1]

                endOfData = lineCopy.index("\"")

                task = lineCopy[0:endOfData]

                lineCopy = line.split("percent=\"")[1]

                endOfData = lineCopy.index("\"")

                percent = lineCopy[0:endOfData]

                currentStatus = {"task": task, "percent": float(percent)}

            if ("<nmaprun " in line):

                currentStatus = {"task": "Initializing", "percent": 0}

            if ("<runstats>" in line) and check_endtask == 2:

                currentStatus = "Finished"

        return {"hosts": hosts, "endedTasks": endedTasks, "currentStatus": currentStatus, "error": error}
    
    else: 

        return ("File does not exist")

@bp_wiretap.route('/tcp_probe_start', methods = ['POST'])
#@login_required
def tcp_probe_start ():

    data = json.loads(request.data.decode('utf-8'))

    addr = data["address"]
    port = data["port"]
    dev = data["devId"]
    funct = data["function"]
    registers = data["registers"]

    if (not(re.search("^((25[0-5]|((2[0-4]|1\d|[1-9]|)\d))\.){3}(25[0-5]|((2[0-4]|1\d|[1-9]|)\d))$", addr))):

        return {"started": False, 'error': "Bad Address"}
    
    try:

        if ((int(port) < 0) or (int(port) > 65536)):

            return {"started": False, "error": "Bad Port"}
        
    except:

        return {"started": False, "error": "Bad Port"}
    
    try:
    
        if ((int(dev) < 1) or (int(dev) > 255)):

            return {"started": False, "error": "Bad Device"}
    
    except:

        return {"started": False, "error": "Bad Device"}
    
    try:
    
        if (not(int(funct) in [1, 2, 3, 4])):

            return {"started": False, "error": "Bad Function"}
    
    except:

        return {"started": False, "error": "Bad Function"}

    registersProcessed = []

    registersSplit = registers.replace(" ", "").split(",")

    for register in registersSplit:

        if ("-" in register):

            registerRange = register.split("-")

            try:

                if (((int(registerRange[0]) < 0) or (int(registerRange[0]) > 65536)) or ((int(registerRange[1]) < 0) or (int(registerRange[1]) > 65536))):

                    return {"started": False, "error": "Bad Registers"}
                
            except:

                return {"started": False, "error": "Bad Registers"}

            registersExpanded = list(range(int(registerRange[0]), int(registerRange[1]) + 1))
            registersFixed = [str(x) for x in registersExpanded]

            if (not(registersProcessed == [])):

                registersProcessed += registersFixed

            else:

                registersProcessed = registersFixed

        else:

            try:

                if ((int(register) < 0) or (int(register) > 65536)):

                    return {"started": False, "error": "Bad Registers"}
                
            except:

                return {"started": False, "error": "Bad Registers"}

            registersProcessed.append(str(register))

    registersFinal = ",".join(registersProcessed)

    global tcpProbeSubprocess

    tcpProbeSubprocess = None

    currentDir = script_dir
    
    relative_path = "tcp_probe.py"

    logging.info('tcp_probe_start- currentDir is : %s',currentDir)

    logging.info('python_executable_path is : %s',python_executable_path)

    # Combine base directory and relative path using Path object methods
    file_path = f"{currentDir}/{relative_path}"

    tcpProbeSubprocess = subprocess.Popen([python_executable_path, f"{file_path}", f"{addr}", f"{port}", f"{dev}", f"{funct}", f"{registersFinal}"])

    # probe_ip(addr,int(port),int(dev),int(funct),[int(x) for x in registersFinal.split(",")])

    return {"started": True, "error": ""}

@bp_wiretap.route('/tcp_probe_read', methods = ['POST'])
# #@login_required
def tcp_probe_read():

    # Define the file path
    json_file_path = os.path.join(base_path, "tcp_probe.json")

    # Check if the file exists
    if not os.path.exists(json_file_path):
        # If the file does not exist, create an empty JSON file
        with open(json_file_path, 'w') as file:
            json.dump({}, file)  # Create an empty JSON object

    data = get_json_lock(f"{base_path}/tcp_probe.json", config=False)
    
    formattedData = {}

    formattedData["status"] = data.get("status")
    formattedData["device"] = data.get("device")
    formattedData["error"] = data.get("error")

    for function in data:

        functionSelected = None

        if function == "1":

            functionSelected = "read-coils"

        elif function == "2":

            functionSelected = "read-discrete-inputs"

        elif function == "3":

            functionSelected = "read-holding-registers"

        elif function == "4":

            functionSelected = "read-input-registers"

        else:

            continue

        formattedData[functionSelected] = {}

        for register in data[function]["registersList"]:

            if (str(register) in data[function]):

                if (function == "1"):

                    formattedData[functionSelected][str(register)] = {}

                    formattedData[functionSelected][str(register)]["hex"] = "-"
                    formattedData[functionSelected][str(register)]["val"] = data[function][str(register)]

                else:

                    registers = []

                    registers.append(data[function][str(register)])

                    formattedData[functionSelected][str(register)] = {}

                    hexPreformat = f"{data[function][str(register)]:04x}"

                    hexPostformat = f"{hexPreformat[0:2]} {hexPreformat[2:]}"

                    formattedData[functionSelected][str(register)]["hex"] = hexPostformat

                    if (str(register + 1) in data[function]):

                        registers.append(data[function][str(register + 1)])

                        hexExtPreformat = f"{data[function][str(register + 1)]:04x}"

                        hexExtPostformat = f"{hexExtPreformat[0:2]} {hexExtPreformat[2:]}"

                        formattedData[functionSelected][str(register)]["hex"] = f"{formattedData[functionSelected][str(register)]['hex']} {hexExtPostformat}"

                    if (len(registers) == 1):

                        wordOrder = Endian.Big
                        byteOrder = Endian.Big

                        for dataType in ["int16", "uint16"]:

                            formattedData[functionSelected][str(register)][dataType] = {}

                            for byteOrder in [Endian.Big, Endian.Little]:

                                key = f"{'B' if byteOrder == Endian.Big else 'L'}{'B' if wordOrder == Endian.Big else 'L'}"

                                decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder = byteOrder, wordorder = wordOrder)

                                try:

                                    if (dataType == "int16"):

                                        decodedData = decoder.decode_16bit_int()

                                    elif (dataType == "uint16"):

                                        decodedData = decoder.decode_16bit_uint()

                                    if (math.isnan(decodedData)):

                                        decodedData = "-"

                                    formattedData[functionSelected][str(register)][dataType][key] = decodedData

                                except:

                                    formattedData[functionSelected][str(register)][dataType][key] = "-"

                        for dataType in ["int32", "uint32", "float32"]:

                            formattedData[functionSelected][str(register)][dataType] = {}

                            for key in ["BB", "BL", "LB", "LL"]:
                            
                                formattedData[functionSelected][str(register)][dataType][key] = "-"

                    elif (len(registers) == 2):

                        for dataType in ["int16", "uint16", "int32", "uint32", "float32"]:

                            formattedData[functionSelected][str(register)][dataType] = {}

                            for wordOrder in [Endian.Big, Endian.Little]:

                                for byteOrder in [Endian.Big, Endian.Little]:

                                    key = f"{'B' if byteOrder == Endian.Big else 'L'}{'B' if wordOrder == Endian.Big else 'L'}"

                                    decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder = byteOrder, wordorder = wordOrder)

                                    try:

                                        if (dataType == "int16"):

                                            decodedData = decoder.decode_16bit_int()

                                        elif (dataType == "uint16"):

                                            decodedData = decoder.decode_16bit_uint()

                                        elif (dataType == "int32"):

                                            decodedData = decoder.decode_32bit_int()

                                        elif (dataType == "uint32"):

                                            decodedData = decoder.decode_32bit_uint()

                                        elif (dataType == "float32"):

                                            decodedData = decoder.decode_32bit_float()

                                        if (math.isnan(decodedData)):

                                            decodedData = "-"

                                        formattedData[functionSelected][str(register)][dataType][key] = decodedData

                                    except:

                                        formattedData[functionSelected][str(register)][dataType][key] = "-"

            else:

                formattedData[functionSelected][str(register)] = {}

                formattedData[functionSelected][str(register)]["hex"] = "-"

                for dataType in ["int16", "uint16", "int32", "uint32", "float32"]:

                    formattedData[functionSelected][str(register)][dataType] = {}

                    formattedData[functionSelected][str(register)][dataType]["BB"] = "-"
                    formattedData[functionSelected][str(register)][dataType]["BL"] = "-"
                    formattedData[functionSelected][str(register)][dataType]["LB"] = "-"
                    formattedData[functionSelected][str(register)][dataType]["LL"] = "-"

    return formattedData

@bp_wiretap.route('/tcp_probe_kill', methods = ['POST'])
#@login_required
def tcp_probe_kill ():

    try:

        global tcpProbeSubprocess

        if (not(tcpProbeSubprocess == None)):

            tcpProbeSubprocess.kill()

            tcpProbeSubprocess = None

        return ("Success")
    
    except Exception as e:

        print(e)

        return ("Failed")
    
@bp_wiretap.route('/remove_register', methods = ['POST'])
#@login_required
def remove_register ():

    try:

        data = None

        requestData = json.loads(request.data.decode('utf-8'))

        with fasteners.InterProcessLock("/sos-config/modbus_tcp_info/tcp_probe.json"):

            with open("/sos-config/modbus_tcp_info/tcp_probe.json", "r") as f:

                data = json.load(f)

        if requestData["function"] == "read-coils":

            function = "1"

        elif requestData["function"] == "read-discrete-inputs":

            function = "2"

        elif requestData["function"] == "read-holding-registers":

            function = "3"

        elif requestData["function"] == "read-input-registers":

            function = "4"

        register = int(requestData["register"])

        data[function]["registersList"].remove(register)

        with fasteners.InterProcessLock("/sos-config/modbus_tcp_info/tcp_probe.json"):

            with open("/sos-config/modbus_tcp_info/tcp_probe.json", "w") as f:

                f.write(json.dumps(data))

        return ("Done")
    
    except:

        return ("Failed")
    
@bp_wiretap.route('/make_tag_map', methods = ['POST'])
#@login_required
def make_tag_map():
    data = get_json_lock("sos_templates_modbus")
    templates = get_json_lock("sos_templates")
    requestData = json.loads(request.data.decode('utf-8'))
    device_type = requestData["devType"]
    template = requestData["map_name"]
    deviceTemplates = data[device_type]

    deviceTemplateNames = [x.replace(" ", "") for x in deviceTemplates]

    if (template.replace(" ", "") in deviceTemplateNames):
        return {"status": "Error", "error": "dupName"}
    
    elif (template == ""):
        return {"status": "Error", "error": "noName"}
    
    if not(device_type in templates):

        templates[device_type] = []
    
    templates[device_type][template] = {}

    tag_map_array = []

    dWOrder = requestData["byteWord"]
    if (dWOrder == 'BB'):
        byteWordOrder = "bigByte_bigWord"

    elif (dWOrder == 'BL'):
        byteWordOrder = "bigByte_smallWord"

    elif (dWOrder == 'LB'):
        byteWordOrder = "smallByte_bigWord"

    elif (dWOrder == 'LL'):
        byteWordOrder = "smallByte_smallWord"
    else:
        return {"status": "Error", "error": "bWOrder"}
    
    if (requestData["tagMap"] == []):
        return {"status": "Error", "error": "tagMapEmpty"}

    for tag in requestData["tagMap"]:
        templates[device_type][template][tag["measure"]] = {}
        templates[device_type][template][tag["measure"]]["source_measure"] = tag["name"]
        templates[device_type][template][tag["measure"]]["source_unit"] = tag["settings"]["unit"]

        quantity = 1

        if (tag["dataType"] in ['int16', 'uint16']):

            quantity = 1

        elif (tag["dataType"] in ['int32', 'uint32', 'float32']):

            quantity = 2

        # Fixed Error in setting scale_mode
        autoscaling = {}
        
        scale_mode = tag["settings"]["scale_mode"]
        autoscaling["scale_mode"] = scale_mode
        
        if (scale_mode == "slope_intercept"):

            autoscaling["offset"] = float(tag["settings"]["offset"])
            autoscaling["slope"] = float(tag["settings"]["slope"])

        elif (scale_mode == "point_slope"):
            
            autoscaling["slope"] = float(tag["settings"]["offset"])
            autoscaling["offset"] = float(tag["settings"]["slope"])

            autoscaling["target_min"] = float(tag["settings"]["target_min"])
            autoscaling["target_max"] = float(tag["settings"]["target_max"])
            autoscaling["value_min"] = float(tag["settings"]["value_min"])
            autoscaling["value_max"] = float(tag["settings"]["value_max"])

        tag_map_array.append({
            "address": int(tag["register"]),
            "autoScaling": autoscaling,
            "byteword_order": byteWordOrder,
            "dataType": tag["dataType"],
            "description": "",
            "function": tag["function"],
            "measure": tag["measure"],
            "name": tag["name"],
            "quantity": quantity,
            "unit": tag["settings"]["unit"]
        })

    data[device_type][template] = tag_map_array

    with json_lock('sos_templates_modbus'):
        save_json_config('sos_templates_modbus', data)
    with json_lock('sos_templates'): 
        save_json_config('sos_templates', templates)
        
    # Add to call groups
    auto_gen_call_groups_simple(device_type, template, 10)

    return {"status": "Success"}, 201

@bp_wiretap.route('/fetch_new_templates', methods = ['POST'])
#@login_required
def fetch_new_templates ():

    site_devices = get_json_lock("site_devices")

    device_templates = get_json_lock('sos_templates_modbus')
    device_templates_list = {}

    for dev_type in device_templates.keys():

        device_templates_list[dev_type] = []

        for dev_temp in device_templates[dev_type].keys():

            device_templates_list[dev_type].append(dev_temp)

    return {"types": site_devices, "templates": device_templates_list}



# new routes


@bp_wiretap.route('/discover', methods = ['GET', 'POST'])
# #@login_required
def discover():
    adapters = get_ethernet_adapters()
    return render_template('/wire_tap/discover.html', adapters = adapters)

def list_virtual_ports():
    """List available serial ports, including the specific virtual ports created."""
    ports = list(serial.tools.list_ports.comports())
    specific_ports = ['/dev/ttys004']

    for specific_port in specific_ports:
        if os.path.exists(specific_port):
            port_info = serial.tools.list_ports_common.ListPortInfo(specific_port)
            ports.append(port_info)

    return ports

@bp_wiretap.route('/discover_wiretap', methods = ['GET', 'POST'])
# #@login_required
def discover_wiretap():
    
    # List all available COM ports
    #ports = serial.tools.list_ports.comports()

    ports = list_virtual_ports()
    
    # Print details about each COM port
    serial_ports = []

    for port in ports:
        print('The Ports are ',port)

        serial_ports.append({"Port": port.device,"Description":port.description, "Hardware ID":port.hwid})

    print('serial_ports are ',serial_ports)

    return render_template('/wire_tap/discover_wiretap.html', serial_ports = serial_ports, dataFound = True)

@bp_wiretap.route('/start_wiretap', methods = ['POST'])
def start_wiretap():

    data = request.form

    ports = data["ports"].replace(" ", "").replace(",", " ")

    global wiretapSubprocess

    #workingDirectory = os.getcwd().replace("\\", "/")

    workingDirectory = project_directory

    logging.info('start_wiretap Serial port - workingDirectory is : %s',workingDirectory)
    
    wiretapSubprocess = subprocess.Popen([python_executable_path, f"{workingDirectory}/background/modbus_rtu_wiretap/modbus_rtu_wiretap_v1_1.py", ports])#, stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)

    print([python_executable_path, f"{workingDirectory}/background/modbus_rtu_wiretap/modbus_rtu_wiretap_v1-1.py", ports])

    return "Started"

@bp_wiretap.route('/stop_wiretap', methods = ['GET', 'POST'])
def stop_wiretap():

    try:

        global wiretapSubprocess

        if (not(wiretapSubprocess == None)):

            wiretapSubprocess.kill()

            wiretapSubprocess = None
            
        return "Finished"
    
    except Exception as e:

        return "Errored"
    
@bp_wiretap.route('/fetch_counts', methods = ['POST'])
def fetch_counts():

    workingDirectory = os.getcwd().replace("\\", "/")
        
    countsFilePath = f'{log_base_path}/counts.json'
    
    counts = get_json_lock(countsFilePath, config = False)

    return f'{counts.get("total")}'


@bp_wiretap.route('/fetch_device_list', methods = ['POST'])
def fetch_device_list():

    if (wiretapDBExists):

        wireTapped_Data = db.get_all()

    else:

        wireTapped_Data = None

    ids = []

    if not(wireTapped_Data is None):

        found = False

        tappedSerialPorts = request.form["ports"]

        if not(type(tappedSerialPorts) == type([])):
                    
            tappedSerialPorts = [tappedSerialPorts]

        for i in wireTapped_Data:

            found = False

            if (not(i.port in tappedSerialPorts)):

                continue

            if not(found) and not((i.id, i.port) in [(x[1], x[2]) for x in ids]) and (i.port in tappedSerialPorts):

                ids.append(f"{i.id}{i.port},{i.id},{i.port},{i.port} - {i.id:03d},{False}")

        ids.sort(key = lambda x: x[3])

    return ";".join(ids)

@bp_wiretap.route('/fetch_registers', methods = ['GET', 'POST'])
# #@login_required
def fetch_registers():

    data = json.loads(request.data.decode('utf-8'))

    addr = data["address"]
    port = data["port"]
    device = data["devId"]
    function = data["function"]
    registers = data["registers"]

    wordOrder = Endian.Big
    byteOrder = Endian.Big

    result_data= []
    
    start = 0
    ends = 0
    try:
        
        if('-' in registers):
            start = int(registers.split('-')[0])
            ends = int(registers.split('-')[1])+1
        else:
            ends = int(registers)+1

    except:
        return {"status": 'failure', 'error': "Invalid Registers Range"}

    if (not(re.search("^((25[0-5]|((2[0-4]|1\d|[1-9]|)\d))\.){3}(25[0-5]|((2[0-4]|1\d|[1-9]|)\d))$", addr))):

        return {"status": 'failure', 'error': "Bad Address"}
    
    try:

        if ((int(port) < 0) or (int(port) > 65536)):

            return {"status": 'failure', "error": "Bad Port"}
        
    except:

        return {"status": 'failure', "error": "Bad Port"}
    
    try:
    
        if ((int(device) < 1) or (int(device) > 255)):

            return {"status": 'failure', "error": "Bad Device"}
        device = int(device)
    
    except:

        return {"status": 'failure', "error": "Bad Device"}
    
    try:
    
        if (not(int(function) in [1, 2, 3, 4])):

            return {"status": 'failure', "error": "Bad Function"}
        function= int(function)
    
    except:

        return {"status": 'failure', "error": "Bad Function"}

    try:
        
        client = ModbusTcpClient(host = addr, port = port, timeout = 2)
        client.connect()

    except:
        return {"status": 'failure', "error": "invalid IP"}
    

    for register in range(start,ends):
        
        try:

            if (function == 1):
                res1 = client.read_coils(register, 1, unit = device)

            elif (function == 2):
                res1 = client.read_discrete_inputs(register, 1, unit = device)

            elif (function == 3):
                res1 = client.read_holding_registers(register, 1, unit = device)

            elif (function == 4):
                res1 = client.read_input_registers(register, 1, unit = device)
            
                
            try:
                hex_value = (hex(res1.registers[0])).upper()
                if len(hex_value)>1:
                    chunks = [hex_value[i:i+2] for i in range(0, len(hex_value), 2)]
                    hex_value = " ".join(chunks)
            except:
                hex_value = '-'                

            try:
                decoder = BinaryPayloadDecoder.fromRegisters(res1.registers, byteorder = byteOrder, wordorder = wordOrder)
                int16 = decoder.decode_16bit_int()

            except:

                int16 = "-"



            try:
                decoder = BinaryPayloadDecoder.fromRegisters(res1.registers, byteorder = byteOrder, wordorder = wordOrder)

                int32 = decoder.decode_32bit_int()

            except:

                int32 = "-"



            try:    
                decoder = BinaryPayloadDecoder.fromRegisters(res1.registers, byteorder = byteOrder, wordorder = wordOrder)
                uint16 = decoder.decode_16bit_uint()

            except:

                uint16 = "-"



            try:
                decoder = BinaryPayloadDecoder.fromRegisters(res1.registers, byteorder = byteOrder, wordorder = wordOrder)
                uint32 = decoder.decode_32bit_uint()

            except:

                uint32 = "-"



            try:
                decoder = BinaryPayloadDecoder.fromRegisters(res1.registers, byteorder = byteOrder, wordorder = wordOrder)
                float32 = decoder.decode_32bit_float()
            except:
                float32 = "-"
            

            if(res1.registers[0]):
                result_data.append({'register':40000+int(register),'hex_value':hex_value,'int16':int16,'int32':int32,'uint16':uint16,'uint32':uint32,'float32':float32,'slope':'-','intercept':'-','scaled':'-'})
        except:
            pass
    
    return {'status':'success',"registers":result_data}


def get_ethernet_adapters():

    address_information = psutil.net_if_addrs()

    formatted_information = []

    for inter in address_information.keys():

        interface = inter.lstrip()

        current_interface = {"name": interface}

        for entry in address_information[interface]:

            if (entry.family == socket.AF_INET):

                current_interface["Subnet Mask"] = entry.netmask
                current_interface["ipv4_address"] = entry.address

        formatted_information.append(current_interface)

    valid_interfaces = [x for x in formatted_information if (("name" in x) and ("Subnet Mask" in x) and ("ipv4_address" in x))]
    valid_interfaces.sort(key = lambda x: x['name'] if not(x['name'] in ['en0', 'eth0', 'wlan0', 'ethernet_0', "Wi-Fi"]) else "1")

    return valid_interfaces
