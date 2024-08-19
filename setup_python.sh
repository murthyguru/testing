#!/bin/bash

LOG_FILE=$1
LOG_DIR=$(dirname "$LOG_FILE")
BASE_DIR=$(dirname "$LOG_DIR")
VENV_DIR="$BASE_DIR/mac_venv"

# Function to log messages
log_message() {
    echo "$1" >> "$LOG_FILE"
}

# Function to send progress updates
send_progress() {
    echo "progress:$1" >> "$LOG_FILE"
}

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Ensure virtual environment directory exists
mkdir -p "$VENV_DIR"

# Add Homebrew to PATH if not already in PATH
if ! command -v brew &> /dev/null
then
    log_message "Adding Homebrew to PATH"
    export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
fi

# Function to check if python3.8 is installed
check_python() {
    send_progress 10
    if command -v python3.8 &> /dev/null
    then
        log_message "Python 3.8 is already installed"
        PYTHON_PATH=$(command -v python3.8)
    else
        log_message "Python 3.8 is not installed. Installing..."
        brew install python@3.8
        PYTHON_PATH=$(command -v python3.8)
        if [ -z "$PYTHON_PATH" ]; then
            log_message "Python 3.8 installation failed or path not found."
            exit 1
        fi
    fi
}

# Function to set up virtual environment
setup_venv() {
    send_progress 30
    if [ ! -d "$VENV_DIR/bin" ]; then
        log_message "Creating virtual environment in $VENV_DIR"
        $PYTHON_PATH -m venv "$VENV_DIR"
    else
        log_message "Virtual environment already exists in $VENV_DIR"
    fi
}

# Function to check if nmap is installed
check_nmap() {
    send_progress 50
    if command -v nmap &> /dev/null
    then
        log_message "Nmap is already installed"
    else
        log_message "Nmap is not installed. Installing..."
        brew install nmap
        if ! command -v nmap &> /dev/null; then
            log_message "Nmap installation failed or path not found."
            exit 1
        fi
    fi
}

# Requirements to install
REQUIREMENTS=$(cat <<EOF
flask==1.1.1
flask-sqlalchemy==2.4.0
flask-migrate==2.5.2
flask_login==0.4.1
flask_wtf==0.14.2
pytz
twilio
getmac
xlsxwriter
ujson==4.3.0
email_validator
websockets==9.1
waitress==1.3.0
openpyxl==2.6.2
requests>=2.22.0
gunicorn==19.9.0
fasteners==0.15
flask-talisman==0.7.0
pymodbus==2.2.0
astral==1.10.1
dateutils==0.6.6
itsdangerous==1.1.0
jinja2==2.11.0
opcua==0.98.9
psutil==5.7.0
pykarbon==1.1.8
comtrade==0.0.3
flask-cors==3.0.10
python3-nmap==1.4.9
dataclasses==0.6
asyncua==0.9.14
opencv-python==4.5.3.56
sqlalchemy==1.3.7
WTForms==2.3.3
werkzeug==0.16.1
markupsafe==2.0.1
boto3==1.21.46
opencv-python-headless==4.5.3.56
python-crontab==3.0.0
configparser>=5.2.0
urllib3==1.25.11
pandas==1.4.4
numpy==1.19
PyQt5==5.13.0     
PyQt5-Qt5==5.15.2     
PyQt5-sip==12.13.0    
PyQtWebEngine==5.12       
PyQtWebEngine-Qt5==5.15.2
EOF
)

# Function to install required Python libraries
install_requirements() {
    send_progress 70
    if [ -z "$PYTHON_PATH" ]; then
        log_message "Python 3.8 installation failed or path not found."
        exit 1
    else
        log_message "Using Python at $PYTHON_PATH"
        "$VENV_DIR/bin/python3" -m pip install --upgrade pip
        echo "$REQUIREMENTS" | "$VENV_DIR/bin/python3" -m pip install -r /dev/stdin
    fi
}

# Main script execution
check_python
setup_venv
check_nmap
install_requirements
send_progress 100

log_message "Python virtual environment path: $VENV_DIR/bin/python3"
echo "$VENV_DIR/bin/python3"
