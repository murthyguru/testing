"""WiBotic Websocket Network API Packet Tools

Tools for creating and interpreting binary packets sent over a Websocket
connection to a WiBotic charging system"""

__copyright__ = "Copyright 2023 WiBotic Inc."
__version__ = "0.1"
__email__ = "info@wibotic.com"
__status__ = "Technology Preview"

from enum import Enum, IntEnum
from collections import namedtuple
from typing import Optional

# Compatibility imports
from helpers.wibotic.core.packettype import (
    ADCUpdate,
    ParamUpdate,
    ParamResponse,
    StageResponse,
    CommitResponse,
    ConnectedDevices,
    IncomingMessage,
    ExtendedParameterResponse,
    ExtendedParameterSetResponse,
    IncomingAssociation,
    IncomingOTAStatus,
    RequestConnectionStatus,
    ParamReadRequest,
    ParamWriteRequest,
    ParamStageRequest,
    ParamCommitRequest,
    SubscribeRequest,
    UnsubscribeRequest,
    ExtendedWriteRequest,
    ExtendedReadRequest,
    ParsedIncomingType,
    DataRequest,
)

_C_TYPE = {
    "uint32_t": "<L",
    "uint16_t": "<H",
    "uint8_t": "<B",
    "float": "<f",
}


class DeviceID(IntEnum):
    """Device Address Identifiers"""

    TX = 1
    RX_1 = 2


class ParamStatus(IntEnum):
    """Response Codes"""

    FAILURE = 0
    HARDWARE_FAIL = 1
    INVALID_INPUT = 2
    NON_CRITICAL_FAIL = 3
    READ_ONLY = 4
    SUCCESS = 5
    NOT_AUTHORIZED = 6
    PENDING = 7
    CLAMPED = 8

class ParamLocation(IntEnum):
    """Location of Param on Device"""

    ACTIVEPARAMSET = 0
    NVMSTAGING = 1
    NVM = 2


class ChargerState(IntEnum):
    """State From Charger ADC Packet"""

    IDLE = 0
    RAMP_UP = 1
    CC_CHARGE = 2
    CV_CHARGE = 3
    CHG_COMPLETE = 4
    STOPPING = 5
    ALARM = 6
    CHECK_VOLT = 7
    RECOVERY = 8
    FATAL = 9
    POWER_SUPPLY = 10
    NEGATIVE_DELTA_V = 11


class TransmitterState(IntEnum):
    """State From Transmitter ADC Packet"""

    OFF = 0
    IDLE = 1
    RAMP_UP = 2
    CHARGING = 3
    RX_NO_CHARGE = 4
    POWER_UNPOWERED = 5
    ALARM = 6
    SCANNING = 7


Transmitter_Version_Name = {
    1: "TR100",
    2: "TR100",
    3: "TR300",
    4: "TR100",
    5: "TR110",
    6: "TR301",
    7: "TR302",
    8: "TR150",
    9: "TR301",
    10: "TR450",
    11: "TR450",
    12: "TR302",
    13: "TR150",
}

Charger_Version_Name = {
    1: "OC200",
    2: "OC210",
    3: "OC110",
    4: "OC300",
    5: "OC250",
    6: "OC250",
    7: "OC251",
    8: "OC301",
    9: "OC210",
    10: "OC261",
    11: "OC262",
    12: "OC262WP",
    13: "BDOC",
    14: "OC301",
    15: "OC150",
    16: "OC450",
}


class Topic(IntEnum):
    """Topics that can be subscribed to"""

    ADC_PACKETS = 0
    RADIO_ASSOCIATIONS = 1
    UPDATE_PROGRESS = 2
    NEW_LOG_FILE = 3
    GLOBAL_PARAM_UPDATES = 4


class OtaCtrl(IntEnum):
    """Values for OtaCtrl"""
    START_RX_SHIM = 0x01
    START_RX_APP  = 0x02

    START_TX_SHIM = 0x03
    START_TX_APP  = 0x04


class OtaState(IntEnum):
    """Values for IncomingOTAStatus state"""
    NONE            = 0x00,
    INITIALIZING    = 0x01,
    WRITING_TX_SHIM = 0x02,
    WRITING_TX_APP  = 0x03,
    WRITING_RX_SHIM = 0x04,
    WRITING_RX_APP  = 0x05,
    FINALIZING      = 0x06,
    FAILED          = 0x07,
    SHIM_COMPLETE   = 0x08,
    APP_COMPLETE    = 0x09


class BatteryChemistry(IntEnum):
    """
    Battery Chemistry Identifiers.
    You can use the Battery_Chemistry_Information dictionary to look up specific
    values for each battery chemistry.
    """

    Custom = 0
    LithiumIon = 1
    NiCad = 2
    LeadAcid = 3
    LiFePO4 = 4
    LiHV = 5
    NiMH = 6


Battery_Chemistry_Information = {
    BatteryChemistry.Custom: {
        "min_voltage_per_cell": 500,
        "max_voltage_per_cell": 65535,
        "restart_per_cell": 65534,
        "overvolt_per_cell": 65535,
    },
    BatteryChemistry.LithiumIon: {
        "min_voltage_per_cell": 3000,
        "max_voltage_per_cell": 4200,
        "restart_per_cell": 4075,
        "overvolt_per_cell": 4350,
    },
    BatteryChemistry.NiCad: {
        "min_voltage_per_cell": 500,
        "max_voltage_per_cell": 1800,
        "restart_per_cell": 1375,
        "overvolt_per_cell": 1810,
    },
    BatteryChemistry.LeadAcid: {
        "min_voltage_per_cell": 1930,
        "max_voltage_per_cell": 2440,
        "restart_per_cell": 2165,
        "overvolt_per_cell": 2540,
    },
    BatteryChemistry.LiFePO4: {
        "min_voltage_per_cell": 2500,
        "max_voltage_per_cell": 3650,
        "restart_per_cell": 3375,
        "overvolt_per_cell": 3800,
    },
    BatteryChemistry.LiHV: {
        "min_voltage_per_cell": 3000,
        "max_voltage_per_cell": 4350,
        "restart_per_cell": 4225,
        "overvolt_per_cell": 4450,
    },
    BatteryChemistry.NiMH: {
        "min_voltage_per_cell": 500,
        "max_voltage_per_cell": 1650,
        "restart_per_cell": 1375,
        "overvolt_per_cell": 1700,
    },
}


class ParamID(IntEnum):
    """Parameter Identifiers"""

    ExampleId1 = 0
    ExampleId2 = 1
    ExampleId3 = 2
    Address = 3
    RadioChannel = 4
    ManualMode = 5
    DroppedPackets = 6
    TargetCtrl = 7
    TxGateDriverPot = 8
    TxPowerAmplifierPot = 9
    TxDdsPot = 10
    TxVicorEnable = 11
    TxGateDriverEnable = 12
    TxPowerEnable = 13
    HardwareCommand = 14
    TxDdsFrequency = 15
    TxZMatchEnable = 16
    TxZFet1 = 17
    TxZFet2 = 18
    TxZFet3 = 19
    TxZFet4 = 20
    Fan1Enable = 21
    Fan2Enable = 22
    TxPowerLevel = 23
    TargetVrect = 24
    VrectTolerance = 25
    DigitalBoardVersion = 26
    RxBatteryConnect = 27
    RxBatteryChargerEnable = 28
    RxZIn1 = 29
    RxZIn2 = 30
    RxZOut1 = 31
    RxZOut2 = 32
    Fan3Enable = 33
    BatteryCurrentMax = 34
    ChargerCurrentLimit = 35
    MobileRxVoltageLimit = 36
    RxBatteryVoltageMin = 37
    BuildHash = 38
    TargetFirmwareId = 39
    TxPlvlMin = 40
    OtaMode = 41
    RxBatteryVoltage = 42
    RxBatteryCurrent = 43
    RxTemperature = 44
    EthIPAddr = 45
    EthNetMask = 46
    EthGateway = 47
    EthDNS = 48
    EthUseDHCP = 49
    EthUseLLA = 50
    DevMACOUI = 51
    DevMACSpecific = 52
    EthInterfacePort = 53
    EthMTU = 54
    EthICMPReply = 55
    EthTCPTTL = 56
    EthUDPTTL = 57
    EthUseDNS = 58
    EthTCPKeepAlive = 59
    ChargeEnable = 60
    I2cAddress = 61
    RxBatteryNumCells = 62
    RxBatterymVPerCell = 63
    TxPowerLimit = 64
    TxWirelessPowerLossLimit = 65
    MaxChargeTime = 66
    LogEnable = 67
    RxBatteryChemistry = 68
    RxWirelessTrackingGain = 69
    IgnoreBatteryCondition = 70
    PowerBoardVersion = 71
    TxDutyCycle = 72
    LEDPower12v = 73
    ModifyPowerLevel = 74
    UpdaterMode = 75
    RadioDebug = 76
    RSSIConnectThresh = 77
    AccessLevel = 78
    ConnectedDevices = 79
    LcdVersion = 80
    RadioConnectionRequest = 81
    CANMessageConfig = 82
    CANID = 83
    OtaCtrl = 84
    CoilCheckBaseStation = 85
    RecoveryChargeEnable = 86
    CANBitRate = 87
    BatteryRestartPerCell = 88
    MaxCVChargeTime = 89
    ThermalFans = 90
    PowerUnpowered = 91
    ADCViewRate = 92
    ActiveTempAlarms = 93
    RadioTestMode = 94
    SystemMaxPowerWireless = 95
    SystemMaxCurrentWireless = 96
    SystemMaxPowerWall = 97
    SystemMaxCurrentWall = 98
    OnlyWallPower = 99
    ComputedCurrentLimit = 100
    DigitalOnly = 101
    StayRecovery = 102
    SystemMaxVoltage = 103
    BootCount = 104
    RadioPowerLevel = 105
    BootloaderVersion = 106
    BaseUAVCANV1SubjectID = 107
    VPASet = 108
    LEDTest = 109
    IMin = 110
    FixedVrect = 111
    InputPowerSupplyLimit = 112
    BaseUAVCANV1ServiceID = 113
    PowerUnpoweredOnTime = 114
    PowerUnpoweredOffTime = 115
    PowerOffset = 116
    RadioMode = 117
    RadioChannelRestrictLow = 118
    RadioChannelRestrictHigh = 119
    RadioFilter1 = 120
    RadioFilter2 = 121


class ExtParamID(IntEnum):
    """Extended Paramter Identifiers"""

    NiceName = 0
    AllowedWSOrigin = 1
    OTPBlock = 2
    EEPROMBlock = 3
    LogFileInfo = 4
    StoredOTAInfo = 5
    FwRevName = 6


class CANName(Enum):
    """Nicknames for WiBotic parameters"""

    ExampleId1 = "EX1"
    ExampleId2 = "EX2"
    ExampleId3 = "EX3"
    Address = "ADDR"
    RadioChannel = "RADC"
    ManualMode = "MANU"
    DroppedPackets = "DROP"
    TargetCtrl = "CTRL"
    TxGateDriverPot = "TGDP"
    TxPowerAmplifierPot = "TPAP"
    TxDdsPot = "TDDS"
    TxVicorEnable = "TVEN"
    TxGateDriverEnable = "TGDE"
    TxPowerEnable = "TXEN"
    HardwareCommand = "HCMD"
    TxDdsFrequency = "DDFR"
    TxZMatchEnable = "ZMCH"
    TxZFet1 = "FET1"
    TxZFet2 = "FET2"
    TxZFet3 = "FET3"
    TxZFet4 = "FET4"
    Fan1Enable = "FAN1"
    Fan2Enable = "FAN2"
    TxPowerLevel = "PLVL"
    TargetVrect = "VREC"
    VrectTolerance = "VTOL"
    DigitalBoardVersion = "DBRD"
    RxBatteryConnect = "BTCO"
    RxBatteryChargerEnable = "CHRG"
    RxZIn1 = "ZIN1"
    RxZIn2 = "ZIN2"
    RxZOut1 = "ZO1"
    RxZOut2 = "ZO2"
    Fan3Enable = "FAN3"
    BatteryCurrentMax = "IMAX"
    ChargerCurrentLimit = "ILIM"
    MobileRxVoltageLimit = "VLIM"
    RxBatteryVoltageMin = "VMIN"
    BuildHash = "HASH"
    TargetFirmwareId = "FWID"
    TxPlvlMin = "PMIN"
    OtaMode = "OTAM"
    RxBatteryVoltage = "VBAT"
    RxBatteryCurrent = "IBAT"
    RxTemperature = "TEMP"
    EthIPAddr = "IP"
    EthNetMask = "NMSK"
    EthGateway = "GATE"
    EthDNS = "DNS"
    EthUseDHCP = "DHCP"
    EthUseLLA = "LLA"
    DevMACOUI = "MACO"
    DevMACSpecific = "MACS"
    EthInterfacePort = "PORT"
    EthMTU = "MTU"
    EthICMPReply = "ICMP"
    EthTCPTTL = "TCP"
    EthUDPTTL = "UDP"
    EthUseDNS = "DNSE"
    EthTCPKeepAlive = "KEEP"
    ChargeEnable = "ENBL"
    I2cAddress = "I2C"
    RxBatteryNumCells = "CELL"
    RxBatterymVPerCell = "CLMV"
    TxPowerLimit = "PLIM"
    TxWirelessPowerLossLimit = "PLOS"
    MaxChargeTime = "TTIM"
    LogEnable = "LGEN"
    RxBatteryChemistry = "CHEM"
    RxWirelessTrackingGain = "GAIN"
    IgnoreBatteryCondition = "IGNR"
    PowerBoardVersion = "PBRD"
    TxDutyCycle = "DUTY"
    LEDPower12v = "LED"
    ModifyPowerLevel = "PMOD"
    UpdaterMode = "UPDA"
    RadioDebug = "RDBG"
    RSSIConnectThresh = "RSSI"
    AccessLevel = "ACCS"
    ConnectedDevices = "CONN"
    LcdVersion = "LCD"
    RadioConnectionRequest = "DCM"
    CANMessageConfig = "CNMG"
    CANID = "CNID"
    OtaCtrl = "OTAC"
    CoilCheckBaseStation = "CCHK"
    RecoveryChargeEnable = "RCOV"
    CANBitRate = "CNBR"
    BatteryRestartPerCell = "BRPC"
    MaxCVChargeTime = "VTIM"
    ThermalFans = "QFAN"
    PowerUnpowered = "PUP"
    ADCViewRate = "AVR"
    ActiveTempAlarms = "ATMP"
    RadioTestMode = "RATM"
    SystemMaxPowerWireless = "SMPW"
    SystemMaxCurrentWireless = "SMIW"
    SystemMaxPowerWall = "SMPM"
    SystemMaxCurrentWall = "SMIM"
    OnlyWallPower = "FWAL"
    ComputedCurrentLimit = "CCLI"
    DigitalOnly = "DIGT"
    StayRecovery = "STRE"
    SystemMaxVoltage = "VMAX"
    BootCount = "BOOT"
    RadioPowerLevel = "RPOW"
    BootloaderVersion = "BTLD"
    BaseUAVCANV1SubjectID = "BUID"
    VPASet = "VPAS"
    LEDTest = "LEDT"
    IMin = "IMIN"
    FixedVrect = "FVRC"
    InputPowerSupplyLimit = "IPSL"
    BaseUAVCANV1ServiceID = "BSID"
    PowerUnpoweredOnTime = "PUPN"
    PowerUnpoweredOffTime = "PUPF"
    PowerOffset = "APWL"
    RadioMode = "RAM"
    RadioChannelRestrictLow = "RCRL"
    RadioChannelRestrictHigh = "RCRH"
    RadioFilter1 = "RFL1"
    RadioFilter2 = "RFL2"
    NiceName = "NAME"
    AllowedWSOrigin = "OKWS"
    OTPBlock = "OTP"
    EEPROMBlock = "EEPR"
    LogFileInfo = "LOGS"
    StoredOTAInfo = "OTAI"
    FwRevName = "FW_V"


# Information about which devices can save which parameters
PARAM_PERSISTABLE_MAP = {
    ParamID.ExampleId1: set([]),
    ParamID.ExampleId2: set([]),
    ParamID.ExampleId3: set([]),
    ParamID.Address: set([]),
    ParamID.RadioChannel: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.ManualMode: set([]),
    ParamID.DroppedPackets: set([]),
    ParamID.TargetCtrl: set([]),
    ParamID.TxGateDriverPot: set([]),
    ParamID.TxPowerAmplifierPot: set([]),
    ParamID.TxDdsPot: set([]),
    ParamID.TxVicorEnable: set([]),
    ParamID.TxGateDriverEnable: set([]),
    ParamID.TxPowerEnable: set([]),
    ParamID.HardwareCommand: set([]),
    ParamID.TxDdsFrequency: set([]),
    ParamID.TxZMatchEnable: set([]),
    ParamID.TxZFet1: set([]),
    ParamID.TxZFet2: set([]),
    ParamID.TxZFet3: set([]),
    ParamID.TxZFet4: set([]),
    ParamID.Fan1Enable: set([]),
    ParamID.Fan2Enable: set([]),
    ParamID.TxPowerLevel: set([]),
    ParamID.TargetVrect: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.VrectTolerance: set([DeviceID.TX]),
    ParamID.DigitalBoardVersion: set([]),
    ParamID.RxBatteryConnect: set([]),
    ParamID.RxBatteryChargerEnable: set([]),
    ParamID.RxZIn1: set([]),
    ParamID.RxZIn2: set([]),
    ParamID.RxZOut1: set([]),
    ParamID.RxZOut2: set([]),
    ParamID.Fan3Enable: set([]),
    ParamID.BatteryCurrentMax: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.ChargerCurrentLimit: set([]),
    ParamID.MobileRxVoltageLimit: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RxBatteryVoltageMin: set([]),
    ParamID.BuildHash: set([]),
    ParamID.TargetFirmwareId: set([]),
    ParamID.TxPlvlMin: set([]),
    ParamID.OtaMode: set([]),
    ParamID.RxBatteryVoltage: set([]),
    ParamID.RxBatteryCurrent: set([]),
    ParamID.RxTemperature: set([]),
    ParamID.EthIPAddr: set([DeviceID.TX]),
    ParamID.EthNetMask: set([DeviceID.TX]),
    ParamID.EthGateway: set([DeviceID.TX]),
    ParamID.EthDNS: set([DeviceID.TX]),
    ParamID.EthUseDHCP: set([DeviceID.TX]),
    ParamID.EthUseLLA: set([DeviceID.TX]),
    ParamID.DevMACOUI: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.DevMACSpecific: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.EthInterfacePort: set([DeviceID.TX]),
    ParamID.EthMTU: set([DeviceID.TX]),
    ParamID.EthICMPReply: set([DeviceID.TX]),
    ParamID.EthTCPTTL: set([DeviceID.TX]),
    ParamID.EthUDPTTL: set([DeviceID.TX]),
    ParamID.EthUseDNS: set([DeviceID.TX]),
    ParamID.EthTCPKeepAlive: set([DeviceID.TX]),
    ParamID.ChargeEnable: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.I2cAddress: set([DeviceID.RX_1]),
    ParamID.RxBatteryNumCells: set([DeviceID.RX_1]),
    ParamID.RxBatterymVPerCell: set([DeviceID.RX_1]),
    ParamID.TxPowerLimit: set([DeviceID.TX]),
    ParamID.TxWirelessPowerLossLimit: set([DeviceID.TX]),
    ParamID.MaxChargeTime: set([DeviceID.RX_1]),
    ParamID.LogEnable: set([]),
    ParamID.RxBatteryChemistry: set([DeviceID.RX_1]),
    ParamID.RxWirelessTrackingGain: set([DeviceID.RX_1]),
    ParamID.IgnoreBatteryCondition: set([DeviceID.RX_1]),
    ParamID.PowerBoardVersion: set([]),
    ParamID.TxDutyCycle: set([DeviceID.TX]),
    ParamID.LEDPower12v: set([]),
    ParamID.ModifyPowerLevel: set([]),
    ParamID.UpdaterMode: set([]),
    ParamID.RadioDebug: set([]),
    ParamID.RSSIConnectThresh: set([DeviceID.RX_1]),
    ParamID.AccessLevel: set([]),
    ParamID.ConnectedDevices: set([]),
    ParamID.LcdVersion: set([]),
    ParamID.RadioConnectionRequest: set([]),
    ParamID.CANMessageConfig: set([DeviceID.RX_1]),
    ParamID.CANID: set([DeviceID.RX_1]),
    ParamID.OtaCtrl: set([]),
    ParamID.CoilCheckBaseStation: set([]),
    ParamID.RecoveryChargeEnable: set([DeviceID.RX_1]),
    ParamID.CANBitRate: set([DeviceID.RX_1]),
    ParamID.BatteryRestartPerCell: set([DeviceID.RX_1]),
    ParamID.MaxCVChargeTime: set([DeviceID.RX_1]),
    ParamID.ThermalFans: set([DeviceID.TX]),
    ParamID.PowerUnpowered: set([DeviceID.TX]),
    ParamID.ADCViewRate: set([]),
    ParamID.ActiveTempAlarms: set([DeviceID.RX_1]),
    ParamID.RadioTestMode: set([]),
    ParamID.SystemMaxPowerWireless: set([]),
    ParamID.SystemMaxCurrentWireless: set([]),
    ParamID.SystemMaxPowerWall: set([]),
    ParamID.SystemMaxCurrentWall: set([]),
    ParamID.OnlyWallPower: set([DeviceID.RX_1]),
    ParamID.ComputedCurrentLimit: set([]),
    ParamID.DigitalOnly: set([DeviceID.TX]),
    ParamID.StayRecovery: set([DeviceID.RX_1]),
    ParamID.SystemMaxVoltage: set([]),
    ParamID.BootCount: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RadioPowerLevel: set([]),
    ParamID.BootloaderVersion: set([]),
    ParamID.BaseUAVCANV1SubjectID: set([DeviceID.RX_1]),
    ParamID.VPASet: set([]),
    ParamID.LEDTest: set([]),
    ParamID.IMin: set([DeviceID.RX_1]),
    ParamID.FixedVrect: set([]),
    ParamID.InputPowerSupplyLimit: set([DeviceID.TX]),
    ParamID.BaseUAVCANV1ServiceID: set([DeviceID.RX_1]),
    ParamID.PowerUnpoweredOnTime: set([DeviceID.TX]),
    ParamID.PowerUnpoweredOffTime: set([DeviceID.TX]),
    ParamID.PowerOffset: set([DeviceID.RX_1]),
    ParamID.RadioMode: set([DeviceID.TX]),
    ParamID.RadioChannelRestrictLow: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RadioChannelRestrictHigh: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RadioFilter1: set([]),
    ParamID.RadioFilter2: set([]),
}

# Information about which devices ideally should contain which parameters
PARAM_ACCESSIBLE_MAP = {
    ParamID.ExampleId1: set([]),
    ParamID.ExampleId2: set([]),
    ParamID.ExampleId3: set([]),
    ParamID.Address: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RadioChannel: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.ManualMode: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.DroppedPackets: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.TargetCtrl: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.TxGateDriverPot: set([]),
    ParamID.TxPowerAmplifierPot: set([DeviceID.TX]),
    ParamID.TxDdsPot: set([DeviceID.TX]),
    ParamID.TxVicorEnable: set([DeviceID.TX]),
    ParamID.TxGateDriverEnable: set([DeviceID.TX]),
    ParamID.TxPowerEnable: set([DeviceID.TX]),
    ParamID.HardwareCommand: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.TxDdsFrequency: set([DeviceID.TX]),
    ParamID.TxZMatchEnable: set([DeviceID.TX]),
    ParamID.TxZFet1: set([DeviceID.TX]),
    ParamID.TxZFet2: set([DeviceID.TX]),
    ParamID.TxZFet3: set([DeviceID.TX]),
    ParamID.TxZFet4: set([DeviceID.TX]),
    ParamID.Fan1Enable: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.Fan2Enable: set([DeviceID.TX]),
    ParamID.TxPowerLevel: set([]),
    ParamID.TargetVrect: set([DeviceID.RX_1]),
    ParamID.VrectTolerance: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.DigitalBoardVersion: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RxBatteryConnect: set([DeviceID.RX_1]),
    ParamID.RxBatteryChargerEnable: set([DeviceID.RX_1]),
    ParamID.RxZIn1: set([DeviceID.RX_1]),
    ParamID.RxZIn2: set([DeviceID.RX_1]),
    ParamID.RxZOut1: set([DeviceID.RX_1]),
    ParamID.RxZOut2: set([DeviceID.RX_1]),
    ParamID.Fan3Enable: set([DeviceID.TX]),
    ParamID.BatteryCurrentMax: set([DeviceID.RX_1]),
    ParamID.ChargerCurrentLimit: set([DeviceID.RX_1]),
    ParamID.MobileRxVoltageLimit: set([DeviceID.RX_1]),
    ParamID.RxBatteryVoltageMin: set([DeviceID.RX_1]),
    ParamID.BuildHash: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.TargetFirmwareId: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.TxPlvlMin: set([]),
    ParamID.OtaMode: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RxBatteryVoltage: set([DeviceID.RX_1]),
    ParamID.RxBatteryCurrent: set([DeviceID.RX_1]),
    ParamID.RxTemperature: set([DeviceID.RX_1]),
    ParamID.EthIPAddr: set([DeviceID.TX]),
    ParamID.EthNetMask: set([DeviceID.TX]),
    ParamID.EthGateway: set([DeviceID.TX]),
    ParamID.EthDNS: set([DeviceID.TX]),
    ParamID.EthUseDHCP: set([DeviceID.TX]),
    ParamID.EthUseLLA: set([DeviceID.TX]),
    ParamID.DevMACOUI: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.DevMACSpecific: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.EthInterfacePort: set([DeviceID.TX]),
    ParamID.EthMTU: set([DeviceID.TX]),
    ParamID.EthICMPReply: set([]),
    ParamID.EthTCPTTL: set([DeviceID.TX]),
    ParamID.EthUDPTTL: set([DeviceID.TX]),
    ParamID.EthUseDNS: set([DeviceID.TX]),
    ParamID.EthTCPKeepAlive: set([]),
    ParamID.ChargeEnable: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.I2cAddress: set([]),
    ParamID.RxBatteryNumCells: set([DeviceID.RX_1]),
    ParamID.RxBatterymVPerCell: set([DeviceID.RX_1]),
    ParamID.TxPowerLimit: set([DeviceID.TX]),
    ParamID.TxWirelessPowerLossLimit: set([DeviceID.TX]),
    ParamID.MaxChargeTime: set([DeviceID.RX_1]),
    ParamID.LogEnable: set([DeviceID.TX]),
    ParamID.RxBatteryChemistry: set([DeviceID.RX_1]),
    ParamID.RxWirelessTrackingGain: set([DeviceID.RX_1]),
    ParamID.IgnoreBatteryCondition: set([DeviceID.RX_1]),
    ParamID.PowerBoardVersion: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.TxDutyCycle: set([DeviceID.TX]),
    ParamID.LEDPower12v: set([DeviceID.TX]),
    ParamID.ModifyPowerLevel: set([DeviceID.TX]),
    ParamID.UpdaterMode: set([DeviceID.TX]),
    ParamID.RadioDebug: set([DeviceID.TX]),
    ParamID.RSSIConnectThresh: set([DeviceID.RX_1]),
    ParamID.AccessLevel: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.ConnectedDevices: set([DeviceID.TX]),
    ParamID.LcdVersion: set([DeviceID.TX]),
    ParamID.RadioConnectionRequest: set([DeviceID.TX]),
    ParamID.CANMessageConfig: set([DeviceID.RX_1]),
    ParamID.CANID: set([DeviceID.RX_1]),
    ParamID.OtaCtrl: set([DeviceID.TX]),
    ParamID.CoilCheckBaseStation: set([DeviceID.RX_1]),
    ParamID.RecoveryChargeEnable: set([DeviceID.RX_1]),
    ParamID.CANBitRate: set([DeviceID.RX_1]),
    ParamID.BatteryRestartPerCell: set([DeviceID.RX_1]),
    ParamID.MaxCVChargeTime: set([DeviceID.RX_1]),
    ParamID.ThermalFans: set([DeviceID.TX]),
    ParamID.PowerUnpowered: set([DeviceID.TX]),
    ParamID.ADCViewRate: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.ActiveTempAlarms: set([DeviceID.RX_1]),
    ParamID.RadioTestMode: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.SystemMaxPowerWireless: set([DeviceID.RX_1]),
    ParamID.SystemMaxCurrentWireless: set([DeviceID.RX_1]),
    ParamID.SystemMaxPowerWall: set([DeviceID.RX_1]),
    ParamID.SystemMaxCurrentWall: set([DeviceID.RX_1]),
    ParamID.OnlyWallPower: set([DeviceID.RX_1]),
    ParamID.ComputedCurrentLimit: set([DeviceID.RX_1]),
    ParamID.DigitalOnly: set([DeviceID.TX]),
    ParamID.StayRecovery: set([DeviceID.RX_1]),
    ParamID.SystemMaxVoltage: set([DeviceID.RX_1]),
    ParamID.BootCount: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RadioPowerLevel: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.BootloaderVersion: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.BaseUAVCANV1SubjectID: set([DeviceID.RX_1]),
    ParamID.VPASet: set([DeviceID.TX]),
    ParamID.LEDTest: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.IMin: set([DeviceID.RX_1]),
    ParamID.FixedVrect: set([DeviceID.RX_1]),
    ParamID.InputPowerSupplyLimit: set([DeviceID.TX]),
    ParamID.BaseUAVCANV1ServiceID: set([DeviceID.RX_1]),
    ParamID.PowerUnpoweredOnTime: set([DeviceID.TX]),
    ParamID.PowerUnpoweredOffTime: set([DeviceID.TX]),
    ParamID.PowerOffset: set([DeviceID.RX_1]),
    ParamID.RadioMode: set([DeviceID.TX]),
    ParamID.RadioChannelRestrictLow: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RadioChannelRestrictHigh: set([DeviceID.TX, DeviceID.RX_1]),
    ParamID.RadioFilter1: set([DeviceID.TX]),
    ParamID.RadioFilter2: set([DeviceID.TX]),
}

# Information about which C-Style type represents a parameter
PARAM_TYPE_MAP = {
    ParamID.ExampleId1: _C_TYPE.get("uint8_t"),
    ParamID.ExampleId2: _C_TYPE.get("uint16_t"),
    ParamID.ExampleId3: _C_TYPE.get("int32_t"),
    ParamID.Address: _C_TYPE.get("uint8_t"),
    ParamID.RadioChannel: _C_TYPE.get("uint8_t"),
    ParamID.ManualMode: _C_TYPE.get("uint8_t"),
    ParamID.DroppedPackets: _C_TYPE.get("uint8_t"),
    ParamID.TargetCtrl: _C_TYPE.get("uint32_t"),
    ParamID.TxGateDriverPot: _C_TYPE.get("uint16_t"),
    ParamID.TxPowerAmplifierPot: _C_TYPE.get("uint16_t"),
    ParamID.TxDdsPot: _C_TYPE.get("uint16_t"),
    ParamID.TxVicorEnable: _C_TYPE.get("uint8_t"),
    ParamID.TxGateDriverEnable: _C_TYPE.get("uint8_t"),
    ParamID.TxPowerEnable: _C_TYPE.get("uint8_t"),
    ParamID.HardwareCommand: _C_TYPE.get("uint8_t"),
    ParamID.TxDdsFrequency: _C_TYPE.get("float"),
    ParamID.TxZMatchEnable: _C_TYPE.get("uint8_t"),
    ParamID.TxZFet1: _C_TYPE.get("uint8_t"),
    ParamID.TxZFet2: _C_TYPE.get("uint8_t"),
    ParamID.TxZFet3: _C_TYPE.get("uint8_t"),
    ParamID.TxZFet4: _C_TYPE.get("uint8_t"),
    ParamID.Fan1Enable: _C_TYPE.get("uint8_t"),
    ParamID.Fan2Enable: _C_TYPE.get("uint8_t"),
    ParamID.TxPowerLevel: _C_TYPE.get("uint16_t"),
    ParamID.TargetVrect: _C_TYPE.get("uint16_t"),
    ParamID.VrectTolerance: _C_TYPE.get("uint16_t"),
    ParamID.DigitalBoardVersion: _C_TYPE.get("uint8_t"),
    ParamID.RxBatteryConnect: _C_TYPE.get("uint8_t"),
    ParamID.RxBatteryChargerEnable: _C_TYPE.get("uint8_t"),
    ParamID.RxZIn1: _C_TYPE.get("uint8_t"),
    ParamID.RxZIn2: _C_TYPE.get("uint8_t"),
    ParamID.RxZOut1: _C_TYPE.get("uint8_t"),
    ParamID.RxZOut2: _C_TYPE.get("uint8_t"),
    ParamID.Fan3Enable: _C_TYPE.get("uint8_t"),
    ParamID.BatteryCurrentMax: _C_TYPE.get("uint16_t"),
    ParamID.ChargerCurrentLimit: _C_TYPE.get("uint16_t"),
    ParamID.MobileRxVoltageLimit: _C_TYPE.get("uint16_t"),
    ParamID.RxBatteryVoltageMin: _C_TYPE.get("uint16_t"),
    ParamID.BuildHash: _C_TYPE.get("uint32_t"),
    ParamID.TargetFirmwareId: _C_TYPE.get("uint32_t"),
    ParamID.TxPlvlMin: _C_TYPE.get("uint8_t"),
    ParamID.OtaMode: _C_TYPE.get("uint32_t"),
    ParamID.RxBatteryVoltage: _C_TYPE.get("uint32_t"),
    ParamID.RxBatteryCurrent: _C_TYPE.get("uint32_t"),
    ParamID.RxTemperature: _C_TYPE.get("uint32_t"),
    ParamID.EthIPAddr: _C_TYPE.get("uint32_t"),
    ParamID.EthNetMask: _C_TYPE.get("uint32_t"),
    ParamID.EthGateway: _C_TYPE.get("uint32_t"),
    ParamID.EthDNS: _C_TYPE.get("uint32_t"),
    ParamID.EthUseDHCP: _C_TYPE.get("uint8_t"),
    ParamID.EthUseLLA: _C_TYPE.get("uint8_t"),
    ParamID.DevMACOUI: _C_TYPE.get("uint32_t"),
    ParamID.DevMACSpecific: _C_TYPE.get("uint32_t"),
    ParamID.EthInterfacePort: _C_TYPE.get("uint16_t"),
    ParamID.EthMTU: _C_TYPE.get("uint32_t"),
    ParamID.EthICMPReply: _C_TYPE.get("uint8_t"),
    ParamID.EthTCPTTL: _C_TYPE.get("uint8_t"),
    ParamID.EthUDPTTL: _C_TYPE.get("uint8_t"),
    ParamID.EthUseDNS: _C_TYPE.get("uint8_t"),
    ParamID.EthTCPKeepAlive: _C_TYPE.get("uint8_t"),
    ParamID.ChargeEnable: _C_TYPE.get("uint8_t"),
    ParamID.I2cAddress: _C_TYPE.get("uint8_t"),
    ParamID.RxBatteryNumCells: _C_TYPE.get("uint8_t"),
    ParamID.RxBatterymVPerCell: _C_TYPE.get("uint16_t"),
    ParamID.TxPowerLimit: _C_TYPE.get("uint16_t"),
    ParamID.TxWirelessPowerLossLimit: _C_TYPE.get("uint16_t"),
    ParamID.MaxChargeTime: _C_TYPE.get("uint32_t"),
    ParamID.LogEnable: _C_TYPE.get("uint8_t"),
    ParamID.RxBatteryChemistry: _C_TYPE.get("uint8_t"),
    ParamID.RxWirelessTrackingGain: _C_TYPE.get("uint16_t"),
    ParamID.IgnoreBatteryCondition: _C_TYPE.get("uint8_t"),
    ParamID.PowerBoardVersion: _C_TYPE.get("uint8_t"),
    ParamID.TxDutyCycle: _C_TYPE.get("uint8_t"),
    ParamID.LEDPower12v: _C_TYPE.get("uint8_t"),
    ParamID.ModifyPowerLevel: _C_TYPE.get("int16_t"),
    ParamID.UpdaterMode: _C_TYPE.get("uint8_t"),
    ParamID.RadioDebug: _C_TYPE.get("uint8_t"),
    ParamID.RSSIConnectThresh: _C_TYPE.get("uint8_t"),
    ParamID.AccessLevel: _C_TYPE.get("uint8_t"),
    ParamID.ConnectedDevices: _C_TYPE.get("uint16_t"),
    ParamID.LcdVersion: _C_TYPE.get("uint8_t"),
    ParamID.RadioConnectionRequest: _C_TYPE.get("uint32_t"),
    ParamID.CANMessageConfig: _C_TYPE.get("uint8_t"),
    ParamID.CANID: _C_TYPE.get("uint8_t"),
    ParamID.OtaCtrl: _C_TYPE.get("uint8_t"),
    ParamID.CoilCheckBaseStation: _C_TYPE.get("uint32_t"),
    ParamID.RecoveryChargeEnable: _C_TYPE.get("uint8_t"),
    ParamID.CANBitRate: _C_TYPE.get("uint16_t"),
    ParamID.BatteryRestartPerCell: _C_TYPE.get("uint16_t"),
    ParamID.MaxCVChargeTime: _C_TYPE.get("uint32_t"),
    ParamID.ThermalFans: _C_TYPE.get("uint8_t"),
    ParamID.PowerUnpowered: _C_TYPE.get("uint8_t"),
    ParamID.ADCViewRate: _C_TYPE.get("uint16_t"),
    ParamID.ActiveTempAlarms: _C_TYPE.get("uint8_t"),
    ParamID.RadioTestMode: _C_TYPE.get("uint8_t"),
    ParamID.SystemMaxPowerWireless: _C_TYPE.get("uint32_t"),
    ParamID.SystemMaxCurrentWireless: _C_TYPE.get("uint32_t"),
    ParamID.SystemMaxPowerWall: _C_TYPE.get("uint32_t"),
    ParamID.SystemMaxCurrentWall: _C_TYPE.get("uint32_t"),
    ParamID.OnlyWallPower: _C_TYPE.get("uint8_t"),
    ParamID.ComputedCurrentLimit: _C_TYPE.get("uint32_t"),
    ParamID.DigitalOnly: _C_TYPE.get("uint8_t"),
    ParamID.StayRecovery: _C_TYPE.get("uint8_t"),
    ParamID.SystemMaxVoltage: _C_TYPE.get("uint32_t"),
    ParamID.BootCount: _C_TYPE.get("uint32_t"),
    ParamID.RadioPowerLevel: _C_TYPE.get("uint8_t"),
    ParamID.BootloaderVersion: _C_TYPE.get("uint32_t"),
    ParamID.BaseUAVCANV1SubjectID: _C_TYPE.get("uint16_t"),
    ParamID.VPASet: _C_TYPE.get("uint32_t"),
    ParamID.LEDTest: _C_TYPE.get("uint16_t"),
    ParamID.IMin: _C_TYPE.get("uint32_t"),
    ParamID.FixedVrect: _C_TYPE.get("uint32_t"),
    ParamID.InputPowerSupplyLimit: _C_TYPE.get("uint32_t"),
    ParamID.BaseUAVCANV1ServiceID: _C_TYPE.get("uint8_t"),
    ParamID.PowerUnpoweredOnTime: _C_TYPE.get("uint16_t"),
    ParamID.PowerUnpoweredOffTime: _C_TYPE.get("uint16_t"),
    ParamID.PowerOffset: _C_TYPE.get("uint16_t"),
    ParamID.RadioMode: _C_TYPE.get("uint16_t"),
    ParamID.RadioChannelRestrictLow: _C_TYPE.get("uint8_t"),
    ParamID.RadioChannelRestrictHigh: _C_TYPE.get("uint8_t"),
    ParamID.RadioFilter1: _C_TYPE.get("uint32_t"),
    ParamID.RadioFilter2: _C_TYPE.get("uint32_t"),
}


class AdcID(IntEnum):
    """ADC Identifiers"""

    PacketCount = 0
    Timestamp = 1
    ChargeState = 2
    Flags = 3
    PowerLevel = 4
    VMon3v3 = 5
    VMon5v = 6
    IMon5v = 7
    VMon12v = 8
    IMon12v = 9
    VMonGateDriver = 10
    IMonGateDriver = 11
    VMonPa = 12
    IMonPa = 13
    TMonPa = 14
    VMonBatt = 15
    VMonCharger = 16
    VRect = 17
    TBoard = 18
    ICharger = 19
    IBattery = 20
    TargetIBatt = 21
    ISingleCharger1 = 22
    ISingleCharger2 = 23
    ISingleCharger3 = 24
    RfSense = 25
    VMon48v = 26
    IMon48v = 27
    TMonAmb = 28
    RadioRSSI = 29
    RadioQuality = 30
    TCharger = 31


ADC_TYPE_MAP = {
    AdcID.PacketCount: _C_TYPE.get("uint16_t"),
    AdcID.Timestamp: _C_TYPE.get("uint32_t"),
    AdcID.ChargeState: _C_TYPE.get("uint8_t"),
    AdcID.Flags: _C_TYPE.get("uint16_t"),
    AdcID.PowerLevel: _C_TYPE.get("uint16_t"),
    AdcID.VMon3v3: _C_TYPE.get("float"),
    AdcID.VMon5v: _C_TYPE.get("float"),
    AdcID.IMon5v: _C_TYPE.get("float"),
    AdcID.VMon12v: _C_TYPE.get("float"),
    AdcID.IMon12v: _C_TYPE.get("float"),
    AdcID.VMonGateDriver: _C_TYPE.get("float"),
    AdcID.IMonGateDriver: _C_TYPE.get("float"),
    AdcID.VMonPa: _C_TYPE.get("float"),
    AdcID.IMonPa: _C_TYPE.get("float"),
    AdcID.TMonPa: _C_TYPE.get("float"),
    AdcID.VMonBatt: _C_TYPE.get("float"),
    AdcID.VMonCharger: _C_TYPE.get("float"),
    AdcID.VRect: _C_TYPE.get("float"),
    AdcID.TBoard: _C_TYPE.get("float"),
    AdcID.ICharger: _C_TYPE.get("float"),
    AdcID.IBattery: _C_TYPE.get("float"),
    AdcID.TargetIBatt: _C_TYPE.get("float"),
    AdcID.ISingleCharger1: _C_TYPE.get("float"),
    AdcID.ISingleCharger2: _C_TYPE.get("float"),
    AdcID.ISingleCharger3: _C_TYPE.get("float"),
    AdcID.RfSense: _C_TYPE.get("float"),
    AdcID.VMon48v: _C_TYPE.get("float"),
    AdcID.IMon48v: _C_TYPE.get("float"),
    AdcID.TMonAmb: _C_TYPE.get("float"),
    AdcID.RadioRSSI: _C_TYPE.get("uint8_t"),
    AdcID.RadioQuality: _C_TYPE.get("uint8_t"),
    AdcID.TCharger: _C_TYPE.get("float"),
}

_EXT_ID_TO_STRUCT = {
    ExtParamID.NiceName: (
        "<16s",
        namedtuple(
            "NiceName",
            ["name"],
        ),
        [True],
    ),
    ExtParamID.AllowedWSOrigin: (
        "<256s",
        namedtuple(
            "AllowedWSOrigin",
            ["origin"],
        ),
        [True],
    ),
    ExtParamID.OTPBlock: (
        "<64s",
        namedtuple(
            "OTPBlock",
            ["data"],
        ),
        [False],
    ),
    ExtParamID.EEPROMBlock: (
        "<16s",
        namedtuple(
            "EEPROMBlock",
            ["data"],
        ),
        [False],
    ),
    ExtParamID.LogFileInfo: (
        "<IIB",
        namedtuple(
            "LogFileInfo",
            ["count", "current", "status_flags"],
        ),
        [False, False, False],
    ),
    ExtParamID.StoredOTAInfo: (
        "<II16s16s",
        namedtuple(
            "StoredOTAInfo",
            ["tx_build_hash", "rx_build_hash", "tx_fw_name", "rx_fw_name"],
        ),
        [False, False, True, True],
    ),
    ExtParamID.FwRevName: (
        "<16s",
        namedtuple(
            "FwRevName",
            ["name"],
        ),
        [True],
    ),
}


class _ResponseType(IntEnum):
    PARAM_UPDATE = 0x80
    PARAM_RESPONSE = 0x81
    ADC_UPDATE = 0x82
    STAGE_RESPONSE = 0x83
    COMMIT_RESPONSE = 0x84
    CONNECTION_STATUS = 0x85
    INCOMING_MESSAGE = 0x86
    RX_ASSOCIATION = 0x87
    OTA_STATUS = 0x88
    EXTENDED_PARAM_RESPONSE = 0x91
    EXTENDED_PARAM_SET_RESPONSE = 0x92


class _RequestType(IntEnum):
    PARAM_READ_REQUEST = 0x01
    PARAM_WRITE_REQUEST = 0x03
    PARAM_STAGE_REQUEST = 0x04
    PARAM_COMMIT_REQUEST = 0x05
    REQUEST_CONNECTION_STATUS = 0x06
    SUBSCRIBE_REQUEST = 0x11
    UNSUBSCRIBE_REQUEST = 0x12
    EXTENDED_WRITE_REQUEST = 0x20
    EXTENDED_READ_REQUEST = 0x21


def process_data(data):
    """Takes binary data and processes it into an object that can be easily parsed"""

    event = {
        _ResponseType.PARAM_UPDATE: ParamUpdate.parse_packet,
        _ResponseType.PARAM_RESPONSE: ParamResponse.parse_packet,
        _ResponseType.STAGE_RESPONSE: StageResponse.parse_packet,
        _ResponseType.COMMIT_RESPONSE: CommitResponse.parse_packet,
        _ResponseType.ADC_UPDATE: ADCUpdate.parse_packet,
        _ResponseType.CONNECTION_STATUS: ConnectedDevices.parse_packet,
        _ResponseType.INCOMING_MESSAGE: IncomingMessage.parse_packet,
        _ResponseType.RX_ASSOCIATION: IncomingAssociation.parse_packet,
        _ResponseType.OTA_STATUS: IncomingOTAStatus.parse_packet,
        _ResponseType.EXTENDED_PARAM_RESPONSE: ExtendedParameterResponse.parse_packet,
        _ResponseType.EXTENDED_PARAM_SET_RESPONSE: ExtendedParameterSetResponse.parse_packet,
        _RequestType.PARAM_READ_REQUEST: ParamReadRequest.parse_packet,
        _RequestType.PARAM_WRITE_REQUEST: ParamWriteRequest.parse_packet,
        _RequestType.PARAM_STAGE_REQUEST: ParamStageRequest.parse_packet,
        _RequestType.PARAM_COMMIT_REQUEST: ParamCommitRequest.parse_packet,
        _RequestType.REQUEST_CONNECTION_STATUS: RequestConnectionStatus.parse_packet,
        _RequestType.SUBSCRIBE_REQUEST: SubscribeRequest.parse_packet,
        _RequestType.UNSUBSCRIBE_REQUEST: UnsubscribeRequest.parse_packet,
        _RequestType.EXTENDED_WRITE_REQUEST: ExtendedWriteRequest.parse_packet,
        _RequestType.EXTENDED_READ_REQUEST: ExtendedReadRequest.parse_packet,
    }
    response_type = _ResponseType(data[0]) if data[0] > 0x7F else _RequestType(data[0])
    return event[response_type](data)


def first_empty(l) -> Optional[int]:
    """Returns the index of the first empty character in l"""
    try:
        return next(
            char for char in enumerate(l) if char[1] in (0x00, 0xFF)
        )[0]
    except StopIteration:
        return None