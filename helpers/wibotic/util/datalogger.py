import concurrent.futures
import csv
import logging
import time
from contextlib import contextmanager
from threading import Event
from typing import Any, Callable, Dict, List, Optional, TextIO, Union, TYPE_CHECKING

from helpers.wibotic.core import packettools as wpt, packettype

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from wibotic.can import WiboticCANNode
    from helpers.wibotic.interface.wiboticsocket import WiboticSocket

LogRecord = Dict[str, Any]
WiboticPacketInterfaces = Union["WiboticCANNode", "WiboticSocket"]


class DataLog:
    def __init__(self):
        """A class designed to hold a list of dicts and helper accessor methods.

        The data keeps insertion order based on data keys added and each key's data
        keeps insertion order for when data gets added.

        self.data is organized in a way
        """
        self.data: List[Dict[str, Any]] = []
        self._data_keys = {}  # Uses a dictionary to keep insertion order

    def __getitem__(self, key) -> List[Any]:
        """Gets an array of all the items contained in the data associated with the key.

        Called using `object[key]`

        :param key: Key to lookup in the dictionaries that make up the data log
        :raises KeyError: When the key is not present in any dictionaries in the log
        :return: Array of all data[key] items. Elements are None when not present
            in a given dictionary record.
        """
        if key not in self._data_keys:
            raise KeyError(key)
        _record = [data.get(key, None) for data in self.data]
        return _record

    def __contains__(self, key):
        """Allows testing if a key is within

        :param key: _description_
        :return: _description_
        """
        return key in self._data_keys

    def append(self, new_data: LogRecord):
        """Keeps keys insertion ordered and appends data keeping insertion order.

        :param new_data: Dictionary of key, value pairs to log as a record
        """
        self.data.append(new_data)
        self._data_keys.update({key: None for key in new_data.keys()})

    def write_csv(self, output: TextIO):
        """Write CSV log to an output IO object. Meant for post-logging only.

        :param output: Output file or other IO object. Note: Any file object
            passed here should be opened in Text mode with the argument (newline="")
            to avoid extra empty lines in the output file.
        """
        fields = list(self._data_keys)
        d_writer = csv.DictWriter(output, fieldnames=fields, delimiter=",")
        d_writer.writeheader()
        d_writer.writerows(self.data)


class AbstractDataLogger:
    def __init__(
        self,
        frequency: float = 1.0,
    ):
        """Base Class data collection on an interface and can format the data for export.

        :param frequency: How many times per second to log [Hz], defaults to 1.0
        """
        self._logged_adc: Dict[Any, DataLog] = {}
        self._ideal_delay = 1 / frequency  # Seconds [1/Hertz]

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self):
        """Start Logging Data. Is also called when initialized as a context manager."""
        raise NotImplementedError

    def stop(self):
        """Stop Logging Data. Is also called during teadown as a context manager."""
        raise NotImplementedError

    def get_data(self, device: Optional[wpt.DeviceID] = None) -> DataLog:
        """Returns a dict containing sequential lists of ADC packets received while running

        :param device: Device's data to retreive data from, defaults to None which is
            used for example in the ThreadLogger where no device gets tracked specifically.
        :return: DataLog object of the specific device.
        """
        device = device if device is not None else "0"  # For non-packet interface
        return self._logged_adc[device]

    def last_record(self, device: Optional[wpt.DeviceID] = None) -> LogRecord:
        """Gets the last log record from a given device,

        :param device: Device's data to retreive data from, defaults to None which is
            used for example in the ThreadLogger where no device gets tracked specifically.
        :return: Last LogRecord for a given device
        """
        device = device if device is not None else "0"  # For non-packet interface
        return self._logged_adc[device].data[-1]


class PacketDataLogger(AbstractDataLogger):
    def __init__(
        self,
        interface: WiboticPacketInterfaces,
        frequency: float = 1.0,
    ):
        """Datalogger for WiBotic hardware interfaces that receive packets.

        :param interface: Callable function that will be called and the result logged.
        :param frequency: How many times per second to log [Hz], defaults to 1.0
        """
        self._interface = interface
        self._adc_processor_fn = None
        super().__init__(frequency)

    def start(self):
        last_recorded_type_time: Dict[wpt.DeviceID, float] = {}

        async def adc_processor(adc: packettype.ADCUpdate):
            if not self._packet_time_check(adc.device, last_recorded_type_time):
                return  # Time Check failed, too early to log new data
            self._packet_append(adc)

        self._adc_processor_fn = adc_processor
        self._interface.register_handler(packettype.ADCUpdate, adc_processor)

    def stop(self):
        self._interface.unregister_handler(packettype.ADCUpdate, self._adc_processor_fn)

    def _packet_time_check(
        self, device: wpt.DeviceID, last_recorded_type_time: Dict[wpt.DeviceID, float]
    ):
        time_since_last = time.monotonic() - last_recorded_type_time.get(device, 0)
        if time_since_last < self._ideal_delay:  # Too early to log new data
            return False
        last_recorded_type_time[device] = time.monotonic()
        return True

    def _packet_append(self, adc: packettype.ADCUpdate):
        if adc.device not in self._logged_adc:  # Initialize log if not already
            self._logged_adc[adc.device] = DataLog()
        try:
            parsed_packet = {adcid.name: value for adcid, value in adc.values.items()}
            self._logged_adc[adc.device].append(parsed_packet)
        except Exception:  # Exceptions get swallowed otherwise
            logger.exception("DataLogger error")


class ThreadDataLogger(AbstractDataLogger):
    def __init__(
        self,
        interface: Callable[[], Dict[str, Any]],
        frequency: float = 1.0,
    ):
        """Datalogger for any function's response that can be called many times.

        :param interface: Callable function that will be called and the result logged.
        :param frequency: How many times per second to log [Hz], defaults to 1.0
        """
        self._interface = interface
        super().__init__(frequency)

    def start(self):
        self._stop_thread_event = Event()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        initial_time = time.monotonic()
        self._logged_adc["0"] = DataLog()

        def timeout_calculator():  # Allows precise timing intervals for 'slow' callbacks
            delay_remainder = (time.monotonic() - initial_time) % self._ideal_delay
            return self._ideal_delay - delay_remainder

        def threaded_logger():
            while not self._stop_thread_event.wait(timeout=(timeout_calculator())):
                self._logged_adc["0"].append(self._interface())

        self._thread = self._executor.submit(threaded_logger)

    def stop(self):
        self._stop_thread_event.set()
        self._thread.result(timeout=2)
        self._executor.shutdown()


@contextmanager
def datalogger(
    interface: Union[WiboticPacketInterfaces, Callable[[], LogRecord]],
    frequency: float = 1.0,
):
    """Factory function to dispatch Datalogger type creation based on interface type.

    :param interface: The interface to log from
    :param frequency: How many times per second to log [Hz], defaults to 1.0
    :raises TypeError: When an unknown interface type is given
    :yield: Apprpropirate type of DataLogger for the provided interface
    """
    if hasattr(interface, "register_handler"):
        with PacketDataLogger(interface, frequency) as packet_logger:
            yield packet_logger
    elif callable(interface):
        with ThreadDataLogger(interface, frequency) as thread_logger:
            yield thread_logger
    else:
        raise TypeError(f"Not able to use Datalogger for type: {type(interface)}")
