import os
import json
import time
import datetime
import serial
import binascii
import signal
import fasteners
import traceback

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server.sync import StartTcpServer
from pymodbus.version import version

from threading import Thread, Event, Lock
from collections import deque

from helpers.common import printd, printe, get_json_lock, save_json_config
from background.modbus_rtu_wiretap.datastore_v1 import WiretapStore as db, WiretapDTO

class DataFetch(Thread):

    def __init__ (self, port = "/dev/ttyS0"):

        Thread.__init__(self)

        self.exit = Event()
        self.port = port
        self.serialObject = serial.Serial(self.port)
        self.fetchedData = deque()

    def run (self):

        printd(f"Starting data fetcher for port {self.port}")

        while not(self.exit.is_set()):
                
            try:

                self.fetchedData.append(binascii.hexlify(self.serialObject.read()).decode("utf-8"))

            except Exception as e:

                continue

        self.serialObject.close()

        printd(f"Exiting data Fetcher for port {self.port}")

    def setExit (self):

        self.exit.set()

    def fetchData (self):

        dataCollected = []

        if not(self.exit.is_set()):

            while (len(self.fetchedData)):

               dataCollected.append(self.fetchedData.popleft())

        return dataCollected

class DataProcessor(Thread):

    def __init__ (self, threadId, serverContext, addToDB, clearInterval = 300, port = "/dev/ttyS0"):

        Thread.__init__(self)

        self.exit = Event()
        self.port = port
        self.fetcher = DataFetch(port = self.port)
        self.addToDB = addToDB
        self.threadId = threadId
        self.servContext = serverContext
        self.collectedData = []
        self.clearInterval = clearInterval

        with serialStreamLock:

            serialStreams = get_json_lock(serialStreamsFilePath, config = False)
            serialStreams[self.port] = []

            with fasteners.InterProcessLock(serialStreamsFilePath):

                save_json_config(serialStreamsFilePath, serialStreams, config = False)

        self.fetcher.start()

    def run (self):

        try:

            printd(f"Starting data processor for port {self.port}")

            commandCodes = {'01': 8, '02': 8, '03': 8, '04': 8, '05': 8, '06': 8, '0F': 11, '10': 13}
            
            communications = {}
            unclaimedRequests = []

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

                        with fasteners.InterProcessLock(serialStreamsFilePath):

                            save_json_config(serialStreamsFilePath, serialStreams, config = False)

                if (len(self.collectedData) < 8):

                    continue

                elif (len(self.collectedData) > 1000):

                    self.collectedData = []

                    printd(f"Update on port {self.port}:\nList became too long. Restarting Fetcher.")

                    self.fetcher.setExit()

                    if self.fetcher.is_alive():
                    
                        self.fetcher.join()

                    self.fetcher = DataFetch(port = self.port)
                    self.fetcher.start()

                    continue

                else:

                    if not(self.collectedData[1] in commandCodes.keys()):

                        self.collectedData.pop(0)

                    else:

                        if not(len(self.collectedData) >= commandCodes[self.collectedData[1]]):

                            continue

                        else:
                            
                            proposedRequest = self.collectedData[:commandCodes[self.collectedData[1]]]

                            crcString = bytearray([int(x, 16) for x in proposedRequest])

                            if (self.crc16(crcString) == b'\x00\x00'):
                                
                                unclaimedRequests.append(proposedRequest)
                                
                                self.collectedData = self.collectedData[commandCodes[self.collectedData[1]]:]
                                
                                printd(f"Port {self.port} Status Update: Starting main loop")
                                
                                break
                            
                            else:

                                self.collectedData.pop(0)

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

                        with fasteners.InterProcessLock(serialStreamsFilePath):

                            save_json_config(serialStreamsFilePath, serialStreams, config = False)

                for key, value in communications.items():

                    if ((datetime.datetime.now() - value["time"]).total_seconds() > self.clearInterval):

                        printd(f"Port {self.port} Status Update:\nResetting value in communications")

                        communications[key]["time"] = datetime.datetime.now()

                        printd(f"Working with key {key}")

                        self.servContext[value["id"]].store[self.servContext[value["id"]].decode(value["call"])].reset()

                if (len(self.collectedData) < 2):

                    continue

                if (len(self.collectedData) > 1000):

                    self.collectedData = []

                    printd(f"Update on port {self.port}:\nList became too long. Restarting Fetcher.")

                    self.fetcher.setExit()

                    if self.fetcher.is_alive():
                    
                        self.fetcher.join()

                    self.fetcher = DataFetch(port = self.port)
                    self.fetcher.start()

                    continue

                if not(self.collectedData[1] in commandCodes.keys()):

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

                                    deviceID = int(request[0], 16)
                                    requestCall = int(request[1], 16)
                                    dataStartAddress = int((request[2] + request[3]), 16)

                                    if not(self.servContext.__contains__(int(request[0], 16))):

                                        self.servContext.__setitem__(deviceID, ModbusSlaveContext())

                                    self.servContext[deviceID].setValues(requestCall, dataStartAddress, [int(response[x] + response[x + 1], 16) for x in range(3, (len(response) - 2), 2)])

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

                                        foundPairs = get_json_lock(foundPairsFilePath, config = False)
                                        foundPairs.append({
                                                    
                                                            "threadId": self.threadId,
                                                            "uuid": sQLUUId,
                                                            "port": self.port,
                                                            "deviceId": deviceID,
                                                            "request": foundPairRequest,
                                                            "response": foundPairResponse,
                                                            "time": sQLTime.isoformat()

                                                        })
                                        
                                        if (len(foundPairs) > 20):
                                                    
                                            foundPairs.pop(0)

                                        with fasteners.InterProcessLock(foundPairsFilePath):

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

    def setExit (self):

        self.exit.set()
        self.fetcher.setExit()

class TcpServerProcessing(Thread):

    def __init__ (self, context, identity, increment, port):

        Thread.__init__(self)

        self.exit = Event()
        self.port = port
        self.context = context
        self.identity = identity
        self.increment = increment
        self.maxPorts = 200

    def run (self):

        mapping = get_json_lock("wiretap_port_mapping")

        mapping[self.port] = (6502 + self.increment)

        with fasteners.InterProcessLock("/sos-config/wiretap_port_mapping.json"):

            save_json_config("wiretap_port_mapping", mapping)
        while (not(self.exit.is_set()) and (self.increment < self.maxPorts)):

            try:

                StartTcpServer(self.context, identity = self.identity, address = ("127.0.0.1", (6502 + self.increment)))

            except Exception as e:

                if (self.increment >= self.maxPorts):

                    printe("Could not find an open port from 6502 to 6602")

                    break

                self.increment = self.increment + 1

                mapping = get_json_lock("wiretap_port_mapping")

                mapping[self.port] = (6502 + self.increment)

                with fasteners.InterProcessLock("/sos-config/wiretap_port_mapping.json"):

                    save_json_config("wiretap_port_mapping", mapping)

            time.sleep(2)

        if (self.increment < self.maxPorts):

            printd(f"TCP Server created for serial port {self.port} on TCP port {(6502 + self.increment)}")

    def setExit (self):

        self.exit.set()

        printd(f"TCP Server Exited")

class ProcessingController:

    def __init__ (self, clearInterval, listeningPorts):

        Thread.__init__(self)

        self.exit = Event()
        self.contexts = []
        self.identity = []
        self.processors = []
        self.tcpServers = []
        self.addToDBQueue = deque()

        foundPairs = get_json_lock(foundPairsFilePath, config = False)
        foundPairs = []
        save_json_config(foundPairsFilePath, foundPairs, config = False)

        for i in range(0, len(listeningPorts)):

            self.contexts.append(ModbusServerContext(single = False))

            new_processor = DataProcessor(i, self.contexts[i], self.addToSQLDB, clearInterval = clearInterval, port = listeningPorts[i])
            new_processor.start()

            self.processors.append(new_processor)

            self.identity.append(ModbusDeviceIdentification())

            self.tcpServers.append(TcpServerProcessing(self.contexts[i], self.identity[i], i, listeningPorts[i]))
            self.tcpServers[i].start()

    def addToSQLDB (self, sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime):

        self.addToDBQueue.append([sQLUUId, sQLId, sQLCall, sQLPort, sQLRequest, sQLResponse, sQLTime])

    def run (self):

        while (not(self.exit.is_set())):

            if bool(self.addToDBQueue):

                element = self.addToDBQueue.popleft()

                db.insert(element)

                for processor in self.processors:

                    if (processor.exit.is_set()):

                        processor.join(timeout = 3)

        for processor in self.processors:

            processor.setExit()
            processor.join(timeout = 3)

        for tcpServer in self.tcpServers:

            tcpServer.setExit()
            tcpServer.join(timeout = 3)

        printd(f"Exiting Controller")

    def setExit (self):

        self.exit.set()

    def quitAll (self, *args):

        self.setExit()

params = get_json_lock("background")["modbus_rtu_wiretap"]["parameters"]

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

if ("clear_interval" in params):

    argsDict["clearInterval"] = params["clear_interval"]

if ("portRecieve" in params):

    if (type(params["portRecieve"]) == type([])):

        argsDict["listeningPorts"] = params["portRecieve"]

    else:

        argsDict["listeningPorts"] = [params["portRecieve"]]

controller = ProcessingController(argsDict["clearInterval"], argsDict["listeningPorts"])

for sig in ('TERM', 'HUP', 'INT', 'QUIT'):

    signal.signal(getattr(signal, f"SIG{sig}"), controller.quitAll)

controller.run()
