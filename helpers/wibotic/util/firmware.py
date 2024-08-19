import os
from typing import IO, Tuple, Union, AnyStr
from zipfile import ZipFile
import helpers.wibotic.core.packettools as wpt


# Constants for Firmware versioning
FIRMWARE_CTRL_BLOCK_OFFSET = 0x30
_BUILD_HASH_OFFSET = 0x1D0


def _read_fw_rev(file: IO[bytes], offset: int):
    file.seek(offset)
    hash_bytes = file.read(20)
    name_bytes = file.read(16)

    # Parse hash bytes from how they are stored on WiBotic Systems
    hash_bytes_array = [hash_bytes[n : n + 4] for n in range(0, len(hash_bytes), 4)]
    reversed_hash_bytes = b"".join(hash_bytes_array[::-1])

    return (
        int.from_bytes(reversed_hash_bytes, "little"),
        name_bytes[: wpt.first_empty(name_bytes)].decode("utf8"),
    )


def read_firmware_rev(
    firmware_file: Union[AnyStr, os.PathLike, IO[bytes]],
    device: wpt.DeviceID
) -> Tuple[int, str]:
    """Returns the device's firmware (hash, name) from the given file
    
    :param firmware_file: Path to or IO[bytes] of the zipped firmware bundle
    :raises FileNotFoundError: When firmware_file is not a valid firmware bundle
    :return: _description_
    """
    bin_paths = {wpt.DeviceID.TX: "tx-m7-ota.bin", wpt.DeviceID.RX_1: "rx-m4-ota.bin"}
    file_path = bin_paths[device]

    with ZipFile(firmware_file) as archive:
        with archive.open(file_path) as firmware:
            firmware.seek(0, os.SEEK_END)
            if firmware.tell() < 36:
                raise FileNotFoundError("File is too small")

            return _read_fw_rev(
                firmware, FIRMWARE_CTRL_BLOCK_OFFSET + _BUILD_HASH_OFFSET
            )