#!/usr/bin/env python3
"""
Test that fd reuse doesn't leak buffers between clients.

Scenario:
  1. Client A connects, sends a PARTIAL message (no newline)
  2. Client A disconnects
  3. Client B connects (may reuse A's fd)
  4. Client B sends a complete message with newline
  5. Server broadcasts B's message to C
  6. C should receive ONLY B's message, NOT A's partial data + B's message

Failure modes:
  - If add_client() doesn't initialize bufs[fd] = NULL, B's fd might inherit A's partial buffer
  - Result: C sees "partial_from_A" + "message_from_B" concatenated
  - OR: C sees A's partial message treated as a complete line (garbage broadcast)

This catches the issue where add_client() is missing bufs[fd] = NULL initialization.
"""

import socket
import subprocess
import sys
import time
import random


def recv_until(sock, deadline, want=None):
    """Read from socket until want is found or deadline exceeded."""
    buf = b""
    sock.setblocking(False)
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
            if chunk == b"":
                break
            buf += chunk
            if want is not None and want in buf:
                return buf
        except BlockingIOError:
            time.sleep(0.05)
    return buf


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
        c = None
        while time.monotonic() < deadline:
            if server.poll() is not None:
                print("FAIL: server died at startup")
                return 1
            try:
                c = socket.create_connection(("127.0.0.1", port), timeout=0.2)
                break
            except OSError:
                time.sleep(0.1)

        if c is None:
            print("FAIL: server never came up")
            return 1

        # Client A: send PARTIAL message (no newline), then close
        a = socket.create_connection(("127.0.0.1", port))
        time.sleep(0.1)
        a.sendall(b"garbage_from_A_no_newline")
        a.close()
        time.sleep(0.1)

        # Drain C's arrival broadcasts (for A and nothing for A's close yet)
        got_before = recv_until(c, time.monotonic() + 0.3)

        # Client B: connect (might reuse A's fd), send complete message
        b = socket.create_connection(("127.0.0.1", port))
        time.sleep(0.1)
        b.sendall(b"clean_message_from_B\n")
        time.sleep(0.1)

        # Now collect C's broadcasts: should see A left, B arrived, then B's message
        got_after = recv_until(c, time.monotonic() + 1.0,
                               want=b"client")

        # Check for the bug: A's partial garbage appearing in the broadcast
        if b"garbage_from_A" in got_after:
            print("FAIL: C received A's partial buffer message!")
            print(f"  This means bufs[fd] was not NULL'd on fd reuse.")
            print(f"  C got: {got_after!r}")
            return 1

        # Check for success: B's clean message appears
        if b"clean_message_from_B" in got_after:
            print("PASS: C received clean message; no buffer leakage on fd reuse")
            return 0
        else:
            print("FAIL: C did not receive B's message")
            print(f"  got_before: {got_before!r}")
            print(f"  got_after:  {got_after!r}")
            return 1

    finally:
        try:
            c.close()
        except Exception:
            pass
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
