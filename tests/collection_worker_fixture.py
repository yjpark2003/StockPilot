"""Offline process fixtures for deadline and process-tree tests."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

request = json.loads(sys.stdin.readline())
mode = sys.argv[1]
if mode == 'hang':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen([sys.executable, '-c',
                              'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'],
                             start_new_session=True)
    Path(sys.argv[2]).write_text(json.dumps([os.getpid(), child.pid]))
    time.sleep(60)
elif mode == 'stock':
    method = request['method']
    if method == 'get_weekly_price':
        data = dict(weekly_data=[{'date': '2026-11-02', 'close': 100}, {'date': '2026-11-03', 'close': 110}],
                    current_price=110, start_price=100, end_price=110, change_rate=10)
        print(json.dumps({'status': 'ok', 'data': data}))
    else:
        time.sleep(60)
elif mode == 'empty':
    print(json.dumps({'status':'empty','data':[]}))
elif mode == 'error':
    print(json.dumps({'status':'error','error':'접속 실패'}))
