@echo off
if "%~1"=="" (
    echo No file path provided. Exiting...
    exit /b 1
)

REM Set the full file path from the parameter
set "LOG_FILE=%~1"

REM Extract directory path from the parameter
set "LOG_DIR=%~dp1"

REM Remove trailing backslash if it exists
set "LOG_DIR=%LOG_DIR:~0,-1%"

REM Output the log directory to verify
echo The log directory is: %LOG_DIR%

REM Extract and store the base path up to 'wiretap_files'
for /f "tokens=1-4 delims=\" %%a in ("%LOG_DIR%") do (
    set "BASE_DIR=%%a\%%b\%%c\%%d"
)

REM Output the base directory to verify
echo The base directory is: %BASE_DIR%

REM Check if requirements.txt already exists
if exist "%BASE_DIR%\requirements.txt" (
    echo requirements.txt already exists in %BASE_DIR%
) else (
    REM Create the requirements.txt file in the BASE_DIR and write the content
    (
    echo flask==1.1.1
    echo flask-sqlalchemy==2.4.0
    echo flask-migrate==2.5.2
    echo flask_login==0.4.1
    echo flask_wtf==0.14.2
    echo pytz
    echo twilio
    echo getmac
    echo xlsxwriter
    echo ujson==4.3.0
    echo email_validator
    echo websockets==9.1
    echo waitress==1.3.0
    echo openpyxl==2.6.2
    echo requests^>=2.22.0
    echo gunicorn==19.9.0
    echo fasteners==0.15
    echo flask-talisman==0.7.0
    echo pymodbus==2.2.0
    echo astral==1.10.1
    echo dateutils==0.6.6
    echo itsdangerous==1.1.0
    echo jinja2==2.11.0
    echo opcua==0.98.9
    echo psutil==5.7.0
    echo pykarbon==1.1.8
    echo comtrade==0.0.3
    echo flask-cors==3.0.10
    echo python3-nmap==1.4.9
    echo dataclasses==0.6
    echo asyncua==0.9.14
    echo opencv-python==4.5.3.56
    echo sqlalchemy==1.3.7
    echo WTForms==2.3.3
    echo werkzeug==0.16.1
    echo markupsafe==2.0.1
    echo boto3==1.21.46
    echo opencv-python-headless==4.5.3.56
    echo python-crontab==3.0.0
    echo configparser^>=5.2.0
    echo urllib3==1.25.11
    echo pandas==1.4.4
    echo numpy==1.19
    echo PyQt5==5.13.0
    echo PyQt5-Qt5==5.15.2
    echo PyQt5-sip==12.13.0
    echo PyQtWebEngine==5.12
    echo PyQtWebEngine-Qt5==5.15.2
    ) > "%BASE_DIR%\requirements.txt"

    echo requirements.txt file created successfully in %BASE_DIR%
)

SET VENV_DIR=%BASE_DIR%\mac_venv
set "PYTHON_VERSION=3.8.10"
set "PYTHON_INSTALL_DIR=%VENV_DIR%\Python38"
set "PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe"
set "DOWNLOAD_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_INSTALLER%"
set PYTHON_PATH="%PYTHON_INSTALL_DIR%\python.exe"

set "NMAP_VERSION=7.92"
set "NMAP_INSTALL_DIR=C:\Program Files (x86)\Nmap"
set "NMAP_INSTALLER=nmap-%NMAP_VERSION%-setup.exe"
set "NMAP_DOWNLOAD_URL=https://nmap.org/dist/%NMAP_INSTALLER%"

:: Ensure log directory exists
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
    echo Created log directory >> "%LOG_FILE%"
) else (
    echo Log directory already exists >> "%LOG_FILE%"
)

:: Ensure virtual environment directory exists
if not exist "%VENV_DIR%" (
    mkdir "%VENV_DIR%"
    echo Created virtual environment directory >> "%LOG_FILE%"
) else (
    echo Virtual environment directory already exists >> "%LOG_FILE%"
)

goto :check_python
:: Function to log messages
:log_message
echo %~1 >> "%LOG_FILE%"
goto :EOF

:: Function to send progress updates
:send_progress
echo progress:%~1 >> "%LOG_FILE%"
goto :EOF

:check_python
call :log_message "Test Rajesh"
REM Check if the installer exists, if not, download it
if not exist "%PYTHON_PATH%" (
    echo Downloading Python %PYTHON_VERSION% installer...
    powershell -command "Invoke-WebRequest -Uri %DOWNLOAD_URL% -OutFile %PYTHON_INSTALLER%"
    REM Install Python silently
    call :log_message "Installing Python %PYTHON_VERSION% to %PYTHON_INSTALL_DIR%..."
    %PYTHON_INSTALLER% /quiet InstallAllUsers=0 TargetDir=%PYTHON_INSTALL_DIR% PrependPath=0

    REM Check if installation was successful
    if %errorlevel% neq 0 (
        call :log_message "Python installation failed!"
        exit /b %errorlevel%
    )

    REM Set PYTHON_PATH environment variable
    set PYTHON_PATH=%PYTHON_INSTALL_DIR%\python.exe
    call :log_message "Python 3.8 installed successfully. Path: %PYTHON_PATH%"
) else (
    call :log_message "Python 3.8 already exists in %PYTHON_PATH%"
)

:setup_venv
call :send_progress 30
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    call :log_message "Creating virtual environment in %VENV_DIR%"
    "%PYTHON_PATH%" -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        call :log_message "Failed to create virtual environment."
        exit /b 1
    )
) else (
    call :log_message "Virtual environment already exists in %VENV_DIR%"
)

:install_requirements
call :send_progress 50
call :log_message "Using Python at %PYTHON_PATH%"
call "%VENV_DIR%\Scripts\activate.bat"

REM Check if pip is installed
"%PYTHON_PATH%" -m pip --version >> "%LOG_FILE%" 2>&1
if %errorlevel% neq 0 (
    call :log_message "Pip not found. Installing pip..."
    "%PYTHON_PATH%" -m ensurepip >> "%LOG_FILE%" 2>&1
    if %errorlevel% neq 0 (
        call :log_message "Failed to install pip. Exiting..."
        exit /b 1
    )
    call :log_message "Pip installed successfully."
)

call :log_message "Installing requirements from requirements.txt"
"%PYTHON_PATH%" -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1
"%PYTHON_PATH%" -m pip install -r "%BASE_DIR%\requirements.txt" >> "%LOG_FILE%" 2>&1
if %errorlevel% neq 0 (
    call :log_message "Failed to install Python requirements from requirements.txt."
    exit /b 1
)

goto :check_nmap

:check_nmap
call :send_progress 70
if exist "%NMAP_INSTALL_DIR%" (
    call :log_message "Nmap is already installed"
    goto :finalize
) else (
    call :log_message "Nmap is not installed. Installing..."

    REM Check if the installer exists, if not, download it
    if not exist "%NMAP_INSTALL_DIR%" (
        call :log_message "Downloading Nmap %NMAP_VERSION% installer..."
        powershell -Command "try { Invoke-WebRequest -Uri %NMAP_DOWNLOAD_URL% -OutFile %NMAP_INSTALLER% -ErrorAction Stop } catch { exit 1 }"
        if %errorlevel% neq 0 (
            call :log_message "Failed to download Nmap installer from %NMAP_DOWNLOAD_URL%"
            exit /b %errorlevel%
        )
    )

    REM Install Nmap interactively if silent installation is not supported
    call :log_message "Installing Nmap %NMAP_VERSION% to %NMAP_INSTALL_DIR% interactively..."
    start /wait %NMAP_INSTALLER%
    if %errorlevel% neq 0 (
        call :log_message "Nmap installation failed!"
        exit /b %errorlevel%
    )

    REM Verify installation
    where nmap > nul
    if %errorlevel% neq 0 (
        call :log_message "Nmap installation verification failed!"
        exit /b %errorlevel%
    )

    REM Set NMAP environment variable
    setx NMAP_HOME "%NMAP_INSTALL_DIR%" /m
    if %errorlevel% neq 0 (
        call :log_message "Failed to set NMAP_HOME environment variable."
        exit /b %errorlevel%
    )

    REM Update PATH environment variable
    setx PATH "%NMAP_INSTALL_DIR%;%NMAP_INSTALL_DIR%\bin;%PATH%" /m
    if %errorlevel% neq 0 (
        call :log_message "Failed to update PATH environment variable."
        exit /b %errorlevel%
    )

    call :log_message "Nmap %NMAP_VERSION% installed successfully in %NMAP_INSTALL_DIR%."
    call :log_message "NMAP_HOME set to %NMAP_INSTALL_DIR%."
    call :log_message "PATH updated with %NMAP_INSTALL_DIR% and %NMAP_INSTALL_DIR%\bin."
)

goto :finalize




:finalize
call :send_progress 100
call :log_message "Setup completed successfully. Python virtual environment path: %PYTHON_PATH%"
echo "%PYTHON_PATH%"
goto :EOF

endlocal
