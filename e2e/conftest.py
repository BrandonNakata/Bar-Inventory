import subprocess
import sys
import os
import time
import socket
import urllib.request
from pathlib import Path


import pytest
from playwright.sync_api import Playwright

def is_up(url):
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:
            return resp.status == 200
    except OSError:          # connection refused / reset while the server is still booting
        return False



def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))      # 0 = "OS, pick one for me"
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def api_url(tmp_path_factory):
    folder = tmp_path_factory.mktemp("db")   # a brand-new empty folder
    db_file = folder / "bar.db"
    port = free_port()
    backend_location = Path(__file__).parent.parent / "backend"
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", str(port)], cwd=backend_location, env = {**os.environ, "BAR_DB_PATH": str(db_file)})
    url = "http://127.0.0.1:" + str(port) + "/"
    end_time = time.monotonic() + 20

    while time.monotonic() < end_time:
        if is_up(url+"api/health"):
            break
        time.sleep(.1)

        if proc.poll() is not None:
            raise RuntimeError(f"Server crashed (exit code {proc.returncode})")
    else:
        proc.terminate()
        raise RuntimeError("Server never returned 200")
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

@pytest.fixture
def request_context(playwright: Playwright, api_url):
    api = playwright.request.new_context(base_url=api_url)
    yield api
    api.dispose()
