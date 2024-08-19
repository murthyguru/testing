import os
import sys
import json
import time
import math
import struct
import datetime
import serial
import binascii
import signal
import fasteners
import traceback

from threading import Thread, Event, Lock
from collections import deque

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(os.path.dirname(current))
sys.path.append(parent)
from helpers.common import get_json_lock, save_json_config
from background.modbus_rtu_wiretap.datastore_v1 import WiretapStore as db
from background.modbus_rtu_wiretap.measuresstore_v1 import MeasureStore as measdb
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
import logging

db.copy_datastore_db_if_not_exists()
measdb.copy_measures_db_if_not_exists()

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

python_executable_path = os.path.join(os.getenv('USERPROFILE'), 'wiretap_files', 'mac_venv', 'Scripts', 'python.exe')

workingDirectory = project_directory

foundPairsFilePath = f'{log_base_path}/foundPairs.json'
serialStreamsFilePath = f'{log_base_path}/serialStreams.json'
countsFilePath = f'{log_base_path}/counts.json'

os.makedirs(os.path.dirname(foundPairsFilePath), exist_ok=True)
os.makedirs(os.path.dirname(serialStreamsFilePath), exist_ok=True)
os.makedirs(os.path.dirname(countsFilePath), exist_ok=True)

foundPairsLock = Lock()
serialStreamLock = Lock()
countsLock = Lock()


# Function to clean the content of JSON files
def clean_json_files():
    json_defaults = {
        foundPairsFilePath: [],
        serialStreamsFilePath: {},
        countsFilePath: {},
        log_path:''
    }
    for file_path, default_value in json_defaults.items():
        if os.path.exists(file_path):
            with open(file_path, 'w') as file:
                json.dump(default_value, file)
            logging.info(f"Cleaned file: {file_path}")

# Function to clean SQLite tables
def clean_sqlite_tables():
    db.clean_all_tables()
    measdb.clean_all_tables()
    logging.info("Cleaned SQLite tables.")

# Run cleanup functions
clean_json_files()
clean_sqlite_tables()

class DataFetch(Thread):
    def __init__(self, port="/dev/ttyS0", retries=5, delay=2):
        Thread.__init__(self)
        self.exit = Event()
        self.port = port
        self.serialObject = None
        self.fetchedData = deque()
        
        for attempt in range(retries):
            try:
                self.serialObject = serial.Serial(self.port, baudrate=9600, timeout=1)
                break
            except serial.SerialException as e:
                logging.error(f"Attempt {attempt + 1} failed: Could not open port {self.port}. {e}")
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    raise

    def run(self):
        logging.info(f"Starting data fetcher for port {self.port}")
        while not self.exit.is_set():
            try:
                data = self.serialObject.read().hex()
                if data:
                    self.fetchedData.append(data)
                    logging.debug(f"Data fetched from port {self.port}: {data}")
                else:
                    logging.debug(f"No data received from port {self.port}")
            except Exception as e:
                logging.error(f"Error reading from serial port {self.port}: {e}")
                continue
        self.serialObject.close()
        logging.info(f"Exiting data Fetcher for port {self.port}")

    def setExit(self):
        self.exit.set()

    def fetchData(self):
        dataCollected = []
        if not self.exit.is_set():
            while len(self.fetchedData):
                dataCollected.append(self.fetchedData.popleft())
        return dataCollected

class DataProcessor(Thread):
    def __init__(self, addToDB, addToMeasures, port="/dev/ttyS0"):
        Thread.__init__(self)
        self.exit = Event()
        self.port = port
        self.fetcher = DataFetch(port=self.port)
        self.addToDB = addToDB
        self.addToMeasures = addToMeasures
        self.collectedData = []

        with countsLock:
            countsFile = get_json_lock(countsFilePath, config=False)
            countsFile[self.port] = {}
            save_json_config(countsFilePath, countsFile, config=False)

        with serialStreamLock:
            serialStreams = get_json_lock(serialStreamsFilePath, config=False)
            serialStreams[self.port] = []
            save_json_config(serialStreamsFilePath, serialStreams, config=False)

        self.fetcher.start()

    def run(self):
        try:
            logging.info(f"Starting data processor for port {self.port}")
            commandCodes = {'01': 8, '02': 8, '03': 8, '04': 8, '05': 8, '06': 8, '0F': 11, '10': 13}
            communications = {}
            unclaimedRequests = []

            while True:
                if self.exit.is_set() or self.fetcher.exit.is_set():
                    logging.info(f"Exiting Data Processor on port {self.port}")
                    self.fetcher.setExit()
                    if self.fetcher.is_alive():
                        self.fetcher.join()
                    self.exit.set()
                    return

                newData = self.fetcher.fetchData()
                if len(newData) > 0:
                    self.collectedData += newData
                    logging.debug(f"Collected data: {self.collectedData}")
                    with serialStreamLock:
                        serialStreams = get_json_lock(serialStreamsFilePath, config=False)
                        serialStreams[self.port] += newData
                        serialStreams[self.port] = serialStreams[self.port][-500:]
                        save_json_config(serialStreamsFilePath, serialStreams, config=False)

                if len(self.collectedData) < 8:
                    continue
                elif len(self.collectedData) > 1000:
                    self.collectedData = []
                    logging.info(f"Update on port {self.port}: List became too long. Restarting Fetcher.")
                    self.fetcher.setExit()
                    if self.fetcher.is_alive():
                        self.fetcher.join()
                    self.fetcher = DataFetch(port=self.port)
                    self.fetcher.start()
                    continue
                else:
                    if self.collectedData[1] not in commandCodes.keys():
                        logging.warning(f"Where > 8 < 1000 - self.collectedData - Invalid command code: {self.collectedData[1]} not in command code keys {commandCodes.keys()}")
                        self.collectedData.pop(0)
                    else:
                        if len(self.collectedData) >= commandCodes[self.collectedData[1]]:
                            proposedRequest = self.collectedData[:commandCodes[self.collectedData[1]]]
                            crcString = bytearray.fromhex("".join(proposedRequest))
                            if self.crc16(crcString) == b'\x00\x00':
                                unclaimedRequests.append(proposedRequest)
                                self.collectedData = self.collectedData[commandCodes[self.collectedData[1]]:]
                                logging.info(f"Port {self.port} Status Update: Starting main loop")
                                break
                            else:
                                logging.warning(f"Invalid CRC for request: {proposedRequest}")
                                self.collectedData.pop(0)

            while True:
                if self.exit.is_set() or self.fetcher.exit.is_set():
                    logging.info(f"Exiting Data Processor on port {self.port}")
                    self.fetcher.setExit()
                    if self.fetcher.is_alive():
                        self.fetcher.join()
                    self.exit.set()
                    return

                newData = self.fetcher.fetchData()
                if len(newData) > 0:
                    self.collectedData += newData
                    with serialStreamLock:
                        serialStreams = get_json_lock(serialStreamsFilePath, config=False)
                        serialStreams[self.port] += newData
                        serialStreams[self.port] = serialStreams[self.port][-500:]
                        save_json_config(serialStreamsFilePath, serialStreams, config=False)

                if len(self.collectedData) < 2:
                    continue

                if len(self.collectedData) > 1000:
                    self.collectedData = []
                    logging.info(f"Update on port {self.port}: List became too long. Restarting Fetcher.")
                    self.fetcher.setExit()
                    if self.fetcher.is_alive():
                        self.fetcher.join()
                    self.fetcher = DataFetch(port=self.port)
                    self.fetcher.start()
                    continue

                if self.collectedData[1] not in commandCodes.keys():
                    logging.warning(f"> 2 < 1000 - self.collectedData - Invalid command code: {self.collectedData[1]} not in command code keys {commandCodes.keys()}")
                    self.collectedData.pop(0)
                else:
                    needMoreData = []
                    foundResponse = False
                    for request in unclaimedRequests:
                        needMoreData.append(False)
                        if self.collectedData[:2] == request[:2]:
                            if len(self.collectedData) >= 3 and len(self.collectedData) >= (int(self.collectedData[2], 16) + 5):
                                if self.crc16(bytearray.fromhex("".join(self.collectedData[:(int(self.collectedData[2], 16) + 5)]))) == b'\x00\x00':
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
                                    with foundPairsLock:
                                        foundPairs = get_json_lock(foundPairsFilePath, config=False)
                                        foundPairs.append({
                                            "uuid": sQLUUId,
                                            "port": self.port,
                                            "deviceId": deviceID,
                                            "request": foundPairRequest,
                                            "response": foundPairResponse,
                                            "time": sQLTime.isoformat()
                                        })
                                        if len(foundPairs) > 20:
                                            foundPairs.pop(0)
                                        save_json_config(foundPairsFilePath, foundPairs, config=False)
                                    communications[sQLUUId] = {"id": sQLId, "call": sQLCall, "time": sQLTime}
                                    self.addToDB(sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime)
                                    with countsLock:
                                        countsFile = get_json_lock(countsFilePath, config=False)
                                        countsFile["total"] += 1
                                        if deviceID not in countsFile[self.port]:
                                            countsFile[self.port][deviceID] = 0
                                        countsFile[self.port][deviceID] += 1
                                        save_json_config(countsFilePath, countsFile, config=False)
                                    unclaimedRequests.pop(unclaimedRequests.index(request))
                                    self.collectedData = self.collectedData[(int(self.collectedData[2], 16) + 5):]
                                    foundResponse = True
                                    break
                            else:
                                needMoreData[-1] = True

                    if foundResponse:
                        continue

                    if len(self.collectedData) >= commandCodes[self.collectedData[1]]:
                        proposedRequest = self.collectedData[:commandCodes[self.collectedData[1]]]
                        crcString = bytearray.fromhex("".join(proposedRequest))
                        if self.crc16(crcString) == b'\x00\x00':
                            unclaimedRequests.append(proposedRequest)
                            if len(unclaimedRequests) > 20:
                                unclaimedRequests.pop(0)
                            self.collectedData = self.collectedData[commandCodes[self.collectedData[1]]:]
                        else:
                            if not any(needMoreData):
                                self.collectedData.pop(0)
        except Exception as e:
            logging.error(f"Error with running the Data Processor on port {self.port}:\n{traceback.format_exc()}\n{e}\nExiting Data Processor Execution")
            self.fetcher.setExit()
            if self.fetcher.is_alive():
                self.fetcher.join()
            self.exit.set()

    def crc16(self, data: bytes):
        crc = 0xffff
        for cur_byte in data:
            crc = crc ^ cur_byte
            for _ in range(8):
                a = crc
                carry_flag = a & 0x0001
                crc = crc >> 1
                if carry_flag == 1:
                    crc = crc ^ 0xa001
        return bytes([crc % 256, crc >> 8 % 256])

    def setExit(self):
        self.exit.set()
        self.fetcher.setExit()

class ProcessingController:
    def __init__(self, listeningPorts):
        self.exit = Event()
        self.identity = []
        self.processors = []
        self.tcpServers = []
        self.addToDBQueue = deque()
        self.addToMeasuresQueue = deque()
        self.siteDevices = None
        self.siteDevicesMTime = None
        self.templates = {}
        self.mapping = {}
        foundPairs = get_json_lock(foundPairsFilePath, config=False)
        foundPairs = []
        save_json_config(foundPairsFilePath, foundPairs, config=False)
        with countsLock:
            countsFile = get_json_lock(countsFilePath, config=False)
            countsFile["total"] = 0
            save_json_config(countsFilePath, countsFile, config=False)
        for port in listeningPorts:
            new_processor = DataProcessor(self.addToSQLDB, self.addToMeasures, port=port)
            new_processor.start()
            self.processors.append(new_processor)

    def addToSQLDB(self, sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime):
        self.addToDBQueue.append([sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime])

    def addToMeasures(self, startAddress, endAddress, response, port):
        self.addToMeasuresQueue.append([startAddress, endAddress, response, port])

    def run(self):
        while not self.exit.is_set():
            if bool(self.addToDBQueue):
                element = self.addToDBQueue.popleft()
                db.insert(element)
                for processor in self.processors:
                    if processor.exit.is_set():
                        processor.join(timeout=3)
        for processor in self.processors:
            processor.setExit()
            processor.join(timeout=3)
        logging.info("Exiting Controller")

    def setExit(self):
        self.exit.set()

    def quitAll(self, *args):
        self.setExit()

ports = sys.argv[1:]

workingDirectory = project_directory

if not os.path.isfile(foundPairsFilePath):
    with open(foundPairsFilePath, "w+") as f:
        f.write("[]")

if not os.path.isfile(serialStreamsFilePath):
    with open(serialStreamsFilePath, "w+") as f:
        f.write("{}")

if not os.path.isfile(countsFilePath):
    with open(countsFilePath, "w+") as f:
        f.write("{}")

argsDict = {"listeningPorts": ports if type(ports) == list else [ports]}

controller = ProcessingController(argsDict["listeningPorts"])
for sig in ('TERM', 'INT'):
    signal.signal(getattr(signal, f"SIG{sig}"), controller.quitAll)
controller.run()
