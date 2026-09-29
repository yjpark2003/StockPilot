# -*- coding: utf-8 -*-
"""주간 주식 분석 시스템 - 메인 실행 파일"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def cmd_analyze(args):
    """분석 실행"""
    from scripts.run_analysis import run_analysis
    from analyzers.period import PeriodError, period_from_namespace

    try:
        period = period_from_namespace(args)
    except PeriodError as e:
        print(f"분석 구간 오류: {e}", file=sys.stderr)
        raise SystemExit(2)

    asyncio.run(run_analysis(args.market, getattr(args, "with_dart", False), period=period))


def cmd_server(args):
    """웹 서버 시작"""
    from server.app import start_server
    start_server(host=args.host, port=args.port)


def cmd_cron_install(args):
    """cron 설치"""
    import subprocess
    cron_script = os.path.join(os.path.dirname(__file__), "scripts", "install_cron.sh")
    os.chmod(cron_script, 0o755)

    cron_line = f"{args.minute} {args.hour} * * * {cron_script}"
    print(f"다음 cron 항목을 등록하세요:")
    print(f"  crontab -e")
    print(f"  {cron_line}")
    print()
    print(f"또는 자동 등록:")
    print(f"  (crontab -l 2>/dev/null; echo '{cron_line}') | crontab -")


def main():
    parser = argparse.ArgumentParser(description="주간 주식 분석 시스템")
    subparsers = parser.add_subparsers(dest="command", help="실행할 명령어")

    # analyze 서브커맨드
    analyze_parser = subparsers.add_parser("analyze", help="분석 실행")
    analyze_parser.add_argument("--market", choices=["all", "domestic", "foreign"], default="all",
                               help="분석할 시장 (all: 전체, domestic: 국내만, foreign: 해외만)")
    analyze_parser.add_argument("--with-dart", action="store_true",
                               help="DART 공시 데이터 포함 (기본: 비활성화)")
    from analyzers.period import add_period_arguments
    add_period_arguments(analyze_parser)

    # server 서브커맨드
    server_parser = subparsers.add_parser("server", help="웹 서버 시작")
    server_parser.add_argument("--host", default="0.0.0.0", help="바인드 주소")
    server_parser.add_argument("--port", type=int, default=8001, help="포트 번호")

    # cron 서브커맨드
    cron_parser = subparsers.add_parser("cron", help="cron 설정 안내")
    cron_parser.add_argument("--hour", type=int, default=18, help="실행 시 (기본: 18)")
    cron_parser.add_argument("--minute", type=int, default=0, help="실행 분 (기본: 0)")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "server":
        cmd_server(args)
    elif args.command == "cron":
        cmd_cron_install(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
