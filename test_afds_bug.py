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

        # Now A should receive B's broadcast: "client 1: test_message\n"
        #
        # Subject requirement: "send the messages as fast as you can"
        # Expected: < 50ms (immediate on local socket with no buffer)
        # Acceptable: < 200ms (system under load)
        # Broken (blocking): > 2000ms (recv() blocked on non-readable A)
        #
        # If bug exists (&afds instead of &rfds):
        # - Server tries recv() on A even though A is not readable
        # - recv() on blocking socket with no data blocks forever
        # - Server hung, B's message never broadcasts
        # - Timeout after 2+ seconds confirms hang

        start = time.monotonic()
        a_data, success = recv_until(a, start + 2.0,
                                      want_bytes=b"client 1: test_message\n")
        elapsed = time.monotonic() - start

        if not success:
            print("FAIL: A did not receive B's message within 2.0s")
            print("  Server is BLOCKED (likely recv() on non-readable socket)")
            print("  Bug: Using &afds instead of &rfds in dispatch loop")
            print("  Impact: recv() blocks on A, server hangs, B's message lost.")
            print(f"  Data received: {a_data!r}")
            return 1

        if elapsed > 0.2:
            print(f"WARN: Message took {elapsed:.3f}s (subject expects 'as fast as you can')")
            print("  Server is working but slower than expected. Check for:")
            print("  - Unnecessary buffering")
            print("  - Multiple select() calls per message")
            print("  - System overload")
            return 1

        print(f"PASS: Message received in {elapsed:.3f}s")
        print("  Correctly uses &rfds in dispatch loop, sends fast")

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
