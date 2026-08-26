# -*- coding: utf-8 -*-
"""분석 실행 스크립트"""
import asyncio
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzers import WeeklyAnalyzer
from reporters import HtmlReporter


def load_env():
    """환경변수 로드 (.env 파일)"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def load_config(market: str = "domestic"):
    """설정 파일 로드"""
    if market == "foreign":
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "foreign_stocks.yaml")
    else:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "stocks.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run_analysis(market: str = "all", with_dart: bool = False, progress_callback=None):
    """전체 분석 실행"""
    load_env()  # .env 파일 로드

    # 설정 로드
    domestic_config = load_config("domestic")

    # DART API 키 로드 (옵션인 경우에만)
    dart_api_key = ""
    if with_dart:
        dart_key_env = domestic_config.get("api", {}).get("dart_key_env", "DART_API_KEY")
        dart_api_key = os.environ.get(dart_key_env, "")

    print(f"=== 주간 주식 분석 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
    if with_dart:
        print("[DART 공시 데이터 포함]")

    # 분석 수행
    analyzer = WeeklyAnalyzer(news_count=3, dart_api_key=dart_api_key, with_dart=with_dart, progress_callback=progress_callback)
    reporter = HtmlReporter()

    try:
        all_results = {"domestic": [], "foreign": []}

        # 종목 수 계산
        total_stocks = 0
        current_idx = 0
        
        if market in ("all", "domestic"):
            domestic_stocks = domestic_config.get("stocks", [])
            total_stocks += len(domestic_stocks)
        if market in ("all", "foreign"):
            foreign_config = load_config("foreign")
            foreign_stocks = foreign_config.get("foreign_stocks", [])
            total_stocks += len(foreign_stocks)

        # 국내 종목 분석
        if market in ("all", "domestic"):
            domestic_stocks = domestic_config.get("stocks", [])
            print(f"\n[국내] 분석 대상: {', '.join([s['name'] for s in domestic_stocks])}")
            all_results["domestic"] = await analyzer.analyze_all(domestic_stocks, "domestic", current_idx, total_stocks)
            current_idx += len(domestic_stocks)

        # 해외 종목 분석
        if market in ("all", "foreign"):
            foreign_config = load_config("foreign")
            foreign_stocks = foreign_config.get("foreign_stocks", [])
            print(f"\n[해외] 분석 대상: {', '.join([s['name'] for s in foreign_stocks])}")
            all_results["foreign"] = await analyzer.analyze_all(foreign_stocks, "foreign", current_idx, total_stocks)

        # 리포트 생성
        output_dir = reporter.generate(all_results)

        print(f"\n=== 분석 완료 ===")
        print(f"리포트 위치: {output_dir}")
        return output_dir
    finally:
        await analyzer.close()


def main():
    """메인 실행"""
    import argparse
    parser = argparse.ArgumentParser(description="주간 주식 분석")
    parser.add_argument("--market", choices=["all", "domestic", "foreign"], default="all",
                       help="분석할 시장 (all: 전체, domestic: 국내만, foreign: 해외만)")
    parser.add_argument("--with-dart", action="store_true",
                       help="DART 공시 데이터 포함 (기본: 비활성화)")
    args = parser.parse_args()

    asyncio.run(run_analysis(args.market, args.with_dart))


if __name__ == "__main__":
    main()
