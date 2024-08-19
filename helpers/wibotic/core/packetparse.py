import struct
import helpers.wibotic.core.packettools as pt
from helpers.wibotic.core import packettype


def param_update(data):
    try:
        device_id, param_id, param_value, param_status, location = struct.unpack_from(
            "<BLLBB", data, 1
        )
    except struct.error:  # Backward Compatibiltiy for firmware Rev < 21 where location didn't exist
        try:
            device_id, param_id, param_value, param_status = struct.unpack_from("<BLLB", data, 1)
            location = pt.ParamLocation.ACTIVEPARAMSET
        except struct.error:  # Backward Compatibility, for firmware Rev < 17 where param_status didn't exist
            device_id, param_id, param_value = struct.unpack_from("<BLL", data, 1)
            param_status = pt.ParamStatus.SUCCESS
            location = pt.ParamLocation.ACTIVEPARAMSET
    return packettype.ParamUpdate(
        pt.DeviceID(device_id),
        pt.ParamID(param_id),
        param_value,
        pt.ParamStatus(param_status),
        pt.ParamLocation(location),
    )


def param_response(data):
    try:
        device_id, param_id, param_status, param_value, location = struct.unpack_from(
            "<BLBLB", data, 1
        )
    except struct.error:  # Backward Compatibiltiy for firmware Rev < 21 where location didn't exist
        try:
            device_id, param_id, param_status, param_value = struct.unpack_from(
                "<BLBL", data, 1
            )
            location = pt.ParamLocation.ACTIVEPARAMSET
        except struct.error:  # Backward Compatibility, for firmware Rev < 18 where param_value didn't exist
            device_id, param_id, param_status = struct.unpack_from("<BLB", data, 1)
            param_value = None
            location = pt.ParamLocation.ACTIVEPARAMSET
    return packettype.ParamResponse(
        pt.DeviceID(device_id),
        pt.ParamID(param_id),
        pt.ParamStatus(param_status),
        param_value,
        pt.ParamLocation(location),
    )


def stage_response(data):
    device_id, param_id, stage_status = struct.unpack_from("<BLB", data, 1)
    return packettype.StageResponse(
        pt.DeviceID(device_id),
        pt.ParamID(param_id),
        pt.ParamStatus(stage_status),
    )


def commit_response(data):
    device_id, status = struct.unpack_from("<BB", data, 1)
    return packettype.CommitResponse(
        pt.DeviceID(device_id),
        pt.ParamStatus(status),
    )


def adc_update(data):
    device_id = pt.DeviceID(struct.unpack_from("<B", data, 1)[0])
    number_adc_data = (len(data) - 2) // 6
    adc_values = {}
    for x in range(number_adc_data):
        data_location = 2 + (x * 6)
        adc_id = pt.AdcID(struct.unpack_from("<H", data, data_location)[0])
        adc_convert_as = pt.ADC_TYPE_MAP.get(adc_id)
        adc_data = struct.unpack_from(adc_convert_as, data, data_location + 2)
        adc_values[adc_id] = adc_data[0]
    return packettype.ADCUpdate(device_id, adc_values)


def connection_status(data):
    device_as_bit = struct.unpack_from("<H", data, 1)[0]
    parsed_devices = {
        pt.DeviceID(bit_position + 1)
        for bit_position in range(15)
        if (device_as_bit >> bit_position) & 0x01
    }
    return packettype.ConnectedDevices(parsed_devices)


def incoming_message(data):
    device_id, message_level = struct.unpack_from("<BB", data, 1)
    return packettype.IncomingMessage(
        pt.DeviceID(device_id),
        message_level,
        data[3:].decode("utf-8"),
    )


def association_read(data):
    device_id, rssi, mac = struct.unpack_from("<BB6s", data, 1)

    return packettype.IncomingAssociation(
        device_id,
        rssi,
        int.from_bytes(mac, byteorder="little", signed=False),
    )


def incoming_ota_status(data):
    device_id, completion, state = struct.unpack_from("<BBB", data, 1)
    return packettype.IncomingOTAStatus(device_id, completion, state)


def extended_param(data):
    device_id, ext_param_id = struct.unpack_from("<BH", data, 1)

    return packettype.ExtendedParameterResponse(
        pt.DeviceID(device_id),
        pt.ExtParamID(ext_param_id),
        data[4:],
    )


def extended_param_set_response(data):
    device_id, ext_param_id, param_status = struct.unpack_from("<BHB", data, 1)

    return packettype.ExtendedParameterSetResponse(
        pt.DeviceID(device_id),
        pt.ExtParamID(ext_param_id),
        pt.ParamStatus(param_status),
        data[5:],
    )


def param_read_request(data):
    dest, param, location = struct.unpack_from(">BLB", data, 1)

    return packettype.ParamReadRequest(
        pt.DeviceID(dest),
        pt.ParamID(param),
        pt.ParamLocation(location),
    )


def param_write_request(data):
    dest, param, value, location = struct.unpack_from(">BLLB", data, 1)

    return packettype.ParamWriteRequest(
        pt.DeviceID(dest),
        pt.ParamID(param),
        value,
        pt.ParamLocation(location),
    )


def param_stage_request(data):
    dest, param = struct.unpack_from(">BL", data, 1)

    return packettype.ParamStageRequest(
        pt.DeviceID(dest),
        pt.ParamID(param),
    )


def param_commit_request(data):
    dest = struct.unpack_from(">B", data, 1)

    return packettype.ParamCommitRequest(
        pt.DeviceID(dest),
    )


def request_connection_status(data):
    return packettype.RequestConnectionStatus()


def subscribe_request(data):
    topic = struct.unpack_from(">B", data, 1)

    return packettype.SubscribeRequest(
        pt.Topic(topic),
    )


def unsubscribe_request(data):
    topic = struct.unpack_from(">B", data, 1)

    return packettype.UnsubscribeRequest(
        pt.Topic(topic),
    )


def extended_write_request(data):
    dest, ext_id = struct.unpack_from("<BH", data, 1)

    return packettype.ExtendedWriteRequest(
        pt.DeviceID(dest),
        pt.ExtParamID(ext_id),
        data[4:],
    )


def extended_read_request(data):
    dest, ext_id = struct.unpack_from("<BH", data, 1)

    return packettype.ExtendedReadRequest(
        pt.DeviceID(dest),
        pt.ExtParamID(ext_id),
    )
