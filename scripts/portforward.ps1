# Port Forwarding Setup for Stock Server
# Run in PowerShell as Administrator

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("setup", "remove", "status", "test")]
    [string]$Action,

    [int]$Port = 8000,

    [string]$WSLAddress = ""
)

$ErrorActionPreference = "Stop"

# Get WSL2 IP
function Get-WSL2IP {
    $ip = wsl hostname -I 2>$null | ForEach-Object { $_.Trim().Split(" ")[0] }
    if (-not $ip) {
        Write-Host "[ERROR] Cannot get WSL2 IP." -ForegroundColor Red
        Write-Host "Check if WSL2 is running: wsl" -ForegroundColor Yellow
        exit 1
    }
    return $ip
}

# Setup port forwarding
function Set-PortForward {
    param([int]$Port, [string]$WSLIP)

    Write-Host "=== Setting up port forwarding ===" -ForegroundColor Cyan
    Write-Host "  Port: $Port" -ForegroundColor Gray
    Write-Host "  WSL2 IP: $WSLIP" -ForegroundColor Gray

    netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 2>$null
    netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectport=$Port connectaddress=$WSLIP

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Port forwarding setup complete" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Port forwarding setup failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "`n=== Adding firewall rule ===" -ForegroundColor Cyan

    $ruleName = "StockServer-Port$Port"
    Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

    New-NetFirewallRule -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -Description "Stock Analysis Server - WSL2 Port Forwarding" | Out-Null

    if ($?) {
        Write-Host "[OK] Firewall rule added" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Failed to add firewall rule" -ForegroundColor Yellow
    }

    $windowsIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -ne "127.0.0.1" } | Select-Object -First 1).IPAddress

    Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
    Write-Host "  Windows IP: $windowsIP" -ForegroundColor White
    Write-Host "  Access URL: http://${windowsIP}:${Port}" -ForegroundColor Yellow
    Write-Host "`n  Access from other PC on same LAN using above URL." -ForegroundColor Gray
}

# Remove port forwarding
function Remove-PortForward {
    param([int]$Port)

    Write-Host "=== Removing port forwarding ===" -ForegroundColor Cyan

    netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0

    $ruleName = "StockServer-Port$Port"
    Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

    Write-Host "[OK] Port forwarding and firewall rule removed" -ForegroundColor Green
}

# Show status
function Get-PortForwardStatus {
    param([int]$Port)

    Write-Host "=== Port Forwarding Status ===" -ForegroundColor Cyan

    $forwarding = netsh interface portproxy show all | Select-String ":$Port "
    if ($forwarding) {
        Write-Host "  Port Forwarding: Configured" -ForegroundColor Green
        Write-Host "  $forwarding" -ForegroundColor Gray
    } else {
        Write-Host "  Port Forwarding: Not configured" -ForegroundColor Yellow
    }

    $rule = Get-NetFirewallRule -DisplayName "StockServer-Port$Port" -ErrorAction SilentlyContinue
    if ($rule) {
        Write-Host "  Firewall: Configured" -ForegroundColor Green
    } else {
        Write-Host "  Firewall: Not configured" -ForegroundColor Yellow
    }

    $wslIP = Get-WSL2IP
    Write-Host "`n=== WSL2 Connection Test ===" -ForegroundColor Cyan
    Write-Host "  WSL2 IP: $wslIP" -ForegroundColor Gray

    try {
        $response = Invoke-WebRequest -Uri "http://${wslIP}:${Port}" -TimeoutSec 3 -UseBasicParsing
        Write-Host "  WSL2 Server: OK ($($response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host "  WSL2 Server: Connection failed" -ForegroundColor Red
    }
}

# Test connection
function Test-PortForward {
    param([int]$Port)

    Write-Host "=== Connection Test ===" -ForegroundColor Cyan

    $wslIP = Get-WSL2IP
    Write-Host "`n1. WSL2 Connection Test" -ForegroundColor Yellow
    Write-Host "   IP: $wslIP" -ForegroundColor Gray

    try {
        $response = Invoke-WebRequest -Uri "http://${wslIP}:${Port}" -TimeoutSec 3 -UseBasicParsing
        Write-Host "   Result: OK (HTTP $($response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host "   Result: Failed - $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "   Check if server is running in WSL2." -ForegroundColor Yellow
    }

    Write-Host "`n2. Port Forwarding Test" -ForegroundColor Yellow
    $forwarding = netsh interface portproxy show all | Select-String ":$Port "
    if ($forwarding) {
        Write-Host "   Result: Configured" -ForegroundColor Green
    } else {
        Write-Host "   Result: Not configured" -ForegroundColor Red
    }

    $windowsIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -ne "127.0.0.1" } | Select-Object -First 1).IPAddress

    Write-Host "`n=== Connection Info ===" -ForegroundColor Green
    Write-Host "  Same PC: http://localhost:${Port}" -ForegroundColor White
    Write-Host "  Same LAN: http://${windowsIP}:${Port}" -ForegroundColor Yellow
    Write-Host "`n  Test connection from another PC using above URL." -ForegroundColor Gray
}

# Execute
switch ($Action) {
    "setup" {
        if (-not $WSLAddress) {
            $WSLAddress = Get-WSL2IP
        }
        Set-PortForward -Port $Port -WSLIP $WSLAddress
    }
    "remove" {
        Remove-PortForward -Port $Port
    }
    "status" {
        Get-PortForwardStatus -Port $Port
    }
    "test" {
        Test-PortForward -Port $Port
    }
}
