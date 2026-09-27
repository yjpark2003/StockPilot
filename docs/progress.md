# 주간 주식 분석 리포트 시스템 - 진행 상황

## 프로젝트 개요
- **목적**: 국내/해외 주식을 자동 분석하여 HTML 리포트 생성
- **기술 스택**: Python 3 (FastAPI + Playwright + yfinance + Jinja2 + Chart.js)
- **환경**: WSL2

## 현재 상태: 완료

### ✅ 완료된 기능

#### 1. 데이터 수집기 (Collectors)
- `naver_finance.py` - 국내 주식 가격/차트 데이터 (네이버 금융)
- `yfinance_collector.py` - 해외 주식 가격/차트/뉴스 (yfinance)
- `dart.py` - DART 공시 데이터 (**선택적 사용**)
- `krx.py` - KRX 거래소 데이터 (HTML 응답으로 인해 제한적)
- `investor_trend.py` - 투자자별 매매 동향 (외국인/기관/개인)
- `toss_news.py` - 국내 뉴스 (토스증권)

#### 2. 분석기 (Analyzers)
- `weekly_analyzer.py` - 주간 분석 오케스트레이터

#### 3. 리포터 (Reporters)
- `html_reporter.py` - HTML 리포트 생성

#### 4. 웹 서버
- `server/app.py` - FastAPI 기반 웹 서버
- `server/dashboard.py` - 종목 관리 대시보드 HTML

#### 5. 종목 관리 API
- `GET /api/stocks` - 전체 종목 목록 조회
- `GET /api/stocks/domestic` - 국내 종목 목록
- `POST /api/stocks/domestic` - 국내 종목 추가
- `DELETE /api/stocks/domestic/{code}` - 국내 종목 삭제
- `GET /api/stocks/foreign` - 해외 종목 목록
- `POST /api/stocks/foreign` - 해외 종목 추가
- `DELETE /api/stocks/foreign/{ticker}` - 해외 종목 삭제
- `GET /api/stocks/search` - 종목 검색 (한글명/종목코드/yfinance)
- `GET /dashboard` - 종목 관리 대시보드 페이지

#### 5. 설정 파일
- `config/stocks.yaml` - 국내 종목 설정 (8종목)
- `config/foreign_stocks.yaml` - 해외 종목 설정 (5개별 + 4 ETF)

### 📊 현재 종목 목록

#### 국내 (8종목)
- 현대차2우B (005387)
- 삼성전자 (005930)
- 미래에셋증권 (006800)
- 한국전력 (015760)
- KODEX 200 (069500)
- GS (078930)
- 하나금융지주 (086790)
- ACE KRX 금현물 (411060)

#### 해외 (9종목)
- 개별: AAPL, AMZN, NVDA, AVGO, GOOGL
- ETF: JEPQ, DGRO, SCHD, VOOG

### 🎨 UI 구조

#### 메인 페이지 (서버)
```
┌─────────────────────────────────────────┐
│  [전체 분석] [국내] [해외]              │  ← 우측 상단 (고정)
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│           주간 주식 분석 리포트           │  ← 헤더
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 📋 국내: 삼성전자, SK하이닉스 ...        │  ← 정보 바
│ 🌍 해외: Apple, NVIDIA ...              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 📊 2026 08/14 - 08/21                   │  ← 리포트 목록
│    주간 리포트                          │
└─────────────────────────────────────────┘
```

#### 리포트 인덱스 페이지
```
┌─────────────────────────────────────────┐
│  [전체 분석 실행] [새로고침]             │  ← 우측 상단 (고정)
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│         2026-08-21 주간 리포트           │  ← 헤더
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 📋 국내 종목                            │  ← 정보 바
│ [현대차2우B -7.9%] [삼성전자 +2.5%] ...  │
│                                         │
│ 🌍 해외 종목                            │
│ [Apple +1.8%] [Amazon +2.3%] ...        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  🇰🇷 국내  │  🌍 해외                    │  ← 탭
└─────────────────────────────────────────┘
```

### 🔧 주요 설정

#### DART 공시 데이터 (선택적)
- **기본값**: 비활성화
- **활성화 방법**: `--with-dart` 옵션 사용
- **환경변수**: `DART_API_KEY` 설정 필요

```bash
# DART 없이 실행 (기본)
python3 scripts/run_analysis.py --market all

# DART 포함 실행
python3 scripts/run_analysis.py --market all --with-dart
```

### 📁 파일 구조
```
StockPilot/
├── config/
│   ├── stocks.yaml          # 국내 종목 설정
│   └── foreign_stocks.yaml  # 해외 종목 설정
├── collectors/
│   ├── naver_finance.py     # 국내 데이터
│   ├── yfinance_collector.py # 해외 데이터
│   ├── dart.py              # DART 공시 (선택적)
│   ├── krx.py               # KRX 데이터
│   ├── investor_trend.py    # 투자자 동향
│   └── toss_news.py         # 뉴스 수집
├── analyzers/
│   └── weekly_analyzer.py   # 분석 오케스트레이터
├── reporters/
│   └── html_reporter.py     # HTML 리포트 생성
├── server/
│   ├── app.py               # 웹 서버
│   └── dashboard.py         # 종목 관리 대시보드
├── scripts/
│   ├── run_analysis.py      # 분석 실행 스크립트
│   ├── portforward.bat      # Windows 포트 포워딩
│   └── portforward.ps1      # PowerShell 포트 포워딩
├── reports/
│   └── weekly/
│       └── YYYY-MM-DD/      # 날짜별 리포트
└── docs/
    ├── network-setup.md     # 네트워크 설정 가이드
    └── progress.md          # 이 문서
```

### 🚀 실행 방법

```bash
# 전체 분석 실행
python3 scripts/run_analysis.py --market all

# 국내만 분석
python3 scripts/run_analysis.py --market domestic

# 해외만 분석
python3 scripts/run_analysis.py --market foreign

# DART 공시 포함 분석
python3 scripts/run_analysis.py --market all --with-dart

# 웹 서버 시작
python3 -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### 📝 최근 변경 사항 (2026-08-24)

1. **UI 개편**
   - 헤더: 제목만 표시
   - 정보 바: 종목 목록 + 가격 변동률
   - 분석 실행 버튼: 우측 상단 고정 (플로팅)

2. **날짜 표시 개선**
   - 리포트 목록에 주간 기간 표시
   - 형식: `2026 08/14 - 08/21`

3. **DART 공시 선택적 사용**
   - 기본값: 비활성화
   - `--with-dart` 옵션으로 활성화

4. **성능 최적화** ⚡
   - yfinance 우선 사용 (국내 주식)
   - Playwright 대기 시간 대폭缩减
   - 1종목 분석 시간: 22초 → 11초 (50% 개선)

5. **진행률 표시** 📊
   - CLI: `[1/8] 종목명 분석 중...` 형식
   - 웹: 실시간 프로그레스 바 (SSE + 폴링 폴백)
   - API: `/api/progress` (JSON), `/api/progress/stream` (SSE)

6. **종목 관리 대시보드** ✅
   - `/dashboard` - 종목 관리 대시보드 페이지
   - 국내/해외 종목 추가/삭제 기능
   - 종목 검색 (yfinance API 사용)
   - 실시간 통계 (전체/국내/해외 종목 수)
   - 메인 페이지에서 종목 관리 링크 추가

7. **종목 검색 기능 개선** ✅
   - 한글 종목명 검색 지원 (SK텔레콤, SK하이닉스, 네이버, 카카오 등)
   - 한글 종목명 → 종목코드 매핑 테이블 추가
   - 현재 등록된 종목 + 새 종목 검색 모두 지원
   - 검색 API: `GET /api/stocks/search?q=검색어&market=domestic`

8. **분석 구간 지정** ✅ (2026-09-27)
   - 월 내 주차 / ISO 주차 / 시작일~종료일 세 가지 방식 (`analyzers/period.py`)
   - "9월 첫째 주차" = 1일이 속한 ISO 주 (예: 2026년 9월 1주차 → 08/31~09/06, ISO 36주차)
   - 월 내 주차는 앵커가 속한 ISO 주 기준이라 월 경계에서 다음 달로 넘어간다
     (2026-08-31 → 9월 1주차)
   - 최대 45일 제한, 잘못된 값은 조용히 무시하지 않고 오류로 알림
   - CLI: `main.py analyze --year/--month/--week`, `--iso-year/--iso-week`, `--start/--end`
   - 웹: 메인 페이지 **분석 구간 지정 패널** (드롭다운 + 날짜 입력, 구간 미리보기)
     `GET /api/period/preview`
   - 지정 구간 리포트는 `reports/weekly/<구간 종료일>/`에 저장해 당일 리포트와 분리

9. **데이터 기준 배지 + 누락 경고** ✅ (2026-09-27)
   - 섹션별 배지: 구간 일치 / **구간 일부 미수집** / 기준일 스냅샷 / 미지원
   - 구간 거래일 대비 수집된 날짜를 대조해 누락 시 자동으로 배지를 downgrade
   - 리포트 상단 경고 배너 + 상세 페이지 가격 섹션에 빠진 날짜 표시
   - **원인**: yfinance 국내(KRX) 피드는 최근 거래일이 1~2거래일 늦게 반영된다.
     9월 4주차(거래일 9/21~9/25)를 9/27에 실행하면 9/24·9/25가 빠져 3일만 표시됨.
     해외 피드는 정상.
   - **정정**: 리포터가 표시 구간을 *수집된* 날짜로 좁히던 동작을 제거.
     지정 구간은 요청 구간 그대로 저장·표시하고(누락 사실을 숨기지 않기 위해),
     자동 구간만 기존처럼 좁힌다. 부수적으로 폴더명(구간 종료일)과
     `meta.end` 불일치도 해소.

10. **뉴스 데이터 신뢰도 개선** ✅ (2026-09-27)
   - 토스 뉴스: 실제 제목을 `aria-label`에서 추출, 발행일은
     `contentParams.id`(14자리) → 상대 시각 → 절대 날짜 순으로 판별
   - yfinance 뉴스: `pub_date` 분리 후 구간 필터
   - 투자자별 매매동향: 네이버 레거시 소스 폐기(`302`/`410`) 확인 후
     반복 접근 제거, 즉시 미지원 반환
   - 제약: 토스는 최신 6건 고정이라 과거 구간 조회는 공백이 있을 수 있다

### 🔜 향후 계획
- [ ] 국내 주가 소스 지연 대응 (KRX 직접 수집 또는 지연 구간 재수집 주기)
- [ ] 자동 스케줄러 (매일 18시 실행)
- [ ] 모바일 반응형 디자인
- [ ] Microsoft Teams 알림 기능 (Microsoft Graph API 사용)
- [ ] 이메일 발송 기능
- [ ] 종목 분석 히스토리 저장

### 📋 검토 완료 사항
- Microsoft Teams 알림 기능 검토 완료 (2026-08-24)
  - Microsoft Graph API 사용 방식으로 결정
  - Azure AD 앱 등록 필요
  - 개인 Microsoft 계정 사용 가능
  - 현재 계획 보류 (필요 시 구현)
