#!/usr/bin/env python3
"""
Test that recv() is only called on readable fds (using &rfds), not all fds (&afds).

Common bug: Student writes:
    if (!FD_ISSET(fd, &afds))  // BUG: should be &rfds
        continue;

Or in send_all:
    if (FD_ISSET(fd, &afds) && fd != except)  // BUG: should be &wfds
        send(...);

Scenario:
  1. Client A connects but does NOT send any data (not readable)
  2. Client B connects and sends a message
  3. If the bug exists:
     - Code checks &afds (all connected fds) instead of &rfds (readable fds)
     - It tries recv() on A even though A is not readable
     - Non-blocking recv() returns -1 with EAGAIN
     - Code checks "if (r <= 0)" and incorrectly treats EAGAIN as disconnect
     - A is removed from the server
  4. If correct:
     - Code only checks &rfds (readable fds)
     - It skips A and only recv() from B
     - A stays connected and receives B's broadcast

Verification:
  - After B sends, A should still be able to receive future broadcasts
  - If A was removed, it won't be in the server anymore (can't send/recv)
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

        # Client A: connected, but does NOT send anything (not readable)
        time.sleep(0.1)

        # Client B: connects and sends a complete message
        b = socket.create_connection(("127.0.0.1", port))
        time.sleep(0.1)

        # Drain A's arrival broadcasts (for B)
        a_got_b_arrival = recv_until(a, time.monotonic() + 0.3,
                                      want=b"server: client 1 just arrived")

        if b"server: client 1 just arrived" not in a_got_b_arrival:
            print("FAIL: Setup sanity check: A didn't receive B's arrival broadcast")
            return 1

        # B sends a message
        b.sendall(b"test_message\n")
        time.sleep(0.1)

        # Now, if the bug exists (recv on &afds instead of &rfds):
        # - Server tried recv() on A even though A is not readable
        # - Non-blocking recv() returned -1 (EAGAIN)
        # - Server removed A thinking it disconnected
        #
        # If correct:
        # - Server only recv() on readable fds (B)
        # - A stays connected

        # Test: A should still be able to receive broadcasts
        # (If A was removed, this will timeout)
        c = socket.create_connection(("127.0.0.1", port))
        time.sleep(0.1)

        # B and C arrivals should reach A
        a_got_c_arrival = recv_until(a, time.monotonic() + 1.0,
                                      want=b"server: client 2 just arrived")

        if b"server: client 2 just arrived" not in a_got_c_arrival:
            print("FAIL: A did not receive C's arrival broadcast!")
            print("  This likely means A was incorrectly removed from the server.")
            print("  Probable cause: recv() was called on &afds instead of &rfds,")
            print("    causing recv() on non-readable A to return -1 (EAGAIN),")
            print("    and the code treated this as a disconnect.")
            print(f"  A received: {a_got_c_arrival!r}")
            return 1

        print("PASS: A remained connected and received broadcasts")
        print("  (correctly using &rfds, not &afds)")

        c.close()
        b.close()
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
        try:
            c.close()
        except Exception:
            pass
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
