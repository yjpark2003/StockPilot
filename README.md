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

### 2. 웹 서버 시작
```bash
python3 main.py server --port 8000
```
브라우저에서 http://localhost:8000 접속

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
│   ├── portforward.ps1      # Windows 포트포워딩 (PowerShell)
│   └── portforward.bat      # Windows 포트포워딩 (배치)
├── docs/
│   ├── network-setup.md     # 네트워크 설정 가이드
│   └── progress.md          # 진행 상황 문서
├── .env                     # API 키 설정 (git 제외)
├── main.py                  # 메인 진입점
└── requirements.txt         # 의존성
```