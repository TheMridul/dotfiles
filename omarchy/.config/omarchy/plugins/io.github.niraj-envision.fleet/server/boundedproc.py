"""Subprocess capture with hard time and memory bounds."""
import os
import selectors
import signal
import subprocess
import tempfile
import time

MAX_INPUT = 1024 * 1024


class Result:
    def __init__(self, returncode, stdout, stderr, stdout_truncated=False,
                 stderr_truncated=False, timed_out=False):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.stdout_truncated = stdout_truncated
        self.stderr_truncated = stderr_truncated
        self.timed_out = timed_out


def run(argv, *, input_data=None, env=None, timeout=30, stdout_limit=2 * 1024 * 1024,
        stderr_limit=256 * 1024):
    """Run argv while draining excess output instead of retaining it in RAM."""
    timeout = max(1.0, min(float(timeout), 300.0))
    if input_data is not None and isinstance(input_data, str):
        input_data = input_data.encode()
    if input_data is not None and len(input_data) > MAX_INPUT:
        raise ValueError("subprocess input exceeds 1 MiB")
    input_file = None
    if input_data is not None:
        input_file = tempfile.TemporaryFile()
        input_file.write(input_data)
        input_file.seek(0)
    p = subprocess.Popen(argv, stdin=input_file or subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                         start_new_session=True)
    if input_file is not None:
        input_file.close()
    sel = selectors.DefaultSelector()
    buffers = {p.stdout: bytearray(), p.stderr: bytearray()}
    limits = {p.stdout: stdout_limit, p.stderr: stderr_limit}
    truncated = {p.stdout: False, p.stderr: False}
    for stream in buffers:
        os.set_blocking(stream.fileno(), False)
        sel.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    timed_out = False
    while sel.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0 and not timed_out:
            timed_out = True
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 1.0
        for key, _ in sel.select(max(0.05, min(max(remaining, 0.0), 0.25))):
            stream = key.fileobj
            try:
                chunk = os.read(stream.fileno(), 65536)
            except BlockingIOError:
                continue
            if not chunk:
                sel.unregister(stream)
                continue
            room = limits[stream] - len(buffers[stream])
            if room > 0:
                buffers[stream].extend(chunk[:room])
            if len(chunk) > max(room, 0):
                truncated[stream] = True
        if timed_out and time.monotonic() >= deadline:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            for stream in list(buffers):
                try:
                    sel.unregister(stream)
                except (KeyError, ValueError):
                    pass
            break
        if p.poll() is not None and not sel.get_map():
            break
    p.wait()
    result = Result(124 if timed_out else p.returncode, bytes(buffers[p.stdout]),
                    bytes(buffers[p.stderr]), truncated[p.stdout],
                    truncated[p.stderr], timed_out)
    p.stdout.close()
    p.stderr.close()
    sel.close()
    return result
