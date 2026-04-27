#!/usr/bin/env python3
"""
Test: recv() is only called on readable fds (&rfds), NOT all fds (&afds).

Bug pattern:
    if (!FD_ISSET(fd, &afds))  // WRONG: should be &rfds
        continue;

Mechanism (socket behavior is BLOCKING by default):
  - select() modifies rfds to contain only readable fds
  - If code checks &afds instead of &rfds, it tries recv() on non-readable sockets
  - recv() on a BLOCKING socket with no data BLOCKS indefinitely
  - Server hangs, unable to process other clients

Test scenario:
  1. Client A connects but never sends (not readable)
  2. Client B connects and sends a message
  3. If bug exists:
     - Server tries recv() on A (blocking, hangs forever)
     - B's message is never processed or broadcast
  4. If correct:
     - select() only marks B as readable
     - recv() only called on B
     - B's message is broadcast to A immediately
"""

import socket
import subprocess
import sys
import time
import random


def recv_until(sock, deadline, want_bytes=None):
    """Read until want_bytes found or deadline, return (data, success)."""
    buf = b""
    sock.setblocking(False)
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
            if chunk == b"":
                break
            buf += chunk
            if want_bytes and want_bytes in buf:
                return buf, True
        except BlockingIOError:
            time.sleep(0.05)
    return buf, want_bytes is None or (want_bytes in buf)


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <binary>", file=sys.stderr)
        sys.exit(2)

    binary = sys.argv[1]
    port = random.randint(20000, 60000)
    server = subprocess.Popen(
        [binary, str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )

    try:
        # Wait for server to bind
        deadline = time.monotonic() + 5.0
        a = None
        while time.monotonic() < deadline:
            if server.poll() is not None:
                print("FAIL: server died at startup")
                return 1
            try:
                a = socket.create_connection(("127.0.0.1", port), timeout=0.2)
                break
            except OSError:
                time.sleep(0.1)

        if a is None:
            print("FAIL: server never came up")
            return 1

        # Client A connects, then waits (doesn't send)
        time.sleep(0.1)

        # Client B connects and immediately sends a message
        b = socket.create_connection(("127.0.0.1", port), timeout=1)
        time.sleep(0.1)
        b.sendall(b"test_message\n")

        # Now A should receive:
        # 1. "server: client 1 just arrived\n" (B's arrival)
        # 2. "client 1: test_message\n" (B's broadcast)
        #
        # If bug exists:
        # - Server is stuck in recv() on A (blocking, no data)
        # - Neither of the above reaches A
        # - This times out after 2 seconds

        start = time.monotonic()
        a_data, success = recv_until(a, start + 2.0,
                                      want_bytes=b"client 1: test_message\n")
        elapsed = time.monotonic() - start

        if not success:
            print("FAIL: A did not receive B's message within 2.0s")
            print("  This indicates the server is BLOCKED trying to recv() on A.")
            print("  Probable cause: Using &afds instead of &rfds in dispatch loop")
            print("  Impact: recv() blocked on non-readable client A, server hung.")
            print(f"  Data received: {a_data!r}")
            return 1

        print(f"PASS: Message received in {elapsed:.3f}s (server responsive)")
        print("  Correctly uses &rfds in dispatch loop, not &afds")

        return 0

    finally:
        try:
            a.close()
        except Exception:
            pass
        try:
            b.close()
        except Exception:
            pass
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
