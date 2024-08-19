#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Simulated WiBotic Socket
Handle packet requests in a blocking / callback manner
Responses are simulated websocket messages
"""

__copyright__ = "Copyright 2022 WiBotic Inc."
__version__ = "0.1"
__email__ = "info@wibotic.com"
__status__ = "Technology Preview"

import asyncio
import datetime
import logging
import random
import shelve
import threading
from typing import (
    List,
    Optional,
    Union,
    Callable,
)

from helpers.wibotic.core import packettools as pt
from helpers.wibotic.interface.wiboticsocket import SynchronousWebsocketWrapper, WiboticSocket

log = logging.getLogger(__name__)


class SimulatedWebsocketWrapper(SynchronousWebsocketWrapper):
    def __init__(self, url: str, subprotocol: str, ping_timeout: Optional[int] = 20):
        """Create a new simulated WiBotic socket that handles requests in a blocking / callback manner
        The url should take the form of "ws://192.168.2.20/ws" for connecting to WiBotic systems
        """
        self.websocket_url = url
        self.connected: bool = False
        self._event_loop = None
        self._subprotocol = subprotocol
        self._ping_timeout = ping_timeout
        self.shelve_name = None
        self.param_map = {str(pt.DeviceID.TX): dict(), str(pt.DeviceID.RX_1): dict()}
        self.ext_param_map = {
            str(pt.DeviceID.TX): dict(),
            str(pt.DeviceID.RX_1): dict(),
        }
        self.active_param_map = {
            str(pt.DeviceID.TX): dict(),
            str(pt.DeviceID.RX_1): dict(),
        }
        self.staging_param_map = {
            str(pt.DeviceID.TX): dict(),
            str(pt.DeviceID.RX_1): dict(),
        }
        self.start_time = datetime.datetime.now()
        self.response_time = lambda: 0
        self._init_params()
        self._init_socket()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _init_params(self):
        self.param_map[str(pt.DeviceID.RX_1)][str(pt.ParamID.DevMACOUI)] = int(
            "34D954", 16
        )
        self.param_map[str(pt.DeviceID.TX)][str(pt.ParamID.DevMACOUI)] = int(
            "34D954", 16
        )

        # copy persistant params to active param map
        for device, params in self.param_map.items():
                for param, value in params.items():
                    self.active_param_map[device][param] = value

        self.active_param_map[str(pt.DeviceID.TX)][
            str(pt.ParamID.ConnectedDevices)
        ] = 0x01
        self.active_param_map[str(pt.DeviceID.TX)][str(pt.ParamID.ADCViewRate)] = 100
        self.active_param_map[str(pt.DeviceID.RX_1)][str(pt.ParamID.ADCViewRate)] = 100

    def _init_socket(self):
        self._init_complete = threading.Event()
        self._threaded_exception: BaseException = None
        self._my_thread = threading.Thread(target=self._async_start, daemon=True)
        self._my_thread.start()
        self._init_complete.wait()
        if self._threaded_exception is not None:
            raise self._threaded_exception
        if self.connected:
            log.debug("Thread Initialized")
        else:
            raise ConnectionError

    def _loop(self):
        if self._event_loop is None or self._event_loop.is_closed():
            self._event_loop = asyncio.new_event_loop()
        return self._event_loop

    def _send(self, data: Union[bytearray, memoryview]) -> int:
        """Send a bytearray via the websocket"""
        if self.connected:
            asyncio.run_coroutine_threadsafe(
                self._outgoing_messages.put(data), self._loop()
            )
            return len(data)
        raise ConnectionError

    def close(self) -> None:
        """Gracefully close the socket"""
        self.connected = False
        self._loop().call_soon_threadsafe(self._consumer_task.cancel)
        self._my_thread.join()
        if self._threaded_exception:
            raise self._threaded_exception

    def _async_start(self):
        try:
            self._loop().run_until_complete(self._connect())
            self._event_loop.close()
            self.connected = False
        except Exception as exc:
            log.exception(exc)
            self._threaded_exception = exc
        finally:
            self._init_complete.set()

    async def _connect(self):
        try:
            websocketIn = asyncio.Queue()
            websocketOut = asyncio.Queue()
            log.debug("Websocket Connected")
            self._outgoing_messages = asyncio.Queue()
            self.connected = True
            self._init_complete.set()
            self._consumer_task = asyncio.ensure_future(
                self._consumer_handler(websocketIn)
            )
            self._producer_task = asyncio.ensure_future(
                self._producer_handler(websocketOut)
            )
            self._sim_task = asyncio.ensure_future(
                self._sim_api(websocketOut, websocketIn)
            )
            self._adc_tx_task = asyncio.ensure_future(
                self._adc_update(pt.DeviceID.TX, websocketIn)
            )
            self._adc_rx_task = asyncio.ensure_future(
                self._adc_update(pt.DeviceID.RX_1, websocketIn)
            )
            done, pending = await asyncio.wait(
                [
                    self._consumer_task,
                    self._producer_task,
                    self._sim_task,
                    self._adc_rx_task,
                    self._adc_tx_task,
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            all_excs: List[BaseException] = []
            for task in done:
                try:
                    task_exc = task.exception()
                    log.error(task_exc)
                    all_excs.append(task_exc)  # Gather all exceptions
                    log.debug(task.result())
                except asyncio.CancelledError:
                    pass
            log.debug("Stopped")
            if all_excs:
                raise all_excs[0]  # Raise the only exception
        except Exception as exc:
            log.exception(exc)
            self._threaded_exception = exc

    async def _process_incoming_message(self, msg):
        pass

    async def _consumer_handler(self, websocket):
        while True:
            message = await websocket.get()
            log.debug("Data Received: %s", message)
            await self._process_incoming_message(message)

    async def _producer_handler(self, websocket):
        while True:
            message = await self._outgoing_messages.get()
            log.debug("Data Outgoing: %s", message)
            await websocket.put(message)

    async def _sim_api(self, requests, responses):
        while True:
            message = await requests.get()
            resp = self._handle_message(message)
            if not resp:
                continue
            await asyncio.sleep(self.response_time())
            await responses.put(resp)

    def _handle_message(self, message):
        request = pt.process_data(message)
        if isinstance(request, pt.RequestConnectionStatus):
            return pt.ConnectedDevices(
                self.active_param_map[str(pt.DeviceID.TX)][
                    str(pt.ParamID.ConnectedDevices)
                ]
            ).as_packet()
        elif isinstance(request, pt.ParamReadRequest):
            # Str wrapper for shelve encoding
            param = str(request.param)
            device = str(request.dest)

            # Check if Param exists or allowed at location or allowed on device
            if (
                request.param not in pt.ParamID
                or (request.location != pt.ParamLocation.ACTIVEPARAMSET
                and request.dest not in pt.PARAM_PERSISTABLE_MAP[request.param])
                or request.dest not in pt.PARAM_ACCESSIBLE_MAP[request.param]
            ):
                return pt.ParamUpdate(
                    request.dest,
                    request.param,
                    0,
                    pt.ParamStatus.INVALID_INPUT,
                    request.location,
                ).as_packet()
            if not self.check_device_connected(request.dest):
                return  # Unconnected device will never respond

            # Check location of requested param
            if request.location == pt.ParamLocation.NVM:
                params = (
                    shelve.open(f"{self.shelve_name}_params")
                    if self.shelve_name
                    else self.param_map
                )
            elif request.location == pt.ParamLocation.ACTIVEPARAMSET:
                params = self.active_param_map
            elif request.location == pt.ParamLocation.NVMSTAGING:
                params = self.staging_param_map

            # Get value
            if param not in params[device]:
                value = 0
            else:
                value = params[device][param]

            # Close shelf if applicable
            if isinstance(params, shelve.Shelf):
                params.close()
            return pt.ParamUpdate(
                request.dest,
                request.param,
                value,
                pt.ParamStatus.SUCCESS,
                request.location,
            ).as_packet()
        elif isinstance(request, pt.ParamWriteRequest):
            # Str wrapper for shelve encoding
            param = str(request.param)
            device = str(request.dest)

            # Check if Param exists or allowed at location or allowed on device
            if (
                request.param not in pt.ParamID
                or (request.location != pt.ParamLocation.ACTIVEPARAMSET
                and request.dest not in pt.PARAM_PERSISTABLE_MAP[request.param])
                or request.dest not in pt.PARAM_ACCESSIBLE_MAP[request.param]
                or not self.check_device_connected(request.dest)
            ):
                return pt.ParamResponse(
                    request.dest,
                    request.param,
                    pt.ParamStatus.INVALID_INPUT,
                    0,
                    request.location,
                ).as_packet()

            # Check location of requested param
            if request.location == pt.ParamLocation.NVM:
                params = (
                    shelve.open(f"{self.shelve_name}_params", writeback=True)
                    if self.shelve_name
                    else self.param_map
                )
            elif request.location == pt.ParamLocation.ACTIVEPARAMSET:
                params = self.active_param_map
            elif request.location == pt.ParamLocation.NVMSTAGING:
                params = self.staging_param_map

            # Set value
            params[device][param] = request.value

            # Close shelf if applicable
            if isinstance(params, shelve.Shelf):
                params.close()
            return pt.ParamResponse(
                request.dest,
                request.param,
                pt.ParamStatus.SUCCESS,
                request.value,
                request.location,
            ).as_packet()
        elif isinstance(request, pt.ParamStageRequest):
            # Str wrapper for shelve encoding
            param = str(request.param)
            device = str(request.dest)

            # Check if param exists and if param is persistable
            if (
                request.param not in pt.ParamID
                or request.dest not in pt.PARAM_PERSISTABLE_MAP[request.param]
                or not self.check_device_connected(request.dest)
            ):
                return pt.StageResponse(
                    request.dest, request.param, pt.ParamStatus.FAILURE
                ).as_packet()

            # Stage parameter (default to 0 if no value set)
            if param not in self.active_param_map[device]:
                self.active_param_map[device][param] = 0
            self.staging_param_map[device][param] = self.active_param_map[device][param]
            return pt.StageResponse(
                request.dest, request.param, pt.ParamStatus.SUCCESS
            ).as_packet()
        elif isinstance(request, pt.ParamCommitRequest):
            # Str wrapper for shelve encoding
            device = str(request.dest)

            if not self.check_device_connected(request.dest):
                return pt.CommitResponse(
                    request.dest, pt.ParamStatus.FAILURE
                ).as_packet()
            params = (
                shelve.open(f"{self.shelve_name}_params", writeback=True)
                if self.shelve_name
                else self.param_map
            )

            # Copy staged values to NVM
            for key, value in self.staging_param_map[device].items():
                params[device][key] = value

            # Close shelf if applicable
            if isinstance(params, shelve.Shelf):
                params.close()
            return pt.CommitResponse(request.dest, pt.ParamStatus.SUCCESS).as_packet()
        elif isinstance(request, pt.SubscribeRequest):
            pass
        elif isinstance(request, pt.UnsubscribeRequest):
            pass
        elif isinstance(request, pt.ExtendedWriteRequest):
            # Str wrapper for shelve encoding
            device = str(request.dest)

            if request.ext_id not in pt.ExtParamID or not self.check_device_connected(
                request.dest
            ):
                return pt.ExtendedParameterSetResponse(
                    request.dest,
                    request.ext_id,
                    pt.ParamStatus.INVALID_INPUT,
                    request.data,
                ).as_packet()
            params = (
                shelve.open(f"{self.shelve_name}_extparams", writeback=True)
                if self.shelve_name
                else self.ext_param_map
            )
            params[device][str(request.ext_id)] = request.data
            if isinstance(params, shelve.Shelf):
                params.close()
            return pt.ExtendedParameterSetResponse(
                request.dest, request.ext_id, pt.ParamStatus.SUCCESS, request.data
            ).as_packet()
        elif isinstance(request, pt.ExtendedReadRequest):
            # Str wrapper for shelve encoding
            device = str(request.dest)

            if request.ext_id not in pt.ExtParamID or not self.check_device_connected(
                request.dest
            ):
                return pt.ExtendedParameterResponse(
                    request.dest, request.ext_id, "".ljust(16).encode("utf-8")
                ).as_packet()
            params = (
                shelve.open(f"{self.shelve_name}_extparams")
                if self.shelve_name
                else self.ext_param_map
            )
            if str(request.ext_id) not in params[device]:
                value = b""
            else:
                value = params[device][str(request.ext_id)]
            if isinstance(params, shelve.Shelf):
                params.close()
            return pt.ExtendedParameterResponse(
                request.dest, request.ext_id, value.ljust(16)
            ).as_packet()
        else:
            log.debug("Unknown type: " + type(request))

    async def _adc_update(self, deviceID, websocketIn):
        while True:
            values = None
            if deviceID == pt.DeviceID.TX and self.check_device_connected(deviceID):
                values = {
                    pt.AdcID.Timestamp: int(
                        (datetime.datetime.now() - self.start_time).total_seconds()
                    ),
                    pt.AdcID.PacketCount: int(
                        datetime.datetime.now().microsecond // 1000
                    ),
                    pt.AdcID.ChargeState: random.choice(list(pt.TransmitterState)),
                    pt.AdcID.PowerLevel: random.randint(0, 255),
                    pt.AdcID.IMon5v: random.uniform(0.0, 255.0),
                    pt.AdcID.VMonGateDriver: random.uniform(0.0, 255.0),
                    pt.AdcID.IMonGateDriver: random.uniform(0.0, 255.0),
                    pt.AdcID.VMonPa: random.uniform(0.0, 255.0),
                    pt.AdcID.IMonPa: random.uniform(0.0, 255.0),
                    pt.AdcID.TMonPa: random.uniform(0.0, 255.0),
                    pt.AdcID.VMon48v: random.uniform(0.0, 255.0),
                    pt.AdcID.IMon48v: random.uniform(0.0, 255.0),
                    pt.AdcID.TMonAmb: random.uniform(0.0, 255.0),
                    pt.AdcID.RadioRSSI: random.randint(0, 255),
                    pt.AdcID.RadioQuality: random.randint(0, 255),
                    pt.AdcID.Flags: random.randint(0, 255),
                }
            elif deviceID == pt.DeviceID.RX_1 and self.check_device_connected(deviceID):
                values = {
                    pt.AdcID.Timestamp: int(
                        (datetime.datetime.now() - self.start_time).total_seconds()
                    ),
                    pt.AdcID.PacketCount: int(
                        datetime.datetime.now().microsecond // 1000
                    ),
                    pt.AdcID.ChargeState: random.choice(list(pt.ChargerState)),
                    pt.AdcID.Flags: random.randint(0, 255),
                    pt.AdcID.VMonBatt: random.uniform(0.0, 255.0),
                    pt.AdcID.VMonCharger: random.uniform(0.0, 255.0),
                    pt.AdcID.VRect: random.uniform(0.0, 255.0),
                    pt.AdcID.TBoard: random.uniform(0.0, 255.0),
                    pt.AdcID.ICharger: random.uniform(0.0, 255.0),
                    pt.AdcID.IBattery: random.uniform(0.0, 255.0),
                    pt.AdcID.TargetIBatt: random.uniform(0.0, 255.0),
                    pt.AdcID.RadioRSSI: random.randint(0, 255),
                    pt.AdcID.RadioQuality: random.randint(0, 255),
                }
            if values:
                await websocketIn.put(pt.ADCUpdate(deviceID, values).as_packet())
            await asyncio.sleep(
                self.active_param_map[str(deviceID)][str(pt.ParamID.ADCViewRate)] / 1000
            )

    def check_device_connected(self, deviceID: pt.DeviceID):
        """Returns true if device connected"""
        connectedDevices = self.active_param_map[str(pt.DeviceID.TX)][
            str(pt.ParamID.ConnectedDevices)
        ]
        return bool((connectedDevices >> (deviceID - 1)) & 0x01)


class SimulatedWiboticSocket(WiboticSocket, SimulatedWebsocketWrapper):
    """Wrapper to use simulated WebsocketWrapper with WiboticSocket"""

    def set_shelve_name(self, shelve_name: str):
        """Pass a shelf_name to save/load parameters to a shelf for persistence between sessions
        By default params are not saved between sessions"""
        self.shelve_name = shelve_name
        with shelve.open(f"{self.shelve_name}_params", writeback=True) as p:
            # If new shelve, fill out with structure
            if not p:
                p[str(pt.DeviceID.TX)] = dict()
                p[str(pt.DeviceID.RX_1)] = dict()

            # Grab any persisted params from in memory
            for device, params in self.param_map.items():
                for param, value in params.items():
                    p[device][param] = value

            # Update active and staging params
            for device, params in p.items():
                for param, value in params.items():
                    self.active_param_map[device][param] = value
                    self.staging_param_map[device][param] = value
        with shelve.open(f"{self.shelve_name}_extparams", writeback=True) as p:
            if not p:
                p[str(pt.DeviceID.TX)] = dict()
                p[str(pt.DeviceID.RX_1)] = dict()

    def set_response_time(self, time_func: Callable):
        """Sets response time function to time_func
        time_func will decide the amount of time in seconds the sim api will wait to respond
        Ex:
            set_response_time(lambda: 0)
            set_response_time(lambda: random.uniform(0.0, 20.0)"""
        self.response_time = time_func

    def set_oc_connected(self, connected: bool):
        """Sets the OC connection state to connected"""
        self.active_param_map[str(pt.DeviceID.TX)][str(pt.ParamID.ConnectedDevices)] = (
            connected << 1 | 0x1
        )
