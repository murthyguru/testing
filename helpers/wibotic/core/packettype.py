import struct
from helpers.wibotic.core import packettools as pt


class ParsedIncomingType:
    """Base class for interpreted data"""

    def as_packet(self):
        raise NotImplementedError

    @classmethod
    def parse_packet(cls, data):
        raise NotImplementedError


class ADCUpdate(ParsedIncomingType):
    """Contains new ADC values that are sent periodically"""

    def __init__(self, device, values):
        self.device = device
        self.values = values

    def __repr__(self):
        output = "{\nADC Update\n%s\n" % str(self.device)
        for pid, pval in self.values.items():
            output += "%s = %s\n" % (str(pid), str(pval))
        output += "\n}"
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BB",
            pt._ResponseType.ADC_UPDATE,
            self.device,
        )
        packet = bytearray(packet_data)
        for pid, pval in self.values.items():
            packet = packet + bytearray(struct.pack("<H", pid))
            adc_convert_as = pt.ADC_TYPE_MAP.get(pid)
            packet = packet + bytearray(struct.pack(adc_convert_as, pval)).ljust(
                4, "\0".encode("utf-8")
            )
        return packet

    @classmethod
    def parse_packet(cls, data):
        device_id = pt.DeviceID(struct.unpack_from("<B", data, 1)[0])
        number_adc_data = (len(data) - 2) // 6
        adc_values = {}
        for x in range(0, number_adc_data):
            data_location = 2 + (x * 6)
            adc_id = pt.AdcID(struct.unpack_from("<H", data, data_location)[0])
            adc_convert_as = pt.ADC_TYPE_MAP.get(adc_id)
            adc_data = struct.unpack_from(adc_convert_as, data, data_location + 2)
            adc_values[adc_id] = adc_data[0]
        return ADCUpdate(device_id, adc_values)


class ParamUpdate(ParsedIncomingType):
    """Contains a response to a request to read a value from a parameter"""

    def __init__(self, device, param, value, status, location):
        self.device = device
        self.param = param
        self.value = value
        self.status = status
        self.location = location

    def __repr__(self):
        output = (
            "{\nParameter Update\nDevice:%s, Parameter:%s = %s, Status:%s, Location:%s\n}"
            % (
                str(self.device),
                str(self.param),
                str(self.value),
                str(self.status),
                str(self.location),
            )
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBLLBB",
            pt._ResponseType.PARAM_UPDATE,
            self.device,
            self.param,
            self.value,
            self.status,
            self.location,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        try:
            (
                device_id,
                param_id,
                param_value,
                param_status,
                location,
            ) = struct.unpack_from("<BLLBB", data, 1)
        except struct.error:  # Backward Compatibiltiy for firmware Rev < 21 where location didn't exist
            try:
                device_id, param_id, param_value, param_status = struct.unpack_from(
                    "<BLLB", data, 1
                )
                location = pt.ParamLocation.ACTIVEPARAMSET
            except struct.error:  # Backward Compatibility, for firmware Rev < 17 where param_status didn't exist
                device_id, param_id, param_value = struct.unpack_from("<BLL", data, 1)
                param_status = pt.ParamStatus.SUCCESS
                location = pt.ParamLocation.ACTIVEPARAMSET
        return ParamUpdate(
            pt.DeviceID(device_id),
            pt.ParamID(param_id),
            param_value,
            pt.ParamStatus(param_status),
            pt.ParamLocation(location),
        )


class ParamResponse(ParsedIncomingType):
    """Contains a response to a parameter update request"""

    def __init__(self, device, param, status, data, location):
        self.device = device
        self.param = param
        self.status = status
        self.data = data
        self.location = location

    def __repr__(self):
        output = (
            "{\nParameter Response\nDevice:%s, Parameter:%s, Status:%s, Data:%s, Location:%s\n}"
            % (
                str(self.device),
                str(self.param),
                str(self.status),
                str(self.data),
                str(self.location),
            )
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBLBLB",
            pt._ResponseType.PARAM_RESPONSE,
            self.device,
            self.param,
            self.status,
            self.data,
            self.location,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        try:
            (
                device_id,
                param_id,
                param_status,
                param_value,
                location,
            ) = struct.unpack_from("<BLBLB", data, 1)
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
        return ParamResponse(
            pt.DeviceID(device_id),
            pt.ParamID(param_id),
            pt.ParamStatus(param_status),
            param_value,
            pt.ParamLocation(location),
        )


class StageResponse(ParsedIncomingType):
    """Contains a response to a parameter stage request"""

    def __init__(self, device, param, status):
        self.device = device
        self.param = param
        self.status = status

    def __repr__(self):
        output = (
            "{\nParameter Stage Response\nDevice:%s, Parameter:%s, Status:%s\n}"
            % (str(self.device), str(self.param), str(self.status))
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBLB",
            pt._ResponseType.STAGE_RESPONSE,
            self.device,
            self.param,
            self.status,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        device_id, param_id, stage_status = struct.unpack_from("<BLB", data, 1)
        return StageResponse(
            pt.DeviceID(device_id),
            pt.ParamID(param_id),
            pt.ParamStatus(stage_status),
        )


class CommitResponse(ParsedIncomingType):
    """Contains a response to a parameter commit request"""

    def __init__(self, device, status):
        self.device = device
        self.status = status

    def __repr__(self):
        output = "{\nParameter Commit Response\nDevice:%s, Status:%s\n}" % (
            str(self.device),
            str(self.status),
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBB",
            pt._ResponseType.COMMIT_RESPONSE,
            self.device,
            self.status,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        device_id, status = struct.unpack_from("<BB", data, 1)
        return CommitResponse(
            pt.DeviceID(device_id),
            pt.ParamStatus(status),
        )


class ConnectedDevices(ParsedIncomingType):
    """Contains the current devices available from the current connection"""

    def __init__(self, device_list):
        self.devices = device_list

    def __repr__(self):
        return str(self.devices)

    def as_packet(self):
        packet_data = struct.pack(
            "<BH",
            pt._ResponseType.CONNECTION_STATUS,
            self.devices,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        device_as_bit = struct.unpack_from("<H", data, 1)[0]
        parsed_devices = []
        for bit_position in range(0, 15):
            if (device_as_bit >> bit_position) & 0x01:
                parsed_devices.append(pt.DeviceID(bit_position + 1))
        return ConnectedDevices(parsed_devices)


class IncomingMessage(ParsedIncomingType):
    """Contains a human readable message from a WiBotic device"""

    def __init__(self, device, level, message):
        self.device = device
        self.level = level
        self.message = message

    def __repr__(self):
        output = "[%s]: %s" % (str(self.device), str(self.message))
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBB",
            pt._ResponseType.INCOMING_MESSAGE,
            self.device,
            self.level,
        )
        return bytearray(packet_data) + bytearray(self.message)

    @classmethod
    def parse_packet(cls, data):
        device_id, message_level = struct.unpack_from("<BB", data, 1)
        return IncomingMessage(
            pt.DeviceID(device_id),
            message_level,
            data[3:].decode("utf-8"),
        )


class ExtendedParameterResponse(ParsedIncomingType):
    """Contains a response to an extended parameter"""

    def __init__(self, device, ext_id, data):
        self.device = device
        self.ext_id = ext_id
        self.data = data

    def __repr__(self):
        output = (
            "{\nExtended Parameter Response\nDevice:%s, Parameter:%s, Data:%s\n}"
            % (str(self.device), str(self.ext_id), str(self.data))
        )
        return output

    def parse(self):
        """For backwards compatability."""
        return self.value

    @property
    def value(self):
        struct_members = pt._EXT_ID_TO_STRUCT[self.ext_id][1]
        unpacked = struct.unpack(pt._EXT_ID_TO_STRUCT[self.ext_id][0], self.data)

        def interpret_pass(unpacked):
            for member_index, needs_utf8 in enumerate(
                pt._EXT_ID_TO_STRUCT[self.ext_id][2]
            ):
                if needs_utf8:
                    yield unpacked[member_index][
                        : pt.first_empty(unpacked[member_index])
                    ].decode("utf8")
                else:
                    yield unpacked[member_index]

        return struct_members(*interpret_pass(unpacked))

    def as_packet(self):
        packet_data = struct.pack(
            "<BBH",
            pt._ResponseType.EXTENDED_PARAM_RESPONSE,
            self.device,
            self.ext_id,
        )
        return bytearray(packet_data) + bytearray(self.data)

    @classmethod
    def parse_packet(cls, data):
        device_id, ext_param_id = struct.unpack_from("<BH", data, 1)

        return ExtendedParameterResponse(
            pt.DeviceID(device_id),
            pt.ExtParamID(ext_param_id),
            data[4:],
        )


class ExtendedParameterSetResponse(ExtendedParameterResponse):
    """Contains a response to an extended parameter set"""

    def __init__(self, device, ext_id, status, data):
        super().__init__(device, ext_id, data)
        self.status = status

    def __repr__(self):
        output = (
            "{\nExtended Parameter Set Response\nDevice:%s, Parameter:%s, Status:%s, Data:%s\n}"
            % (str(self.device), str(self.ext_id), str(self.status), str(self.data))
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBHB",
            pt._ResponseType.EXTENDED_PARAM_SET_RESPONSE,
            self.device,
            self.ext_id,
            self.status,
        )
        return bytearray(packet_data) + bytearray(self.data)

    @classmethod
    def parse_packet(cls, data):
        device_id, ext_param_id, param_status = struct.unpack_from("<BHB", data, 1)

        return ExtendedParameterSetResponse(
            pt.DeviceID(device_id),
            pt.ExtParamID(ext_param_id),
            pt.ParamStatus(param_status),
            data[5:],
        )


class IncomingAssociation(ParsedIncomingType):
    """Contains information about a device that requested association"""

    def __init__(self, device, rssi, mac):
        self.device = device
        self.rssi = rssi
        self.mac = mac

    def __repr__(self):
        output = "{\nMAC: %s\nRSSI: %s\n}" % (hex(self.mac), str(self.rssi))
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBB6s",
            pt._ResponseType.RX_ASSOCIATION,
            self.device,
            self.rssi,
            self.mac,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        device_id, rssi, mac = struct.unpack_from("<BB6s", data, 1)

        return IncomingAssociation(
            device_id,
            rssi,
            int.from_bytes(mac, byteorder="little", signed=False),
        )


class IncomingOTAStatus(ParsedIncomingType):
    """Contains information about an ongoing OTA update's progress"""

    def __init__(self, device, completion, state):
        self.device = device
        self.completion = completion
        self.state = state

    def __repr__(self):
        output = "{\nPercent Complete: %s\nState: %s\n}" % (self.completion, self.state)
        return output

    def as_packet(self):
        packet_data = struct.pack(
            "<BBBB",
            pt._ResponseType.OTA_STATUS,
            self.device,
            self.completion,
            self.state,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        device_id, completion, state = struct.unpack_from("<BBB", data, 1)
        return IncomingOTAStatus(device_id, completion, state)


class DataRequest:
    """Base class for data to send"""

    def as_packet(self):
        raise NotImplementedError

    @classmethod
    def parse_packet(cls, data):
        raise NotImplementedError


class RequestConnectionStatus(DataRequest):
    """Builds a binary packet containing a request to send
    which devices are currently connected to the WiBotic system"""

    def as_packet(self):
        return bytearray([pt._RequestType.REQUEST_CONNECTION_STATUS])

    @classmethod
    def parse_packet(cls, data):
        return RequestConnectionStatus()


class ParamReadRequest(DataRequest):
    """Builds a binary packet containing a request to read a parameter
    from the WiBotic system"""

    def __init__(self, destination_device, parameter, location=0):
        self.dest = destination_device
        self.param = parameter
        self.location = location

    def __repr__(self):
        output = "{\nParam Read Request\nDevice:%s, Parameter:%s, Location:%s\n}" % (
            str(self.dest),
            str(self.param),
            str(self.location),
        )
        return output

    def as_packet(self):
        packed_data = struct.pack(
            ">BBLB",
            pt._RequestType.PARAM_READ_REQUEST,
            self.dest,
            self.param,
            self.location,
        )
        return bytearray(packed_data)

    @classmethod
    def parse_packet(cls, data):
        dest, param, location = struct.unpack_from(">BLB", data, 1)

        return ParamReadRequest(
            pt.DeviceID(dest),
            pt.ParamID(param),
            pt.ParamLocation(location),
        )


class ParamWriteRequest(DataRequest):
    """Builds a binary packet containing a request to write a new
    value to a parameter on the WiBotic system"""

    def __init__(self, destination_device, parameter, new_value, location=0):
        self.dest = destination_device
        self.param = parameter
        self.value = new_value
        self.location = location

    def __repr__(self):
        output = (
            "{\nParam Write Request\nDevice:%s, Parameter:%s, Value:%s, Location:%s\n}"
            % (str(self.dest), str(self.param), str(self.value), str(self.location))
        )
        return output

    def as_packet(self):
        packed_data = struct.pack(
            ">BBLLB",
            pt._RequestType.PARAM_WRITE_REQUEST,
            self.dest,
            self.param,
            self.value,
            self.location,
        )
        return bytearray(packed_data)

    @classmethod
    def parse_packet(cls, data):
        dest, param, value, location = struct.unpack_from(">BLLB", data, 1)

        return ParamWriteRequest(
            pt.DeviceID(dest),
            pt.ParamID(param),
            value,
            pt.ParamLocation(location),
        )


class ParamStageRequest(DataRequest):
    """Builds a binary packet containing a request to stage a parameter
    for a later commit into non-volatile storage"""

    def __init__(self, destination_device, parameter):
        self.dest = destination_device
        self.param = parameter

    def __repr__(self):
        output = "{\nParam Stage Request\nDevice:%s, Parameter:%s\n}" % (
            str(self.dest),
            str(self.param),
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            ">BBL",
            pt._RequestType.PARAM_STAGE_REQUEST,
            self.dest,
            self.param,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        dest, param = struct.unpack_from(">BL", data, 1)

        return ParamStageRequest(
            pt.DeviceID(dest),
            pt.ParamID(param),
        )


class ParamCommitRequest(DataRequest):
    """Builds a binary packet containing a request to commit staged
    parameters into non-voltatile storage"""

    def __init__(self, destination_device):
        self.dest = destination_device

    def __repr__(self):
        output = "{\nParam Commit Request\nDevice:%s\n}" % (str(self.dest))
        return output

    def as_packet(self):
        packet_data = struct.pack(
            ">BB",
            pt._RequestType.PARAM_COMMIT_REQUEST,
            self.dest,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        dest = struct.unpack_from(">B", data, 1)[0]

        return ParamCommitRequest(
            pt.DeviceID(dest),
        )


class SubscribeRequest(DataRequest):
    """Builds a binary packet containing a request to subscribe to a topic
    in the WiBotic system"""

    def __init__(self, topic):
        self.topic = topic

    def __repr__(self):
        output = "{\nSubscribe Request\nTopic:%s\n}" % (str(self.topic))
        return output

    def as_packet(self):
        packet_data = struct.pack(
            ">BB",
            pt._RequestType.SUBSCRIBE_REQUEST,
            self.topic,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        topic = struct.unpack_from(">B", data, 1)[0]

        return SubscribeRequest(
            pt.Topic(topic),
        )


class UnsubscribeRequest(DataRequest):
    """Builds a binary packet containing a request to unsubscribe from a topic
    in the WiBotic system"""

    def __init__(self, topic):
        self.topic = topic

    def __repr__(self):
        output = "{\nUnsubscribe Request\nTopic:%s\n}" % (str(self.topic))
        return output

    def as_packet(self):
        packet_data = struct.pack(
            ">BB",
            pt._RequestType.UNSUBSCRIBE_REQUEST,
            self.topic,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        topic = struct.unpack_from(">B", data, 1)[0]

        return UnsubscribeRequest(
            pt.Topic(topic),
        )


class ExtendedWriteRequest(DataRequest):
    """Builds a binary packet containing a block of data to write"""

    def __init__(self, destination_device, ext_id, data):
        self.dest = destination_device
        self.ext_id = ext_id
        self.data = data

    def __repr__(self):
        output = (
            "{\nExtended Parameter Set Request\nDevice:%s, Parameter:%s, Data:%s\n}"
            % (str(self.dest), str(self.ext_id), str(self.data))
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            ">BBH",
            pt._RequestType.EXTENDED_WRITE_REQUEST,
            self.dest,
            self.ext_id,
        )
        return bytearray(packet_data) + bytearray(self.data)

    @classmethod
    def parse_packet(cls, data):
        dest, ext_id = struct.unpack_from(">BH", data, 1)

        return ExtendedWriteRequest(
            pt.DeviceID(dest),
            pt.ExtParamID(ext_id),
            data[4:],
        )


class ExtendedReadRequest(DataRequest):
    """Builds a binary packet containing a block of data to read"""

    def __init__(self, destination_device, ext_id):
        self.dest = destination_device
        self.ext_id = ext_id

    def __repr__(self):
        output = "{\nExtended Parameter Read Request\nDevice:%s, Parameter:%s\n}" % (
            str(self.dest),
            str(self.ext_id),
        )
        return output

    def as_packet(self):
        packet_data = struct.pack(
            ">BBH",
            pt._RequestType.EXTENDED_READ_REQUEST,
            self.dest,
            self.ext_id,
        )
        return bytearray(packet_data)

    @classmethod
    def parse_packet(cls, data):
        dest, ext_id = struct.unpack_from(">BH", data, 1)

        return ExtendedReadRequest(
            pt.DeviceID(dest),
            pt.ExtParamID(ext_id),
        )
