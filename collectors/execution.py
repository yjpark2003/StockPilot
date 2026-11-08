"""Bound entire collection stages, including blocking libraries and browser children."""
import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import time


def descendants(pid):
    """Capture children before their parent exits, including detached browser groups."""
    found = {}
    if not Path('/proc').is_dir():
        return found
    parents = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            # comm may contain spaces and parentheses.
            fields = path.read_text().rsplit(')', 1)[1].split()
            parents[int(path.parent.name)] = (int(fields[1]), fields[19])
        except (OSError, ValueError, IndexError):
            continue
    frontier = {pid}
    while frontier:
        children = {child for child, (parent, _) in parents.items() if parent in frontier and child not in found}
        found.update({child: parents[child][1] for child in children})
        frontier = children
    return found


def signal_child(pid, started, sig):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if fields[19] == started:
            os.kill(pid, sig)
    except (OSError, IndexError):
        pass


async def stop_process(process, children=None):
    children = {**(children or {}), **descendants(process.pid)}
    for pid, started in reversed(list(children.items())):
        signal_child(pid, started, signal.SIGTERM)
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    # A broken browser may ignore graceful shutdown. Never wait for it indefinitely.
    await asyncio.sleep(0.1)
    for pid, started in reversed(list(children.items())):
        signal_child(pid, started, signal.SIGKILL)
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(process.wait(), 0.5)
    except TimeoutError:
        pass


class StageRunner:
    def __init__(self, consecutive_timeouts=3, worker_command=None):
        self.threshold = consecutive_timeouts
        self.failures = {}
        self.worker_command = worker_command or [sys.executable, '-m', 'collectors.worker']

    async def run(self, stage, source, payload, limit, callback=None):
        started = time.monotonic()
        result = {'stage': stage, 'source': source, 'limit_seconds': round(limit, 3)}
        circuit = (source, payload.get('method'))
        if self.failures.get(circuit, 0) >= self.threshold:
            return {**result, 'status': 'skipped', 'error': '연속 시간 초과로 이번 분석에서 해당 소스를 건너뜁니다.', 'elapsed_seconds': 0}
        if limit < 1:
            return {**result, 'status': 'timeout', 'error': '종목 전체 제한시간을 초과했습니다.', 'elapsed_seconds': 0}
        if callback:
            await callback({'stage': stage, 'source': source, 'limit_seconds': limit, 'started_at': time.time()})
        process = None
        communication = None
        error_reader = None
        watcher = None
        children = {}
        try:
            # Reserve up to one second of the stage budget for terminating the worker.
            async with asyncio.timeout(max(0.01, limit - 1)):
                process = await asyncio.create_subprocess_exec(
                    *self.worker_command, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    limit=1024 * 1024,
                    cwd=str(Path(__file__).resolve().parent.parent), start_new_session=True,
                )
                async def watch_children():
                    while process.returncode is None:
                        children.update(descendants(process.pid))
                        await asyncio.sleep(0.05)
                watcher = asyncio.create_task(watch_children())
                process.stdin.write(json.dumps(payload).encode() + b'\n')
                await process.stdin.drain()
                error_reader = asyncio.create_task(process.stderr.read())
                communication = asyncio.create_task(process.stdout.readline())
                # Shield pipe readers so their output can still be drained after termination.
                stdout = await asyncio.shield(communication)
                if not stdout:
                    stderr = await asyncio.shield(error_reader)
                    raise RuntimeError(stderr.decode(errors='replace')[-1500:] or f'수집 프로세스 종료 ({process.returncode})')
                message = json.loads(stdout)
                if message.get('status') not in ('ok', 'empty', 'error', 'timeout'):
                    raise RuntimeError('수집 프로세스의 응답 형식이 잘못되었습니다.')
                result.update(message)
        except TimeoutError:
            result.update(status='timeout', error=f'{limit:g}초 제한시간을 초과했습니다.')
        except asyncio.CancelledError:
            raise
        except Exception as error:
            result.update(status='error', error=str(error))
        finally:
            if watcher:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            if process:
                await stop_process(process, children)
            if communication:
                if not communication.done():
                    communication.cancel()
                await asyncio.gather(communication, return_exceptions=True)
            if error_reader:
                if not error_reader.done():
                    error_reader.cancel()
                await asyncio.gather(error_reader, return_exceptions=True)
        if result.get('status') == 'timeout':
            if payload.get('full_budget', True):
                self.failures[circuit] = self.failures.get(circuit, 0) + 1
        else:
            self.failures[circuit] = 0
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        print(f"수집 {stage} ({source}): {result['status']} · {result['elapsed_seconds']}초 "
              f"{result.get('error', '')}", flush=True)
        return result
