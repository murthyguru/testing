#!/usr/bin/env python3
# coding=utf-8
""" WiBotic Socket
Handle packet requests in a blocking / callback manner
"""

__copyright__ = "Copyright 2023 WiBotic Inc."
__version__ = "0.1"
__email__ = "info@wibotic.com"
__status__ = "Technology Preview"

import asyncio
import functools
import io
import logging
import os
import threading
import time
import traceback
import queue
from contextlib import contextmanager
from typing import (
    IO,
    AnyStr,
    Awaitable,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from urllib.parse import urljoin
from zipfile import ZipExtFile, ZipFile

import requests
import websockets.client
import websockets.exceptions
from helpers.wibotic.core import packettools as wpt, packettype
from helpers.wibotic.util import connections, firmware

log = logging.getLogger(__name__)

_CallableT = TypeVar("_CallableT", bound=Callable)
_ExpectedResponseT = TypeVar("_ExpectedResponseT", bound=packettype.ParsedIncomingType)


def retryable(fn: _CallableT) -> _CallableT:
    """Retry the function retry kwarg times"""

    @functools.wraps(fn)
    def retry_n_times(*args, **kwargs):
        result = None
        last_exception = None
        for _ in range(kwargs.pop("retry", 1)):
            try:
                result = fn(*args, **kwargs)
                if result is not None:
                    return result
            except (WiboticSocket.Timeout, WiboticSocket.ParameterFailure) as e:
                last_exception = e
        if result is not None:
            return result
        raise last_exception

    return retry_n_times  # type: ignore # see https://github.com/python/mypy/issues/1927


class SynchronousWebsocketWrapper:
    class Timeout(TimeoutError):
        """The process did not complete in the required time"""

    def __init__(self, url: str, subprotocol: str, ping_timeout: Optional[int] = 20):
        """Create a new WiBotic socket that handles requests in a blocking / callback manner
        The url should take the form of "ws://192.168.2.20/ws" for connecting to WiBotic systems"""
        self.websocket_url = url
        self.connected: bool = False
        self._event_loop = None
        self._subprotocol = subprotocol
        self._ping_timeout = ping_timeout
        self._init_socket()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _init_socket(self):
        self._init_complete = threading.Event()
        self._threaded_exception: BaseException = None
        self._my_thread = threading.Thread(
            target=self._async_start,
            daemon=True,
            name=f'WiboticSocket - {self.websocket_url}'
        )
        self._my_thread.start()
        self._init_complete.wait()
        if self._threaded_exception is not None:
            raise self._threaded_exception
        if self.connected:
            log.info("Thread Initialized")
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
            websocket = await asyncio.wait_for(
                websockets.client.connect(
                    self.websocket_url,
                    subprotocols=[self._subprotocol],
                    close_timeout=2,
                    ping_timeout=self._ping_timeout,
                ),
                timeout=2,
            )
        except (
            asyncio.TimeoutError,
            OSError,
            websockets.exceptions.InvalidHandshake,
        ) as exc:
            log.error("%s connecting to %s", repr(exc), self.websocket_url)
            return

        try:
            log.debug("Websocket Connected")
            self._outgoing_messages = asyncio.Queue()
            self.connected = True
            self._init_complete.set()
            self._consumer_task = asyncio.ensure_future(
                self._consumer_handler(websocket)
            )
            self._producer_task = asyncio.ensure_future(
                self._producer_handler(websocket)
            )
            done, pending = await asyncio.wait(
                [self._consumer_task, self._producer_task],
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
        except (OSError, websockets.exceptions.InvalidMessage) as exc:
            log.exception(exc)
        except websockets.exceptions.ConnectionClosed as exc:
            log.error(exc)
        except websockets.exceptions.InvalidStatusCode as exc:
            if exc.status_code == 502:
                log.error("Too many connections to %s", self.websocket_url)
            else:
                log.exception(exc)
                self._threaded_exception = exc
        except Exception as exc:
            log.exception(exc)
            self._threaded_exception = exc
        finally:
            await websocket.close()

    async def _process_incoming_message(self, msg):
        pass

    async def _consumer_handler(self, websocket: websockets.client.WebSocketClientProtocol):
        while True:
            message = await websocket.recv()
            log.debug("Data Received: %s", message)
            asyncio.ensure_future(self._process_incoming_message(message))

    async def _producer_handler(self, websocket: websockets.client.WebSocketClientProtocol):
        while True:
            message = await self._outgoing_messages.get()
            log.debug("Data Outgoing: %s", message)
            await websocket.send(bytes(message))


class WiboticSocket(SynchronousWebsocketWrapper):
    class ParameterTimeout(SynchronousWebsocketWrapper.Timeout):
        """The parameter request was not answered in time"""

    class ParameterFailure(Exception):
        """The parameter request had an error"""

    class ParameterNotAuthorized(ParameterFailure):
        """The parameter request was not authorized"""

    class ParameterInvalidInput(ParameterFailure):
        """The parameter request contained invalid input"""

    def __init__(self, url: str, ping_timeout: Optional[int] = 20):
        self._incoming_message_callback = None
        self._wibotic_packet_handlers: Dict[
            Type[packettype.ParsedIncomingType], Set[Callable]
        ] = {}
        self._wibotic_topic_subscriptions: Set[wpt.Topic] = set()
        self._param_lock = threading.Lock()  # 1 pending param request per connection
        super().__init__(url, "wibotic", ping_timeout)

    async def _process_incoming_message(self, msg):
        try:
            processed_message = wpt.process_data(msg)
        except Exception:
            log.error(traceback.print_exc())
            return
        specific_handlers = []
        try:
            specific_handlers = self._wibotic_packet_handlers[type(processed_message)]
        except KeyError:
            log.debug("No Specific handler for incoming %s packet", type(processed_message))
        try:
            await asyncio.gather(
                *[self._incoming_message_callback(processed_message)] if self._incoming_message_callback is not None else [], # Global Message Callback
                *[fn(processed_message) for fn in specific_handlers], # Specific Message Callbacks
            )
        except Exception:
            log.exception("Exception occurred in registered message callback")

    @contextmanager
    def temporary_handler(
        self,
        packet_type: Type[_ExpectedResponseT],
        fn: Callable[[_ExpectedResponseT], Awaitable[None]],
    ) -> Generator[None, None, None]:
        """Registers an async decorated function to be called when a given
        packet type is received and unregisters when context is exited"""
        try:
            self.register_handler(packet_type, fn)
            yield
        finally:
            self.unregister_handler(packet_type, fn)

    def register_handler(
        self,
        packet_type: Type[_ExpectedResponseT],
        fn: Callable[[_ExpectedResponseT], Awaitable[None]],
    ) -> None:
        """Registers an async decorated function to be called when a given
        packet type is received"""
        log.debug("Registering handler for %s", packet_type)
        asyncio.run_coroutine_threadsafe(
            self._register_handler(packet_type, fn), self._loop()
        )

    def unregister_handler(
        self,
        packet_type: Type[_ExpectedResponseT],
        fn: Callable[[_ExpectedResponseT], Awaitable[None]],
    ) -> None:
        """Unregisters an async decorated function to be called when a given
        packet type is received"""
        log.debug("Removing handler for %s", packet_type)
        asyncio.run_coroutine_threadsafe(
            self._unregister_handler(packet_type, fn), self._loop()
        )

    async def _register_handler(self, packet_type, fn):
        self._wibotic_packet_handlers.setdefault(packet_type, set())
        self._wibotic_packet_handlers[packet_type].add(fn)
        log.debug("Handler registered for %s", packet_type)

    async def _unregister_handler(self, packet_type, fn):
        try:
            self._wibotic_packet_handlers[packet_type].remove(fn)
            if len(self._wibotic_packet_handlers[packet_type]) == 0:
                del self._wibotic_packet_handlers[packet_type]
            log.debug("Handler unregistered for %s", packet_type)
            return True
        except KeyError:
            return False

    def register_complete_handler(
        self, fn: Callable[[packettype.ParsedIncomingType], Awaitable[None]]
    ) -> None:
        """Registers a single async decorated function to be called when any
        packet is received. Will overwrite last registered function. Set to None
        to disable"""
        log.debug("Registering handler for all packets")
        asyncio.run_coroutine_threadsafe(
            self._register_complete_handler(fn), self._loop()
        )

    async def _register_complete_handler(self, fn):
        self._incoming_message_callback = fn

    def reconnect(self) -> None:
        """Attempt a reconnection of the WiboticSocket"""
        log.info('attempting reconnection')
        if self.connected:
            self.close()
        self._init_socket()
        for topic in self._wibotic_topic_subscriptions:
            self._subscribe_to_topic(topic)

    def subscribe_to_topic(self, topic: wpt.Topic):
        self._wibotic_topic_subscriptions.add(topic)
        self._subscribe_to_topic(topic)

    def _subscribe_to_topic(self, topic: wpt.Topic):
        subscribe_req = packettype.SubscribeRequest(topic)
        self._send(subscribe_req.as_packet())

    def unsubscribe_from_topic(self, topic: wpt.Topic):
        try:
            self._wibotic_topic_subscriptions.remove(topic)
            unsubscribe_req = packettype.UnsubscribeRequest(topic)
            self._send(unsubscribe_req.as_packet())
        except KeyError:
            log.warning("No topic: %s", topic)

    def get_devices(self, timeout: float = 1.0) -> Set[wpt.DeviceID]:
        """Send a request to get which devices are connected to the transmitter
        that the websocket is connected to and waits for a response. This is similar
        to getting ParamID.ConnectedDevices. The difference is that this will cause
        a ConnectedDevices packet to be sent and any callbacks involving it to be
        triggered."""
        request = packettype.RequestConnectionStatus()
        response = self._send_wait_response(
            request.as_packet(), packettype.ConnectedDevices, timeout=timeout
        )
        return response.devices

    def set_parameter(
        self,
        destination: wpt.DeviceID,
        parameter: wpt.ParamID,
        data,
        location: wpt.ParamLocation = wpt.ParamLocation.ACTIVEPARAMSET,
        timeout: float = 1.0,
    ) -> packettype.ParamResponse:
        """Attempts to set the given parameter with data on the specified
        destination. Raises ParameterFailure if set was not successful.
        Note that NVM locations cannot be written directly and must be
        staged first."""
        param_data_request = packettype.ParamWriteRequest(destination, parameter, data, location)
        try:
            response = self._send_wait_response(
                param_data_request.as_packet(),
                packettype.ParamResponse,
                lambda data: data.param == parameter,
                timeout=timeout,
            )
        except self.Timeout:
            raise WiboticSocket.ParameterTimeout from None
        if not self._check_status_ok(response.status):
            raise WiboticSocket.ParameterFailure(response)
        return response

    def get_parameter(
        self,
        destination: wpt.DeviceID,
        parameter: wpt.ParamID,
        location: wpt.ParamLocation = wpt.ParamLocation.ACTIVEPARAMSET,
        timeout: float = 1.0,
    ) -> packettype.ParamUpdate:
        """Attempts to get the given parameter from the specified destination"""
        param_data_request = packettype.ParamReadRequest(destination, parameter, location)
        try:
            response = self._send_wait_response(
                param_data_request.as_packet(),
                packettype.ParamUpdate,
                lambda data: data.param == parameter,
                timeout=timeout,
            )
        except self.Timeout:
            raise WiboticSocket.ParameterTimeout from None
        if not self._check_status_ok(response.status):
            if response.status == wpt.ParamStatus.NOT_AUTHORIZED:
                raise WiboticSocket.ParameterNotAuthorized(response)
            if response.status == wpt.ParamStatus.INVALID_INPUT:
                raise WiboticSocket.ParameterInvalidInput(response)
            raise WiboticSocket.ParameterFailure(response)
        return response

    def stage_parameter(
        self, destination: wpt.DeviceID,
        parameter: wpt.ParamID,
        timeout: float = 1.0,
    ) -> packettype.StageResponse:
        """Stages the given parameter for later commit into non-volatile storage"""
        param_data_request = packettype.ParamStageRequest(destination, parameter)
        try:
            response = self._send_wait_response(
                param_data_request.as_packet(),
                packettype.StageResponse,
                lambda data: data.param == parameter,
                timeout=timeout,
            )
        except self.Timeout:
            raise WiboticSocket.ParameterTimeout from None
        if not self._check_status_ok(response.status):
            raise WiboticSocket.ParameterFailure(response)
        return response

    def commit_parameters(
        self,
        destination: wpt.DeviceID,
        timeout: float = 3.0,
    ) -> packettype.CommitResponse:
        """Commits pending staged parameters into non-volatile storage"""
        param_data_request = packettype.ParamCommitRequest(destination)
        try:
            response = self._send_wait_response(
                param_data_request.as_packet(),
                packettype.CommitResponse,
                timeout=timeout,
            )
        except self.Timeout:
            raise WiboticSocket.ParameterTimeout from None
        if not self._check_status_ok(response.status):
            raise WiboticSocket.ParameterFailure(response)
        return response

    @retryable
    def set_extended_parameter(
        self, destination: wpt.DeviceID,
        parameter: wpt.ExtParamID,
        data,
        timeout: float = 3.0,
    ) -> packettype.ExtendedParameterSetResponse:
        """Attempts to set the given extended parameter with data on the specified
        destination. Raises ParameterFailure if set was not successful."""
        param_data_request = packettype.ExtendedWriteRequest(destination, parameter, data)
        try:
            response = self._send_wait_response(
                param_data_request.as_packet(),
                packettype.ExtendedParameterSetResponse,
                lambda data: data.ext_id == parameter,
                timeout=timeout,
            )
        except self.Timeout:
            raise WiboticSocket.ParameterTimeout from None
        if not self._check_status_ok(response.status):
            raise WiboticSocket.ParameterFailure(response)
        return response

    @retryable
    def get_extended_parameter(
        self,
        destination: wpt.DeviceID,
        parameter: wpt.ExtParamID,
        timeout: float = 1.0,
    ) -> packettype.ExtendedParameterResponse:
        """Attempts to get the given extended parameter from the specified destination"""
        param_data_request = packettype.ExtendedReadRequest(destination, parameter)
        try:
            response = self._send_wait_response(
                param_data_request.as_packet(),
                packettype.ExtendedParameterResponse,
                lambda data: data.ext_id == parameter,
                timeout=timeout,
            )
            if response.data == b"":
                raise WiboticSocket.ParameterFailure(response)
        except self.Timeout:
            raise WiboticSocket.ParameterTimeout from None
        return response

    def _send_wait_response(
        self,
        send_data: bytearray,
        expected_response_type: Type[_ExpectedResponseT],
        expected_response_attr_check: Callable[[_ExpectedResponseT], bool] = None,
        timeout: float = 1.0,
    ) -> _ExpectedResponseT:
        if not self.connected:
            raise ConnectionError

        got_response = threading.Condition(self._param_lock)
        response = None

        async def process_param(data):
            if (
                expected_response_attr_check is not None
                and not expected_response_attr_check(data)
            ):
                log.warning("Unexpected Result")
                return
            with got_response:
                nonlocal response
                response = data
                got_response.notify()
            log.debug("WiBotic System Responded:\n%s", data)

        with got_response:  # Acquire before registering callback
            with self.temporary_handler(expected_response_type, process_param):
                self._send(send_data)
                got_response.wait(1000)

        if response is None and expected_response_type is not None:
            raise WiboticSocket.Timeout
        return response

    def get_next_adc(self, device: wpt.DeviceID, timeout: int = 1) -> packettype.ADCUpdate:
        """Returns the next ADC packet sent by the specified device. Blocks until this occurs or timeout"""
        if not self.connected:
            raise ConnectionError

        got_response = threading.Condition()
        response = None

        async def adc_watcher(adc: packettype.ADCUpdate):
            if adc.device == device:
                with got_response:
                    nonlocal response
                    response = adc
                    got_response.notify()
                log.debug("WiBotic system sent an ADC packet - unblocked")

        with got_response:
            with self.temporary_handler(packettype.ADCUpdate, adc_watcher):
                got_response.wait(timeout)

        if response is None:
            raise WiboticSocket.Timeout
        return response

    def read_device_fw_rev(self, device: wpt.DeviceID) -> Tuple[int, str]:
        """Returns the device's firmware (hash, name)"""
        return (
            self.get_parameter(device, wpt.ParamID.BuildHash).value,
            self.get_extended_parameter(device, wpt.ExtParamID.FwRevName).parse().name,
        )

    def read_stored_fw_rev(self) -> Tuple[int, int, str, str]:
        """Returns the stored firmware as a namedtuple
        (tx_build_hash, rx_build_hash, tx_fw_name, rx_fw_name)"""
        return self.get_extended_parameter(
            wpt.DeviceID.TX, wpt.ExtParamID.StoredOTAInfo
        ).value

    def _ota_state_wait(
        self, messages: queue.Queue, state: wpt.OtaState, timeout: float = 60
    ) -> Optional[wpt.OtaState]:
        """Takes a queue of IncomingOTAStatus messages and waits until a state other than the given
        state is recieved, or timeout after the given number of seconds since the last message have passed
        Returns the last received status or None if timeout"""
        while True:
            try:
                update = messages.get(timeout=timeout)
            except queue.Empty:
                return None
            status = update.state
            if status != state:
                return status

    def rescue_oc(
        self, mac: int, progress_callback: Optional[Callable[[float], None]] = None
    ) -> Optional[wpt.OtaState]:
        """Rescue a charger that disconnected in the middle of an update and did not reconnect normally
        Returns final OtaState received
        mac: last six hexadecimal digits of the OC's MAC address
        progress_callback: optional, is called and passed a percent to completion"""
        completion = 0
        messages: queue.Queue[packettype.IncomingOTAStatus] = queue.Queue()
        states = [
            wpt.OtaState.WRITING_RX_APP,
            wpt.OtaState.FINALIZING,
            wpt.OtaState.APP_COMPLETE,
        ]

        async def ota_callback(data: packettype.IncomingOTAStatus):
            nonlocal completion
            completion = data.completion
            if progress_callback:
                progress_callback(completion)
            messages.put(data)

        self.register_handler(packettype.IncomingOTAStatus, ota_callback)
        self.subscribe_to_topic(wpt.Topic.UPDATE_PROGRESS)

        self.set_parameter(wpt.DeviceID.TX, wpt.ParamID.RadioConnectionRequest, mac)
        self.set_parameter(
            wpt.DeviceID.TX, wpt.ParamID.UpdaterMode, 1
        )  # Send OTA Beacons
        self.set_parameter(
            wpt.DeviceID.TX, wpt.ParamID.OtaCtrl, wpt.OtaCtrl.START_RX_APP
        )

        for index in range(len(states) - 1):
            status = self._ota_state_wait(messages, states[index])
            if status != states[index + 1]:
                break

        self.unregister_handler(packettype.IncomingOTAStatus, ota_callback)
        return status

    @staticmethod
    def _check_status_ok(status: wpt.ParamStatus) -> bool:
        return status in (wpt.ParamStatus.SUCCESS, wpt.ParamStatus.NON_CRITICAL_FAIL)


class WiboticAuxStream(SynchronousWebsocketWrapper, io.RawIOBase):
    def __init__(self, websocket_url: str, ping_timeout: Optional[int] = None) -> None:
        self.read_pipe_fd, self.write_pipe_fd = os.pipe()
        super().__init__(websocket_url, "wibotic.serial", ping_timeout)

    def _close_pipe(self):
        if self.read_pipe_fd:
            try:
                os.close(self.read_pipe_fd)
                os.close(self.write_pipe_fd)
            except OSError:
                pass
        self.read_pipe_fd = None
        self.write_pipe_fd = None

    def __exit__(self, *_exc):
        SynchronousWebsocketWrapper.__exit__(self, *_exc)
        self._close_pipe()

    def __del__(self):
        self._close_pipe()

    def close(self):
        SynchronousWebsocketWrapper.close(self)
        self._close_pipe()

    def read(self, n: int = -1) -> bytes:
        """Reads specified number of bytes from the socket. Attempts to read an infinite
        number of bytes until the connection closes if not specified."""
        if self.read_pipe_fd is None:  # Connection closed
            return b""  # EOF
        if n == -1:
            return self.readall()
        return os.read(self.read_pipe_fd, n)

    def readinto(self, b: Union[bytearray, memoryview]) -> int:  # type: ignore # supports most of ReadableBuffer
        msg = self.read(len(b))
        b[: len(msg)] = msg
        return len(msg)

    def read_n_bytes(self, n_bytes):
        """Helper method to return when exactly n_bytes have been received"""
        rx_bytes = bytearray(n_bytes)
        byte_view = memoryview(rx_bytes)
        got_bytes = 0
        while got_bytes < n_bytes:
            read_len = self.readinto(byte_view[got_bytes:])
            if read_len == 0:
                return bytes(rx_bytes[:got_bytes])
            got_bytes += read_len
        return bytes(rx_bytes)

    def write(self, b: Union[bytearray, memoryview]) -> int:  # type: ignore # supports most of WritableBuffer
        return self._send(b)

    def readable(self) -> bool:
        return self.connected

    def writable(self) -> bool:
        return self.connected

    async def _process_incoming_message(self, msg):
        os.write(self.write_pipe_fd, msg)


class OTAError(Exception):
    """An OTA based Error."""


class WiboticHTTP:
    def __init__(self, address: str, ws: WiboticSocket) -> None:
        """Create a new WiBotic Http connection that handles requests in a blocking / callback manner
        The url should take the form of "192.168.2.20" for connecting to WiBotic systems"""
        self._address = address
        self._TR_ADDRESS_HTTP = f"http://{self._address}/"
        self.ws = ws

    class _logging_file_upload_generator:
        """Allows logging and streaming of uploads"""

        def __init__(
            self,
            file: ZipExtFile,
            file_size: int,
            progress_callback: Optional[Callable[[float], None]] = None,
        ):
            self.file = file
            self.file_size = file_size
            self.progress_callback = progress_callback
            self.data_read = 0

        def __iter__(self):
            while data == self.file.read(2 ** (8 * 2)):
                if self.progress_callback:
                    self.progress_callback(
                        progress=100 * self.data_read / self.file_size
                    )
                self.data_read += len(data)
                yield data

        def __len__(self):
            return self.file_size

    class _iterable_to_file_adapter:
        def __init__(self, iterable):
            self.iterator = iter(iterable)
            self.length = len(iterable)

        def read(self, size=-1):
            return next(self.iterator, b"")

        def __len__(self):
            return self.length

    def upload_firmware(
        self,
        file: Union[AnyStr, os.PathLike, IO[bytes]],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Upload firmware to the WiBotic TR
        Optionally, progress_callback is called and passed a percent to completion"""
        ota_firmware = self.ws.read_stored_fw_rev()
        target_fw_hash, target_fw_name = firmware.read_firmware_rev(
            file, wpt.DeviceID.TX
        )
        log.info(f"Stored Firmware version: {ota_firmware.tx_fw_name}")
        if ota_firmware.tx_build_hash == (target_fw_hash >> 128):
            return
        log.info("Uploading Firmware...")
        with ZipFile(file) as archive:
            for filename in archive.namelist():
                file_size = archive.getinfo(filename).file_size
                log.info(f"  Uploading {filename}...")
                with archive.open(filename) as firmware_file:
                    try:
                        response = requests.post(
                            urljoin(self._TR_ADDRESS_HTTP, "ingestupdate"),
                            data=self._iterable_to_file_adapter(
                                self._logging_file_upload_generator(
                                    firmware_file, file_size, progress_callback
                                )
                            ),
                            headers={"Content-Type": "application/octet-stream"},
                        )
                    except ConnectionError:
                        raise ConnectionError(
                            "Confirm that the SD card is inserted, then power-cycle the TR."
                        )
                    if response.status_code != requests.codes.ok:
                        raise OTAError(
                            f"Firmware Upload Failed. Code: {response.status_code}"
                        )

    def upload_firmware_from_link(
        self, url: AnyStr, progress_callback: Optional[Callable[[float], None]] = None
    ) -> None:
        """Upload firmware to the WiBotic TR from a download url
        Optionally, progress_callback is called and passed a percent to completion"""
        log.info("Downloading Firmware...")
        req = requests.get(url, stream=True, timeout=3)
        # Load OTA Firmware
        log.info("Uploading Firmware...")
        with io.BytesIO(req.content) as file:
            self.upload_firmware(file, progress_callback)

    def update_using_loaded_firmware(
        self,
        device: wpt.DeviceID,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Updates device to firmware version stored on the WiBotic TR
        Optionally, progress_callback is called and passed a percent to completion"""
        log.info("Updating Firmware...")
        target_fw_hash = (
            self.ws.read_stored_fw_rev().tx_build_hash
            if device == wpt.DeviceID.TX
            else self.ws.read_stored_fw_rev().rx_build_hash
        )
        dev_fw_hash, dev_fw_name = self.ws.read_device_fw_rev(device)
        if dev_fw_hash == target_fw_hash:
            return  # Firmware already updated to target version
        completion = 0
        messages: queue.Queue[packettype.IncomingOTAStatus] = queue.Queue()

        tx_state_timeouts = {
            wpt.OtaState.INITIALIZING: 12,
            wpt.OtaState.WRITING_TX_SHIM: 2,
        }
        rx_state_timeouts = {
            wpt.OtaState.INITIALIZING: 12,
            wpt.OtaState.WRITING_RX_SHIM: 12,
            wpt.OtaState.WRITING_RX_APP: 2,
            wpt.OtaState.FINALIZING: 20,
            wpt.OtaState.APP_COMPLETE: 20,
        }

        async def ota_callback(data: packettype.IncomingOTAStatus):
            nonlocal completion
            completion = data.completion
            if progress_callback:
                progress_callback(completion)
            messages.put(data)

        try:
            self.ws.register_handler(packettype.IncomingOTAStatus, ota_callback)
            self.ws.subscribe_to_topic(wpt.Topic.UPDATE_PROGRESS)
            ota_ctrls = {
                wpt.DeviceID.TX: wpt.OtaCtrl.START_TX_SHIM,
                wpt.DeviceID.RX_1: wpt.OtaCtrl.START_RX_SHIM,
            }
            self.ws.set_parameter(
                wpt.DeviceID.TX, wpt.ParamID.OtaCtrl, ota_ctrls[device]
            )

            if device == wpt.DeviceID.TX:
                for index in range(len(tx_state_timeouts) - 1):
                    status = self.ws._ota_state_wait(
                        messages,
                        list(tx_state_timeouts)[index],
                        list(tx_state_timeouts.values())[index],
                    )
                    if status != list(tx_state_timeouts)[index + 1]:
                        break
                self._finish_ota_tr()
            elif device == wpt.DeviceID.RX_1:
                for index in range(len(rx_state_timeouts) - 1):
                    status = self.ws._ota_state_wait(
                        messages,
                        list(rx_state_timeouts)[index],
                        list(rx_state_timeouts.values())[index],
                    )
                    if status != list(rx_state_timeouts)[index + 1]:
                        break
                    if index == 1:
                        log.info("Waiting for device to reboot...")
                    elif index == 2:
                        log.info("Continuing Update...")
                    elif index == 3:
                        log.info("Waiting for device to reboot...")
                connections._wait_for_oc_connect(
                    self.ws, timeout_sec=20
                )  # Finish bootup
            else:
                raise TypeError(f"device type {device} unknown")
        except (ConnectionError, TimeoutError) as exc:
            raise OTAError(f"Update stopped at progress: {completion}%") from exc

        self.ws.unregister_handler(packettype.IncomingOTAStatus, ota_callback)
        target_fw_hash = (
            self.ws.read_stored_fw_rev().tx_build_hash
            if device == wpt.DeviceID.TX
            else self.ws.read_stored_fw_rev().rx_build_hash
        )
        updated_dev_fw_hash, updated_dev_fw_name = self.ws.read_device_fw_rev(device)
        if updated_dev_fw_hash != target_fw_hash:
            raise OTAError(f"Unexpected Firmware Version {updated_dev_fw_name}")

    def _finish_ota_tr(self):
        time.sleep(12)  # Reboot & Network Restart Allowance
        for _ in range(10):  # Reconnect attempts max, most likely will reconnect
            log.info("Rebooting...")
            try:
                self.ws.reconnect()
                if self.ws.get_parameter(
                    wpt.DeviceID.TX, wpt.ParamID.TargetFirmwareId
                ).value in [
                    0x301,
                    0x302,
                ]:
                    log.debug("Reconnected in shim mode. Trying again.")
                    raise ConnectionError
                log.info("Reconnected")
                break
            except (ConnectionError, self.ws.ParameterTimeout):
                time.sleep(2)
        else:
            raise ConnectionError("Unable to reconnect to TR.")

    def upload_and_upgrade_firmware(
        self,
        device_id: wpt.DeviceID,
        firmware_path: Union[AnyStr, os.PathLike],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Upload firmware to the WiBotic TR and update device to uploaded version
        Optionally, progress_callback is called and passed a percent to completion"""
        dev_fw_hash, dev_fw_name = self.ws.read_device_fw_rev(device_id)
        target_fw_hash, target_fw_name = firmware.read_firmware_rev(
            firmware_path, device_id
        )
        log.info(f"Current Firmware on {device_id.name}: {dev_fw_name}")
        if dev_fw_hash != (target_fw_hash >> 128):
            log.info("Uploading Firmware...")
            self.upload_firmware(firmware_path, progress_callback)
            self.update_using_loaded_firmware(device_id, progress_callback)
        log.info("Device firmware is up to date")
