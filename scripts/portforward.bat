@echo off
REM ============================================
REM  Stock Server - Port Forwarding Setup
REM ============================================

setlocal

set PORT=8000

if "%1"=="" (
    echo.
    echo ========================================
    echo  Stock Server Port Forwarding Tool
    echo ========================================
    echo.
    echo  Usage:
    echo    %~nx0 setup    - Setup port forwarding
    echo    %~nx0 remove   - Remove port forwarding
    echo    %~nx0 status   - Show current status
    echo    %~nx0 test     - Test connection
    echo.
    echo  ** Run as Administrator **
    echo.
    goto :eof
)

REM Check admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Administrator privileges required.
    echo Right-click and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

if "%1"=="setup" goto :setup
if "%1"=="remove" goto :remove
if "%1"=="status" goto :status
if "%1"=="test" goto :test

echo [ERROR] Unknown command: %1
goto :eof

:setup
echo.
echo === Setting up port forwarding ===

REM Get WSL2 IP
for /f "tokens=1" %%i in ('wsl hostname -I 2^>nul') do set WSLIP=%%i

if "%WSLIP%"=="" (
    echo [ERROR] Cannot get WSL2 IP.
    echo Check if WSL2 is running.
    pause
    exit /b 1
)

echo   WSL2 IP: %WSLIP%
echo   Port: %PORT%

REM Delete existing port forwarding
netsh interface portproxy delete v4tov4 listenport=%PORT% listenaddress=0.0.0.0 >nul 2>&1

REM Add new port forwarding
netsh interface portproxy add v4tov4 listenport=%PORT% listenaddress=0.0.0.0 connectport=%PORT% connectaddress=%WSLIP%

if %errorlevel% equ 0 (
    echo [OK] Port forwarding setup complete
) else (
    echo [ERROR] Port forwarding setup failed
    pause
    exit /b 1
)

REM Add firewall rule
echo.
echo === Adding firewall rule ===

netsh advfirewall firewall delete rule name="StockServer-Port%PORT%" >nul 2>&1
netsh advfirewall firewall add rule name="StockServer-Port%PORT%" dir=in action=allow protocol=TCP localport=%PORT%

if %errorlevel% equ 0 (
    echo [OK] Firewall rule added
) else (
    echo [WARN] Failed to add firewall rule
)

REM Get Windows IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=1" %%b in ("%%a") do set WINIP=%%b
)

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo  Windows IP: %WINIP%
echo  Access URL: http://%WINIP%:%PORT%
echo.
echo  Access from other PC on same LAN using above URL.
echo.
pause
goto :eof

:remove
echo.
echo === Removing port forwarding ===

netsh interface portproxy delete v4tov4 listenport=%PORT% listenaddress=0.0.0.0
netsh advfirewall firewall delete rule name="StockServer-Port%PORT%" >nul 2>&1

echo [OK] Port forwarding and firewall rule removed
echo.
pause
goto :eof

:status
echo.
echo === Port Forwarding Status ===
echo.

echo [Port Forwarding Rules]
netsh interface portproxy show all | findstr ":%PORT%"
if %errorlevel% neq 0 echo   Not configured

echo.
echo [Firewall Rules]
netsh advfirewall firewall show rule name="StockServer-Port%PORT%" >nul 2>&1
if %errorlevel% equ 0 (
    echo   Configured
) else (
    echo   Not configured
)

echo.
echo === WSL2 Connection Test ===
for /f "tokens=1" %%i in ('wsl hostname -I 2^>nul') do set WSLIP=%%i
echo   WSL2 IP: %WSLIP%

curl -s -o nul -w "  WSL2 Server: HTTP %%{http_code}" http://%WSLIP%:%PORT% 2>nul
if %errorlevel% neq 0 echo   WSL2 Server: Connection failed
echo.
echo.
pause
goto :eof

:test
echo.
echo === Connection Test ===

for /f "tokens=1" %%i in ('wsl hostname -I 2^>nul') do set WSLIP=%%i

echo.
echo 1. WSL2 Connection Test
echo    IP: %WSLIP%
curl -s -o nul -w "    Result: HTTP %%{http_code}" http://%WSLIP%:%PORT% 2>nul
if %errorlevel% neq 0 echo    Result: Connection failed
echo.

echo 2. Port Forwarding Test
netsh interface portproxy show all | findstr ":%PORT%" >nul
if %errorlevel% equ 0 (
    echo    Result: Configured
) else (
    echo    Result: Not configured
)

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=1" %%b in ("%%a") do set WINIP=%%b
)

echo.
echo ========================================
echo  Connection Info
echo ========================================
echo.
echo  Same PC: http://localhost:%PORT%
echo  Same LAN: http://%WINIP%:%PORT%
echo.
echo  Test connection from another PC using above URL.
echo.
pause
goto :eof
