import datetime
from enum import Enum
from numbers import Real
import os
import shutil
from typing import NamedTuple, Union

from helpers.common import get_json_lock


START_YEAR = 2019


class ByteUnit(Enum):
    """Various constants for byte units, where e.g. 1 KB (kilobyte) = 1000 bytes,
    and 1 KiB (kibibyte) = 1024 bytes.
    """
    B = 1
    KB = 1000
    KiB = 1024
    MB = 1000 * KB
    MiB = 1024 * KiB
    GB = 1000 * MB
    GiB = 1024 * MiB
    TB = 1000 * GB
    TiB = 1024 * GiB


class MeasureConsumption(NamedTuple):
    """NamedTuple representing the statistics of general measure disk usage.

    Attributes:
        unit (str): Disk usage unit (e.g. B, KiB, GB, etc)
        days (int): Number of days counted
        total (float): Total disk usage for the time frame
        average (float): Average disk usage
        free (float): Total free disk space.
    """
    total: float
    average: float
    free: float
    days: int
    unit: str


def _convert_byte_unit(value: dict,
                      to_unit: ByteUnit,
                      from_unit: ByteUnit = ByteUnit.B):
    """Given a dictionary with all values corresponding to a ByteUnit, converts
    all values between ByteUnits.

    Args:
        value (dict): Dictionary where all values are some sort of byte unit.
        to_unit (ByteUnit): ByteUnit to convert to.
        from_unit (ByteUnit, optional): ByteUnit to convert from. Defaults to
            ByteUnit.B.
    """
    for key in value:
        if isinstance(value[key], dict):
            _convert_byte_unit(value[key], to_unit, from_unit)
        if isinstance(value[key], Real):
            value[key] = value[key] * (from_unit.value / to_unit.value)


def get_disk_usage(start_path: str) -> int:
    """Returns the disk usage of a file or directory. If a file is provided,
    will return the usage of that file; if a directory, will sum the usage
    of each file in the directory.

    While the size of a file might be very small (a couple of bytes), file
    systems only actually allocates files in chunks, so the actual disk space a
    file takes up may be different from the file's size.

    Args:
        start_path (str): Path to the file or directory.

    Returns:
        int: Disk usage in bytes
    """
    # According to the python3 docs, st_blocks gives the number of 512-byte
    # blocks allocated for a file. Therefore, multiplying the number of blocks
    # by 512 should give the disk usage for a given file.
    # print('get_disk_usage:')
    # print(start_path)
    if os.path.isfile(start_path):
        st = os.stat(start_path)
        #print('returning on file')
        return st.st_blocks * 512

    else:
        #print('starting walk loop')
        total = 0
        for dirname, _, fnames in os.walk(start_path):
            #print(dirname)
            for filename in fnames:
                #print(' ' + filename)
                filepath = os.path.join(dirname, filename)
                st = os.stat(filepath)
                size = st.st_blocks * 512
                total += size

        return total


def parse_device_id(filename: str) -> str:
    """Given a (measure data) filename, attempts to parse the device ID from
    that filename.

    Filenames for measure data are typically of the form
    <YEAR>_<Month>_<Day>_<DeviceID>.<extension>.

    Args:
        filename (str): Name or path to the file to parse

    Returns:
        str: Parsed device id.
    """
    # Remove any trailing path information and the file extension from
    # the filename
    filename = os.path.splitext(os.path.split(filename)[1])[0]

    # Split the filenam
    file_split = filename.split("_")

    retval = '_'.join(file_split[3:])
    return retval


def detailed_usage(byte_unit: ByteUnit = ByteUnit.B) -> dict:
    """Calculates detailed disk usage by various MyPV systems.

    Data is separated by system including the myPV IQ software, logs, backups,
    and measures. Measures are further divided by device type/kpis/compressed/
    other (unassociated.)

    Args:
        byte_unit (ByteUnit, optional): ByteUnit to return data as. Defaults to 
            ByteUnit.B (bytes).

    Returns:
        dict: Usage details.
    """

    # The main special case we need to worry about is /sos_data
    # So we'll list the contents of that directory, parse individual folders
    # based on the kind of data it should have, and then add some other
    # statistics.
    sos_data_list = os.listdir('/sos_data')

    this_year = datetime.date.today().year
    year_set = {str(i) for i in range(START_YEAR, this_year + 1)}
    # Filter data years and logs out of the sos_data_list
    sos_data_list = [x for x in sos_data_list if x not in year_set and x != "logs"]

    usage_data = {
        'measures': {},
        'mypv': {
            'iq': 0,
            'logs': 0,
            'backups': 0,
            'total': 0
        },
        'other': 0
    }

    usage_data['measures'] = measure_usage_by_type(year_set)
    usage_data['mypv']['logs'] = get_disk_usage('/sos_data/logs')
    for data_item in sos_data_list:
        usage_data['mypv']['iq'] += get_disk_usage(
            os.path.join('/sos_data', data_item)
        )
    usage_data['mypv']['iq'] += mypv_iq_usage()
    usage_data['mypv']['backups'] = backups_usage()

    usage_data.update({'disk': shutil.disk_usage('/')._asdict()})
    
    usage_data['mypv']['total'] = sum(usage_data['mypv'].values())


    iq_total = (usage_data['measures']['total']
                + usage_data['mypv']['total'])

    # shutil's totals might not add up - e.g. maybe 30 gb are used, 28 gb are
    # free, but the total disk space is 62 gb. The difference is probably
    # a number of various partitions the OS creates that aren't visible from
    # root. So, to calculate 'other' we'll normalize the total usage to just be
    # total - free
    usage_data['other'] = (usage_data['disk']['total'] -
                           usage_data['disk']['free'] - iq_total)

    # If the unit is anything except a ByteUnit.B, perform the conversion
    if byte_unit.value > 1:
        _convert_byte_unit(usage_data, byte_unit)

    usage_data['unit'] = byte_unit.name

    return usage_data


def measure_consumption(days: int=30,
                        from_date: datetime.datetime = None,
                        byte_unit: Union[ByteUnit, str] = ByteUnit.B,
                        ) -> MeasureConsumption:
    """Calculates the average and total disk consumption of Measures over a 
    given time period.

    Args:
        days (int, optional): Number of days to add up. Defaults to 30.
        from_date (datetime.datetime, optional): A date to start calculating.
            If None, starts from yesterday. Defaults to None.
        byte_unit (Union[ByteUnit, str], optional): ByteUnit to return
            values as. Use either a ByteUnit enum, or a string corresponding to
            a ByteUnit name. Defaults to ByteUnit.B.

    Raises:
        ValueError: For invalid byte unit.

    Returns:
        MeasureConsumption: MeasureConsumption named tuple with keys total,
            average, free, days and unit.
    """
    if from_date is None:
        # By default, start with the last full measure day, which is probably
        # yesterday.
        from_date = datetime.date.today() - datetime.timedelta(days=1)

    # Do some checks on the byte unit
    if isinstance(byte_unit, ByteUnit):
        # Probably the most common, let's get it out of the way first
        pass
    elif isinstance(byte_unit, str):
        # Will raise a KeyError if the string isn't a member of the ByteUnit
        # enum.
        byte_unit = ByteUnit[byte_unit]
    else:
        raise ValueError("Invalid byte unit %s" % type(byte_unit))

    total = 0

    for _ in range(days):
        total += get_disk_usage(
            from_date.strftime("/sos_data/%Y/%m/%d")
        )
        from_date = from_date - datetime.timedelta(days=1)

    usage = {
        'total': total,
        'average': total / days,
        'free': shutil.disk_usage("/").free
    }

    # If some unit was requested other than byte, perform the conversion
    if byte_unit.value > ByteUnit.B.value:
        _convert_byte_unit(usage, byte_unit)

    usage['days'] = days
    usage['unit'] = byte_unit.name

    return MeasureConsumption(**usage)


def measure_usage_by_type(year_set: Union[int, list, set] = None) -> dict:
    """Returns a dictionary with the disk usage of measure data by device type.
    Compressed (zipped) and other data aret totaled separately.

    Args:
        year_set (Union[int, list, set], optional): Years to compile data for.
            Defaults to None - will compile data for all years.

    Returns:
        dict: Disk usage by device type.
    """
    # Build the year set
    if year_set is None:
        this_year = datetime.date.today().year
        year_set = {str(i) for i in range(START_YEAR, this_year + 1)}
    elif isinstance(year_set, int):
        # Cast to an iterable set
        year_set = {year_set}

    site_devices = get_json_lock("site_devices")

    devices = {}
    usage_by_type = {
        'kpis': 0,
        'compressed': 0,
        'other': 0
    }

    # Build a lookup table of device names and their types, e.g.
    # {"DEV_43": "Inverter"}
    for dev_type, dev_items in site_devices.items():
        for dev in dev_items:
            devices.update({dev['daq_name']: dev_type})
            # Add any new device types to the tallying dictionary.
            if dev_type not in usage_by_type:
                usage_by_type.update({ dev_type: 0 })

    # Go through each year in the year set and get the contents of the
    # corresponding directory
    for data_year in year_set:
        for rootdir, _, filenames in os.walk(
            os.path.join("/sos_data", str(data_year))
        ):
            for fname in filenames:
                # Get the individual filename and disk usage
                f = os.path.join(rootdir, fname)
                u = get_disk_usage(f)
                
                # Categorize the data usage
                # Anything with .zip is added to the 'compressed' category
                if os.path.splitext(fname)[1].lower() == '.zip':
                    usage_by_type['compressed'] += u
                else:
                    # Get the device id from the filename and add the usage
                    # based on that device's type.
                    device_id = parse_device_id(fname)
                    if device_id in devices.keys():
                        usage_by_type[devices[device_id]] += u
                    elif 'kpis' in device_id:
                        usage_by_type['kpis'] += u
                    # If it couldn't be categorized just dump it in the 'other'
                    # category.
                    else:
                        usage_by_type['other'] += u

    # Add the total
    total = sum(usage_by_type.values())
    usage_by_type['total'] = total

    return usage_by_type


def mypv_iq_usage() -> int:
    """Returns the disk usage of /opt/flask_app and /sos-config.

    Returns:
        int: Disk usage in bytes
    """

    return get_disk_usage('/opt/flask_app') + get_disk_usage('/sos-config')


def backups_usage() -> int:
    """Returns the disk usage of /opt/app_backups

    Returns:
        int: disk usage in bytes
    """
    return get_disk_usage('/opt/app_backups')
