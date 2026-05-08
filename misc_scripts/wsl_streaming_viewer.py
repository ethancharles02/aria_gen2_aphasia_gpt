#!/usr/bin/env python3
# NOTE: Script written by AI
import atexit
import os
import socket
import subprocess
import sys
import time

import rerun as rr


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _ensure_rerun_server(port: int) -> subprocess.Popen | None:
    if _is_port_open("127.0.0.1", port):
        return None

    env = os.environ.copy()
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    venv_bin = os.path.join(repo_root, ".venv", "bin")
    env["PATH"] = f"{venv_bin}:" + env.get("PATH", "")
    proc = subprocess.Popen(
        ["rerun", "--serve-web", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    for _ in range(20):
        if _is_port_open("127.0.0.1", port):
            return proc
        time.sleep(0.2)

    proc.terminate()
    raise RuntimeError(f"Failed to start Rerun server on port {port}")


def main() -> int:
    port = int(os.environ.get("ARIA_RERUN_PORT", "9876"))
    endpoint = os.environ.get(
        "ARIA_RERUN_ENDPOINT", f"rerun+http://127.0.0.1:{port}/proxy"
    )

    print("=" * 60)
    print("WSL Streaming Workaround Active")
    print("Run this command in Windows PowerShell:")
    print(f"  py -m rerun {endpoint}")
    print("=" * 60)

    server_proc = _ensure_rerun_server(port)
    if server_proc is not None:
        atexit.register(server_proc.terminate)

    def _spawn_override(*_args, **_kwargs):
        print(f"[WSL workaround] Connecting to headless Rerun server at {endpoint}")
        rr.connect_grpc(endpoint)

    rr.spawn = _spawn_override

    from aria.aria_streaming_viewer import main as aria_streaming_main

    return aria_streaming_main()


if __name__ == "__main__":
    raise SystemExit(main())
