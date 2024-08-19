import os
import sys
import math
import struct
import datetime
import serial
import binascii
import signal
import fasteners
import traceback

from threading import Thread, Event, Lock, get_ident
from collections import deque

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

if __name__ == "__main__":
    #if running this script directly, need to adjust relative path before importing helpers
    #print('modifying path')
    PACKAGE_PARENT = '../..'
    SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
    sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from helpers.common import printd, printe, get_json_lock, save_json_config, json_lock
from background.modbus_rtu_wiretap.datastore_v1 import WiretapStore as db
from background.modbus_rtu_wiretap.measuresstore_v1 import MeasureStore as measdb


"""
    This process implements a wiretap poll through a serial interface on a Karbon / 3350.

    To-do
    - Logging
        - Print statements after exiting threads
    - Performance Metrics
"""

_BAD_SERIAL_RETURN_MESSG_NUM=1000

# Class Definitions
class DataFetch(Thread): 
    def __init__ (self, port = "/dev/ttyS0"):
        """ Grabs and decodes an un-parsed string of data from a serial port. Returns
            a hex string of data.

        Args:
            port (str, optional): Serial port identifier. Defaults to "/dev/ttyS0".
        """
        Thread.__init__(self)
        
        self.exit = Event()
        self.port = port
        self.serialObject = serial.Serial(self.port)
        
        # Only care about one direction - could we use a uni-directional queue?
        self.fetchedData = deque()

    def run(self):
        """
            The method ran when the Thread object's start() is invoked. It sets the state fetchedData constantly
            to the result of a serialObject read. It decodes this into UTF-8 text.
        """
        printd(f"Starting data fetcher for port {self.port}")

        while not ( self.exit.is_set() ):
            try:
                self.fetchedData.append( binascii.hexlify( self.serialObject.read() ).decode("utf-8") )

            except Exception as e:
                printd(f"Exception occurred while processing DataFetch for {self.port}")
                printe(f"Exception occurred while processing DataFetch for {self.port}")
                traceback.print_exc()

        self.serialObject.close()
        printd(f"Exiting data Fetcher for port {self.port}")

    def setExit(self):
        """
            Helper method to set the threading event exit, which terminates the thread in run()
        """
        printd(f"DataFetch ({get_ident()}) received kill command, exiting...")
        
        self.exit.set()

    def fetchData(self):
        """ This method returns an iterable list of the data in the fetchedData deque

        Returns:
            dataCollected: list containing current fetched Data
        """
        dataCollected = []
        if not ( self.exit.is_set() ):
            while ( len(self.fetchedData) ):
               dataCollected.append( self.fetchedData.popleft() )

        return dataCollected

class DataProcessor(Thread):
    def __init__ (self, addToDB, addToMeasures, port = "/dev/ttyS0"):
        """ Constructor For a DataProcessor class.  This object contains state related to 
        decoded data. One DataProcessor object represents one serial port.

        Args:
            addToDB (function): Callback function to handle when the processor detects a data response/return. Handles writing to SQL database.
            addToMeasures (function): Callback function to handle when the processor detects a data response/return. Handles writing to JSON measures.
            port (str, optional): serial port identifier. Defaults to "/dev/ttyS0".
        """
        Thread.__init__(self)

        self.exit = Event()
        self.port = port
        self.fetcher = DataFetch(port = self.port)
        self.addToDB = addToDB
        self.addToMeasures = addToMeasures
        self.collectedData = []

        """
            serialStreamLock used here for excluding other DataProcessor objects from editing serialStreams file at serialStreamsFilePath
        """
        with serialStreamLock:

            serialStreams = get_json_lock(serialStreamsFilePath, config = False)
            serialStreams[self.port] = []

            """
                json_lock is probably not needed, as the foundPairsLock exists. However, it doesn't hurt
                Can be removed to improve performance
            """
            with json_lock(serialStreamsFilePath, config=False):
                save_json_config(serialStreamsFilePath, serialStreams, config = False)

        self.fetcher.start()

    def run(self):
        """
            Method ran by Thread. Gets returned data from a DataFetch object, then processes that into form that can be saved.
            First, establishes a good packet of data to know a response to follow (while loop). Then, parses the response packets
            of information.
        """
        try:
            printd(f"Starting data processor for port {self.port}")

            commandCodes = {'01': 8, '02': 8, '03': 8, '04': 8, '05': 8, '06': 8, '0F': 11, '10': 13}
            
            communications = {}
            unclaimedRequests = []

    
            """
                Try and find a start of any valid packet, so we have data.
            """
            while True:
                # shit wrong
                if ( self.exit.is_set() or self.fetcher.exit.is_set() ):
                    printd(f"Exiting Data Processor on port {self.port}")
                    self.fetcher.setExit()
                    if self.fetcher.is_alive():
                        self.fetcher.join()

                    self.exit.set()
                    return

                newData = self.fetcher.fetchData()
                if ( len(newData) > 0 ):
                    self.collectedData += newData

                    with serialStreamLock:

                        serialStreams = get_json_lock(serialStreamsFilePath, config = False)
                        serialStreams[self.port] += newData
                        serialStreams[self.port] = serialStreams[self.port][-500:]

                        with json_lock(serialStreamsFilePath, config=False):
                            save_json_config(serialStreamsFilePath, serialStreams, config = False)
                
                """
                    Request, NOT response packet, which minimum is 8 entries
                    8 bytes:
                      - Slave ID (1)
                      - Request Type (1)
                      - Start Address (2)
                      - Number of Registers to read (2)
                      - CRC/Checksum (2)
                """
                if (len(self.collectedData) < 8):
                    continue

                elif (len(self.collectedData) > _BAD_SERIAL_RETURN_MESSG_NUM):
                    self.collectedData = []

                    printd(f"Update on port {self.port}:\nList became too long. Restarting Fetcher.")

                    self.fetcher.setExit()

                    if self.fetcher.is_alive():
                        self.fetcher.join()

                    self.fetcher = DataFetch(port = self.port)
                    self.fetcher.start()
                    continue

                else:
                    if not ( self.collectedData[1] in commandCodes.keys() ):
                        self.collectedData.pop(0)
                    else:
                        if not(len(self.collectedData) >= commandCodes[self.collectedData[1]]):
                            continue

                        else:
                            proposedRequest = self.collectedData[:commandCodes[self.collectedData[1]]]

                            crcString = bytearray([int(x, 16) for x in proposedRequest])
                            if ( self.crc16(crcString) == b'\x00\x00'):
                                unclaimedRequests.append(proposedRequest)
                                self.collectedData = self.collectedData[commandCodes[self.collectedData[1]]:]
                                
                                printd(f"Port {self.port} Status Update: Starting main loop")
                                
                                break
                            
                            else:
                                self.collectedData.pop(0)

            """
                Main Process after finding one valid packet.
            """
            while True:
                if (self.exit.is_set() or self.fetcher.exit.is_set()):
                    printd(f"Exiting Data Processor on port {self.port}")

                    self.fetcher.setExit()
                    if self.fetcher.is_alive():
                        self.fetcher.join()

                    self.exit.set()
                    return

                newData = self.fetcher.fetchData()

                if (len(newData) > 0):
                    self.collectedData += newData

                    with serialStreamLock:
                    
                        serialStreams = get_json_lock(serialStreamsFilePath, config = False)
                        serialStreams[self.port] += newData
                        serialStreams[self.port] = serialStreams[self.port][-500:]

                        with json_lock(serialStreamsFilePath, config=False):
                            save_json_config(serialStreamsFilePath, serialStreams, config = False)

                """
                    No packet can have less than 2 entries, max recursion of 2 entries.
                    Error protection, make sure self.collectedData (list) is long enough
                    
                    Lots of non-useful iterations
                    
                    NOTE: Might be able to increase to 5 to increase number of executions but improve and therefore increase performance
                """
                if (len(self.collectedData) < 2):
                    continue

                if (len(self.collectedData) > _BAD_SERIAL_RETURN_MESSG_NUM):

                    self.collectedData = []

                    printd(f"Update on port {self.port}:\nList became too long. Restarting Fetcher.")

                    self.fetcher.setExit()

                    if self.fetcher.is_alive():
                        self.fetcher.join()

                    self.fetcher = DataFetch(port = self.port)
                    self.fetcher.start()

                    continue

                if not ( self.collectedData[1] in commandCodes.keys() ):
                    self.collectedData.pop(0)
                else:
                    needMoreData = []
                    foundResponse = False

                    # Detect Responses
                    for request in unclaimedRequests:
                        needMoreData.append(False)

                        if (self.collectedData[:2] == request[:2]):
                            if ((len(self.collectedData) >= 3) and (len(self.collectedData) >= (int(self.collectedData[2], 16) + 5))):
                                if (self.crc16(bytearray([int(x, 16) for x in self.collectedData[:(int(self.collectedData[2], 16) + 5)]])) == b'\x00\x00'):

                                    response = self.collectedData[:(int(self.collectedData[2], 16) + 5)]

                                    startAddress = int("".join(request[2:4]), 16)

                                    endAddress = startAddress + int("".join(request[4:6]), 16)

                                    self.addToMeasures(startAddress, endAddress, response, self.port)

                                    deviceID = int(request[0], 16)
                                    requestCall = int(request[1], 16)

                                    sQLUUId = "".join(request[2:-2]) + f"{(deviceID * 1000) + requestCall}{self.port}"
                                    sQLId = deviceID
                                    sQLCall = requestCall
                                    sQLPort = self.port
                                    sQLRequest = ",".join(request[2:-2])
                                    sQLResponse = ",".join(response[3:-2])
                                    sQLTime = datetime.datetime.now()

                                    foundPairRequest = ",".join(request)
                                    foundPairResponse = ",".join(response)

                                    """
                                        foundPairsLock used here for excluding other DataProcessor objects from editing foundPairs Object at foundPairsFilePath
                                    """
                                    with foundPairsLock:

                                        foundPairs = get_json_lock(foundPairsFilePath, config = False)
                                        foundPairs.append({
                                                            "uuid": sQLUUId,
                                                            "port": self.port,
                                                            "deviceId": deviceID,
                                                            "request": foundPairRequest,
                                                            "response": foundPairResponse,
                                                            "time": sQLTime.isoformat()
                                                        })
                                        
                                        if (len(foundPairs) > 20):
                                                    
                                            foundPairs.pop(0)

                                        """
                                            json_lock is probably not needed, as the foundPairsLock exists. However, it doesn't hurt
                                            Can be removed to improve performance
                                        """
                                        with json_lock(foundPairsFilePath, config=False):

                                            save_json_config(foundPairsFilePath, foundPairs, config = False)

                                    communications[sQLUUId] = {"id": sQLId, "call": sQLCall, "time": sQLTime}

                                    self.addToDB(sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime)

                                    unclaimedRequests.pop(unclaimedRequests.index(request))

                                    self.collectedData = self.collectedData[(int(self.collectedData[2], 16) + 5):]

                                    foundResponse = True

                                    break

                            else:

                                needMoreData[-1] = True

                    if (foundResponse):
                        continue

                    # If it is not a response, see if it is a request
                    if not(len(self.collectedData) >= commandCodes[self.collectedData[1]]):
                        continue

                    else:
                        proposedRequest = self.collectedData[:commandCodes[self.collectedData[1]]]
                        crcString = bytearray([int(x, 16) for x in proposedRequest])

                        if (self.crc16(crcString) == b'\x00\x00'):
                            unclaimedRequests.append(proposedRequest)

                            if (len(unclaimedRequests) > 20):
                                unclaimedRequests.pop(0)
                            
                            self.collectedData = self.collectedData[commandCodes[self.collectedData[1]]:]
                        else:
                            if not(any(needMoreData)):

                                self.collectedData.pop(0)

        except Exception as e:
            printe(f"Error with running the Data Processor on port {self.port}:\n{traceback.format_exc()}\n{e}\nExiting Data Processor Execution")

            printd(f"Exiting Data Processor on port {self.port} due to an error")

            self.fetcher.setExit()

            if self.fetcher.is_alive():
                self.fetcher.join()

            self.exit.set()

            return

    def crc16 (self, data: bytes):
        """ 
            Cyclic Redundancy Check, used for checksum. Detects changes to digital data
        
            Exclusive OR:
                    - 1 XOR 1 = 0
                    - 1 XOR 0 = 1
        Args:
            data (bytes): bytes list

        Returns:
            ret_list: bytes list of crc
        """
        
        # crc instantiated as 2-byte/16bit number
        crc = 0xffff
        for cur_byte in data:
            
            # ^ = exclusive or (XOR)
            crc = crc ^ cur_byte

            for _ in range(8):
                a = crc
                carry_flag = a & 0x0001
                crc = crc >> 1

                if carry_flag == 1:
                    crc = crc ^ 0xa001
        
        return bytes([crc % 256, crc >> 8 % 256])

    def setExit (self):
        """
            Signals exit run methods, and fetcher's run method.
        """
        
        printd(f"DataProcessor ({get_ident()}) received kill command, exiting...")
        
        self.exit.set()
        self.fetcher.setExit()

class ProcessingController:
    def __init__ (self, listeningPorts):
        """ Constructor for a ProcessingController class. The main thread which has DataProcessors for multiple serial ports.
        
        Args:
            listeningPorts (list): List containing string identifiers for each serial port
        """
        Thread.__init__(self)

        self.exit = Event()
        self.identity = []
        self.processors = []
        self.tcpServers = []
        self.addToDBQueue = deque()
        self.addToMeasuresQueue = deque()
        
        # track json files in /sos-config
        self.__siteDevices = None
        self.__siteDevicesMTime = None
        self.__templates = None
        self.__templatesMTime = None
        
        """
            self.mapping associates a device's daq and modbus template with its communication id and serial port.
            Example structure:
            "ttys0": {
                "5": [ "DEV_45", "Eaton_PowerXpert_DC_feeder":
                                [
                                    {
                                        "accepted_max": null,
                                        "accepted_min": null,
                                        "address": 306,
                                        "autoScaling": {
                                        "offset": 0,
                                        "scale_mode": "slope_intercept",
                                        "slope": 1,
                                        "target_max": 0,
                                        "target_min": 0,
                                        "value_max": 0,
                                        "value_min": 0
                                        },
                                        "byteword_order": "bigByte_bigWord",
                                        "dataType": "int16",
                                        "function": "read-holding-registers",
                                        "logging": "instant",
                                        "measure": "current_1",
                                        "name": "current_1",
                                        "quantity": 1,
                                        "unit": "A"
                                    }
                                ]
                            ]
            }
        """
        self.mapping = {}

        # foundPairsFilePath = Global Scope
        foundPairs = get_json_lock(foundPairsFilePath, config = False)
        foundPairs = []
        save_json_config(foundPairsFilePath, foundPairs, config = False)

        """
            Iterable
            Does not need to be restarted when sos_template_modbus or site_devices change
        """
        for i in range(0, len(listeningPorts)):
            new_processor = DataProcessor(self.addToSQLDB, self.addToMeasures, port = listeningPorts[i])
            new_processor.start()

            self.processors.append(new_processor)

    def addToSQLDB(self, sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime):
        """ This function adds the necessary meta-data to a queue, which is then popped and added under
            the self.run() method

        Args:
            sQLUUId (str): SQLlite string row primary key
            sQLId (int): SQLite int Entry ID
            sQLCall (int): Call id, used in calculating id_call for optimized lookups
            sQLPort (str): Serial Port identifier
            sQLRequest (str): Encoded Request
            sQLResponse (str): Encoded Response
            sQLTime (str): Time of inserted entry
        """
        self.addToDBQueue.append( [ sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime ] )

    def addToMeasures(self, startAddress, endAddress, response, port):
        """ This function adds the necessary meta-data to a queue, which is then popped and added under
            the self.run() method

        Args:
            startAddress (str): Beginning MODBUS Address of call
            endAddress (str): Ending MODBUS Address of call
            response (str): Encoded Data Response
            port (str): Serial Port Identifier
        """
        self.addToMeasuresQueue.append( [ startAddress, endAddress, response, port ] )
        
    def run(self):
        """
            Method ran by thread. Gets saved data from the DataProcessor object(s), then saves to db stores. Uses save methods from measurestore and datastore.
            
            No time.sleep
        """
        while ( not ( self.exit.is_set() ) ):
            reload = False
            
            siteDevicesMTime = os.stat('/sos-config/site_devices.json').st_mtime
            if not( siteDevicesMTime == self.__siteDevicesMTime ):
                reload = True
                self.__siteDevicesMTime = siteDevicesMTime
                self.__siteDevices = get_json_lock('site_devices')
                printd("site_devices has changed, need to reload...")
            
            modbusTemplatesMTime = os.stat('/sos-config/sos_templates_modbus.json').st_mtime
            if not ( modbusTemplatesMTime == self.__templatesMTime ):
                reload = True
                # Need to re-load the site_devices into memory
                self.__templatesMTime = siteDevicesMTime
                self.__templates = get_json_lock('sos_template_modbus')
                printd("sos_templates_modbus has changed, need to reload...")
                
            if reload:
                # Set self.mapping to an empty dict
                self.mapping = {}

                for deviceType in self.__siteDevices:
                    for device in self.__siteDevices[deviceType]:
                        dev_wiretapped = device.get('wiretapped', False)
                        
                        # Check if the wiretapped value is not None, "None", "". If so, the device is not wiretapped
                        if not ( dev_wiretapped in ( None, "None", "" ) ):
                            
                            # Alex - self.mapping is 100% instantiated to empty dict
                            # if ( not ( device["wiretapped"] in self.mapping ) ):
                            #     self.mapping[device["wiretapped"]] = {}
                            
                            self.mapping[dev_wiretapped] = {}
                            self.mapping[dev_wiretapped][device["network"]["params"]["comm_id"]] = [ device["daq_name"], self.__templates[ device["device_type" ] ][ device["daq_template"] ] ]

            if bool(self.addToDBQueue):
                element = self.addToDBQueue.popleft()

                db.insert(element)

                for processor in self.processors:
                    if (processor.exit.is_set()):
                        
                        # Current thread should block until processor is exited
                        processor.join(timeout = 3)

            if bool(self.addToMeasuresQueue):
                
                """
                    self.addToMeasuresQueue is a 2D List
                    Structure for entry in self.addToMeasuresQueue (list):
                    [ startAddress, endAddress, response, port ]
                """
                
                element = self.addToMeasuresQueue.popleft()

                startAddress = element[0]
                endAddress = element[1]
                mq_response = element[2]
                serial_port = element[3]
                
                if ( ( serial_port in self.mapping ) and ( int( mq_response[0], 16 ) ) in self.mapping[ serial_port ]):
                    
                    response = mq_response[3:-2]

                    for measure in self.mapping[ serial_port ][int(mq_response[0], 16)][1]:
                        
                        if ( ( int(measure["address"]) <= endAddress ) and ( int( measure["address"]) >= startAddress ) ):

                            if ((measure["function"] == "read-holding-registers") or (measure["function"] == "read-input-registers")):
                                adjustedAddress = (int(measure["address"]) - startAddress) * 2

                                if (adjustedAddress < len(response)):
                                    if (measure["dataType"] in ["int16", "uint16"]):
                                        registers = [int("".join(response[adjustedAddress:adjustedAddress + 2]), 16)]

                                    elif (measure["dataType"] in ["int32", "uint32", "float32"]):
                                        registers = [int("".join(response[adjustedAddress:adjustedAddress + 2]), 16), int("".join(response[adjustedAddress + 2:adjustedAddress + 4]), 16)]

                                    elif (measure["dataType"] == "bitpacked16"):
                                        if (int("".join(response[adjustedAddress:adjustedAddress + 2]), 16) & (2**measure["bit"]) == (2**measure["bit"])):
                                            value = 1

                                        else:
                                            value = 0

                                    if not( measure["dataType"] == "bitpacked16" ):
                                        wordOrder = None
                                        byteOrder = None

                                        if ("bigWord" in measure["byteword_order"]):
                                            wordOrder = Endian.Big

                                        else:
                                            wordOrder = Endian.Little

                                        if ("bigByte" in measure["byteword_order"]):
                                            byteOrder = Endian.Big

                                        else:
                                            byteOrder = Endian.Little

                                        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder = byteOrder, wordorder = wordOrder)

                                        if (measure["dataType"] == "int16"):
                                            value = decoder.decode_16bit_int()

                                        elif (measure["dataType"] == "uint16"):
                                            value = decoder.decode_16bit_uint()
                                        
                                        elif (measure["dataType"] == "int32"):
                                            value = decoder.decode_32bit_int()

                                        elif (measure["dataType"] == "uint32"):
                                            value = decoder.decode_32bit_uint()

                                        elif (measure["dataType"] == "float32"):
                                            value = decoder.decode_32bit_float()

                                        autoScaling = measure.get("autoScaling", {})
                                        scale_mode = autoScaling.get("scale_mode", {})
                                        slope = autoScaling.get("slope", 1)
                                        offset = autoScaling.get("offset", 1)
                                        target_min = autoScaling.get("target_min", 1)
                                        target_max = autoScaling.get("target_max", 1)
                                        value_min = autoScaling.get("value_min", 1)
                                        value_max = autoScaling.get("value_max", 1)
                                        
                                        if scale_mode == 'slope_intercept':
                                            value = round( ( float( slope ) * value) + float( offset ), 2)
                                        
                                        elif scale_mode == 'point_slope':
                                            value = round( ( ( target_max - target_min ) / ( value_max - value_min ) ) * ( value - value_min ) + target_min )
                                            
                            else:
                                adjustedAddress = math.floor((int(measure["address"]) - startAddress) / 8)
                                if (adjustedAddress < len(response)):
                                    byteSelected = bin(int(response[adjustedAddress], 16))[::-1][:-2]
                                    diff = (int(measure["address"]) - (startAddress + (adjustedAddress * 8)))
                                    value = byteSelected[diff]
                            measdb.insert( ( self.mapping[ serial_port ][ int(mq_response[0], 16) ][0], measure["measure"], value, datetime.datetime.now()))
                pass

        for processor in self.processors:

            processor.setExit()
            processor.join(timeout = 3)

        printd(f"Exiting Controller")

    def setExit (self):
        """
            Signal Exit of DataProcessors and itself.
        """
        printd(f"ProcessingController ({get_ident()}) received kill command, exiting...")
        
        processor: DataProcessor
        for processor in self.processors:
            processor.setExit()
        
        self.exit.set()

    def quitAll (self, *args):
        """
            Wrapper to call setExit
        """
        self.setExit()



# Main Thread
"""
Threading Diagram:
Main Thread -> controller: ProcessingController -> new_processor: DataProcessor -> fetcher: DataFetch
           One                              One or More                         One
                                       (For Each Serial Port)
"""

# On Start, set wiretapped to True for plant_config
plant_config = get_json_lock("plant_config")
if not ( "plant_type" in plant_config ):
    plant_config["plant_type"] = {}

# If 'wireTapped' key is either missing or set False
if not ( plant_config["plant_type"].get("wireTapped", False) ):
    # Will fire if plant_type has just been set to {}
    
    plant_config["plant_type"]["wireTapped"] = True

    with json_lock("plant_config"):
        save_json_config("plant_config", plant_config)

params = get_json_lock("background")["modbus_rtu_wiretap"]["parameters"]

# Global
logsDirectoryPath = '/sos_data/logs/wireTapLogs'
foundPairsFilePath = '/sos_data/logs/wireTapLogs/foundPairs.json'
serialStreamsFilePath = '/sos_data/logs/wireTapLogs/serialStreams.json'

foundPairsLock = Lock()
serialStreamLock = Lock()

if not(os.path.isdir(logsDirectoryPath)):
    os.mkdir(logsDirectoryPath)
    
if not(os.path.isfile(foundPairsFilePath)):
    with open(foundPairsFilePath, "w+") as f:
        f.write("[]")
    
if not(os.path.isfile(serialStreamsFilePath)):
    with open(serialStreamsFilePath, "w+") as f:
         f.write("{}")

argsDict = {}

""" Alex - Changed from portRecieve to port_receive for naming convention purposes
if ("portRecieve" in params):
    if (type(params["portRecieve"]) == type([])):
        argsDict["listeningPorts"] = params["portRecieve"]

    else:
        argsDict["listeningPorts"] = [params["portRecieve"]]
"""

if ("port_receive" in params):
    if (type(params["port_receive"]) == type([])):
        argsDict["listeningPorts"] = params["port_receive"]

    else:
        argsDict["listeningPorts"] = [params["port_receive"]]


# Begin ProcessingController class
controller = ProcessingController(argsDict["listeningPorts"])

for sig in ('TERM', 'HUP', 'INT', 'QUIT'):
    signal.signal(getattr(signal, f"SIG{sig}"), controller.quitAll)

controller.run()


"""
Zade Current Status Notes (10/09/23)
    - On-office and bench testing
    - Limited by switching ports from 232 to 485
    - Functional on Ethernet Side
    - Stop and start process if getting no data
    - ttys1 acts up, return good serial data for a period of time, but then turn into trash values
    - Ask Onlogic about Ubuntu 18-22, Serial port ttys1 moving to 485, getting garbage data
"""