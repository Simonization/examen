#!/usr/bin/env python3
"""
SIGPIPE probe.

Scenario:
  - 3 clients connect: A (id 0), B (id 1), C (id 2).
  - B closes its socket without reading anything queued.
  - A sends a message.
  - The server's send_all walks fds and tries to send to B.
    If send() lacks MSG_NOSIGNAL and B's TCP stack has already torn
    the connection down (RST), the kernel raises SIGPIPE in the
    server -> server dies.
  - C should still receive A's message ("client 0: hi\n").

Pass: C receives the broadcast AND the server is still alive afterwards.
Fail: C receives nothing or server has exited.
"""

import os, socket, subprocess, sys, time, random


def wait_msg(sock, want, timeout=1.0):
    sock.setblocking(False)
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
            if chunk == b"":
                break
            buf += chunk
            if want in buf:
                return buf
        except BlockingIOError:
            time.sleep(0.05)
    return buf


def main():
    binary = sys.argv[1]
    port = random.randint(20000, 60000)
    server = subprocess.Popen([binary, str(port)],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 5.0
        a = None
        while time.monotonic() < deadline:
            if server.poll() is not None:
                print(f"FAIL: server died at startup")
                return 1
            try:
                a = socket.create_connection(("127.0.0.1", port), timeout=0.2)
                break
            except OSError:
                time.sleep(0.1)
        if a is None:
            print("FAIL: server never came up")
            return 1

        b = socket.create_connection(("127.0.0.1", port))
        c = socket.create_connection(("127.0.0.1", port))
        time.sleep(0.2)

        # drain arrival broadcasts on A and C
        wait_msg(a, b"server: client 2 just arrived\n", 0.4)
        wait_msg(c, b"", 0.2)

        # B closes hard (RST-ish) without reading
        b.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                     (1).to_bytes(2, "little") + (0).to_bytes(2, "little") + b"\x00" * 4)
        b.close()
        time.sleep(0.1)

        # A sends a message; server must still be alive after fanout
        a.sendall(b"hi\n")
        got = wait_msg(c, b"client 0: hi\n", 1.0)

        if server.poll() is not None:
            print(f"FAIL: server died (likely SIGPIPE). exit code = {server.returncode}")
            print(f"  C received before death: {got!r}")
            return 1

        if b"client 0: hi\n" in got:
            print("PASS: server survived peer-RST fanout; C got the broadcast")
            return 0
        print(f"FAIL: C did not receive A's broadcast. got={got!r}")
        return 1
    finally:
        try: a.close()
        except Exception: pass
        try: c.close()
        except Exception: pass
        server.terminate()
        try: server.wait(timeout=2)
        except subprocess.TimeoutExpired: server.kill()


if __name__ == "__main__":
    sys.exit(main())
