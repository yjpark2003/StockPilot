# Stock Server - 네트워크 접속 가이드

## 개요

이 가이드는 WSL2에서 실행 중인 주식 분석 웹 서버를 같은 LAN의 다른 PC에서 접속할 수 있도록 설정하는 방법을 설명합니다.

---

## 빠른 시작

### 1. 서버 실행
```bash
# WSL2 터미널에서
cd ~/work/StockPilot
python3 main.py server --host 0.0.0.0 --port 8001
```

### 2. 포트 포워딩 설정
```powershell
# Windows PowerShell (관리자)에서
cd \\wsl$\Ubuntu\home\<username>\work\StockPilot\scripts
.\portforward.bat setup
```

### 3. 다른 PC에서 접속
```
http://[Windows IP]:8001
```

---

## 상세 설정

### Windows 포트 포워딩이란?

WSL2는 기본적으로 NAT 네트워크를 사용하여 호스트 PC와 동일한 IP를 공유하지 않습니다. 따라서 같은 LAN의 다른 PC에서 WSL2 서비스에 직접 접근할 수 없습니다.

포트 포워딩은 Windows 호스트의 특정 포트로 들어오는 트래픽을 WSL2 내부의 같은 포트로 전달하는 설정입니다.

```
[다른 PC] -->> [Windows:8001] -->> [WSL2:8001]
```

---

## 설정 방법

### 방법 1: 자동 설정 스크립트 사용 (권장)

#### 1단계: 스크립트 복사
Windows에서 다음 경로로 이동:
```
\\wsl$\Ubuntu\home\<username>\work\StockPilot\scripts\
```

#### 2단계: 관리자 PowerShell에서 실행
```powershell
# PowerShell을 관리자 권한으로 실행
# 먼저 Windows 디렉토리로 이동 (UNC 경로 문제 해결)
cd C:\Windows

# 설정 실행
\\wsl$\Ubuntu\home\<username>\work\StockPilot\scripts\portforward.bat setup

# 또는 PowerShell 스크립트 사용
\\wsl$\Ubuntu\home\<username>\work\StockPilot\scripts\portforward.ps1 -Action setup
```

#### 3단계: 확인
```
=== 설정 완료 ===
  Windows IP: 192.168.1.XXX
  접속 주소: http://192.168.1.XXX:8001
```

### 방법 2: 수동 설정

#### 1단계: WSL2 IP 확인
```bash
# WSL2 터미널에서
hostname -I
# 예: 172.x.x.x
```

#### 2단계: 포트 포워딩 설정
```powershell
# Windows PowerShell (관리자)에서
netsh interface portproxy add v4tov4 `
    listenport=8001 `
    listenaddress=0.0.0.0 `
    connectport=8001 `
    connectaddress=172.x.x.x
```

#### 3단계: 방화벽 규칙 추가
```powershell
netsh advfirewall firewall add rule `
    name="StockServer-Port8001" `
    dir=in `
    action=allow `
    protocol=TCP `
    localport=8001
```

---

## 명령어 참조

### 포트 포워딩 관리

| 명령어 | 설명 |
|--------|------|
| `netsh interface portproxy show all` | 현재 포트포워딩 규칙 확인 |
| `netsh interface portproxy delete v4tov4 listenport=8001 listenaddress=0.0.0.0` | 포트포워딩 규칙 삭제 |

### 방화벽 관리

| 명령어 | 설명 |
|--------|------|
| `netsh advfirewall firewall show rule name="StockServer-Port8001"` | 방화벽 규칙 확인 |
| `netsh advfirewall firewall delete rule name="StockServer-Port8001"` | 방화벽 규칙 삭제 |

### 스크립트 명령어

| 명령어 | 설명 |
|--------|------|
| `.\portforward.bat setup` | 포트포워딩 + 방화벽 설정 |
| `.\portforward.bat remove` | 설정 제거 |
| `.\portforward.bat status` | 현재 상태 확인 |
| `.\portforward.bat test` | 연결 테스트 |

---

## 문제 해결

### 0. UNC 경로 오류 (cd \\wsl... 실패)

**증상:** 
```
UNC 경로는 지원되지 않습니다. Windows 디렉토리를 기본으로 합니다.
'??꾧뎄'은(는) 내부 또는 외부 명령...
```

**원인:** Windows CMD는 UNC 경로(`\\wsl$...`)를 현재 디렉토리로 사용할 수 없습니다.

**해결책:**
```powershell
# 1. 먼저 Windows 디렉토리로 이동
cd C:\Windows

# 2. 스크립트를 전체 경로로 실행
\\wsl$\Ubuntu\home\<username>\work\StockPilot\scripts\portforward.bat setup

# 또는 PowerShell 스크립트 사용
\\wsl$\Ubuntu\home\<username>\work\StockPilot\scripts\portforward.ps1 -Action setup
```

### 1. 다른 PC에서 접속이 안됨

**원인:** WSL2 IP 변경

WSL2를 재시작하면 IP가 변경될 수 있습니다.

```bash
# WSL2에서 새 IP 확인
hostname -I

# Windows에서 포트포워딩 재설정
netsh interface portproxy delete v4tov4 listenport=8001 listenaddress=0.0.0.0
netsh interface portproxy add v4tov4 listenport=8001 listenaddress=0.0.0.0 connectport=8001 connectaddress=[새 IP]
```

### 2. 방화벽 차단

```powershell
# Windows Defender 방화벽 임시 비활성화 (테스트용)
netsh advfirewall set allprofiles state off

# 다시 활성화
netsh advfirewall set allprofiles state on
```

### 3. 서버가 응답하지 않음

```bash
# WSL2에서 서버 상태 확인
curl http://localhost:8001

# 서버 재시작
python3 main.py server --host 0.0.0.0 --port 8001
```

### 4. 포트 충돌

```powershell
# 8001 포트 사용 프로세스 확인
netstat -ano | findstr :8001

# 다른 포트 사용
python3 main.py server --host 0.0.0.0 --port 8001
```

---

## 네트워크 구성도

```
┌─────────────────────────────────────────────────────────┐
│                      LAN 네트워크                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐    ┌──────────────────────────────┐  │
│  │   다른 PC    │    │         Windows PC           │  │
│  │              │    │  ┌────────────────────────┐  │  │
│  │  브라우저    │───▶│  │   WSL2 (Ubuntu)       │  │  │
│  │              │    │  │   172.x.x.x:8001       │  │  │
│  │  접속:       │    │  │                        │  │  │
│  │  WindowsIP  │    │  └────────────────────────┘  │  │
│  │  :8001      │    │           ▲                   │  │
│  │              │    │           │ 포트포워딩        │  │
│  └──────────────┘    │    0.0.0.0:8001 ───────────┘  │  │
│                      └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 자동화 설정

### WSL2 시작 시 자동 포트포워딩

Windows 작업 스케줄러를 사용하여 WSL2 시작 시 자동으로 포트포워딩을 설정할 수 있습니다.

```powershell
# 작업 스케줄러에 등록
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-File C:\path\to\portforward.ps1 -Action setup"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "WSL2-PortForward" `
    -Action $action -Trigger $trigger -RunLevel Highest `
    -Description "WSL2 Port Forwarding Setup"
```

---

## 참고사항

- 포트포워딩 설정은 **관리자 권한**이 필요합니다
- WSL2 재시작 시 IP가 변경될 수 있어 재설정이 필요할 수 있습니다
- Windows 방화벽이 외부 트래픽을 차단할 수 있으므로 방화벽 규칙 설정이 필요합니다
- 포트 충돌이 발생하면 다른 포트를 사용하세요
