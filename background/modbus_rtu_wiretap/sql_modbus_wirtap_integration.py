from datetime import datetime
from background.modbus_rtu_wiretap.measuresstore_v1 import MeasureStore as measdb, MeasureObj

def retrieveDeviceInfo (devices, oldDataTime):

    result = {}

    for device in devices:

        result[device] = devices[device]

        measures = measdb.get_with_daq(device)

        for tag in result[device]:

            tag['daq_name'] = device
            tag['filler'] = False
            tag['duplicate'] = False

            if (tag['measure'] == 'myPV_online'):

                maxDiff = 0
                now = datetime.now()

                for measure in measures:

                    diff = (now - measure.last_updated).seconds

                    if (diff > maxDiff):

                        maxDiff = diff

                if (maxDiff > oldDataTime):

                    tag['tag_value'] = 0

                else:

                    tag['tag_value'] = 1

                tag['tag_time'] = now

            else:

                for measure in measures:

                    if measure.measure_name == tag["measure"]:

                        tag['tag_value'] = measure.measure_value
                        tag['tag_time'] = measure.last_updated

    return result