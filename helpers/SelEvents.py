import os
import datetime
from itertools import accumulate, groupby
from pyexpat import model
import re
import telnetlib

from helpers.common import extractZip, printd, compress
try:
    from . import pycev_mod as pycev
except:
    import pycev_mod as pycev
import time
import json
import re
from ftplib import FTP
try:
    from . import comtrade as com
except:
    import comtrade as com


def send_command_tn(tn, command):
    command = command.encode('ascii') + b"\r\n\x02"
    tn.write(command)
    response = tn.read_until(b"\x03")[:-1]

    if response[:len(command)] == command:
        response = response[len(command):]

    prompt_symbol = tn.read_until(b"\x03")[3:-1]
    return response, prompt_symbol


def login_tn(tn, device_code, level=1, password="OTTER"):
    """Log into a existing telnet session at the desired privilege level."""
    if level == 1:
        command = "ACC"
    elif level == 2:
        command = "2AC"
    else:
        Exception("Invalid Command")

    # Write login command to the telnet session
    command_bytes = command.encode('ascii') + b"\r\n\x02"
    tn.write(command_bytes)

    # Wait until being prompted to enter password
    if device_code == '735':
        password_prompt = b"\r\n\x02\r\nPassword: ?"
    else:
        password_prompt = b"\r\n\x02Password: ?"
    response = tn.read_until(password_prompt)

    # Write password to telnet, \x03 means "end of message"
    tn.write(password.encode('ascii') + b"\r\n\x03")

    # Relay will send asterisks back
    response = tn.read_until(b"\x03")[len(password)+5:-1]

    # Read prompt symbol
    prompt_symbol = (tn.read_until(b"\x03")[3:-1])
    # The prompt symbol determines what level the client is logged into >, => or =>>
    if ((command == "ACC" and prompt_symbol != b"=>") or
            (command == "2AC" and prompt_symbol != b"=>>")):
        raise Exception("Login FAIL")


class SelEvents:
    def __init__(self, ip, daq='', model='751' ,telnet_port=23, pass_1="OTTER", pass_2="TAIL"):
        self.ip = ip
        self.telnet_port = telnet_port
        self.pass_1 = pass_1
        self.pass_2 = pass_2
        self.model =model
        self.daq = daq

    def get_history_simple(self, start=None, end=None):
        """Return list of dictionaries with basic information"""
        # Parse each event and append to list
        events = []
        # Create new telnet session and wait to be prompted, SEL model is 651, 751, 751a, or 735
        if not (self.model == '851' or self.model == 851):
            
            try:
                self.tn = telnetlib.Telnet(self.ip, port=self.telnet_port,timeout=1)
            except BaseException as e:
                print(e)
                raise e
            #print('done')
            if self.model == '751':
                self.tn.read_until(b"\x03")
            elif self.model == '751A' or self.model == '751a':
                self.tn.read_eager()
            else:
                self.tn.read_some()

            # print('read until')
            # Log into session
            try:
                login_tn(self.tn, device_code=self.model,password=self.pass_1)
                # print('logged in')
            except Exception as e:
                print(e)
            # print('logged in')

            # Send CHistory command and clean up response
            
            history = send_command_tn(self.tn, "CHIST")[0].decode().strip().split('\r\n')

            # Extract Header
            header = history[2]

            #print(header)
            if len(history) >= 3:
                for line in history[3:]:
                    if line:
                        line = line.replace('"', "").split(',')
                        #print(line)
                        if self.model == '751':
                            # Padding zeroes for month and day values which will be set for uid
                            events.append({
                                "#": line[0],
                                "REF": line[1],
                                "DATE": "{}/{}/{}".format(line[4], line[2], line[3]),
                                "TIME": "{}:{}:{}.{}".format(*line[5:10]),
                                "EVENT": line[9],
                                "LOCAT": line[10],
                                "CURRENT": line[11],
                                "FREQ": line[12],
                                "TARGETS": line[13],
                                "UID": ''.join([line[4], line[2].zfill(2), line[3].zfill(2), *line[5:9]])
                            })
                        elif self.model == '751A' or self.model == '751a':
                            events.append({
                                "#": line[0],
                                "REF": ''.join([line[3], line[1], line[2], *line[4:8]]),
                                "DATE": "{}/{}/{}".format(line[3], line[1], line[2]),
                                "TIME": "{}:{}:{}.{}".format(*line[4:8]),
                                "EVENT": line[8],
                                "CURRENT": line[9],
                                "FREQ": line[10],
                                "TARGETS": line[11],
                                "1610": line[12],
                                "UID": ''.join([line[3], line[1].zfill(2), line[2].zfill(2), *line[4:8]])
                            })
                        elif self.model == '651' or self.model == '651_R2':
                            events.append({
                                "#": line[0],
                                "REF": ''.join([line[3], line[1], line[2], *line[4:8]]),
                                "DATE":  "{}/{}/{}".format(line[3], line[1], line[2]),
                                "TIME": "{}:{}:{}.{}".format(*line[4:8]),
                                "EVENT": line[8],
                                "LOCAT": line[9],
                                "CURRENT": line[10],
                                "FREQ": line[11],
                                "TARGETS": line[12],
                                "UID": ''.join([line[3], line[1].zfill(2), line[2].zfill(2), *line[4:8]]),
                            })
                        elif self.model == '735':
                            events.append({
                                "#": line[0],
                                "REF": line[1],
                                "DATE": "{}/{}/{}".format(line[4], line[2], line[3]),
                                "TIME": "{}:{}:{}.{}".format(*line[5:9]),
                                "EVENT": line[9],
                                "FREQ": line[10],
                                "TARGETS": line[11],
                                "1619": line[12],
                                "UID": ''.join([line[4], line[2].zfill(2), line[3].zfill(2), *line[5:9]])
                            })
                        elif self.model == '351a' or self.model == "351":
                            events.append({
                                "#": line[0],
                                "REF": line[1],
                                "DATE": "{}/{}/{}".format(line[4], line[2], line[3]),
                                "TIME": "{}:{}:{}.{}".format(*line[5:9]),
                                "EVENT": line[9],
                                "LOCATION": line[10],
                                "CURR": line[11],
                                "FREQ": line[12],
                                "GROUP": line[13],
                                "SHOT": line[14],
                                "TARGETS": line[15],
                                "UID": ''.join([line[4], line[2].zfill(2), line[3].zfill(2), *line[5:9]])
                            })
                        
        else:
            chist_data = []
            # handler function to append new data to chist list
            def chist_handler(more_data):
                chist_data.append(more_data)

            # 851, self.daq
            username='FTPUSER'
            password='TAIL'
            with FTP(self.ip) as ftp:
                ftp.login(user=username, passwd=password)
                ftp.cwd('EVENTS')
                c='CHISTORY.TXT'
                # downloads CHISTORY.TXT file, stores in variable chist_data
                ftp.retrlines(f"RETR {c}", chist_handler)
                if len(chist_data) >= 3:
                    for line in chist_data[3:]:
                        if line:
                            line = line.replace('"', "").split(',')
                            events.append({
                                "#": line[0],
                                "REF": line[1],
                                "DATE": "{}/{}/{}".format(line[4], line[2].zfill(2), line[3].zfill(2)),
                                "TIME": "{}:{}:{}.{}".format(line[5].zfill(2), line[6].zfill(2), line[7].zfill(2), line[8].zfill(3)),
                                "EVENT": line[9],
                                "CURR": line[10],
                                "FREQ": line[11],
                                "TARGETS": line[12],
                                "17C5": line[13],
                                "UID": ''.join([line[4], line[2].zfill(2), line[3].zfill(2), line[5].zfill(2), line[6].zfill(2), line[7].zfill(2), line[8].zfill(3)])
                            })
                ftp.quit()
        return events

    def fetch_event_files(self, event_id, folder="temp"):
        """Download all files from a event if not downloaded, return list of files"""
        # Create folder if it doesn't exist
        if not os.path.exists(folder):
            os.makedirs(folder)
        # Get event history from the relay    
        events = self.get_history_simple()
        # Create empty list for the names of the files that will be downloaded
        new = []
        for e in events:
            current_event_id = e['UID']
            if event_id == current_event_id:
                printd(f"Attempting download {self.daq}: {current_event_id}")
                if not (self.model == '851' or self.model == 851):
                    f = event_id + '.CEV'
                    f_zip = f"{f}.zip"
                    f_path = os.path.join(folder, f)
                    f_zip_path = os.path.join(folder, f_zip)
                    f_path_exists = os.path.exists(f_path)
                    f_zip_path_exists = os.path.exists(f_zip_path)
                    
                    if f_path_exists:
                        printd("File path already exists, deleting...")
                        os.remove(f_path)
                    
                    if f_zip_path_exists:
                        printd("Zipped file path already exixts, deleting")
                        os.remove(f_zip_path)
                    
                    # Now the old files are deleted, if applicable....
                    printd('Downloading', f)
                    new.append(f)
                    with open(os.path.join(folder, f), 'wb') as fp:
                        response, _ = send_command_tn(
                            self.tn, "CEV " + e['#'] + ' R')
                    # print(response[-4:])
                        # print(response[:-2])
                        # print('writing...')
                        fp.write(response[:-2])
                        # compress(os.path.join(folder, f), config=False)
                        
                else:
                    # printd("Downloading an 851 Comtrade set")
                    # 851
                    # event_check = f"{event_id[2:8]},{event_id[8:]}"
                    # change event_check to use ref_num of the event
                    event_check = f",{e['REF']}."
                    
                    # print(f"event_check: {event_check}")
                    f_cfg = event_id + ".CFG"
                    f_dat = event_id + ".DAT"
                    f_hdr = event_id + ".HDR"
                    f_cfg_zip = f"{f_cfg}.zip"
                    f_dat_zip = f"{f_dat}.zip"
                    f_hdr_zip = f"{f_hdr}.zip"
                    
                    f_cfg_path = os.path.join(folder, f_cfg)
                    f_dat_path = os.path.join(folder, f_dat)
                    f_hdr_path = os.path.join(folder, f_hdr)
                    f_cfg_zip_path = os.path.join(folder, f_cfg_zip)
                    f_dat_zip_path = os.path.join(folder, f_dat_zip)
                    f_hdr_zip_path = os.path.join(folder, f_hdr_zip)
                    
                    f_cfg_path_exists = os.path.exists(f_cfg_path)
                    f_dat_path_exists = os.path.exists(f_dat_path)
                    f_hdr_path_exists = os.path.exists(f_hdr_path)
                    f_cfg_zip_path_exists = os.path.exists(f_cfg_zip_path)
                    f_dat_zip_path_exists = os.path.exists(f_dat_zip_path)
                    f_hdr_zip_path_exists = os.path.exists(f_hdr_zip_path)
                    
                    if f_cfg_path_exists:
                        printd(f"{f_cfg} already exists, deleting...")
                        os.remove(f_cfg_path)
                    if f_dat_path_exists:
                        printd(f"{f_dat} already exists, deleting...")
                        os.remove(f_dat_path)
                    if f_hdr_path_exists:
                        printd(f"{f_hdr} already exists, deleting...")
                        os.remove(f_hdr_path)
                        
                    if f_cfg_zip_path_exists:
                        printd(f"{f_cfg_zip} already exists, deleting...")
                        os.remove(f_cfg_zip_path)    
                    if f_dat_zip_path_exists:
                        printd(f"{f_dat_zip} already exists, deleting...")
                        os.remove(f_dat_zip_path)    
                    if f_hdr_zip_path_exists:
                        printd(f"{f_hdr_zip} already exists, deleting...")
                        os.remove(f_hdr_zip_path)    
                    
                    # Now the old files are deleted, if applicable...    
                    username='FTPUSER'
                    password='TAIL'
                    
                    printd(f"Downloading {f_cfg}")
                    printd(f"Downloading {f_dat}")
                    printd(f"Downloading {f_hdr}")
                    
                    with FTP(self.ip) as ftp:
                        ftp.login(user=username, passwd=password)
                        ftp.cwd('EVENTS')
                        cwd = ftp.nlst()
                        for filename in cwd:
                            if event_check in filename:
                                if '.CFG' in filename:
                                    cfg_local = f"/sos_data/relay_events/{self.daq}/events/{f_cfg}"
                                    ftp.retrbinary(f"RETR {filename}", open(cfg_local, 'wb').write)
                                    # compress(file_path=cfg_local, config=False)
                                    new.append(f_cfg)
                                elif '.DAT' in filename:
                                    dat_local = f"/sos_data/relay_events/{self.daq}/events/{f_dat}"
                                    ftp.retrbinary(f"RETR {filename}", open(dat_local, 'wb').write)
                                    # compress(file_path=dat_local, config=False)
                                    new.append(f_dat)
                                elif '.HDR' in filename:
                                    hdr_local = f"/sos_data/relay_events/{self.daq}/events/{f_hdr}"
                                    ftp.retrbinary(f"RETR {filename}", open(hdr_local, 'wb').write)
                                    # compress(file_path=hdr_local, config=False)
                                    new.append(f_hdr)
                        ftp.quit()
        print("downloading success")
        return new

    def get_variable_description(self, var_name):
        #print("###################var_name",var_name)
        variables = self.var_descriptions
        if var_name in variables:
            return variables[var_name]

        for key in variables['special_variables']:

            regex = '^['+key.replace("nnn", r"\d{1,3}")+']+$'
            if re.match(regex, var_name):
               # print('>>>>>>>>>>>>>>',regex, var_name)
                try:
                    number = re.search(r'\d{1,3}', var_name).group(0)

                    return variables['special_variables'][key][0].replace('nnn', number)
                except: pass    
        return "No description available"

    def get_event_data(self, event_number, resolution=32, data_tags=None,
                       auto_download=False, **kwargs):
        """Return dictionary of arrays where the data tags are the keys.

        Provide local paths to the event files or folder containing those files.
        If not provided, will attempt to download the files from the relay.

        Args:
            event_number (int): SEL reference number for the event
            resolution (int, optional): Resolution of the data. Defaults
                to 32
            data_tags (list, optional): List of data tags to include in the
                output. Defaults to None (all tags included)
            auto_download (bool, optional): Whether or not to download the files
                from the relay if not present on the local system. Defaults to false.

            Keyword args:
                Provide either the header file locations or a folder name.

                header_f (str): path to header file
                cfg_f (str): path to config file
                dat_f (str): path to data file
                folder (str): path to folder containing header, config and data
                    files. If folder location is provided, it'll check for the
                    files using the default naming scheme.
        """
        # printd("on get_event_data", pycev.__file__, event_number,
        #       resolution, data_tags, auto_download, kwargs)
        a = {}
        if not (self.model == '851' or self.model == 851):
            prefix = ''  # "C4_" if resolution == 4 else "CR_"
            pace = int(32/resolution) if resolution not in [32, 4] else 1
            # print(pace,resolution)

            fname = prefix+str(event_number)+'.CEV'

            folder = kwargs.get('folder', 'temp')
            if f"{fname}.zip" in os.listdir(folder):
                printd(f"{fname} is already zipped. Unzipping...")
                extractZip(os.path.join(folder, f"{fname}.zip"), f"/sos_data/relay_events/{self.daq}/events", False)
            elif not fname in os.listdir(folder):
                print("%s %s Could not find required data files in %s, attempting \n"
                    "to download from relay" % (datetime.datetime.now().isoformat(),
                                                os.path.basename(__file__), folder))
                if auto_download:
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                    path = self.get_event_file(event_number, resolution, folder)
                    print("%s %s Downloaded %s" % (datetime.datetime.now().isoformat(),
                                                os.path.basename(__file__), path))
                else:
                    raise Exception(
                        "Data files do not exist and auto download is set to off")
            printd(f"Attempting parse {self.daq}: {fname}")
            cev = pycev.CEV(file=os.path.join(folder, fname))
            compress(file_path=os.path.join(folder, fname), config=False)
            os.remove(os.path.join(folder, fname))
            printd(f"compressed {fname}")
            if 32 % resolution:
                raise Exception("32 should be divisible by resolution")
            a.update({'analog': {id_: data[::pace] for id_, data in zip(cev.analog_channel_ids,
                                                                    cev.analog_channels) if ((not data_tags) or (id_ in data_tags)) and id_ != "*"}})
            if self.model != '751':
                a_= {}
                for k, v in a['analog'].items():
                    if k[0] == 'I' and k[-3:] != '(A)':
                        k += '(A)'
                    elif 'Y(kV)' in k :
                        k =  k.replace('Y(kV)', '(V)')
                        v = [i/1000.0 for i in v]
                    a_[k] = v
                a['analog'] = a_  
            d = {}
            var_file = "variables_descriptions.json" if self.model == '751' else "variables_descriptions651.json"
            self.var_descriptions = json.load(
                open(os.path.join(os.path.dirname(__file__), var_file)))
            for id_ in (cev.status_channel_ids):
                data = cev.get_status(id_)
                changes = list(accumulate(sum(1 for _ in g) for _, g in groupby(data[::])))
                if len(changes) > 1:
                    if data[0]:
                        changes = [0] + changes

                    changes = [[(changes[i]), (changes[i + 1])] for i in range(0, len(changes) - 1, 2)]
                    d[id_] = {}
                    d[id_]['data'] = changes
                    d[id_]['description'] = self.get_variable_description(id_)
            a.update({'digital': d})
            Ts = (cev._analog_samp_timedelta).total_seconds()
       
            a["time"] = [i*Ts for i in list(range(0, len(a['analog']['IA(A)'])))]
    
            a["relay_settings"] = cev.settings.replace("\n\n", "\n").strip()[1:]#.split(",")[
            # 0].strip()[1:-1].strip()
            a["trip_time_rel"] = (cev._analog_samp_timedelta * cev._trig_row).total_seconds()
            a["trip_time_abs"] = (cev.trigger_time).replace(
                microsecond=0).isoformat()
            a["start_time"] = cev.time[0].replace().isoformat()
            a["fid"] = cev._properties['FID'].replace('FID=','')
            a["freq"] = cev._properties['FREQ']
            a["s_rate"] = cev._properties['SAM/CYC_A']
            print('get_event_data success')
        else:
            raw_pri_amps = ['IA.Raw_Pri', 'IB.Raw_Pri', 'IC.Raw_Pri', 'IN.Raw_Pri']
            raw_pri_volts = ['VA.Raw_Pri', 'VB.Raw_Pri', 'VC.Raw_Pri']
            # 851
            # Use comtrade library
            pace = int(32/resolution) if resolution not in [32, 4] else 1
            f_cfg = f"{event_number}.CFG"
            f_hdr = f"{event_number}.HDR"
            f_dat = f"{event_number}.DAT"

            folder = kwargs.get('folder', 'temp')

            comtrade = com.Comtrade()
            comtrade.load(cfg_file=os.path.join(folder, f_cfg), dat_file=os.path.join(folder, f_dat), hdr_file=os.path.join(folder, f_hdr))
            compress(file_path=os.path.join(folder, f_cfg), config=False)
            compress(file_path=os.path.join(folder, f_dat), config=False)
            compress(file_path=os.path.join(folder, f_hdr), config=False)
            os.remove(os.path.join(folder, f_cfg))
            os.remove(os.path.join(folder, f_dat))
            os.remove(os.path.join(folder, f_hdr))
            print(f"compressing {f_cfg}")
            print(f"compressing {f_dat}")
            print(f"compressing {f_hdr}")
            if 32 % resolution:
                raise Exception("32 should be divisible by resolution")
            a.update({
                'analog': {
                    id_: data[::pace] for id_, data in zip(comtrade.analog_channel_ids, comtrade.analog) if ((not data_tags) or (id_ in data_tags)) and id_ != "*"
                }
            })
            a_= {}
            for k, v in a['analog'].items():
                if k in raw_pri_amps:
                    k = k.replace(".Raw_Pri", "(A)")
                elif k in raw_pri_volts:
                    k = k.replace(".Raw_Pri", "(V)")
                a_[k] = v.tolist()
            a['analog'] = a_
            d = {}
            var_file = "variables_descriptions851.json"
            self.var_descriptions = json.load(
                open(os.path.join(os.path.dirname(__file__), var_file)))
            
            for index, id_ in enumerate(comtrade.status_channel_ids):
                data = comtrade.status[index]

                changes = list(accumulate(sum(1 for _ in g) for _, g in groupby(data[::])))
                if len(changes) > 1:
                    if data[0]:
                        changes = [0] + changes

                    changes = [[(changes[i]), (changes[i + 1])] for i in range(0, len(changes) - 1, 2)]
                    d[id_] = {}
                    d[id_]['data'] = changes
                    d[id_]['description'] = self.get_variable_description(id_)
            a.update({'digital': d})
            # Find way to parse relay settings
            a["time"] = comtrade.time.tolist()
            a["relay_settings"] = "\nNo General Settings Available\n"
            a["trip_time_rel"] = comtrade.trigger_time
            a["trip_time_abs"] = comtrade.trigger_timestamp.replace(microsecond=0).isoformat()
            a["start_time"] = comtrade.trigger_timestamp.replace(microsecond=0).isoformat()
            a["fid"] = comtrade.cfg.rec_dev_id
            a["freq"] = re.search("Freq,\"([0-9.]+)\"", comtrade.hdr).groups()[0]
            a["s_rate"] = re.search("Event.SampRate,\"([0-9.]+)\"", comtrade.hdr).groups()[0]
                
        return a


def get_event_id(event):
    return (event["DATE"]+event["TIME"]).replace('/', '').replace('.', '').replace(':', '')


if __name__ == "__main__":
    import json

    def pprint(a): print(json.dumps(a, indent=2))

    def hprint(a):
        a = ' ' + str(a)+' '
      #print("", '#'*len(a), a, '#'*len(a), sep='\n')
    sel = SelEvents("192.168.1.90", model='735')
    print('11111')

    history = sel.get_history_simple()
    pprint(history)
    event_id = get_event_id(history[0])
    print()

    pprint(sel.fetch_event_files(event_id))
    exit()

    # hprint('get_history_simple()')

    # hprint('update_header_cache()')
    # sel.update_header_cache()

    # hprint('get_history()')
    # pprint(sel.get_history())

    # hprint('get_event_file(10028)')
    # pprint(sel.get_event_file(10028))

    # try:
    #     hprint("get_event_data(10028, data_tags=['IC', 'IA'], resolution=1)")
    #     pprint(sel.get_event_data(10028, data_tags=['IC', 'IA'], resolution=1   ))
    # except Exception as e:
    #     print(e)

    hprint("sel.get_event_data(10105, resolution=32,folder='/sos_data/relay_events/DEV_39/events')")
    pprint(sel.get_event_data(10105, resolution=32,
                              folder='/sos_data/relay_events/DEV_39/events')['digital'])
    exit()
    try:
        hprint("get_event_data(10028, data_tags=['IC', 'IA'], resolution=1)\n"
               "header_f=/sos_data/relay_events/DEV_87/events/HR_10028.HDR\n"
               "cfg_f=/sos_data/relay_events/DEV_87/events/HR_10028.CFG\n"
               "dat_ft=/sos_data/relay_events/DEV_87/events/HR_10028.DAT")
        pprint(sel.get_event_data(10028, data_tags=['IC', 'IA'], resolution=1,
                                  header_f="/sos_data/relay_events/DEV_87/events/HR_10028.HDR",
                                  cfg_f="/sos_data/relay_events/DEV_87/events/HR_10028.CFG",
                                  dat_f="/sos_data/relay_events/DEV_87/events/HR_10028.DAT"))
    except Exception as e:
        print(e)

    # hprint('fetch_event_files(10028,"temp2")')
    # pprint(sel.fetch_event_files(10028,"temp2"))
    input()

    input()
