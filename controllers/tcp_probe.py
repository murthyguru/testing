import os
import sys
import json
from datetime import datetime
from pymodbus.client.sync import ModbusTcpClient

# Function to get the directory of the currently running script
def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))

# Get the directory of app.py
script_dir = get_script_dir()

# Navigate up the directory tree to the desired base path
script_base_path = os.path.dirname(os.path.dirname(script_dir))

# Define the directory for file operations within the base path
project_directory = os.path.join(script_base_path, 'python-screen-app')

# Define the base path for file operations within the home directory
base_path = os.path.join(os.getenv('USERPROFILE'), 'wiretap_files', 'python-screen-app')

# Create the base path directory if it doesn't exist
os.makedirs(base_path, exist_ok=True)


def probe(addr, port, device, function, registers):
    file_path = f"{base_path}/tcp_probe.json"

    # Check if the file exists
    if not os.path.exists(file_path):
        # If the file does not exist, create an empty JSON file
        with open(file_path, 'w') as file:
            json.dump({}, file)  # Create an empty JSON object
    else:
         # Always create a new empty JSON file
        with open(file_path, 'w') as file:
            json.dump({}, file)  # Create an empty JSON object
    
    def read_json(file_path):
        try:
            if os.path.getsize(file_path) == 0:
                return {}
            with open(file_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {
                "status": "Exited due to an error",
                "mostRecentError": datetime.now().isoformat(sep=' ', timespec='milliseconds'),
                "error": str(e)
            }

    def write_json(data, file_path):
        with open(file_path, "w") as f:
            f.write(json.dumps(data))

    registerReads = read_json(file_path)
    registerReads["status"] = "Started"

    if "device" not in registerReads:
        registerReads["device"] = device
    elif device != registerReads["device"]:
        registerReads = {"status": "Started", "device": device}

    write_json(registerReads, file_path)

    try:
        client = ModbusTcpClient(host=addr, port=port, timeout=2)
        client.connect()
    except Exception as e:
        registerReads["status"] = "Failed"
        write_json(registerReads, file_path)
        return

    functionStr = str(function)
    if functionStr not in registerReads:
        registerReads[functionStr] = {}

    if "registersList" not in registerReads[functionStr]:
        registerReads[functionStr]["registersList"] = registers
    else:
        registerReads[functionStr]["registersList"] += registers

    registerReads[functionStr]["registersList"] = list(set(registerReads[functionStr]["registersList"]))

    processedRegisters = []

    for register in registers:
        registerReads["status"] = f"{((len(processedRegisters) / len(registers)) * 100):.2f}"
        registerStr = str(register)

        if function == 1:
            res1 = client.read_coils(register, 1, unit=device)
            if not res1.isError():
                registerReads[functionStr][registerStr] = int(res1.bits[0])
        elif function == 2:
            res1 = client.read_discrete_inputs(register, 1, unit=device)
            if not res1.isError():
                registerReads[functionStr][registerStr] = res1.registers[0]
                if register != 255 and str(register + 1) not in registerReads[functionStr]:
                    res2 = client.read_discrete_inputs(register + 1, 1, unit=device)
                    if not res2.isError():
                        registerReads[functionStr][str(register + 1)] = res2.registers[0]
        elif function == 3:
            res1 = client.read_holding_registers(register, 1, unit=device)
            if not res1.isError():
                registerReads[functionStr][registerStr] = res1.registers[0]
                if register != 255 and str(register + 1) not in registerReads[functionStr]:
                    res2 = client.read_holding_registers(register + 1, 1, unit=device)
                    if not res2.isError():
                        registerReads[functionStr][str(register + 1)] = res2.registers[0]
        elif function == 4:
            res1 = client.read_input_registers(register, 1, unit=device)
            if not res1.isError():
                registerReads[functionStr][registerStr] = res1.registers[0]
                if register != 255 and str(register + 1) not in registerReads[functionStr]:
                    res2 = client.read_input_registers(register + 1, 1, unit=device)
                    if not res2.isError():
                        registerReads[functionStr][str(register + 1)] = res2.registers[0]

        processedRegisters.append(register)
        write_json(registerReads, file_path)

    registerReads["status"] = "Finished"

    write_json(registerReads, file_path)

if __name__ == '__main__':
    probe(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), [int(x) for x in sys.argv[5].split(",")])
