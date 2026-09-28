# 주간 주식 분석 리포트 시스템

매일 자동으로 주식을 분석하고 웹에서 리포트를 확인할 수 있는 시스템

## 기능

- 국내/해외 주식 자동 분석
- HTML 리포트 생성 (차트, 뉴스, 투자자 동향)
- 웹 서버를 통한 리포트 열람
- 종목 관리 대시보드
- 한글 종목명 검색 지원

## 종목 리스트 (샘플)

### 국내
| 종목 | 코드 | 시장 |
|------|------|------|
| 삼성전자 | 005930 | KOSPI |
| SK하이닉스 | 000660 | KOSPI |
| NAVER | 035420 | KOSPI |
| 카카오 | 035720 | KOSPI |
| LG화학 | 051910 | KOSPI |
| 삼성SDI | 006400 | KOSPI |
| LG에너지솔루션 | 373220 | KOSPI |
| 삼성바이오로직스 | 207940 | KOSPI |

### 해외
| 종목 | 티커 | 시장 |
|------|------|------|
| Apple | AAPL | NASDAQ |
| Microsoft | MSFT | NASDAQ |
| Alphabet | GOOGL | NASDAQ |
| Amazon | AMZN | NASDAQ |
| NVIDIA | NVDA | NASDAQ |

## 설치

```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

## 실행 방법

### 1. 분석 실행
```bash
# 전체 분석 (국내 + 해외)
python3 main.py analyze

# 국내만
python3 main.py analyze --market domestic

# 해외만
python3 main.py analyze --market foreign
```

#### 분석 구간 지정 (생략하면 요청일 기준 규칙 사용)

```bash
# 월 내 주차 (예: 2026년 9월 1주차 = 08/31(월) ~ 09/06(일), ISO 36주차)
python3 main.py analyze --year 2026 --month 9 --week 1

# ISO 주차 직접 지정
python3 main.py analyze --iso-year 2026 --iso-week 36

# 시작일 ~ 종료일 직접 지정 (최대 45일)
python3 main.py analyze --start 2026-09-01 --end 2026-09-05
```

지정 구간으로 실행하면 리포트도 `reports/weekly/<구간 종료일>/` 아래 저장되므로
오늘짜 리포트를 덮어쓰지 않는다. 웹 화면(`/`)의 **분석 구간 지정** 패널에서도
같은 방식으로 지정할 수 있고, 실행 전에 실제 구간을 미리 본다.

#### 데이터 기준 배지

리포트 각 섹션은 데이터가 어디서 온 것인지 배지로 명시한다.

| 배지 | 대상 | 의미 |
|---|---|---|
| 구간 일치 | 주가 · 뉴스 | 지정 구간으로 조회 |
| 구간 일부 미수집 | 주가 | 휴장일이 아닌 구간 거래일이 소스에 아직 반영되지 않음 |
| 기준일 스냅샷 | 재무 · 공매도 | 수집 시점 현재값이라 구간과 무관 |
| 미지원 | 투자자별 매매동향 · 거래량 | 소스 폐기로 수집 불가 |

> **거래일은 휴장일 달력을 따른다** (`analyzers/market_calendar.py`).
> 주말만 제외하지 않고 공휴일도 제외한다. 2026년 9월 24일(목)·25일(금)은
> 추석 연휴로 국내 증시가 닫혔으므로 9월 4주차의 국내 거래일은 **3일**
> (9/21·22·23) 이다. 같은 구간에서 미국 증시는 정상 거래해 5일이다.
> 그래서 거래일이 다르면 리포트·미리보기에 `국내 3일 / 해외 5일`로 함께 표시한다.
>
> 휴장일 캘린더는 지수 데이터로 검증했다. 국내는 `^KS11` 실제 거래일과
> 2023~2026년 전 기간 대조해 불일치 0건을 확인했고(음력 공휴일·대체공휴일·
> 연말 휴장일 포함), 미국은 `^GSPC`와 대조해 4년 전부 일치한다. 표가 없는
> 연도는 고정공휴일만 계산하므로 정확도가 떨어진다.
>
> 아직 마감되지 않은 세션은 구간에서 제외한다(국내 15:30 KST, 미국은
> KST 다음날 06:00 기준). 마감 전 실행하면 아직 공개되지 않은 데이터를
> 요구하지 않아 날짜가 어긋나지 않는다.
>
> 그래도 소스 반영 지연으로 거래일이 비면 배지가 `구간 일부 미수집`으로
> 바뀌고 리포트 상단에 빠진 날짜를 안내하는 경고가 표시된다. 휴장일은
> 누락으로 세지 않는다.
>
> 지정 구간의 리포트는 **요청하신 구간 그대로** 저장·표시한다. 수집된 날짜로
> 구간을 좁히지 않으므로, 데이터가 빠진 사실이 리포트에서 사라지지 않는다.
> 자동 구간(미지정 실행)만 실제 수집된 거래일로 좁힌다.

### 2. 웹 서버 시작
```bash
python3 main.py server --host 0.0.0.0 --port 8000
```
브라우저에서 http://localhost:8000 접속 (`--host 0.0.0.0` 이면 같은 네트워크의 다른 PC에서도 접속 가능)

종목 관리 대시보드는 별도 스크립트로 편리하게 실행할 수 있습니다.
```bash
./scripts/run_dashboard.sh            # 백그라운드 구동 + 브라우저 자동 실행
./scripts/run_dashboard.sh status     # 상태 확인
./scripts/run_dashboard.sh stop       # 중지
./scripts/run_dashboard.sh restart    # 재시작
./scripts/run_dashboard.sh --port 8001   # 포트 변경
./scripts/run_dashboard.sh --host 0.0.0.0  # 바인드 주소 변경 (기본 0.0.0.0)
./scripts/run_dashboard.sh -f         # 포그라운드 실행
```
대시보드 주소: http://localhost:8000/dashboard (로그: `logs/dashboard.log`)

### 3. 다른 PC에서 접속 (WSL2 사용 시)

WSL2 환경에서는 포트 포워딩 설정이 필요합니다.

```powershell
# Windows PowerShell (관리자)에서
cd \\wsl$\Ubuntu\home\<username>\work\StockPilot\scripts
.\portforward.bat setup
```

상세 내용은 [네트워크 설정 가이드](docs/network-setup.md)를 참조하세요.

### 4. cron 자동 실행 설정
```bash
# 매일 오후 6시 실행
python3 main.py cron --hour 18 --minute 0

# 안내된 명령어를 crontab에 등록
crontab -e
```

## 설정 변경

### 종목 추가/수정

#### 로컬 전용 설정 (권장)
개인 종목은 `config/local/` 디렉토리에 저장하세요. Git에 포함되지 않습니다.

```bash
# 1. 예시 파일 복사
cp config/local/stocks.yaml.example config/local/stocks.yaml
cp config/local/foreign_stocks.yaml.example config/local/foreign_stocks.yaml

# 2. 편집
vim config/local/stocks.yaml
```

#### 설정 우선순위
- `config/local/stocks.yaml` > `config/stocks.yaml` (로컬이 우선)
- `config/local/foreign_stocks.yaml` > `config/foreign_stocks.yaml`

#### 국내 종목
`config/local/stocks.yaml` 파일 생성/편집:
```yaml
stocks:
  - code: "005930"
    name: "삼성전자"
    market: "KOSPI"
```

#### 해외 종목
`config/local/foreign_stocks.yaml` 파일 생성/편집:
```yaml
foreign_stocks:
  - ticker: "AAPL"
    name: "Apple"
    market: "NASDAQ"
    currency: "USD"
```

#### Git에 포함되지 않는 파일
- `.env` (API 키)
- `config/local/` (개인 종목 설정)
- `config/stocks.yaml`, `config/foreign_stocks.yaml` (기본 종목 설정)

### DART API 설정
`.env` 파일에 API 키 설정:
```
DART_API_KEY=your_api_key_here
```
- 발급: https://opendart.fss.or.kr

## 데이터 소스

| 소스 | 수집 데이터 | 시장 | 비고 |
|------|------------|------|------|
| 네이버 금융 | 주가, 뉴스 | 국내 | Playwright 스크래핑 |
| DART | 공시 데이터 | 국내 | API (무료 키 발급) |
| KRX | 거래량, 시장 통계 | 국내 | REST API |
| 컴퍼니가이드 | 재무 심층 분석 | 국내 | Playwright 스크래핑 |
| yfinance | 주가, 뉴스, 재무 | 해외 | 무료 (API 키 불필요) |

## 디렉토리 구조

```
StockPilot/
├── config/
│   ├── stocks.yaml          # 기본 국내 종목 설정 (Git 포함)
│   ├── foreign_stocks.yaml  # 기본 해외 종목 설정 (Git 포함)
│   └── local/               # 로컬 전용 설정 (Git 제외)
│       ├── stocks.yaml      # 개인 국내 종목
│       └── foreign_stocks.yaml # 개인 해외 종목
├── collectors/
│   ├── naver_finance.py     # 네이버 금융 수집기
│   ├── dart.py              # DART 공시 수집기
│   ├── krx.py               # KRX 수집기
│   ├── company_guide.py     # 컴퍼니가이드 수집기
│   └── yfinance_collector.py # 해외 주식 수집기
├── analyzers/
│   └── weekly_analyzer.py   # 분석 엔진
├── reporters/
│   └── html_reporter.py     # HTML 리포트 생성기
├── reports/weekly/          # 생성된 리포트
├── server/
│   ├── app.py               # FastAPI 웹 서버
│   └── dashboard.py         # 종목 관리 대시보드
├── scripts/
│   ├── run_analysis.py      # 분석 실행 스크립트
│   ├── run_dashboard.sh     # 대시보드 서버 구동 스크립트
│   ├── install_cron.sh      # cron 자동 실행 스크립트
│   ├── portforward.ps1      # Windows 포트포워딩 (PowerShell)
│   └── portforward.bat      # Windows 포트포워딩 (배치)
├── docs/
│   ├── network-setup.md     # 네트워크 설정 가이드
│   └── progress.md          # 진행 상황 문서
├── .env                     # API 키 설정 (git 제외)
├── main.py                  # 메인 진입점
└── requirements.txt         # 의존성
```