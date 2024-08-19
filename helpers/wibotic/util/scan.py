import logging
import socket
import struct
from ipaddress import IPv4Address
from typing import Tuple, cast, Union

SEARCH_IDENTIFIER = b"WiBoticDiscover*"  # @ is response, * is request
RESPONSE_IDENTIFIER = b"WiBoticDiscover@"

ask_struct = struct.pack("16s", SEARCH_IDENTIFIER)

logger = logging.getLogger(__name__)


class PacketParseError(Exception):
    pass


def scan_systems(ip_bind: str, scan_for: Union[int, float]=2) -> list[Tuple[IPv4Address, str, int]]:
    """Find WiBotic TRs that are on the subnet of the given local IP address returned
    as a list of tuple of (Address, Nice Name, MAC Address)"""

    UDP_PORT = 30000

    # setup UDP socket
    mclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mclient.settimeout(scan_for)
    mclient.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    mclient.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Broadcast requires binding to an adapter. Also, note that
    # firewalls may also block this request, so check there if
    # you don't see any requests or responses.
    mclient.bind((ip_bind, 0))

    send_address = ("255.255.255.255", UDP_PORT)
    mclient.sendto(ask_struct, send_address)
    logger.info("Finding Systems...")
    found_systems: list[Tuple[IPv4Address, str, int]] = []
    try:
        while True:
            raw_response, response_addr = mclient.recvfrom(1024)

            try:
                magic, hostname, raw_mac = struct.unpack("16s16s6s", raw_response)
                if magic != RESPONSE_IDENTIFIER:
                    raise PacketParseError
                mac = int.from_bytes(raw_mac, "big")

                response = (
                    IPv4Address(response_addr[0]),
                    cast(bytes, hostname).decode("utf-8").rstrip("\x00"),
                    mac,
                )
                logger.info("%s: %s (%X) " % response)
                found_systems.append(response)
            except PacketParseError:
                logger.warning("Got Malformed Packet: Wrong Magic")
            except struct.error:
                logger.warning("Got Malformed Packed: Wrong Length")

    except socket.timeout:
        print("No more systems responded.")
        return found_systems
