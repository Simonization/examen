#!/usr/bin/env python3
"""
Regression test for mini_serv.

Scenario:
  1. client A connects -> gets id 0 (no broadcast received)
  2. client B connects -> gets id 1, A receives "server: client 1 just arrived\n"
  3. client A disconnects
  4. client B MUST receive "server: client 0 just left\n"

Failure mode this test catches:
  buf_w is a shared global. If rm_client() forgets to refresh it (or the
  refresh happens after send_all), client B sees the stale arrival message
  "server: client 1 just arrived\n" instead of the correct
  "server: client 0 just left\n".

Usage:
  cc -Wall -Wextra -Werror mini_serv.c -o mini_serv
  python3 test_leave.py ./mini_serv
"""

import os
import random
import socket
import subprocess
import sys
import time


PORT = random.randint(20000, 60000)
EXPECTED = b"server: client 0 just left\n"
WRONG = b"server: client 1 just arrived\n"


def recv_until(sock, deadline, want_bytes=None):
    """Read from sock until `want_bytes` is contained in the buffer, or deadline."""
    buf = b""
    sock.setblocking(False)
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
            if chunk == b"":
                break
            buf += chunk
            if want_bytes is not None and want_bytes in buf:
                return buf
        except BlockingIOError:
            time.sleep(0.05)
    return buf


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-mini_serv>", file=sys.stderr)
        sys.exit(2)

    binary = sys.argv[1]
    server = subprocess.Popen([binary, str(PORT)],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE)
    try:
        # wait for the server to bind by retrying client A's connect itself
        # (probing then closing would burn a client id and shift A/B's ids).
        deadline = time.monotonic() + 5.0
        a = None
        while time.monotonic() < deadline:
            if server.poll() is not None:
                err = server.stderr.read().decode(errors="replace")
                print(f"FAIL: server exited early: {err}", file=sys.stderr)
                sys.exit(1)
            try:
                a = socket.create_connection(("127.0.0.1", PORT), timeout=0.2)
                break
            except OSError:
                time.sleep(0.1)
        if a is None:
            print("FAIL: server never came up", file=sys.stderr)
            sys.exit(1)
        # client A -> id 0
        time.sleep(0.1)

        # client B -> id 1; A should now have "server: client 1 just arrived\n"
        b = socket.create_connection(("127.0.0.1", PORT))
        time.sleep(0.1)

        # drain whatever A queued (the arrival broadcast for B)
        a_pre = recv_until(a, time.monotonic() + 0.3)
        assert b"server: client 1 just arrived\n" in a_pre, \
            f"setup sanity check failed; A got: {a_pre!r}"

        # A leaves
        a.shutdown(socket.SHUT_RDWR)
        a.close()

        # B should now receive the leave broadcast
        got = recv_until(b, time.monotonic() + 1.0, want_bytes=EXPECTED)

        if EXPECTED in got:
            print("PASS: B received", EXPECTED)
            b.close()
            return 0

        # diagnose the specific bug the user asked about
        if WRONG in got and EXPECTED not in got:
            print("FAIL: B received the stale arrival message instead of the leave message.")
            print(f"  expected: {EXPECTED!r}")
            print(f"  got:      {got!r}")
            print("  hint: buf_w was not refreshed before send_all in rm_client(),")
            print("        so the previous 'just arrived' broadcast leaked through.")
        else:
            print("FAIL: B did not receive the expected leave message.")
            print(f"  expected: {EXPECTED!r}")
            print(f"  got:      {got!r}")

        b.close()
        return 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
