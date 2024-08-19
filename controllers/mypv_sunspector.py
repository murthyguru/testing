
from typing import Union, Dict, List, Tuple

from copy import deepcopy
import datetime
import dateutil.parser
from flask import abort, Blueprint, render_template, request, jsonify
import json
import os
import pytz
import subprocess
import sqlite3
import time


from controllers.helpers import iconography, get_device_info, make_compressed_response

from helpers.common import get_json_lock, printd

#from app import check_perm, roles, send_from_directory


bp_sunspector = Blueprint('bp_sunspector', __name__)


# directories in '/static' to find the most recent file last modified time from
file_lmt_dirs = ['js/sunspector', 'css/sunspector', 'myPV-Style-Reference']


def static_dir_last_updated(dir_abs_path:str="") -> str:
    """
    Finds the most recent last modified time of all the files in a given
    directory, if `dir_abs_path` is not falsey, otherwise finds the most recent
    last modified time of all the files in the directories specified in
    the global list variable `file_lmt_dirs`.

    This function is used by routes so that scripts in their rendered templates
    can implement cache busting.
    """

    if dir_abs_path:
        return str(max(os.path.getmtime(os.path.join(root_path, f))
                       for root_path, dirs, files in os.walk(dir_abs_path)
                       for f in files))

    file_lmts = []

    # search through file_lmt_dirs if dir_abs_path is not specified
    for dir in file_lmt_dirs:
        for rp, dirs, files in os.walk(os.path.join('/opt/flask_app/static', dir)):
            for f in files:
                file_lmts.append(os.path.getmtime(os.path.join(rp, f)))
    
    # return the most recent last modified time as a str
    return str(max(file_lmts))


@bp_sunspector.route('/sunspector', methods=['GET', 'POST'])
def sunspector_dashboard():

    # allows clicking myPV IQ link to go back to the dashboard page if viewing
    # the sunspector remotely, otherwise the link just points to this route
    remote = True if request.args.get('remote') is not None else False

    template = render_template('/sunspector/sunspector_dashboard.html', remote_access=remote, last_update=static_dir_last_updated())
    return make_compressed_response(template)


@bp_sunspector.route('/sunspector_partial/<target>', methods=['GET', 'POST'])
def sunspector_page(target):

    if target in ['irradiance', 'temperature', 'wind']:
        return sunspector_graph(target)

    # only implemented partial as of 2022-05-19
    if target == 'sensors':
        return sunspector_sensors()

    if 'settings' in target:
        return sunspector_settings(target)

    abort(404)


def sunspector_sensors():
    template = render_template('/sunspector/_sunspector_sensors.html', last_update=static_dir_last_updated())
    return make_compressed_response(template)


@bp_sunspector.route('/sunspector/hmi_tiles', methods=['GET'])
def hmi_tiles():
    """
    ### Structure of `hmi_tiles.json`:
    ```
    {
        "kpis": [
            {
                "title": "Expected Energy",
                "devices": {
                    "Project": {
                        "measures": [
                            ["PVGenerationExpectedTOTAL", "kWh"]
                        ],
                        "series_last": [],
                        "properties": []
                    }
                },
                ...
            }
        ],
        "sensors": [
            {
                "dev_daq": "DEV_35",
                "measures": ["irradiance_poa"]
            },
            ...
        ]
    }
    ```

    ### Returned `json` structure:
    -
    ```
    {
        "kpis": [
            {
                "title": "Expected Energy",
                "devices": {
                    "Project": {
                        "measures": [
                            ["PVGenerationExpectedTOTAL", "kWh"]
                        ],
                        "series_last": [],
                        "properties": []
                    }
                }
            },
            ...
        ],
        "sensors": [
            {
                "dev_daq": "DEV_35",
                "title": "POA",
                "dev_name": "Hukseflux SR30"
                "measures": ["irradiance_poa"]
                "measure_names": ["Plane Of Array Irradiance"]
            },
            ...
        ],
        "plant_config": plant_config.json
    }
    ```
    """
    ht = get_json_lock('hmi_tiles')
    

    sensor_tiles = ht.get('sensors', [])
    if len(sensor_tiles):
        sd = get_json_lock('site_devices')
        am = get_json_lock('asset_measures')

        # get dict of all devices in site_devices, with daq_names as keys
        all_devices = { dev['daq_name']: dev for devs in sd.values() for dev in devs }
        # build sensor tiles
        for tile in sensor_tiles:

            try:
                device = all_devices[tile['dev_daq']]
                print(device)
                title = device.get('sos_name', '')
                manufacturer = device.get('manufacturer', '')
                model = device.get('model', '')

                tile['title'] = title
                tile['dev_name'] = f"{manufacturer} {model}"

                measure_names = []
                for measure in tile.get('measures', []):
                    measure_names.append(am[device['device_type']][measure]['name'])

                tile['measure_names'] = measure_names
            except Exception as e:
                print(e)
        

    kpi_tiles = ht.get('kpis', [])
    ht['kpis'] = kpi_tiles
    ht['sensors'] = sensor_tiles
    
    # # sort the tiles in each tile type by title
    # for tile_list in sensor_tiles:
    #     tile_list.sort(key=lambda x: x['title'])

    # add plant_config to ht for expected power calculation
    ht['plant_config'] = get_json_lock('plant_config')

    return make_compressed_response(ht, mimetype='application/json')


def sunspector_graph(target):
    template = render_template('/sunspector/_sunspector_sensor_trend.html', sensor_type=target)
    return make_compressed_response(template)


def sunspector_settings(target):
    if target == 'settings':
        template = render_template('/sunspector/_sunspector_settings.html')
        return make_compressed_response(template)

    elif 'network' in target:
        template = render_template('/sunspector/_sunspector_settings_network.html')
        return make_compressed_response(template)



################################################################################
#  DEVICE INFO PARTIAL QUICK FIX
################################################################################

@bp_sunspector.route('/sunspector/device_info_partial/<daq_name>')
def device_info_partial(daq_name):
    portable = True if request.args.get('portable') == 'True' else False

    template = render_template('/sunspector/device_info/device_info_partial.html', device_info=get_device_info(daq_name), portable=portable)
    return make_compressed_response(template)


@bp_sunspector.route('/sunspector/device_info_partial_settings/<daq_name>')
def device_info_partial_settings(daq_name):
    device_info = get_device_info(daq_name)
    asset_parameters = get_json_lock("asset_parameters")
    portable = True if request.args.get('portable') == 'True' else False

    device_params = asset_parameters[device_info['device_type']]

    template = render_template('/sunspector/device_info/_device_info_partial_settings.html', device_info=device_info, device_params=device_params, portable=portable)
    return make_compressed_response(template)


@bp_sunspector.route('/sunspector/device_info_partial_status_data/<daq_name>')
def device_info_partial_status_data(daq_name):
    template = render_template('/sunspector/device_info/_device_info_partial_status_data.html', device_info=get_device_info(daq_name), iconography=iconography)
    return make_compressed_response(template)



@bp_sunspector.route('/sunspector/get_device_daq_measures', methods=['GET', 'POST'])
def get_device_daq_measures():
    daq_name = request.form['daq_name']
    dev_info = get_device_info(daq_name)

    daq_template_name = dev_info['daq_template']
    sos_templates = get_json_lock("sos_templates")
    daq_template = sos_templates[dev_info['device_type']][daq_template_name]

    return_template = []
    for measure, definition in daq_template.items():
        return_template.append({
                'measure': measure,
                'unit': definition['source_unit']
            })

    return make_compressed_response(return_template, mimetype='application/json')


@bp_sunspector.route('/sunspector/pingdevice', methods=['POST'])
def pingdevice():
    dev_daq = request.form['device']
    device = [ dev for devs in get_json_lock('site_devices').values() for dev in devs if dev['daq_name'] == dev_daq ]

    if len(device) < 1:
        return make_compressed_response(f"No device found with daq_name '{dev_daq}'")
    else:
        device = device[0]

    if device['network']['type'] == "TCP":
        process = subprocess.run(['ping', '-c', '3', device['network']['params']['ip']], encoding='utf-8', stdout=subprocess.PIPE)
        printd(f"route '/sunspector/pingdevice': {dev_daq} ping stdout\n{process.stdout}")
        
        return make_compressed_response(process.stdout)

    return make_compressed_response("Can't ping this type of device.")


################################################################################
#  END DEVICE INFO PARTIAL QUICK FIX
################################################################################


@bp_sunspector.route('/sunspector/ajax_measures', methods = ['GET', 'POST'])
def get_ajax_measures():
    requestdata = json.loads(request.form['data'])
    results = {}

    # specifies number of seconds after which data should be nulled
    # generate timestamp now - that number of seconds
    # if timestamp of value is less than that, its expired
    dnow = datetime.datetime.now()
    dlimit = None
    if 'expired_seconds' in requestdata:
        dlimit = (dnow - datetime.timedelta(seconds=requestdata.pop('expired_seconds'))).isoformat()

    no_result = { 'value': None, 'unit': None, 'time': dnow.isoformat() }

    measure_data_dbconn = sqlite3.connect('/opt/moddata.db', timeout=10)
    measure_db_cursor = measure_data_dbconn.cursor()
    
    for device in requestdata:
        results[device] = {}
        for measure in requestdata[device]:
            measure_db_cursor.execute('SELECT measure_value, destination_unit, last_updated FROM modvalues WHERE device = ? AND measure_name = ?', (device, measure))
            dbreturn = measure_db_cursor.fetchall()
            result = {}
            if len(dbreturn) > 0:
                result = {
                    'value': dbreturn[0][0],
                    'unit': dbreturn[0][1],
                    'time': dbreturn[0][2]
                }
                # check if timestamp is older than limit
                if dlimit and result['time'] < dlimit:
                    result['value'] = None
            else:
                result = no_result
            
            results[device][measure] = result

    measure_db_cursor.close()
    measure_data_dbconn.close()

    return make_compressed_response(results, 'application/json')


@bp_sunspector.route('/sunspector/get_all_measures_by_device', methods = ['GET', 'POST'])
def get_all_measures_by_device():
    daq_name = request.form['daq_name']
    printd(f"route '/sunspector/get_all_measures_by_device': {daq_name} - {datetime.datetime.utcnow().isoformat()}")
    
    return_results = []
    
    measure_data_dbconn = sqlite3.connect('/opt/moddata.db', timeout=10)
    modcurs = measure_data_dbconn.cursor()

    modcurs.execute('SELECT * from modvalues WHERE device = ?', (daq_name,))
    results = modcurs.fetchall()

    modcurs.close()
    measure_data_dbconn.close()

    for result in results:
        return_results.append({
            'measure_value': result[5],
            'timestamp_utc': result[8],
            'measure': result[4],
            'unit': result[7]
        })

    return make_compressed_response(return_results, mimetype='application/json')


@bp_sunspector.route('/sunspector/getkpis', methods=['GET', 'POST'])
def getkpis():
    # read data sent by post
    request_data = json.loads(request.form['data'])

    req_devs = request_data.get('devices')
    if not isinstance(req_devs, dict) or not len(req_devs):
        kpi_data = {'answer': {}}

    else:
        kpi_request = {
            'day': datetime.datetime.now().date().isoformat(),
            'IncludeTseries': False,
            'timezone': "local",
            'devices': req_devs
        }

        kpi_data = getkpis_day(kpi_request)
        if not kpi_data.get('answer'):
            kpi_data['answer'] = {}


    kpi_data['devices'] = clean_kpi_data(req_devs, kpi_data['answer'].get('Devices'))
    return make_compressed_response(kpi_data['devices'], mimetype='application/json')


def clean_kpi_data(req_devs:Dict[str, Dict[str, List[str]]], kpi_devs:Dict[str, Dict[str, Union[str, int, float, bool]]]) -> Dict[str, Dict[str, Union[str, int, float, bool]]]:
    if not kpi_devs:
        kpi_devs = {}

    for dev, dev_cats in req_devs.items():
        if dev not in kpi_devs:
            # create empty dictionary for missing kpis
            kpi_devs[dev] = {}

        for cat, cat_list in dev_cats.items():
            for entry in cat_list:
                if cat == 'series_last':
                    # remove trailing '_last' from kpi name
                    if f"{entry}_last" in kpi_devs[dev]:
                        kpi_devs[dev][entry] = kpi_devs[dev][f"{entry}_last"]
                        kpi_devs[dev].pop(f"{entry}_last")
                    else:
                        # add missing kpis with '-'
                        kpi_devs[dev][entry] = '-'
                    
                elif entry not in kpi_devs[dev]:
                    # add missing kpis with '-'
                    kpi_devs[dev][entry] = '-'
        
    return kpi_devs


def getkpis_day(kpis_request:Dict[str, Union[str, bool, Dict[str, Dict[str, List[str]]]]]) -> Dict[str, Dict[str, Dict[str, Union[str, int, float, bool]]]]:
    if not kpis_request:
        return {"answer": {}}

    # get timezone for local time conversions
    plant_config = get_json_lock("plant_config")
    proj_timezone = plant_config["timezone"]

    # open site devices if query asks for properties
    site_devices = None

    include_tseries = True if kpis_request.get('IncludeTseries') == True else False

    # process ALL prefix
    kpi_request_devs = kpis_request.get('devices', {})
    new_devices_map = {}
    for device, dev_map in kpi_request_devs.items():
        if device[:3] == 'ALL':
            # make deep copy of map for each one, add to 'devices'
            copy_map = deepcopy(dev_map)

            device_type = device[3:]

            # lazy load site_devices.json
            if not site_devices:
                site_devices = get_json_lock("site_devices")

            for site_dev in site_devices[device_type]:
                new_devices_map[site_dev['daq_name']] = copy_map

        else:
            new_devices_map[device] = kpi_request_devs[device]

    kpis_request['devices'] = new_devices_map

    kpisdevices = kpis_request['devices']
    kpisday = kpis_request.get('day')

    if kpisday != None:
        dayd = dateutil.parser.parse(kpisday)

        # go to that folder in sos_data, load the kpis file
        path_name = '/sos_data/' + str(dayd.year) + "/" + ('%02d' % dayd.month) + "/" + ('%02d' % dayd.day) + "/"
        file_name = path_name + str(dayd.year) + "_" + ('%02d' % dayd.month) + "_" + ('%02d' % dayd.day) + "_kpis.json"

        # check if file exists - if not then return nothing? 
        if not os.path.isfile(file_name) or (os.stat(file_name).st_size == 0):
            printd(f"route: '/sunspector/getkpis' -- not a file or empty file: '{file_name}'")
            return {"answer": {}}

        try: 
            kpis_file = get_json_lock(file_name, False)
        except:
            printd(f"route: '/sunspector/getkpis' -- bad json file: '{file_name}'")
            return {"answer": {}}


    # setup blank starter maps, arrays
    responsedata = {}
    responsedata['Devices'] = {}
    shortdata = {}
    shortdata['Devices'] = {}
    allshorttimes = []

    # if returning timeseries, build array of every minute from sun rise to set
    if include_tseries:
        # get timestamps from kpis['Variables']['TimeSeries']
        if kpis_request['timezone'] == 'utc':
            timestamps = get_time_stretch(kpis_file['Variables']['SunriseTime'], kpis_file['Variables']['SunsetTime'])
            utc_timestamps = timestamps
            allshorttimes = kpis_file['Variables']['TimeSeries']
        # if local and sunset time spans to following day, will have to open
        # multiple files ...
        elif kpis_request['timezone'] == 'local':
            sunrise_local = dateutil.parser.parse(kpis_file['Variables']['SunriseTime']).astimezone(pytz.timezone(proj_timezone)).isoformat()
            sunset_local = dateutil.parser.parse(kpis_file['Variables']['SunsetTime']).astimezone(pytz.timezone(proj_timezone)).isoformat()
            timestamps = get_time_stretch(sunrise_local, sunset_local)
            utc_timestamps = get_time_stretch(kpis_file['Variables']['SunriseTime'], kpis_file['Variables']['SunsetTime'])
            
            allshorttimes = kpis_file['Variables']['TimeSeries']

        timestamps = timestamps[0::kpis_request['Tseriesres']]
        utc_timestamps = utc_timestamps[0::kpis_request['Tseriesres']]
        responsedata['TimeSeries'] = timestamps


    for device in kpisdevices:
        responsedata['Devices'][device] = {}
        datamapseries = {}
        datamapmeasures = {}

        # copy device KPI singles into responsedata
        if (('measures' in kpisdevices[device]) and (not (len(kpisdevices[device]['measures']) == 0))):           
            for measure in kpisdevices[device]['measures']:
                if '.' in measure:
                    group, submeasure = measure.split('.')
                    if ((device == 'Project') or (device == 'Variables')): 
                        datavalue = kpis_file[device][group][submeasure]
                    else:
                        datavalue = kpis_file['Devices'][device][group][submeasure]
                else:
                    if ((device == 'Project') or (device == 'Variables')):
                        if measure in kpis_file[device]: 
                            datavalue = kpis_file[device][measure]
                        else:
                            datavalue = None
                    else:
                        if device in kpis_file['Devices'] and measure in kpis_file['Devices'][device]:
                            datavalue = kpis_file['Devices'][device][measure]
                        else:
                            datavalue = None
                datamapmeasures[measure] = datavalue
            responsedata['Devices'][device] = datamapmeasures

        # copy device properties into responsedata
        if (('properties' in kpisdevices[device]) and (not (len(kpisdevices[device]['properties']) == 0))):
            for aproperty in kpisdevices[device]['properties']:
                if device == 'Project':
                    datavalue = plant_config[aproperty]
                else:
                    # lazy load site_devices.json
                    if not site_devices:
                        site_devices = get_json_lock("site_devices")

                    for devicetype in site_devices:
                        for adevice in site_devices[devicetype]:
                            if adevice['daq_name'] == device:
                                datavalue = adevice[aproperty]
                                break
                        else:
                            # only executed if the inner loop did NOT break
                            continue

                        # only executed if the inner loop DID break
                        break

                responsedata['Devices'][device][aproperty] = datavalue

        # no-op if kpisdevices[device] doesn't have a 'series_last' key
        for series in kpisdevices[device].get('series_last', []):
            if '.' in series:
                group, submeasure = series.split('.')
                if device == 'Project':
                    dataarray = kpis_file[device][group][submeasure][-1]
                else:
                    dataarray = kpis_file['Devices'][device][group][submeasure][-1]
            else:
                if device == 'Project':
                    dataarray = kpis_file[device][series][-1]
                else:
                    dataarray = kpis_file['Devices'][device][series][-1]

            responsedata['Devices'][device][f"{series}_last"] = dataarray

        # copy device series into shortData and start arrays in responsedata
        if include_tseries:
            if (not (len(kpisdevices[device]['series']) == 0)):
                for series in kpisdevices[device]['series']:
                    if '.' in series:
                        group, submeasure = series.split('.')
                        if device == 'Project':
                            dataarray = kpis_file[device][group][submeasure]
                        else:
                            try:
                                dataarray = kpis_file['Devices'][device][group][submeasure]
                            except KeyError:
                                dataarray = [None] * len(allshorttimes)
                    else:
                        if device == 'Project':
                            dataarray = kpis_file[device][series]
                        else:
                            dataarray = kpis_file['Devices'][device][series]

                    datamapseries[series] = dataarray
                    responsedata['Devices'][device][series] = []

                shortdata['Devices'][device] = {}
                shortdata['Devices'][device] = datamapseries


    # loop through device, plug in nulls where series doesn't have timestamps
    if include_tseries:
        for device in kpisdevices:
            if (not (len(kpisdevices[device]['series']) == 0)):
                for ctime in utc_timestamps:
                    if ctime in allshorttimes:
                        theindex = allshorttimes.index(ctime)
                        for series in kpisdevices[device]['series']:
                            responsedata['Devices'][device][series].append(shortdata['Devices'][device][series][theindex])
                    else:
                        for series in kpisdevices[device]['series']:
                            responsedata['Devices'][device][series].append(None)

    return {"answer": responsedata}


def get_time_stretch(start_time, end_time):
    start_d = dateutil.parser.parse(start_time).replace(second=0, microsecond=0)
    end_d = dateutil.parser.parse(end_time).replace(second=0, microsecond=0)
    times_array = []
    while start_d != (end_d + datetime.timedelta(minutes=1)):
        times_array.append(start_d.isoformat())
        start_d = start_d + datetime.timedelta(minutes=1)
    return times_array





# @bp_sunspector.route('/sunspector/js/<string:target>', methods=['GET'])
# def js(target):
#     return make_no_cache_response(send_from_directory(f"static/js/sunspector", target))
# 
# 
# @bp_sunspector.route('/sunspector/css/<string:target>', methods=['GET'])
# def css(target):
#     return make_no_cache_response(send_from_directory(f"static/css/sunspector", target))
# 
#
# def make_no_cache_response(response):
#     # HTTP 1.1.
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Pragma"] = "no-cache"  # HTTP 1.0.
#     response.headers["Expires"] = "0"  # Proxies.
# 
#     return response