from flask import Blueprint, render_template, request, redirect, send_from_directory, request, redirect, jsonify
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import TextField, validators, StringField, SubmitField, HiddenField, BooleanField, SelectField, DateField, SelectMultipleField, IntegerField, FloatField, RadioField, FieldList

from werkzeug.utils import secure_filename
from copy import deepcopy
# from logger import add_to_log
import json
import os
import sqlite3
from copy import deepcopy

from helpers.common import printd, printe, json_lock
from controllers.helpers import get_uid_index, get_json_lock, get_json_config, save_json_config, get_formatted_download_string, allowed_file, iconography, get_device_info, get_device_template_info

# roles = get_json_lock('roles', config=True)
roles = {}

# from scripts.devices_export_csv import *
# from scripts.devices_import_csv import *

bp_devices = Blueprint('bp_devices', __name__)

#helper function for splitDevs
def parentClear(send, par, devType, devArr):
    send['parent'] = par.get(devType)
    if isinstance(send['parent'], bool):
        send['parent'] = None
    devArr.append(send)

#initialization of loc, coms, and elec devices
def splitDevs(devices_master):
    devices = deepcopy(devices_master)
    loc_dev = {}
    coms_dev = {}
    elec_dev = {}
    for dev_type, dev_data in devices.items():
        loc_dev[dev_type] = []
        coms_dev[dev_type] = []
        elec_dev[dev_type] = []
        for dev in dev_data:
            devsend = deepcopy(dev)
            parent = dev.get('parent')
            if dev['parent']['loc'] != None:
                parentClear(devsend, parent, "loc", loc_dev[dev_type])
            devsend = deepcopy(dev)
            if dev['parent']['coms'] != None:
                parentClear(devsend, parent, "coms", coms_dev[dev_type])
            devsend = deepcopy(dev)
            if dev['parent']['elec'] != None:
                parentClear(devsend, parent, "elec", elec_dev[dev_type])           
    return loc_dev, coms_dev, elec_dev

def getJsTree(devices):
    #creating a new tree
    tree_json = {
        "core": {
            "animation": 0,
            "check_callback": True,
            "themes": { "stripes" : False, "dots": False},
            'data': [
            ]
        },
        "types": {
            "default": {
              "icon": "../static/jsTree/themes/custom_icons/scada.png"
            },
            "Inverter": {
              "icon": "../static/jsTree/themes/custom_icons/invt.png"
            },
            "Weather_Station": {
                "icon": "../static/jsTree/themes/custom_icons/mteo.png"
            },
            "Transformer": {
                "icon": "../static/jsTree/themes/custom_icons/xfmr.png"
            },
            "Array": {
                "icon": "../static/jsTree/themes/custom_icons/array.png"
            },
            "Energy_Meter": {
                "icon": "../static/jsTree/themes/custom_icons/emtr.png"
            },
            "Battery_Storage": {
                "icon": "../static/jsTree/themes/custom_icons/battery.png"
            },
            "Recloser": {
                "icon": "../static/jsTree/themes/custom_icons/breaker.png"
            },
            "Plant_Controller": {
                "icon": "../static/jsTree/themes/custom_icons/scada.png"
            },
            "Camera": {
                "icon": "../static/jsTree/themes/custom_icons/camera.png"
            }
        },
        "plugins": [
            "dnd",
            "types",
            "sort"
        ]
    }
    master_paths = {}
    
    #helper function for following while loop
    def jsonObjectAdder(dev, type):
        jsonAppend = {"text": dev.get('sos_name'),
                      "id": dev.get('daq_name'),
                      "type": type,
                      'state': {'opened': True},
                      "children": [
                        ]
                    }
        return jsonAppend

    #appending the tree_json['core']['data'] attribute with a new 'data' object value if it does not exist within the 'parent' attribute
    #then sets the master_paths[device['daq_name']] to tree_json['core']['data']'s length-1, then removes device from devs.
    while len(devices) > 0:
        for dev_type, devs in devices.copy().items():
            for device in devs:
                if not device['parent']:
                    tree_json['core']['data'].append(jsonObjectAdder(device, dev_type))
                    master_paths[device['daq_name']] = tree_json['core']['data'][len(tree_json['core']['data'])-1]
                    devs.remove(device)
    #Otherwise if device['parent'] exists in master_paths, master_paths[device['parent']]['children'] will be appended with a new object, then sets
    #master_paths[device['daq_name']] equal to path[len(path)-1], then removes device from devs.
                elif device['parent'] in master_paths:
                    path = master_paths[device['parent']]['children']
                    path.append(jsonObjectAdder(device, dev_type))
                    master_paths[device['daq_name']] = path[len(path)-1]
                    devs.remove(device)
            if len(devs) == 0:
                del devices[dev_type]
    return tree_json


#Finds and changes device tag based on argument values
def findAndChangeParent(devices, name, tag, value, processed_devs):
    for _, dev_list in devices.items():
        for dev in dev_list:
            if dev['daq_name'] == name:
                dev['parent'][tag] = value
                processed_devs.append(dev.get('daq_name'))
                return True
    return False


# calls findAndChangeParent for all entries in search_point['children'], and if data['children'] has 
# entries findAndRedefine recursively calls itself
def findAndRedefine(devices, search_point, tree_type, processed_devs):
    parent = search_point.get('id')
    for data in search_point['children']:
        findAndChangeParent(devices, data['id'], tree_type, parent, processed_devs)
        if len(data['children']) > 0:
            findAndRedefine(devices, data, tree_type, processed_devs)

#returns device data on focus_window.html
@bp_devices.route('/device_focus/<daq_id>')
def render_device_focus_window(daq_id):
    device_info = get_device_info(daq_id)
    asset_parameters = get_json_lock("asset_parameters")
    device_params = asset_parameters[device_info['device_type']]

    return(render_template('/devices/focus_window.html', device_info=device_info, device_params=device_params, daq_id=daq_id))

#renders device table 
@bp_devices.route('/devices_table', methods=['GET', 'POST'])
def device_view_table():
    site_devices = get_json_lock("site_devices")
    device_types = list(site_devices.keys())
    return render_template("/devices/devices_table.html", device_types=device_types)

@bp_devices.route('/getdevicechild', methods=['GET', 'POST'])
def get_device_child():
    site_devices = get_json_lock("site_devices")
    child_device = {}
    #Returns a JSON object containing all plant devices and certain
    #related parameters.
    #Accepts as a request URL argument:
    #device (str): the name of the device request. Defaults to blank (gets
    #all devices).
    if ("parent_device" in request.form):
     
        devices = site_devices[request.form["device_type"]]
        for dev in devices:
            print(request.form["parent_device"])
            if(dev["parent"]['elec'] == request.form["parent_device"]):
                child_device = dev
        return jsonify(child_device)
    
@bp_devices.route('/getplantdevices', methods=['GET', 'POST'])
def get_devices_api():
    """ Returns a JSON object containing all plant devices and certain
        related parameters.
        Accepts as a request URL argument:

    Returns:
        device (str): the name of the device request. Defaults to blank (gets
        all devices).
    """
    
    if ("device" in request.form):
        return jsonify(get_devices(request.form.get('device')))
    return jsonify(get_devices(request.args.get('device')))

def get_devices(device_type = ""):
    """
    Returns a dictionary with available devices, by type.

    Searches the site_devices JSON file for devices matching the
    requested device type, and retrieves values associated with
    the default parameters of interest plus those listed in the
    asset_parameters JSON file related to that type.

    Args:
       device_type (str, optional): Name of the device to retrieve
       info for. Defaults to "" (returns info common to all devices).

    Returns:
       dict: ['data']: a list of device dicts containing the retrieved
       device information,
       ['params']: a list of all keys contained in data.
    """

    site_devices = get_json_lock("site_devices")
    device_list = list(site_devices.keys())
    params=[]
    # Filter out the devices that don't match the requested device, if
    # provided
    if device_type:
        if device_type in device_list:
        # Just replace the device list with the requested parameter
            device_list = [device_type]
            add_params = get_json_lock("asset_parameters")
            for param in add_params[device_type]:
                params.append(param)
        else:
            return "Not in list. Acceptable device names:" + str(device_list)

    result = {
        "data": []
    }
    # Populate the result with objects generated from the json file
    for series in device_list:
        for device in site_devices[series]:
            netinfo = device['network'].get('params')
            newDevice = {}
            # This is hard coded because I wanted to change the key of certain
            # entries. @TODO is there a better way to do this?
            newDevice['ip'] = netinfo.get('ip')
            newDevice['port'] = netinfo.get('port')
            newDevice['comm_id'] = netinfo.get('comm_id')
            newDevice['protocol'] = netinfo.get('protocol')
            newDevice['name'] = device.get('sos_name')
            newDevice['UID'] = device.get('daq_name')
            newDevice['model'] = device.get('model')
            newDevice['data_template'] = device.get('daq_template')
            newDevice['serial_number'] = device.get('serial_number')
            newDevice['device_type'] = device.get('device_type')

            # If additional device parameters are needed, add them to the newDevice
            
            for item in params:
                try:
                    newDevice[item] = device[item]
                except:
                    pass
            result["data"].append(newDevice)

    result["params"] = list(result["data"][0].keys())
    for item in params:
        result["params"].append(item)

    return result

#returns partial devices table
@bp_devices.route('/devices_table_part/<device_type>', methods=['GET', 'POST'])
def devices_table_partial(device_type):
    plant_config = get_json_lock("plant_config")

    site_devices = get_json_lock("site_devices")
    asset_parameters = get_json_lock("asset_parameters")

    device_types = list(site_devices.keys())

    default_params = ["Name","UID","Make","Tag Map","Serial","IP","Port","Protocol","Comm ID"]

    param_list = []

    if device_type == "all":
        param_list = []
    elif device_type in asset_parameters:
        param_list = asset_parameters[device_type]

    target_device = []
    all_devices_list = []

    if device_type == "all":
        for dev_type in site_devices:
            for device in site_devices[dev_type]:
                all_devices_list.append(device)
    else:
        target_device = site_devices[device_type]

    return render_template("/devices/_devices_table_part.html",
        icons=iconography, plant_config=plant_config, device_types=device_types,
        default_params=default_params, all_devices_list=all_devices_list,
        target_device=target_device, param_list=param_list)

@bp_devices.route('/export_devices_csv', methods=['GET','POST'])
#@login_required
def export_devices_csv():
    
    #generate CSV file and save in sos-config, other folder?
    if request.form:
        requestdata = json.loads(request.form['data'])
        print(request.form['data'])
        class_name = requestdata['values']
        file_path = get_formatted_download_string(class_name, "csv")
        full_file_path = '/sos-config/' + file_path
        export_devices_to_csv(full_file_path)
    else:
        file_path = "mypv_devices_export.xlsx"
        export_devices_to_csv()
    return send_from_directory('/sos-config/', file_path, as_attachment=True)

#import devices via a csv file
@bp_devices.route('/import_bulk_devices_csv', methods=['GET','POST'])
#@login_required
def import_bulk_devices_csv():
    temp_file = request.files.get("file", {"filename": ""})
    
    if request.method != 'POST' or not allowed_file(temp_file.filename):
        return redirect('/devices_tree')

    # In a POST, the filename is valid and allowed.
    filename = secure_filename("mypv_devices_upload.xlsx")
    path_to_temp = os.path.join("./uploads/", filename)
    temp_file.save(path_to_temp)

    #Get Value of Delete and Update Existing Checkboxes
    
    delete_devices = request.form.get("delete_devices", False)
    update_existing = request.form.get("update_existing", False)

    #Pass Path to file and checkboxes to csv import script
    import_results = import_devices_from_csv(path_to_temp, delete_devices, update_existing)
    # Calls function that normally renders the device_tree page
    return redirect('/devices_tree')
    

#returns JSON object consisting of loc_devs, coms_devs, and elec_devs
@bp_devices.route('/get_devices_trees', methods=['GET', 'POST'])
def get_devices_trees():
    site_devices = get_json_lock('site_devices')
    loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
    loc_tree = getJsTree(loc_devs)
    coms_tree = getJsTree(coms_devs)
    elec_tree = getJsTree(elec_devs)
    return jsonify([loc_tree, coms_tree, elec_tree])

""" BEGIN DEVICES TREE OPERATION FUNCTIONALITY """
@bp_devices.route('/devices_tree', methods=['GET', 'POST'])
#@login_required
def device_view_tree_2(import_csv_results=None):
    """ Endpoint to handle rendering the devices tree page, displaying and modifying
        devices. Passes any number of device edit forms.

    Args:
        import_csv_results (_type_, optional): Bulk Device import . Defaults to None.

    Returns:
        render_template
    """
    messages = {"success": [], "failure": []}
    target_device = ""
    plant_config = get_json_lock('plant_config')
    site_devices = get_json_lock('site_devices')
    asset_params = get_json_lock('asset_parameters')
    device_templates = get_json_lock('device_templates')
    device_templates_list = {}

    for dev_type in device_templates:
        device_templates_list[dev_type] = []
        for dev_temp in device_templates[dev_type]:
            map_temp = {}
            map_temp['name'] = dev_temp.get('template_name')
            map_temp['id'] = dev_temp.get('template_id')
            device_templates_list[dev_type].append(map_temp)

    loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
    loc_tree = getJsTree(loc_devs)
    coms_tree = getJsTree(coms_devs)
    elec_tree = getJsTree(elec_devs)
    master_tree = [loc_tree, coms_tree, elec_tree]
    
    if import_csv_results:
        import_csv_results = import_csv_results.split('\n')

    if request.method == 'POST' and import_csv_results==None:
        print('received post in devices view 2')

        form_action = request.form.get('action', False)
        if form_action == "delete":
            print('received delete for: ' + request.form['device_id'])
            
            device_info = get_device_info(request.form['device_id'])
            if delete_device(device_info['daq_name']):
                messages = {'success': ['Deleted ' + device_info.get('sos_name')]}
            else:
                messages = {'failure': ['Failed to Delete ' + device_info.get('sos_name')]}
            site_devices = get_json_lock('site_devices') #site devices has changed, re-open
            loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
            loc_tree = getJsTree(loc_devs)
            coms_tree = getJsTree(coms_devs)
            elec_tree = getJsTree(elec_devs)
            master_tree = [loc_tree, coms_tree, elec_tree]
            return render_template('/devices/devices_tree_2.html', edit=False, messages=messages, roles=roles, icons=iconography, plant_config=plant_config, tree_json=master_tree, site_devices=site_devices, device_templates_list=device_templates_list)
        
        else:
            fr = get_clone_form_by_protocol(existing_data=request.form)
            
            if fr.cloneDevice.data:
                asset_params = get_json_lock("asset_parameters")
                clone_daq = fr.daq_name.data
                device_info = get_device_info(clone_daq)
                
                dev_type = device_info.get('device_type', None)
                fields = asset_params[dev_type]

                # Hard-coded electrical parent
                parent_id = device_info["parent"]["elec"]
                params = device_info['network']['params']
                ip = params.get('ip', '000.000.000.000')
                device_comm = params.get('comm_id', '1')
                device_tag_offset = device_info.get('daq_template_offset', 0)
                device_port = params.get('port', 0)

                form_noOfClones = fr.noOfClones.data
                # defaults
                form_incSuffix, form_startValue, form_suffixMask = '1', '1', 'copy '
                supplied_name_enumeration = False
                if fr.incName.data:
                    supplied_name_enumeration = True
                    form_incSuffix = fr.incSuffix.data
                    form_suffixMask = fr.suffixMask.data
                    form_startValue = fr.startValue.data
                
                form_ipSec1, form_ipSec2, form_ipSec3 = "0", "0", "0"
                if fr.incrementIP.data:
                    form_ipSec1 = fr.ipSec1.data if not fr.ipSec1.data=='' else '0'
                    form_ipSec2 = fr.ipSec2.data if not fr.ipSec2.data=='' else '0'
                    form_ipSec3 = fr.ipSec3.data if not fr.ipSec3.data=='' else '0'
                    
                form_comIncrement = fr.comIncrement.data
                if not form_comIncrement:
                    form_comIncrement = '0'
                
                form_tagIncrement = fr.tagIncrement.data
                if not form_tagIncrement:
                    form_tagIncrement = '0'
                    
                form_portIncrement = fr.portInc.data
                if not form_portIncrement:
                    form_portIncrement = '0'
                
                if form_incSuffix == '2':
                    form_startValue ='A'

                if form_suffixMask == '':
                    form_suffixMask = "000" if form_incSuffix == '1' else "-"
                     
                # val_ipSec = form.ip.data.split('.',3)
                val_ipSec = ip.split('.',)

                clone_list = []
                for incCounter in range(int(form_noOfClones)):
                    new_device = deepcopy(device_info)
                    new_device_params = new_device['network']['params']
                    split_value = len(str(form_startValue))
                    # Should not throw exception when split_value > len(form_suffixMask)
                    mask = form_suffixMask
                    if supplied_name_enumeration:
                        mask = form_suffixMask[:-split_value]
                    sos_suffix = str(mask) + str(form_startValue)
                    
                    if form_incSuffix == '1': 
                        form_startValue = str(int(form_startValue)+1)
                    elif form_incSuffix == '2':
                        form_startValue = chr(ord(form_startValue)+1)

                    if not form_ipSec1 == '0':
                        new_oct_1 = int(val_ipSec[1]) + int(form_ipSec1)
                        if (new_oct_1 > 255):
                            new_oct_1 = 255

                        elif (new_oct_1 < 0):
                            new_oct_1 = 0

                        val_ipSec[1] = str(new_oct_1)

                    if not form_ipSec2 == '0':
                        new_oct_2 = int(val_ipSec[2]) + int(form_ipSec2)
                        if (new_oct_2 > 255):
                            new_oct_2 = 255

                        elif (new_oct_2 < 0):
                            new_oct_2 = 0

                        val_ipSec[2] = str(new_oct_2)

                    if not form_ipSec3 == '0':
                        new_oct_3 = int(val_ipSec[3]) + int(form_ipSec3)

                        if (new_oct_3 > 255):
                            new_oct_3 = 255

                        elif (new_oct_3 < 0):
                            new_oct_3 = 0

                        val_ipSec[3] = str(new_oct_3)

                    if not form_comIncrement == '0':
                        new_comm_id = int(device_comm) + int(form_comIncrement)

                        if (new_comm_id > 255):
                            new_comm_id = 255

                        elif (new_comm_id < 1):
                            new_comm_id = 1

                        new_device_params['comm_id'] = str(new_comm_id)
                        device_comm = str(new_comm_id)
                        
                    if not form_portIncrement == '0':
                        new_port = int( device_port ) + int( form_portIncrement )
                        new_device_params['port'] = new_port
                        device_port = new_port
                        
                    if not form_tagIncrement == '0':
                        new_tag_offset = int(device_tag_offset) + int(form_tagIncrement)
                        new_device['daq_template_offset'] = new_tag_offset
                        device_tag_offset = new_tag_offset
                
                    new_device['sos_name'] = f"{device_info['sos_name']}{sos_suffix}"
                    new_device_params['ip'] = val_ipSec[0]+'.'+val_ipSec[1]+'.'+val_ipSec[2]+'.'+val_ipSec[3]
                    
                    print('creating clone device')
                    last_index = get_uid_index("devices")
                    new_device['daq_name'] = "DEV_" + str(last_index)
                    # Asset_measures
                    for field in fields:
                        new_device[field] = device_info.get(field, '')
                    
                    # NOTE: Hard-coded electric parent, need to change to reflect jstree clone
                    new_device['parent']['elec'] = parent_id
                    clone_list.append(new_device)
                
                site_devices = get_json_lock('site_devices')    
                for device in clone_list:
                    site_devices[dev_type].append(device)
                try:
                    with json_lock('site_devices'):
                        save_json_config('site_devices', site_devices)
                except Exception as e:
                    printd(f"Attemped to clone devices and save, failed")
                    print(e)
                    messages['failure'].append('Failed to save site_devices when cloning')

                loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
                loc_tree = getJsTree(loc_devs)
                coms_tree = getJsTree(coms_devs)
                elec_tree = getJsTree(elec_devs)
                master_tree = [loc_tree, coms_tree, elec_tree]
                device_templates_list = {}

                for dev_type in device_templates:
                    device_templates_list[dev_type] = []
                    for dev_temp in device_templates[dev_type]:
                        map_temp = {}
                        map_temp['name'] = dev_temp.get('template_name')
                        map_temp['id'] = dev_temp.get('template_id')
                        device_templates_list[dev_type].append(map_temp)

                return render_template('/devices/devices_tree_2.html', edit=False,roles=roles, icons=iconography, plant_config=plant_config, tree_json=master_tree, site_devices=site_devices, messages=messages, target_device=target_device, device_templates_list=device_templates_list)   
            else:
                # Hit when successful post and need to create device
                # VEENA Code - Need to re-write
                
                dev_type = request.form['device-device_type']
                form = get_device_form(dev_type, (request.form['device-virtual'] == 'True'), request.form['device-daq_template'])

                if form.submit.data or form.submitDeviceTemplate.data:               
                    if form.validate_on_submit():

                        if (request.form.get('device-submitDeviceTemplate', "") != ""):

                            # Added By Veena -- Start --
                            response = create_device_template_from_device(form)
                            if not (response==False):
                                messages['success'].append('Device Template Added')
                                print("Added Template")

                            # Added By Veena -- End --

                            device_templates = get_json_lock('device_templates')
                            device_templates_list = {}

                            for dev_type in device_templates:
                                device_templates_list[dev_type] = []
                                for dev_temp in device_templates[dev_type]:
                                    map_temp = {}
                                    map_temp['name'] = dev_temp.get('template_name')
                                    map_temp['id'] = dev_temp.get('template_id')
                                    device_templates_list[dev_type].append(map_temp)

                        elif (request.form.get('device-submit', "") != ""):                            
                            validationFails = []
                            
                            if ((request.form.get('device-monitored', "n") == "y") and (request.form.get('device-protocol', "None") == "ModbusTCP")):

                                if (request.form.get('device-ip', "") == ""):
                                    validationFails.append("ip")
                                    form.ip.errors.append("IP address must be provided")

                            if (request.form.get('device-sos_name', "") == ""):
                                validationFails.append("sos_name")
                                form.sos_name.errors.append("A name must be provided for devices")

                            if ((request.form.get('device-monitored', "n") == "y") and (request.form.get('device-daq_template', "-") == "-")):
                                validationFails.append("daq_template")
                                form.daq_template.errors.append("A tag map must be selected for monitored devices")

                            if (len(validationFails) > 0):
                                loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
                                loc_tree = getJsTree(loc_devs)
                                coms_tree = getJsTree(coms_devs)
                                elec_tree = getJsTree(elec_devs)
                                master_tree = [loc_tree, coms_tree, elec_tree]
                                return render_template('/devices/devices_tree_2.html',edit=False, roles=roles, form=form, icons=iconography, plant_config=plant_config, tree_json=master_tree, site_devices=site_devices, device_params=asset_params[dev_type], device_templates_list=device_templates_list)

                            else:
                                site_devices = get_json_lock('site_devices')
                                name_to_daq = {}
                                for dev_type in site_devices:
                                    for device in site_devices[dev_type]:
                                        name_to_daq[device['sos_name'].replace(" ", "")] = device['daq_name']

                                request_name = request.form['device-sos_name'].replace(" ", "")
                                if (not(request_name in name_to_daq) or ((request_name in name_to_daq) and (request.form['device-daq_name'] == name_to_daq[request_name]))):

                                    #handles saves and updates
                                    if (request.form['device-daq_name'] == ""):
                                        print('creating device')
                                        response = create_device(form)
                                       
                                        #print(save_res)
                                        if (response):
                                            messages['success'].append("Device Created")
                                            target_device = response
                                        else: 
                                            messages['failure'].append("Failed to Create Device")
                                    else:
                                        print('updating device')
                                        response = save_device(form) 
                                        if (response):
                                            messages['success'].append("Device Saved")
                                            target_device = response
                                        else:
                                            messages['failure'].append("Failed to Save Device")

                                else:
                                    form.sos_name.errors.append("Device name must be unique")

                                    loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
                                    loc_tree = getJsTree(loc_devs)
                                    coms_tree = getJsTree(coms_devs)
                                    elec_tree = getJsTree(elec_devs)
                                    master_tree = [loc_tree, coms_tree, elec_tree]
                                    return render_template('/devices/devices_tree_2.html', edit=False,roles=roles, form=form, icons=iconography, plant_config=plant_config, tree_json=master_tree, site_devices=site_devices, device_params=asset_params[dev_type], device_templates_list=device_templates_list)                            

                        site_devices = get_json_lock('site_devices') #site devices has changed, re-open
                        loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
                        loc_tree = getJsTree(loc_devs)
                        coms_tree = getJsTree(coms_devs)
                        elec_tree = getJsTree(elec_devs)
                        master_tree = [loc_tree, coms_tree, elec_tree]
                        return render_template('/devices/devices_tree_2.html',edit=False, roles=roles, icons=iconography, plant_config=plant_config, tree_json=master_tree, site_devices=site_devices, messages=messages, target_device=target_device, device_templates_list=device_templates_list)
                    else:
                        print('failed to validate')
                        print(form.errors)
                        loc_devs, coms_devs, elec_devs = splitDevs(site_devices)
                        loc_tree = getJsTree(loc_devs)
                        coms_tree = getJsTree(coms_devs)
                        elec_tree = getJsTree(elec_devs)
                        master_tree = [loc_tree, coms_tree, elec_tree]
                        return render_template('/devices/devices_tree_2.html', edit=False,roles=roles, form=form, icons=iconography, plant_config=plant_config, tree_json=master_tree, site_devices=site_devices, device_params=asset_params[dev_type], device_templates_list=device_templates_list)

    return render_template('/devices/devices_tree_2.html',edit=False,roles=roles, icons=iconography, plant_config=plant_config, tree_json=master_tree, site_devices=site_devices, device_templates_list=device_templates_list, import_csv_results=import_csv_results)

#works along new device creation and independently 
def create_device_template_from_device(form):
    print('creating / modifying new device template')

    indexes = get_json_lock('indexes')
    new_index = indexes['templates'] + 1

    daq_temp_new = None
    if form.daq_template.data != "-":
        daq_temp_new = form.daq_template.data
    
    device_templates = get_json_lock('device_templates')
    t_name = f"{form.manufacturer.data.strip()}-{form.model.data.strip()}"
    t_list = device_templates.get(form.device_type.data, [])
    
    new_template = {
        "template_id": "temp_" + str(new_index),
        "template_name": t_name,
        "sos_name": form.sos_name.data,
        "serial_number": form.serial_number.data,
        "model": form.model.data,
        "manufacturer": form.manufacturer.data,
        "daq_template": daq_temp_new,
        "virtual": False,
        "monitored": form.monitored.data,
        "description": form.description.data,
        "device_type": form.device_type.data,
        "system": form.energy_system.data,
        "parent":{
            "loc": True,
            "coms": True,
            "elec": True
        },
        "network": {
            "type": "TCP",
            "params": {
                "ip": form.ip.data,
                "protocol": form.protocol.data,
                "port": form.port.data
            }
        }
    }
    
    new_device_network = new_template["network"]
    new_device_network_params = new_device_network["params"]
    new_device_network_params['protocol'] = form.protocol.data
    new_device_network_params['ip'] = form.ip.data
    
    if (form.protocol.data == "ModbusTCP"):
        new_template["daq_template_offset"] = 0
        new_device_network_params['comm_id'] = form.comm_id.data
        new_template['polling_interval'] = form.polling_interval.data
    elif (form.protocol.data == "SNMP"):
        new_device_network_params['version'] = form.version.data
        new_device_network_params['usercommunity'] = form.user_community.data
        if (form.version.data == "v3"):
            new_device_network_params['auth_passphrase'] = form.auth_passphrase.data
            new_device_network_params['auth_type'] = form.auth_type.data
            new_device_network_params['encrypt_type'] = form.encrypt_type.data
            new_device_network_params['encrypt_passphrase'] = form.encrypt_passphrase.data
    elif (form.protocol.data == "DNP3"):
        dnp3_net_params = new_device_network_params
        dnp3_net_params['master'] = {}
        dnp3_master = dnp3_net_params['master']
        
        dnp3_net_params['max_connect_delay_ms'] = form.max_connect_delay_ms.data
        dnp3_net_params['min_connect_delay_ms'] = form.min_connect_delay_ms.data
        dnp3_master["command_mode"] = "DirectOperate"
        dnp3_master["master_address"] = form.client.data
        dnp3_master["outstation_address"] = form.outstation.data
        dnp3_master["response_timeout_ms"] = form.response_timeout.data
        dnp3_master["polls"] = []
        polls = dnp3_master["polls"]
        for idx, poll in enumerate(form.poll_intervals.data):
            classes = form.poll_classes.data[idx]
            
            polls.append({
                "period_ms": poll,
                "classes": {
                    "class_0": "class_0" in classes,
                    "class_1": "class_1" in classes,
                    "class_2": "class_2" in classes,
                    "class_3": "class_3" in classes
                }
            })
        
        dnp3_master['startup'] = {}
        startup = dnp3_master['startup']
        startup['integrity'] = {
            'class_0': form.class_0_integrity.data,
            'class_1': form.class_1_integrity.data,
            'class_2': form.class_2_integrity.data,
            'class_3': form.class_3_integrity.data
        }
        
        startup['enable_unsol'] = {}
        enable_unsol = startup['enable_unsol']
        startup['disable_unsol'] = {}
        disable_unsol = startup['disable_unsol']
        
        # Loop?
        if form.class_1_unsol.data == "enable":
            enable_unsol['class_1'] = True
            disable_unsol['class_1'] = False
        else:
            enable_unsol['class_1'] = False
            disable_unsol['class_1'] = True
            
        if form.class_2_unsol.data == "enable":
            enable_unsol['class_2'] = True
            disable_unsol['class_2'] = False
        else:
            enable_unsol['class_2'] = False
            disable_unsol['class_2'] = True
        
        if form.class_3_unsol.data == "enable":
            enable_unsol['class_3'] = True
            disable_unsol['class_3'] = False
        else:
            enable_unsol['class_3'] = False
            disable_unsol['class_3'] = True


    asset_params = get_json_lock('asset_parameters')
    for param in asset_params[form.device_type.data]:
        new_template[param] = form[param].data
    
    
    # Issue assigning here...
    foundCopy = False
    for idx, template in enumerate(t_list):
        if template.get('template_name', '') == t_name:
            print('already exists')

            new_template['template_id'] = template.get('template_id', "temp_" + str(new_index))

            foundCopy = True

            # Copy
            del t_list[idx]
            break
        
    if (not foundCopy):
        indexes['templates'] += 1
        
        with json_lock('indexes'):
            save_json_config('indexes', indexes)

    device_templates[form.device_type.data].append(new_template)

    try:
        with json_lock('device_templates'):
            save_json_config('device_templates', device_templates)
        print('device_templates', True, current_user.email, 'info', new_template.get('template_id') + " created")
    except Exception:
        return False
    
    return new_template['template_id']

#save tree
@bp_devices.route('/savetreedata', methods = ['POST'])
#@login_required
def saveTreeData():
    devices = get_json_lock('site_devices')
    tree_type = request.form['type']
    tree = json.loads(request.form['tree_data'])
    pro_devs = []

    for data in tree:
        findAndRedefine(devices, data, tree_type, pro_devs)
        findAndChangeParent(devices, data['id'], tree_type, True, pro_devs)

    for _, dev_list in devices.items():
        for dev in dev_list:
            if dev['parent'][tree_type] != None and not dev['daq_name'] in pro_devs:
                dev['parent'][tree_type] = None

    print("devices values are:",devices)
    with json_lock('site_devices'):
        save_json_config('site_devices', devices)

    return jsonify({"result": "success"})

def save_device(form):
    """ Helper function to update a device per a passed WTForm

    Args:
        form (WTForm): Passed WTForm (FlaskForm)
        
    """
    print("attempting to save device...")
    asset_params = get_json_lock('asset_parameters')

    successful_add_site_devs = True
    successful_add_virtual_devs = True
    dev_virtual = form.virtual.data
    dev_daq = form['daq_name'].data
    
    site_devices = get_json_lock('site_devices')
    virtual_devices = get_json_lock('virtual_devices')
    vd_list = virtual_devices.get('devices', [])
    
    for device in site_devices[form.device_type.data]:
        if device.get('daq_name', '') == dev_daq:
            device["sos_name"] = form.sos_name.data
            device['serial_number'] = form['serial_number'].data
            device['run_kpis'] = form['run_kpis'].data
            device['daq_template'] = form['daq_template'].data
            device['system'] = form['energy_system'].data
            device['monitored'] = form.monitored.data
            device['wiretapped'] = form.wiretapped.data
            
            # Virtual devices have network type of ""
            if device['network']['type'] == "TCP":
                device['network']['params']['ip'] = form.ip.data
                device['network']['params']['port'] = form.port.data
                device['network']['params']['protocol'] = form.protocol.data
                
                if form.protocol.data == "SNMP":
                   device['network']['params']['protocol'] = form.protocol.data
                   device['network']['params']['version'] = form.version.data
                   device['network']['params']['usercommunity'] =  form.user_community.data
                   if form.version.data == "v3":
                    device['network']['params']['auth_passphrase'] = form.auth_passphrase.data
                    device['network']['params']['auth_type'] = form.auth_type.data
                    device['network']['params']['encrypt_type'] = form.encrypt_type.data
                    device['network']['params']['encrypt_passphrase'] = form.encrypt_passphrase.data
                if form.protocol.data == "DNP3":
                    dnp3_net_params = device['network']['params']
                    dnp3_net_params['master'] = {}
                    dnp3_master = dnp3_net_params['master']
                    
                    dnp3_net_params['max_connect_delay_ms'] = form.max_connect_delay_ms.data
                    dnp3_net_params['min_connect_delay_ms'] = form.min_connect_delay_ms.data
                    dnp3_master["command_mode"] = "DirectOperate"
                    dnp3_master["master_address"] = form.client.data
                    dnp3_master["outstation_address"] = form.outstation.data
                    dnp3_master["response_timeout_ms"] = form.response_timeout.data
                    dnp3_master["polls"] = []
                    polls = dnp3_master["polls"]
                    for idx, poll in enumerate(form.poll_intervals.data):
                        classes = form.poll_classes.data[idx]
                        
                        polls.append({
                            "period_ms": poll,
                            "classes": {
                                "class_0": "class_0" in classes,
                                "class_1": "class_1" in classes,
                                "class_2": "class_2" in classes,
                                "class_3": "class_3" in classes
                            }
                        })
                    
                    dnp3_master['startup'] = {}
                    startup = dnp3_master['startup']
                    startup['integrity'] = {
                        'class_0': form.class_0_integrity.data,
                        'class_1': form.class_1_integrity.data,
                        'class_2': form.class_2_integrity.data,
                        'class_3': form.class_3_integrity.data
                    }
                    
                    startup['enable_unsol'] = {}
                    enable_unsol = startup['enable_unsol']
                    startup['disable_unsol'] = {}
                    disable_unsol = startup['disable_unsol']
                    
                    # Loop?
                    if form.class_1_unsol.data == "enable":
                        enable_unsol['class_1'] = True
                        disable_unsol['class_1'] = False
                    else:
                        enable_unsol['class_1'] = False
                        disable_unsol['class_1'] = True
                        
                    if form.class_2_unsol.data == "enable":
                        enable_unsol['class_2'] = True
                        disable_unsol['class_2'] = False
                    else:
                        enable_unsol['class_2'] = False
                        disable_unsol['class_2'] = True
                    
                    if form.class_3_unsol.data == "enable":
                        enable_unsol['class_3'] = True
                        disable_unsol['class_3'] = False
                    else:
                        enable_unsol['class_3'] = False
                        disable_unsol['class_3'] = True
                        
                if form.protocol.data == "ModbusTCP":
                    device['network']['params']['comm_id'] = form.comm_id.data
                    device['polling_interval'] = form['polling_interval'].data

            elif not ( device.get('wiretapped', False) in ( None, "None", "" ) ):
                device['network']['params']['comm_id'] = form.comm_id.data

            device['description'] = form.description.data
            
            for param in asset_params[device['device_type']]:

                device[param] = form[param].data
            
            if dev_virtual:

                device['daq_template_offset'] = 0
                
                for vd in vd_list:
                    if vd.get('device', '') == dev_daq:
                        vd['virtual_mode'] = "mypv_aggregate_meter"
                        if form.device_type.data == "Energy_Meter":
                            if (form.calculation_selector.data == "Sum"):

                                # Summing Inverters
                                vd['parameters']['calculation'] = "sum"
                                source_devices = []

                                for i in form.sum_selector.data:

                                    source_devices.append({"device": i, "power_source_measure": "power_true_kw"})

                                vd["parameters"]["source_devices"] = source_devices

                            else:

                                # Difference in meters power
                                vd['parameters']['calculation'] = "difference"
                                source_devices = []
                                source_devices.append({"device": form.diff_single_selector.data, "energy_generated_source_measure": "power_true_kw"})

                                for i in form.diff_multiple_selector.data:

                                    source_devices.append({"device": i, "energy_consumed_source_measure": "power_true_kw"})

                                vd["parameters"]["source_devices"] = source_devices

                        elif form.device_type.data == "Weather_Station":

                            # Virtual Weather Sensor
                            vd['virtual_mode'] = "mypv_erbs_poa"
                            vd["parameters"]["source_devices"] = [{"device": form.poa_selector.data, "ghi_measure": "irradiance_ghi"}]
                            vd["parameters"]["tracking"] = (form.tracking.data == "True")

                            if (form.tracking.data == "True"):

                                vd["parameters"]["setup-parameters"] = {
                                    "tilt": 0,
                                    "azimuth": 90,
                                    "dni_mult": form.dni_mult.data,
                                    "dhi_mult": form.dhi_mult.data
                                }

                            else:

                                vd["parameters"]["setup-parameters"] = {
                                    "tilt": form.nt_tilt_angle.data,
                                    "azimuth": form.azimuth.data,
                                    "dni_mult": form.dni_mult.data,
                                    "dhi_mult": form.dhi_mult.data
                                }

                            try:
                                with json_lock('virtual_devices'):
                                    save_json_config('virtual_devices', virtual_devices)
                                    
                                print('devices', True, current_user.email, 'info', vd['device'] + " modified")

                            except Exception as e:

                                print(e)
                                successful_add_virtual_devs = False

                            break
                            
            else:

                device['daq_template_offset'] = form['tag_offset'].data

            try:

                with json_lock('site_devices'):

                    save_json_config('site_devices', site_devices)

                print('devices', True, current_user.email, 'info', device['daq_name'] + " modified")

            except Exception:

                successful_add_site_devs = False
                printd(f"Attempted to save {dev_daq}, but failed")

            break
    
    if successful_add_virtual_devs and successful_add_site_devs:

        return form['daq_name'].data
    
    return False

def device_data_from_form(givenForm, last_ind, daq, isVirtual):
    """ Given a form, creates a new device object to be added to the tree.

    Args:
        givenForm (WTform): FlaskForm object that contains device fields
        last_ind (int): integer number for device identifier
        daq (str): requested daq_template 
        isVirtual (bool): is the device virtual or TCP?

    Returns:
        dict: contains the data in the format of a new device
    """
    monitoredData = givenForm.monitored.data if (isVirtual == False) else True
    
    new_device = {
        "daq_name": "DEV_" + str(last_ind),
        "sos_name": givenForm.sos_name.data,
        "serial_number": givenForm.serial_number.data,
        "model": givenForm.model.data,
        "manufacturer": givenForm.manufacturer.data,
        "daq_template": daq,
        "virtual": isVirtual,
        "monitored": monitoredData,
        "description": givenForm.description.data,
        "device_type": givenForm.device_type.data,
        "template": givenForm.device_template.data,
        "run_kpis": givenForm.run_kpis.data,
        "system": givenForm.energy_system.data,
        "parent" : {
            "loc": True,
            "coms": True,
            "elec": True
        },
        "network": {
            "type": "Virtual",
            "params": {
                "protocol": ""
            }
        }
    }
        
    if not isVirtual and givenForm.wiretapped.data in ( None, "None", "" ):
        new_device_network = new_device["network"]
        new_device_network_params = new_device_network["params"]
        new_device_network_params['protocol'] = givenForm.protocol.data
        new_device_network_params['ip'] = givenForm.ip.data
        new_device_network['type'] = 'TCP'
        new_device_network_params['port'] = givenForm.port.data
        
        if (givenForm.protocol.data == "ModbusTCP"):
            new_device["daq_template_offset"] = 0
            new_device_network_params['comm_id'] = givenForm.comm_id.data
            new_device['polling_interval'] = givenForm.polling_interval.data
            
        elif (givenForm.protocol.data == "SNMP"):
            new_device_network_params['version'] = givenForm.version.data
            new_device_network_params['usercommunity'] = givenForm.user_community.data
            if (givenForm.version.data == "v3"):
                new_device_network_params['auth_passphrase'] = givenForm.auth_passphrase.data
                new_device_network_params['auth_type'] = givenForm.auth_type.data
                new_device_network_params['encrypt_type'] = givenForm.encrypt_type.data
                new_device_network_params['encrypt_passphrase'] = givenForm.encrypt_passphrase.data
        elif (givenForm.protocol.data == "DNP3"):
            dnp3_net_params = new_device_network_params
            dnp3_net_params['master'] = {}
            dnp3_master = dnp3_net_params['master']
            
            dnp3_net_params['max_connect_delay_ms'] = givenForm.max_connect_delay_ms.data
            dnp3_net_params['min_connect_delay_ms'] = givenForm.min_connect_delay_ms.data
            dnp3_master["command_mode"] = "DirectOperate"
            dnp3_master["master_address"] = givenForm.client.data
            dnp3_master["outstation_address"] = givenForm.outstation.data
            dnp3_master["response_timeout_ms"] = givenForm.response_timeout.data
            dnp3_master["polls"] = []
            polls = dnp3_master["polls"]
            for idx, poll in enumerate(givenForm.poll_intervals.data):
                classes = givenForm.poll_classes.data[idx]
                
                polls.append({
                    "period_ms": poll,
                    "classes": {
                        "class_0": "class_0" in classes,
                        "class_1": "class_1" in classes,
                        "class_2": "class_2" in classes,
                        "class_3": "class_3" in classes
                    }
                })
            
            dnp3_master['startup'] = {}
            startup = dnp3_master['startup']
            startup['integrity'] = {
                'class_0': givenForm.class_0_integrity.data,
                'class_1': givenForm.class_1_integrity.data,
                'class_2': givenForm.class_2_integrity.data,
                'class_3': givenForm.class_3_integrity.data
            }
            
            startup['enable_unsol'] = {}
            enable_unsol = startup['enable_unsol']
            startup['disable_unsol'] = {}
            disable_unsol = startup['disable_unsol']
            
            # Loop?
            if givenForm.class_1_unsol.data == "enable":
                enable_unsol['class_1'] = True
                disable_unsol['class_1'] = False
            else:
                enable_unsol['class_1'] = False
                disable_unsol['class_1'] = True
                
            if givenForm.class_2_unsol.data == "enable":
                enable_unsol['class_2'] = True
                disable_unsol['class_2'] = False
            else:
                enable_unsol['class_2'] = False
                disable_unsol['class_2'] = True
            
            if givenForm.class_3_unsol.data == "enable":
                enable_unsol['class_3'] = True
                disable_unsol['class_3'] = False
            else:
                enable_unsol['class_3'] = False
                disable_unsol['class_3'] = True
              
    return new_device

def create_device(form):
    last_index = get_uid_index("devices")
    isVirtual = True if (form.virtual.data) else False
    daq_temp_new = None

    if form.daq_template.data != "-":

        daq_temp_new = form.daq_template.data

    if (form.virtual.data):
        print('creating virtual...')
        virtual_devices = get_json_lock("virtual_devices")
        new_device = device_data_from_form(form, last_index, daq_temp_new, isVirtual)
        device_virtual_mode = ""

        if (form.device_type.data == "Energy_Meter"):

            device_virtual_mode = "mypv_aggregate_meter"

            if (form.calculation_selector.data == "Sum"):

                source_devices = []

                for i in form.sum_selector.data:

                    source_devices.append({"device": i, "power_source_measure": "power_true_kw"})

                parameters = {
                    "calculation": "sum",
                    "power_source_measure": "power_true_kw",
                    "energy_accumulated_destination_measure": "energy_accumulated",
                    "energy_received_destination_measure": "energy_received",
                    "source_devices": source_devices
                }

            else:

                source_devices = []
                source_devices.append({"device": form.diff_single_selector.data, "energy_generated_source_measure": "power_true_kw"})

                for i in form.diff_multiple_selector.data:

                    source_devices.append({"device": i, "energy_consumed_source_measure": "power_true_kw"})

                parameters = {
                    "calculation": "difference",
                    "power_source_measure": "power_true_kw",
                    "energy_accumulated_destination_measure": "energy_accumulated",
                    "energy_received_destination_measure": "energy_received",
                    "source_devices": source_devices
                }

        else:

            device_virtual_mode = "mypv_erbs_poa"

            parameters = {
                "model": "erbs",
                "tracking": (form.tracking.data == "True"),
                "ghi_source_measure": "irradiance_ghi",
                "poa_destination_measure": "irradiance_poa",
                "source_devices": [{"device": form.poa_selector.data, "ghi_measure": "irradiance_ghi"}]
            }

            if (form.tracking.data == "True"):

                parameters["setup-parameters"] = {
                    "tilt": 0,
                    "azimuth": 90,
                    "dni_mult": form.dni_mult.data,
                    "dhi_mult": form.dhi_mult.data
                }

            else:
                
                parameters["setup-parameters"] = {
                    "tilt": form.nt_tilt_angle.data,
                    "azimuth": form.azimuth.data,
                    "dni_mult": form.dni_mult.data,
                    "dhi_mult": form.dhi_mult.data
                }

        new_virtual_device = {
            "device": "DEV_" + str(last_index),
            "device_type": form.device_type.data,
            "virtual_mode": device_virtual_mode,
            "solve_order": 1,
            "parameters": parameters
        }

        virtual_devices["devices"].append(new_virtual_device)

        with json_lock('virtual_devices'):

            save_json_config("virtual_devices", virtual_devices)

    else:
        new_device = device_data_from_form(form, last_index, daq_temp_new, isVirtual)

    # if ( ( form.wiretapped.data != "None" ) or ( form.wiretapped.data != None ) ):
    #     new_device["wiretapped"] = form.wiretapped.data
    # else:
    #     new_device["wiretapped"] = None
    
    if ( form.wiretapped.data in ( None, "None", "" ) ):
        new_device["wiretapped"] = None
    else:
        new_device["wiretapped"] = form.wiretapped.data

    asset_params = get_json_lock('asset_parameters')
    for param in asset_params[form.device_type.data]:
        new_device[param] = form[param].data

    site_devices = get_json_lock('site_devices')
    site_devices[form.device_type.data].append(new_device)    
    try:
        with json_lock('site_devices'):
            save_json_config("site_devices", site_devices)
        print('devices', True, current_user.email, 'info', new_device['daq_name'] + " created")
    except Exception as e:
        printd(f"Tried to create device {form.sos_name.data}, failed")
        printd(e)
        return False
    return new_device['daq_name']

#deletes devices by iterating through array until user-selected device is found, then deletes
def delete_device(daq_name):
    print("deleting %s" %daq_name)
    successful_delete_site_devs = True
    successful_delete_virtual_devs = True
    
    # Possible deadlock
    site_devices = get_json_lock('site_devices')
    virtual_devices = get_json_lock("virtual_devices")
    vd_list = virtual_devices.get('devices', [])
   
    
    for device_type in site_devices:
        for idx, dev in enumerate(site_devices[device_type]):
            if dev['parent']['elec'] == daq_name:
                dev['parent']['elec'] = True
            if dev['parent']['coms'] == daq_name:
                dev['parent']['coms'] = True
            if dev['parent']['loc'] == daq_name:
                dev['parent']['loc'] = True
            if dev.get('daq_name', '') == daq_name :      
                if dev.get('virtual', False):
                    print('virtual device...')
                    for v_idx, vd in enumerate(vd_list):
                        if vd.get('device', '') == daq_name:
                            print(f"Attempting to delete {vd.get('device', '')} from virtual_devices.json")
                            # Deleted device may have dependencies on other devices
                            try:
                                del vd_list[v_idx]
                                with json_lock('virtual_devices'):
                                    save_json_config('virtual_devices', virtual_devices)
                                print('devices', True, current_user.email, 'info', daq_name + " deleted from virtual_devices.json")
                            except Exception:
                                # Error either saving, deletion of virtual device
                                successful_delete_virtual_devs = False
                try:         
                    del site_devices[device_type][idx]
                    print('devices', True, current_user.email, 'info', daq_name + " deleted")
                except Exception:
                    successful_delete_site_devs = False
    
    with json_lock('site_devices'):
        save_json_config('site_devices', site_devices)
    
    return (successful_delete_site_devs and successful_delete_virtual_devs)

@bp_devices.route('/test_device_partial/<dev_id>')
def test_device_partial(dev_id):
    answer = {}
    moddbconn = sqlite3.connect('/opt/moddata.db')
    modcurs = moddbconn.cursor()
    modcurs.execute('SELECT * from modvalues WHERE device = ?', (dev_id,))
    results = modcurs.fetchall()

    tagData = []

    for result in results:
        tempres = {}
        tempres['value'] = result[5]
        tempres['time'] = result[8]
        tempres['label'] = result[4]
        tempres['unit'] = result[7]
        tagData.append(tempres)

    moddbconn.close()

    return render_template("/devices/_test_device.html", tagData=tagData)

class DeviceBaseForm(FlaskForm):
    daq_name = HiddenField()
    sos_name = TextField("Name", validators=[validators.length(max = 50)])
    serial_number = TextField("Serial Number")
    model = TextField("Model", validators=[validators.InputRequired(), validators.length(max=50)])
    manufacturer = TextField("Manufacturer", validators=[validators.InputRequired(), validators.length(max=50)])
    virtual = HiddenField()
    wiretapped = HiddenField()
    monitored = BooleanField("Monitored")
    description = TextField("Description")
    device_type = TextField("Device Type")
    network_type = HiddenField()
    run_kpis = BooleanField("Run KPIs")
    energy_system = SelectField("System", choices=[("PV", "Solar PV"), ("ESS", "Energy Storage")])
    device_template = HiddenField()
    form_type = HiddenField()
    submit = SubmitField("Save Device")
    submitDeviceTemplate = SubmitField("Save As Template")
    
class CloneDeviceTemplate(FlaskForm):
    cloneDevice = TextField("Device to be Cloned", validators=[validators.DataRequired()])
    noOfClones = IntegerField("No Of Clones",[validators.NumberRange(min=1)],default=1)
    clonesParentDevice = TextField("Clones Parent Device")
    daq_name = HiddenField()
    
    incName = BooleanField("Increment Name")
    incSuffix = SelectField(u"Suffix", choices=[('1', '123...')])
    suffixMask = TextField("Suffix Mask")
    startValue = IntegerField("Start Value",[validators.NumberRange(min=1)],default=1)
    
    incrementIP = BooleanField("Increment IP")
    ipSec1 = IntegerField("192.xxx.13.1",[validators.NumberRange(min=0)],default=0)
    ipSec2 = IntegerField("192.168.xxx.1",[validators.NumberRange(min=0)],default=0)
    ipSec3 = IntegerField("192.168.13.xxx",[validators.NumberRange(min=0)],default=0)
    
    incrementPort = BooleanField("Increment Port")
    portInc = IntegerField("Port",[validators.NumberRange(min=0)], default=0)
    
    cloneSubmit = SubmitField("Create Devices")
    
def get_clone_form_by_protocol(protocol="ModbusTCP", existing_data=None):
    """ Dynamically gets a CloneDeviceTemplate form by the passed protocol.
    Currently works with the following:
    - DNP3
    - Modbus
    - SNMP

    Args:
        protocol (str, optional): protocol identifier. Defaults to "ModbusTCP".

    Returns:
        WTForm: Wtform for the clone protocol
    """
    
    class dyna_asset(CloneDeviceTemplate):
        pass
    
    if protocol in ("ModbusTCP"):
        setattr(dyna_asset, "comIncrementID", BooleanField("Increment ID") )
        setattr(dyna_asset, "comIncrement", IntegerField("ID Increment",[validators.NumberRange(min=0)],default=0) )
        setattr(dyna_asset, "incrementTags", BooleanField("Increment Tags") )
        setattr(dyna_asset, "tagIncrement", IntegerField("Tags Increment",[validators.NumberRange(min=0)],default=0) )
    
    if existing_data:
        form = dyna_asset(prefix='clone-device', formdata=existing_data)
    else:
        form = dyna_asset(prefix='clone-device')
    return form
    

#given a list of fields, append needed fields to the generic form
def get_device_form(dev_type, virtual, template, deviceID = None, existing_data=None):
    asset_params = get_json_lock("asset_parameters")
    sos_templates = get_json_lock("sos_templates")
    unit_conversions = get_json_lock("unit_conversion")
    site_devices = get_json_lock("site_devices")
    
    fields = asset_params[dev_type]
    daq_templates = list(sos_templates[dev_type].keys())
    daq_templates.append('-')
    
    class dyna_asset(DeviceBaseForm):
        daq_template = SelectField("Tag Mapping", choices=[(choice, choice) for choice in daq_templates])
    
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
    
    
    if virtual == True:
        setattr(dyna_asset, "daq_template", SelectField("Tag Mapping", choices=[(str(template), str(template))]))
        
        virtual_devices = get_json_lock("virtual_devices")

        if (template == "Virtual_Meter"):

            meters = [(x["daq_name"], x["sos_name"]) for x in site_devices["Energy_Meter"]]
            inverters = [(x["daq_name"], x["sos_name"]) for x in site_devices["Inverter"]]

            allDevices = meters + inverters
            allDevicesDaqs = [x[0] for x in allDevices]

            if (not(deviceID == None) and (deviceID in allDevicesDaqs)):
                del allDevices[allDevicesDaqs.index(deviceID)]

                # Move logic to delete_device
                for i in virtual_devices["devices"]:
                    if i['virtual_mode'] != 'mypv_aggregate_meter':
                        continue
                    
                    if (deviceID in [x["device"] for x in i["parameters"]["source_devices"]]):
                        del allDevices[allDevicesDaqs.index(i["device"])]

            setattr(dyna_asset, "calculation_selector", SelectField("Virtual Energy Meter Calculation Type", choices = [("Sum", "Sum"), ("Difference", "Difference")]))
            setattr(dyna_asset, "sum_selector", SelectMultipleField("Select Devices to Sum", choices = allDevices))
            setattr(dyna_asset, "diff_single_selector", SelectField("Device 1", choices = allDevices))
            setattr(dyna_asset, "diff_multiple_selector", SelectMultipleField("Device 2", choices = allDevices))

        elif (template == "Virtual_POA"):
            poa_sensors = [(x["daq_name"], x["sos_name"]) for x in site_devices["Weather_Station"]]

            if (not(deviceID == None) and (deviceID in [x[0] for x in poa_sensors])):
                del poa_sensors[[x[0] for x in poa_sensors].index(deviceID)]
                for i in virtual_devices["devices"]:
                    if i['virtual_mode'] != 'mypv_erbs_poa':
                        continue

                    if (deviceID in [x["device"] for x in i["parameters"]["source_devices"]]):
                        del poa_sensors[[x[0] for x in poa_sensors].index(i["device"])]

            plant_config = get_json_lock("plant_config")

            setattr(dyna_asset, "poa_selector", SelectField("Select GHI Reference Device for the Virtual POA Sensor", choices = poa_sensors))
            setattr(dyna_asset, "tracking", RadioField("", choices = [("False", "Target Fixed Tilt Array"), ("True", "Follow Tracker Simulation")], default = "False"))
            setattr(dyna_asset, "tracking_exists", HiddenField())
            setattr(dyna_asset, "azimuth", FloatField("Target Panel Azimuth Angle", default = 180))
            setattr(dyna_asset, "nt_tilt_angle", FloatField("Target Panel Tilt Angle", default = plant_config['tilt_angle']))
            setattr(dyna_asset, "dni_mult", FloatField("DNI Multiplier", default = 100))
            setattr(dyna_asset, "dhi_mult", FloatField("DHI Multiplier", default = 100))
            
    else:
        # It's a non-virtual device, need to add a comm id, ip, port
        setattr(dyna_asset, "ip", TextField("IP Address", validators = [validators.IPAddress(), validators.Optional()]))
        setattr(dyna_asset, "comm_id", IntegerField("Comm. ID", validators=[validators.NumberRange(min = 1, max = 255), validators.Optional()]))
        setattr(dyna_asset, "port", IntegerField("Port", validators=[validators.NumberRange(min = 0, max = 65536)]))
        setattr(dyna_asset, "protocol", SelectField("Protocol", choices=[("ModbusTCP", "ModbusTCP"), ("SNMP", "SNMP"), ("DNP3", "DNP3")]))
        setattr(dyna_asset, "polling_interval", IntegerField("Polling Interval (s)",[validators.NumberRange(min = 1)]))

        #SNMP FIELDS
        setattr(dyna_asset, "user_community", TextField("User Community"))
        setattr(dyna_asset, "auth_passphrase", TextField("Auth Passphrase"))
        setattr(dyna_asset, "auth_type", TextField("Auth Type"))
        setattr(dyna_asset, "encrypt_passphrase", TextField("Encrypt Passphrase"))
        setattr(dyna_asset, "encrypt_type", TextField("Encrypt Type"))
        setattr(dyna_asset, "version", SelectField("Version", choices=[("v2", "v2"), ("v3", "v3")]))

        #DNP3 FIELDS
        setattr(dyna_asset, "max_connect_delay_ms", IntegerField("Max Connect Delay (ms)", [validators.optional(), validators.NumberRange(min = 1)]))
        setattr(dyna_asset, "min_connect_delay_ms", IntegerField("Min Connect Delay (ms)", [validators.optional(), validators.NumberRange(min = 1)]))
        setattr(dyna_asset, "poll_intervals", FieldList( IntegerField( label="Poll", description="ms", validators=[validators.NumberRange( min=1000 )] ) ))
        setattr(dyna_asset, "poll_classes", FieldList(SelectMultipleField( choices=[ ("class_0", "Class 0 (static)"),("class_1", "Class 1 (event)"), ("class_2", "Class 2 (event)"), ("class_3", "Class 3 (event)") ] )))
        setattr(dyna_asset, "class_0_integrity", BooleanField("Class 0"))
        setattr(dyna_asset, "class_1_integrity", BooleanField())
        
        setattr(dyna_asset, "class_1_unsol", RadioField("Class 1", choices=[ ("disable", ""), ("enable", "") ]) )

        setattr(dyna_asset, "class_2_integrity", BooleanField())
        setattr(dyna_asset, "class_2_unsol", RadioField("Class 2", choices=[ ("disable", ""), ("enable", "") ]) )

        setattr(dyna_asset, "class_3_integrity", BooleanField())
        setattr(dyna_asset, "class_3_unsol", RadioField("Class 3", choices=[ ("disable", ""), ("enable", "") ]) )

        setattr(dyna_asset, "outstation", IntegerField( "Outstation ID", [validators.NumberRange(min = 0)] ) )
        setattr(dyna_asset, "client", IntegerField( "Client ID", [validators.NumberRange(min = 0)] ) )
        
        setattr(dyna_asset, "response_timeout", IntegerField( "Response Timeout (ms)", [validators.NumberRange(min = 100)] ) )
        

        #MODBUS FIELDS
        setattr(dyna_asset, "tag_offset", IntegerField("Tag Offset", validators=[validators.optional(), validators.NumberRange(min=0)]))

    if existing_data:
        form = dyna_asset(prefix='device', formdata=existing_data)
    else:
        form = dyna_asset(prefix='device')
        
    if (virtual):
        form.virtual.data = True
        try:
            if (template == "Virtual_POA"):
                if (len(site_devices["Tracker_Simulator"]) > 0):
                    form.tracking_exists.data = True
                else:
                    form.tracking_exists.data = False
        except:
            form.tracking_exists.data = False
    else:
        form.virtual.data = False

    #Custom Wibotic Form
    if dev_type == "Wibotic":
        print(form.protocol)
        form.protocol.data = "WebSocket"
    return form

@bp_devices.route('/edit_device_partial/<dev_id>')
def edit_device_form_partial(dev_id):
    dev_info = get_device_info(dev_id)
    asset_parameters = get_json_lock("asset_parameters")
    v_sts = dev_info.get('virtual', False)

    form = get_device_form(dev_info.get('device_type'), v_sts, dev_info.get('daq_template'), dev_info.get("daq_name"))

    form.daq_name.data = dev_info.get("daq_name")
    form.sos_name.data = dev_info.get("sos_name")
    form.serial_number.data = dev_info.get("serial_number")
    form.device_type.data = dev_info.get('device_type')
    form.daq_template.data = dev_info.get('daq_template')
    form.manufacturer.data = dev_info.get('manufacturer')
    form.energy_system.data = dev_info.get('system')
    
    form.run_kpis.data = dev_info.get('run_kpis', True)
    
    if dev_info['daq_template'] == None:
        form.daq_template.data = "-"
    form.model.data = dev_info.get('model')
    form.monitored.data = dev_info.get('monitored')
    form.virtual.data = v_sts
    form.wiretapped.data = dev_info.get('wiretapped')

    if 'polling_interval' in dev_info:
        form.polling_interval.data = dev_info['polling_interval'] if dev_info['polling_interval'] else 5

    form.network_type.data = dev_info['network']['type']
  
    dev_info_params = dev_info['network']['params']
    
    if dev_info['network']['type'] == "TCP" and "ip" in form:    
        # if dev_info_params['protocol'] == "SNMP":
        form.version.data = dev_info_params.get('version', None)
        form.user_community.data = dev_info_params.get('usercommunity', None)
        
            # if form.version.data == "v3":
        form.auth_passphrase.data = dev_info_params.get('auth_passphrase', None)
        form.auth_type.data = dev_info_params.get('auth_type', None)
        form.encrypt_type.data = dev_info_params.get('encrypt_type', None)
        form.encrypt_passphrase.data = dev_info_params.get('encrypt_passphrase', None)
                
        # if dev_info_params['protocol'] == "DNP3":    
        form.max_connect_delay_ms.data = dev_info_params.get('max_connect_delay_ms', None)
        form.min_connect_delay_ms.data = dev_info_params.get('min_connect_delay_ms', None)
        dnp3_master = dev_info_params.get("master", {})
        form.response_timeout.data = dnp3_master.get('response_timeout_ms', 100)
        startup = dnp3_master.get("startup", {})
        
        # Loop?
        form.class_0_integrity.data = startup.get("integrity", {}).get("class_0", False) 
        form.class_1_integrity.data = startup.get("integrity", {}).get("class_1", False) 
        form.class_1_unsol.data = "disable" if startup.get("disable_unsol", {}).get("class_1", False) else "enable"
        form.class_2_integrity.data = startup.get("integrity", {}).get("class_2", False) 
        form.class_2_unsol.data = "disable" if startup.get("disable_unsol", {}).get("class_2", False) else "enable"
        form.class_3_integrity.data = startup.get("integrity", {}).get("class_3", False) 
        form.class_3_unsol.data = "disable" if startup.get("disable_unsol", {}).get("class_3", False) else "enable"
        
        form.client.data = dnp3_master.get("master_address", 0)
        form.outstation.data = dnp3_master.get("outstation_address", 0)
        
        for poll in dnp3_master.get("polls", {}):
            form.poll_intervals.append_entry( poll.get("period_ms", 0) )
            classes = poll.get("classes", {})
            t_list = tuple( [cls for cls, truth in classes.items() if truth] )
            form.poll_classes.append_entry( t_list )
        
            # dev_info_params['comm_id'] = 1
        # if dev_info_params['protocol'] == "ModbusTCP":
        form.comm_id.data = dev_info_params.get('comm_id', None)
        form.tag_offset.data = dev_info.get('daq_template_offset', 0)
        
        form.ip.data = dev_info_params.get('ip', None)
        form.port.data = dev_info_params.get('port', 512)
        form.protocol.data = dev_info_params.get('protocol', None)
        
    
    elif not ( ( dev_info.get('wiretapped', False ) in ( None, "None", "" ) ) ):
        form.comm_id.data = dev_info_params['comm_id']

    form.description.data = dev_info.get('description')

    for param in asset_parameters[dev_info['device_type']]:
        form[param].data = dev_info.get(param, None)

    form['form_type'].data = 'edit_device'

    if (v_sts):
        virtual_devices = get_json_lock("virtual_devices")

        for i in range(0, len(virtual_devices["devices"])):
            if (virtual_devices["devices"][i]["device"] == dev_info["daq_name"]):
                virtual_device = virtual_devices["devices"][i]

        if (dev_info['daq_template'] == "Virtual_Meter"):
            calculation_type = virtual_device["parameters"]["calculation"].capitalize()

            form.calculation_selector.data = calculation_type

            if (calculation_type == "Sum"):
                sources = []

                for source_device in virtual_device["parameters"]["source_devices"]:
                    sources.append(source_device["device"])
                form.sum_selector.data = sources

            elif (calculation_type == "Difference"):
                sources = []
                for source_device in virtual_device["parameters"]["source_devices"]:

                    sources.append(source_device["device"])

                form.diff_single_selector.data = sources[0]
                form.diff_multiple_selector.data = sources[1:]

        elif (dev_info['daq_template'] == "Virtual_POA"):
            form.poa_selector.data = virtual_device["parameters"]["source_devices"][0]["device"]

            form.tracking.data = f"{virtual_device['parameters']['tracking']}"

            form.dni_mult.data = virtual_device["parameters"]["setup-parameters"]["dni_mult"]
            form.dhi_mult.data = virtual_device["parameters"]["setup-parameters"]["dhi_mult"]
            if not(virtual_device["parameters"]["tracking"] == "True"):
                form.azimuth.data = virtual_device["parameters"]["setup-parameters"]["azimuth"]
                form.nt_tilt_angle.data = virtual_device["parameters"]["setup-parameters"]["tilt"]
            else:
                site_devices = get_json_lock("site_devices")
                try:
                    if (len(site_devices["Tracker_Simulator"]) > 0):
                        form.tracking_exists.data = True
                    else:
                        form.tracking_exists.data = False
                except:
                    form.tracking_exists.data = False

    return render_template("/devices/_edit_device_form.html", edit=True, form=form, device_params=asset_parameters[dev_info.get('device_type')])

@bp_devices.route('/new_device_partial/<device_type>/<device_template>')
def new_device_form_partial(device_type, device_template):
    # Populates a device edit modal based on information from a device template
    asset_parameters = get_json_lock("asset_parameters")
    device_templates = get_json_lock("device_templates")
    print('received request for new form of type: ' + device_type + " and template " + device_template)
    try:
        # The current requested new device is of an existing device template
        if device_templates[device_type] and device_template != "test":
            for i in device_templates[device_type]:
                if (i["template_id"] == device_template):
                    if (i["virtual"] == True):
                        form = get_device_form(device_type, True, i.get("daq_template"))
                        form.device_type.data = device_type
                        form.network_type.data = None
                        form.virtual.data = True

                    else:
                        form = get_device_form(device_type, False, None)

                        form.network_type.data = "TCP"
                        form.virtual.data = False
                        form.protocol.data = "ModbusTCP"
                    break

            #transfer device type, manufacturer, model, data temp, network, description
            #loop through asset params
            device_temps = get_json_lock("device_templates")
            for device_temp in device_temps[device_type]:
                if device_temp['template_id'] == device_template:
                    form.device_type.data = device_type
                    form.manufacturer.data = device_temp['manufacturer']
                    form.model.data = device_temp['model']
                    form.monitored.data = True
                    form.network_type.data = device_temp['network']['type']
                    form.energy_system.data = device_temp.get('system', 'PV')
                    
                    if not form.virtual.data:
                        device_network = device_temp['network']
                        device_network_params = device_network['params']
                        form.protocol.data = device_network_params['protocol']
                        form.ip.data = device_network_params.get('ip', "")
                        form.port.data = device_network_params.get('port', 502)
                        
                        # if device_network_params['protocol'] == 'ModbusTCP':
                        form.polling_interval.data = device_temp['polling_interval'] if "polling_interval" in device_temp else 5
                        form.tag_offset.data = device_temp.get('daq_template_offset', 0)    
                        form.comm_id.data = device_network_params.get('comm_id', 1)
                        
                        # elif (device_network_params['protocol'] == "SNMP"):
                        form.version.data =  device_network_params.get('version', "")
                        form.user_community.data = device_network_params.get('usercommunity', "")
                        
                        if (form.version.data == "v3"):
                            form.auth_passphrase.data = device_network_params.get('auth_passphrase', "")
                            form.auth_type.data = device_network_params.get('auth_type', "")
                            form.encrypt_type.data = device_network_params.get('encrypt_type', "")
                            form.encrypt_passphrase.data  = device_network_params.get('encrypt_passphrase', "")
                            
                    # elif (device_network_params['protocol'] == "DNP3"):
                        form.max_connect_delay_ms.data = device_network_params.get('max_connect_delay_ms', None)
                        form.min_connect_delay_ms.data = device_network_params.get('min_connect_delay_ms', None)
                        dnp3_master = device_network_params.get("master", {})
                        form.response_timeout.data = dnp3_master.get('response_timeout_ms', 1000)
                        startup = dnp3_master.get("startup", {})
                            
                            # Loop?
                        form.class_0_integrity.data = startup.get("integrity", {}).get("class_0", False) 
                        form.class_1_integrity.data = startup.get("integrity", {}).get("class_1", False) 
                        form.class_1_unsol.data = "disable" if startup.get("disable_unsol", {}).get("class_1", False) else "enable"
                        form.class_2_integrity.data = startup.get("integrity", {}).get("class_2", False) 
                        form.class_2_unsol.data = "disable" if startup.get("disable_unsol", {}).get("class_2", False) else "enable"
                        form.class_3_integrity.data = startup.get("integrity", {}).get("class_3", False) 
                        form.class_3_unsol.data = "disable" if startup.get("disable_unsol", {}).get("class_3", False) else "enable"
                        
                        form.client.data = dnp3_master.get("master_address", 0)
                        form.outstation.data = dnp3_master.get("outstation_address", 0)
                        
                        for poll in dnp3_master.get("polls", {}):
                            form.poll_intervals.append_entry( poll.get("period_ms", 0) )
                            classes = poll.get("classes", {})
                            t_list = tuple( [cls for cls, truth in classes.items() if truth] )
                            form.poll_classes.append_entry( t_list )
                        
                        
                    form.daq_template.data = device_temp['daq_template']
                    form.device_template.data = device_template
                    form.run_kpis.data = True
                    
                    if device_temp['daq_template'] == None:
                        form.daq_template.data = "-"

                    for param in asset_parameters[device_type]:
                        if param == 'aggregate':
                            form['aggregate'].data = True
                        else:
                            form[param].data = device_temp[param]

        else:
            # The current requested device doesn't belong to an existing template
            form = get_device_form(device_type, False, None)
            form.device_type.data = device_type
    
            # Default Parameters
            form.daq_template.data = "-"
            form.network_type.data = "TCP"
            form.virtual.data = False
            form.protocol.data = "ModbusTCP"
            form.monitored.data = True
            form.device_type.data = device_type
            form.energy_system.data = "PV"
            form.polling_interval.data = 1
            form.manufacturer.data = ''
            form.model.data = ''
            form.run_kpis.data = False
            form.description.data = ""
            form.serial_number.data = ""
            form.sos_name.data = ""
            
            form.version.data = "v2"
            form.user_community.data = ""
            form.auth_passphrase.data = ""
            form.auth_type.data = ""
            form.encrypt_type.data = ""
            form.encrypt_passphrase.data = ""
            form.max_connect_delay_ms.data = 1000
            form.min_connect_delay_ms.data = 1000
            
            form.response_timeout.data =  100
            
            # Loop?
            form.class_0_integrity.data = False
            form.class_1_integrity.data = False
            form.class_1_unsol.data = "disable"
            form.class_2_integrity.data = False
            form.class_2_unsol.data = "disable"
            form.class_3_integrity.data = False
            form.class_3_unsol.data = "disable"
            
            form.client.data = 0
            form.outstation.data = 0
            
            form.comm_id.data = 1
            form.tag_offset.data = 0
                    
            form.ip.data = ""
            form.port.data = 502
                    

        if device_type == "Wibotic":
            form.protocol.data = "WebSocket"
            form.port.data = 80
    
    except Exception as e:
        print(e)
        form = get_device_form(device_type, False, None)
    return render_template("/devices/_edit_device_form.html", edit=False, form=form, device_params = asset_parameters[device_type] )

@bp_devices.route('/clone_device_partial/<dev_id>')
def clone_device_form_partial(dev_id):
    dev_info = get_device_info(dev_id)
    protocol = dev_info.get("network", {}).get("params", {}).get("protocol", "ModbusTCP")
    
    clone_info = get_clone_form_by_protocol(protocol)
    clone_info.cloneDevice.data = dev_info.get("sos_name")
    clone_info.daq_name.data = dev_info.get("daq_name")

    parent_id = dev_info["parent"]["elec"]
    
    if not (dev_info["parent"]["elec"] == True):
        parent_info = get_device_info(parent_id)
        clone_info.clonesParentDevice.data = parent_info.get("sos_name")

    return render_template("/devices/_clone_device_form.html", clone_info=clone_info, protocol=protocol)


@bp_devices.route('/configure_device_partial/<dev_id>')
def configure_device_form_partial(dev_id):
    """ Returns a form to be rendered for configuring a virutal device.

    Args:
        dev_id (str): DAQ unique device identifier

    Returns:
        render_template: Rendered jinja template
    """
    dev_info = get_device_info(dev_id)
    asset_parameters = get_json_lock("asset_parameters")
    dev_virtual_sts = dev_info.get("virtual", False)
    
    form = get_device_form(dev_info.get('device_type'), dev_virtual_sts, dev_info.get('daq_template'), dev_info.get("daq_name"))

    form.daq_name.data = dev_info.get("daq_name")
    form.sos_name.data = dev_info.get("sos_name")
    form.serial_number.data = dev_info.get("serial_number")
    form.device_type.data = dev_info.get('device_type')
    form.daq_template.data = dev_info.get('daq_template')
    form.manufacturer.data = dev_info.get('manufacturer')
    form.energy_system.data = dev_info.get('system')
    form.run_kpis.data = dev_info.get('run_kpis', True)
    
    if not dev_virtual_sts:
        form.tag_offset.data = dev_info.get('daq_template_offset', 0)

    if dev_info['daq_template'] == None:
        form.daq_template.data = "-"
        
    form.model.data = dev_info.get('model')
    form.monitored.data = dev_info.get('monitored')

    form.virtual.data = dev_virtual_sts

    if 'polling_interval' in dev_info:
        form.polling_interval.data = dev_info['polling_interval'] if dev_info['polling_interval'] else 5

    form.network_type.data = dev_info['network']['type']

    if dev_info['network']['type'] == "TCP":
        form.ip.data = dev_info['network']['params']['ip']
        form.port.data = dev_info['network']['params']['port']
        form.comm_id.data = dev_info['network']['params']['comm_id']
        form.protocol.data = dev_info['network']['params']['protocol']
    
    elif not ( dev_info.get('wiretapped', False) in ( None, "None", "" ) ):
        form.comm_id.data = dev_info['network']['params']['comm_id']

    form.description.data = dev_info.get('description')

    for param in asset_parameters[dev_info['device_type']]:
        form[param].data = dev_info[param]

    form['form_type'].data = 'edit_device'

    if (dev_info['virtual']):

        virtual_devices = get_json_lock("virtual_devices")

        for i in range(0, len(virtual_devices["devices"])):

            if (virtual_devices["devices"][i]["device"] == dev_info["daq_name"]):

                virtual_device = virtual_devices["devices"][i]

        if (dev_info['daq_template'] == "Virtual_Meter"):

            calculation_type = virtual_device["parameters"]["calculation"].capitalize()

            form.calculation_selector.data = calculation_type

            if (calculation_type == "Sum"):

                sources = []

                for source_device in virtual_device["parameters"]["source_devices"]:

                    sources.append(source_device["device"])

                form.sum_selector.data = sources

            elif (calculation_type == "Difference"):

                sources = []

                for source_device in virtual_device["parameters"]["source_devices"]:

                    sources.append(source_device["device"])

                form.diff_single_selector.data = sources[0]
                form.diff_multiple_selector.data = sources[1:]

        elif (dev_info['daq_template'] == "Virtual_POA"):

            form.poa_selector.data = virtual_device["parameters"]["source_devices"][0]["device"]

            form.tracking.data = f"{virtual_device['parameters']['tracking']}"

            form.dni_mult.data = virtual_device["parameters"]["setup-parameters"]["dni_mult"]
            form.dhi_mult.data = virtual_device["parameters"]["setup-parameters"]["dhi_mult"]

            if not(virtual_device["parameters"]["tracking"] == "True"):

                form.azimuth.data = virtual_device["parameters"]["setup-parameters"]["azimuth"]
                form.nt_tilt_angle.data = virtual_device["parameters"]["setup-parameters"]["tilt"]

            else:

                site_devices = get_json_lock("site_devices")

                try:

                    if (len(site_devices["Tracker_Simulator"]) > 0):

                        form.tracking_exists.data = True

                    else:

                        form.tracking_exists.data = False

                except:

                    form.tracking_exists.data = False

    return render_template("/devices/_configure_virtual_device_partial.html", form=form, device_params=asset_parameters[dev_info.get('device_type')])

""" END DEVICES TREE OPERATION FUNCTIONALITY """

 
@bp_devices.route('/device_info_partial/<daq_name>')
def device_info_partial(daq_name):
    device_info = get_device_info(daq_name)
    portableReq = request.args.get('portable')
    portable = True if portableReq == "True" else False

    return render_template('/devices/device_info_partial.html', device_info=device_info, portable=portable)

@bp_devices.route('/device_info_partial_settings/<daq_name>')
def device_info_partial_settings(daq_name):
    device_info = get_device_info(daq_name)
    asset_parameters = get_json_lock("asset_parameters")
    portableReq = request.args.get('portable')
    portable = True if portableReq == "True" else False
    device_params = asset_parameters[device_info['device_type']]
    #time.sleep(3)
    return render_template('/devices/_device_info_partial_settings.html', device_info=device_info, device_params=device_params, portable=portable)

@bp_devices.route('/device_info_partial_status_data/<daq_name>')
def device_info_partial_status_data(daq_name):
    device_info = get_device_info(daq_name)
    #time.sleep(3)
    return render_template('/devices/_device_info_partial_status_data.html', device_info=device_info, iconography=iconography)

@bp_devices.route('/device_info_partial_decode_popover/<daq_name>/<measure>', methods = ['GET', 'POST'])
def device_info_partial_decode_popover(daq_name, measure):
    device_info = get_device_info(daq_name)
    #get value of measure from DB
    moddbconn = sqlite3.connect('/opt/moddata.db')
    modcurs = moddbconn.cursor()
    modcurs.execute('SELECT measure_value, last_updated FROM modvalues WHERE device = ? AND measure_name = ?', (daq_name, measure))
    results = modcurs.fetchall()

    value = int(results[0][0])

    #open sos_templates, find that measure in device's daq_template
    sos_templates = get_json_lock('sos_templates')
    measure_info = sos_templates[device_info['device_type']][device_info['daq_template']][measure]

    if 'decoding' in measure_info:

        #Table with only active enum option
        if measure_info['source_unit'] == "enum":
            return_html = "<table class='table table-sm' style='font-size: 12px;'><tbody>"
            for enum_value in measure_info['decoding']:
                if int(enum_value) == value:
                    return_html += "<tr><td><strong>Value</strong></td><td>" + str(enum_value) + "</td></tr>"
                    return_html += "<tr><td><strong>Message</strong></td><td>" + measure_info['decoding'][enum_value]['message'] + "</td></tr>"
                    if measure_info['decoding'][enum_value]['alarm']:
                        return_html += "<tr><td><strong>Alarm</strong></td><td style='color: red;'>Yes</td></tr>"
                    else:
                        return_html += "<tr><td><strong>Alarm</strong></td><td>No</td></tr>"
                    return_html += "<tr><td><strong>Description</strong></td><td>" + measure_info['decoding'][enum_value]['description'] + "</td></tr>"
            return_html += ("</tbody></table>")
        elif measure_info['source_unit'] == "bitpacked":
            return_html = "<table class='table table-sm' style='font-size: 12px;'><tbody><tr><td>Active Bits</td><td>Message</td><td>Alarm</td><td>Description</td></tr>"
            #determine which bits of value active
            #loop through with & 32 tiems?
            if "source_value_type" in measure_info and measure_info["source_value_type"] == "hexadecimal":
                # If we save the value as hexadecimal, convert it to base 10 before decogin
                value = int(str(value), 16) 
            for bit in measure_info['decoding']:
                if ((value & (2 ** int(bit))) != 0):
                    return_html += "<tr><td>" + bit + "</td>"
                    return_html += "<td><strong>" + measure_info['decoding'][bit]['message'] + "</strong></td>"
                    if measure_info['decoding'][bit]['alarm']:
                        return_html += "<td style='color:red'>Yes</td>"
                    else:
                        return_html += "<td>No</td>"
                    return_html += "<td>" + measure_info['decoding'][bit]['description'] + "</td></tr>"
                # else: #don't show anything if bit not active?
    else:

        return_html = "Decoding Not Available"

    #handle enum (one match) or bitpacked (multiple)

    moddbconn.close()
    return return_html

@bp_devices.route('/device_info_table/<req_type>/<daq_name>')
def device_info_table(req_type, daq_name):
    asset_parameters = get_json_lock("asset_parameters")

    if req_type == 'device':

        device_info = get_device_info(daq_name)
        device_params = asset_parameters[device_info['device_type']]
        return render_template('/devices/device_info_table.html', device_info=device_info, device_params=device_params)

    elif req_type == 'template':
        #print('template request called for ' + daq_name)
        device_info = get_device_template_info(daq_name)
        device_params = asset_parameters[device_info['device_type']]
        return render_template('/devices/device_info_table.html', device_info=device_info, device_params=device_params)