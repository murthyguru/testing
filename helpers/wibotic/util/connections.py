import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional, Set, Tuple, Union, cast

from helpers.wibotic.core import packettools as wpt
from helpers.wibotic.core import packettype

if TYPE_CHECKING:
    from wibotic.can import WiboticCANNode
    from helpers.wibotic.interface.wiboticsocket import WiboticSocket

logger = logging.getLogger(__name__)

WiboticDeviceStates = Union[wpt.TransmitterState, wpt.ChargerState]
GroupedDeviceStates = Tuple[
    Optional[Set[wpt.TransmitterState]], Optional[Set[wpt.ChargerState]]
]
DEFAULT_TR_ADDRESS = "192.168.2.20"
DEFAULT_TR_WEBSOCKET_URL = f"ws://{DEFAULT_TR_ADDRESS}/ws"


def coil_connect_to_oc(
    ws: "WiboticSocket",
    target_mac: Optional[int] = None,
    timeout_sec: Optional[float] = None,
) -> int:
    """Blocks until any OC is connected by coil check. Specifying target_mac with a
    coil check is uncommon.

    :param ws: Existing instance of WiboticSocket
    :param target_mac: MAC address as integer (full address
        must be specified) Defaults to None which finishes when connected to anything.
    :param timeout_sec: How long to block before raising an exception, Defaults to None
        which blocks forever
    :return: MAC Address of connected OC as integer (34D954000000 = 58108021833728)
    """
    if ws.get_parameter(wpt.DeviceID.TX, wpt.ParamID.RadioConnectionRequest).value:
        ws.set_parameter(wpt.DeviceID.TX, wpt.ParamID.RadioConnectionRequest, 0)
        time.sleep(3)  # Wait for disconnect from DCM mode
    return _wait_for_oc_connect(ws, timeout_sec=timeout_sec, target_mac=target_mac)


def radio_connect_to_oc(
    ws: "WiboticSocket",
    target_mac: int,
    timeout_sec: Optional[float] = None,
) -> int:
    """Blocks until any OC is connected.

    :param ws: Existing instance of WiboticSocket
    :param target_mac: MAC address as integer (full address
        must be specified)
    :param timeout_sec: How long to block before raising an exception, Defaults to None
        which blocks forever
    :return: MAC Address of connected OC as integer (34D954000000 = 58108021833728)
    """
    ws.set_parameter(
        wpt.DeviceID.TX, wpt.ParamID.RadioConnectionRequest, target_mac & 0xFFFFFF
    )
    return _wait_for_oc_connect(ws, timeout_sec=timeout_sec, target_mac=target_mac)


async def _async_wait_for_oc_connect(
    ws: "WiboticSocket",
    target_mac: Optional[int] = None,
) -> int:
    """Asynchronous version, Runs until any OC is connected or timeout.

    :param ws: Existing instance of WiboticSocket
    :param target_mac: MAC address as integer (full address
        must be specified) Defaults to None which finishes when connected to anything.
    :return: MAC Address of connected OC as integer (34D954000000 = 58108021833728)
    """
    connected_mac: Optional[int] = None
    oc_connected = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _get_connected_mac():
        """Attempts to get the MAC and check it against the target_mac if any. Blocking."""
        nonlocal connected_mac
        try:
            _connected_mac = get_mac_ws(ws, wpt.DeviceID.RX_1)
        except (ws.ParameterTimeout, ws.ParameterFailure):
            logger.debug("RX Found, then Error. Sending status request again.")
            ws.get_devices()
            return

        logger.info(f"Connected to OC: {_connected_mac:0X}")
        if _connected_mac and (target_mac is None or _connected_mac == target_mac):
            connected_mac = _connected_mac  # Prevents race conditions on connected_mac
            oc_connected.set()  # Signal loop to finish

    async def _wait_for_oc():
        async def update_connection(devices):  # Connection Event Callback
            if parse_charger_connected(devices):
                loop.call_soon_threadsafe(_get_connected_mac)  # Block after callback

        with ws.temporary_handler(wpt.ConnectedDevices, update_connection):
            ws.get_devices()  # In case already connected
            await oc_connected.wait()

    await _wait_for_oc()
    return cast(int, connected_mac)


def _wait_for_oc_connect(
    ws: "WiboticSocket",
    target_mac: Optional[int] = None,
    timeout_sec: Optional[float] = None,
) -> int:
    """Synchronous version, Blocks until any OC is connected.

    :param ws: Existing instance of WiboticSocket
    :param target_mac: MAC address as integer (full address
        must be specified) Defaults to None which finishes when connected to anything.
    :param timeout_sec: How long to block before raising an exception, Defaults to None
        which blocks forever
    :return: MAC Address of connected OC as integer (34D954000000 = 58108021833728)
    """
    try:
        return asyncio.run(
            asyncio.wait_for(
                _async_wait_for_oc_connect(ws, target_mac), timeout=timeout_sec
            )
        )
    except asyncio.exceptions.TimeoutError as exc:
        raise TimeoutError from exc


async def async_wait_for_oc_disconnect(ws: "WiboticSocket"):
    """Asynchronous version, Runs until there is no OC connected.

    :param ws: Existing instance of WiboticSocket
    """
    oc_disconnected = asyncio.Event()
    loop = asyncio.get_running_loop()

    async def _wait_for_oc():
        async def update_connection(devices):  # Connection Event Callback
            if not parse_charger_connected(devices):
                loop.call_soon_threadsafe(oc_disconnected.set)

        with ws.temporary_handler(wpt.ConnectedDevices, update_connection):
            ws.get_devices()
            await oc_disconnected.wait()

    await _wait_for_oc()


def wait_for_oc_disconnect(ws: "WiboticSocket", timeout_sec: Optional[float] = None):
    """Synchronous version, Blocks until there is no OC connected.

    :param ws: Existing instance of WiboticSocket
    :param timeout_sec: How long to block before raising an exception, Defaults to None
        which blocks forever
    """
    try:
        asyncio.run(
            asyncio.wait_for(async_wait_for_oc_disconnect(ws), timeout=timeout_sec)
        )
    except asyncio.exceptions.TimeoutError as exc:
        raise TimeoutError from exc


def get_mac_ws(ws: "WiboticSocket", device_id: wpt.DeviceID) -> int:
    """Gets the MAC from a specific device using a WiboticSocket connection

    :param ws: Existing instance of WiboticSocket
    :param device_id: Device (TX or RX) to get the MAC of
    :return: MAC Address as integer (34D954000000 = 58108021833728)
    """
    mac = wibotic_mac_combine(
        ws.get_parameter(device_id, wpt.ParamID.DevMACOUI).value,
        ws.get_parameter(device_id, wpt.ParamID.DevMACSpecific).value,
    )
    return mac


def get_mac_cannode(cannode: "WiboticCANNode") -> int:
    """Gets the MAC from a WiBotic OC using a CAN connection

    :param cannode: Existing instance of WiboticCANNode
    :return: MAC Address as integer (34D954000000 = 58108021833728)
    """
    mac = wibotic_mac_combine(
        cannode.read_param(wpt.ParamID.DevMACOUI)[0],
        cannode.read_param(wpt.ParamID.DevMACSpecific)[0],
    )
    return mac


def wibotic_mac_combine(oui: int, uid: int) -> int:
    """MAC formed by 2 mac sections, oui & uid. Masks oui/uid larger than 3 octets.

    The masking is required due to wibotic parameters being passed as larger numbers.
    :param oui: MAC (Organizationally Unique Identifier)
    :param uid: MAC (Uniqe Identifier)
    :return: MAC Address as integer (34D954000000 = 58108021833728)
    """
    mac_mask = 2 ** (8 * 3) - 1
    combo_mac = (oui & mac_mask) << 8 * 3
    combo_mac |= uid & mac_mask
    return combo_mac


def parse_charger_connected(
    connected_devices: Union[int, packettype.ParamUpdate, packettype.ConnectedDevices]
) -> bool:
    """Parses the response from ConnectedDevices parameter read for if a charger is connected.

    :param connected_devices: Read value from ConnectedDevices parameter OR packet resposne
    :return: True/False if a charger is connected
    """
    if isinstance(connected_devices, packettype.ParamUpdate):
        connected_devices = connected_devices.value  # [int] result, processes later
    if isinstance(connected_devices, packettype.ConnectedDevices):
        return wpt.DeviceID.RX_1 in connected_devices.devices
    if isinstance(connected_devices, int):
        return bool(connected_devices & 0b10)
    raise TypeError("Unexpected Type, cannot determine charger connection status")


def wait_for_state(
    ws: "WiboticSocket",
    target_states: GroupedDeviceStates,
    timeout_sec: Optional[float] = None,
):
    """Block until a WiBotic Device is in any of the specified states.

    :param ws: Existing instance of WiboticSocket
    :param target_states: Collection of states for the system (any device) to be in,
    if one of the tuple members is (None or set()) this function will not trigger on
    that device's state changes. (equivalent to entering NONE of the states for that device)
    :param timeout_sec: How long to block before raising an exception, Defaults to None
        which blocks forever
    """
    try:
        return asyncio.run(
            asyncio.wait_for(
                wait_for_state_async(ws, target_states), timeout=timeout_sec
            )
        )
    except asyncio.TimeoutError:
        raise TimeoutError("Desired Device State not Reached") from None


async def wait_for_state_async(ws: "WiboticSocket", target_states: GroupedDeviceStates):
    """Async version of wait_for_state

    :param ws: Existing instance of WiboticSocket
    :param target_states: Collection of states for the system (any device) to be in,
    if one of the tuple members is (None or set()) this function will not trigger on
    that device's state changes. (equivalent to entering NONE of the states for that device)
    """
    state_reached = asyncio.Event()
    loop = asyncio.get_running_loop()
    mapped_target_states = {
        wpt.DeviceID.TX: target_states[0] or set(),
        wpt.DeviceID.RX_1: target_states[1] or set(),
    }

    async def update_state(data: packettype.ADCUpdate):
        if data.values[wpt.AdcID.ChargeState] in mapped_target_states[data.device]:
            loop.call_soon_threadsafe(state_reached.set)

    with ws.temporary_handler(packettype.ADCUpdate, update_state):
        await state_reached.wait()


def wait_for_not_state(
    ws: "WiboticSocket",
    target_states: GroupedDeviceStates,
    timeout_sec: Optional[float] = None,
):
    """Block until a WiBotic Device is not in any of the specified states.

    :param ws: Existing instance of WiboticSocket
    :param target_states: Collection of states for the system (any device) to not be in,
    if one of the tuple members is (None or set()) this function will not trigger on
    that device's state changes. (equivalent to entering ALL states for that device)
    :param timeout_sec: How long to block before raising an exception, Defaults to None
        which blocks forever
    """
    try:
        return asyncio.run(
            asyncio.wait_for(
                wait_for_not_state_async(ws, target_states), timeout=timeout_sec
            )
        )
    except asyncio.TimeoutError:
        raise TimeoutError("Desired Device State not Reached") from None


async def wait_for_not_state_async(
    ws: "WiboticSocket",
    target_states: GroupedDeviceStates,
):
    """Async version of wait_for_not_state

    :param ws: Existing instance of WiboticSocket
    :param target_states: Collection of states for the system (any device) to not be in,
    if one of the tuple members is (None or set()) this function will not trigger on
    that device's state changes. (equivalent to entering ALL states for that device)
    """
    target_states_tr = (
        (set(wpt.TransmitterState) - target_states[0]) if target_states[0] else set()
    )
    target_states_oc = (
        (set(wpt.ChargerState) - target_states[1]) if target_states[1] else set()
    )
    await wait_for_state_async(ws, (target_states_tr, target_states_oc))


def wait_for_state_change(
    ws: "WiboticSocket",
    device_id: wpt.DeviceID,
    timeout_sec: Optional[float] = None,
):
    """Block until a WiBotic Device changes its state.

    :param ws: Existing instance of WiboticSocket
    :param device_id: Device (TX or RX) to wait for state change
    :param timeout_sec: How long to block before raising an exception, Defaults to None
        which blocks forever
    """
    try:
        return asyncio.run(
            asyncio.wait_for(
                wait_for_state_change_async(ws, device_id), timeout=timeout_sec
            )
        )
    except asyncio.TimeoutError:
        raise TimeoutError("Desired Device State not Reached") from None


async def wait_for_state_change_async(
    ws: "WiboticSocket",
    device_id: wpt.DeviceID,
):
    """Async version of wait_for_state_change

    :param ws: Existing instance of WiboticSocket
    :param device_id: Device (TX or RX) to wait for state change
    """
    current_state = ws.get_next_adc(device_id).values[wpt.AdcID.ChargeState]
    target_states_tr = set(wpt.TransmitterState)
    target_states_oc = set(wpt.ChargerState)
    if device_id == wpt.DeviceID.TX:
        target_states_tr.remove(current_state)
        target_states_oc = set()
    elif device_id == wpt.DeviceID.RX_1:
        target_states_tr = set()
        target_states_oc.remove(current_state)
    await wait_for_state_async(ws, (target_states_tr, target_states_oc))
