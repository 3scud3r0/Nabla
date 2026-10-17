"""Bounded subprocess output and process-group termination for optional renderers."""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager


@contextmanager
def publication_lock(path):
    """One writer per PDF, across threads/processes; OS releases locks on crashes."""
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():
        raise ValueError('Publication lock cannot be a symlink')
    with path.open('a+b') as stream:
        if os.name == 'posix':
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        else:
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b'0'); stream.flush()
            stream.seek(0); msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        try:
            yield
        finally:
            if os.name == 'posix':
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
            else:
                stream.seek(0); msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


def run_renderer(arguments, *, cwd, timeout=120, max_log_bytes=1048576):
    if not 0 < timeout <= 600:
        raise ValueError('Renderer timeout must be within (0,600] seconds')
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(arguments,cwd=cwd,stdout=output,stderr=subprocess.STDOUT,
                                   start_new_session=os.name == 'posix')
        try:
            deadline = time.monotonic()+timeout
            while process.poll() is None:
                if os.fstat(output.fileno()).st_size > max_log_bytes:
                    raise RuntimeError('Renderer output exceeded its log budget')
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(arguments,timeout)
                try:
                    process.wait(timeout=min(.05,remaining))
                except subprocess.TimeoutExpired:
                    pass
            if os.fstat(output.fileno()).st_size > max_log_bytes:
                raise RuntimeError('Renderer output exceeded its log budget')
        except BaseException:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
            raise
        output.seek(0,2); size = output.tell()
        output.seek(max(0,size-max_log_bytes))
        log = output.read(max_log_bytes).decode(errors='replace')
        if process.returncode:
            raise RuntimeError(f'Renderer exited with code {process.returncode}: '+log[-4000:])
        return {'returncode':process.returncode,'log':log,'log_truncated':size > max_log_bytes}
