#!/usr/bin/env python3
"""
Slow-peer / blocking-send probe.

Scenario:
  - A (id 0), B (id 1, "slow": never recv()s), C (id 2) connect.
  - A floods data through the server. Each line is fanned out to B and C.
  - Eventually B's TCP receive buffer fills. The server's blocking send()
    to B blocks. The whole server is now frozen.
  - A disconnects. The leave broadcast SHOULD reach C as
    "server: client 0 just left\n".
  - If the server is stuck in send-to-B, C never sees the leave within
    a reasonable timeout.

This affects BOTH mini_serv.c and mini_serv_ref.c — neither makes
sockets non-blocking. The point of the test is to confirm they fail
the same way (so the risk is intrinsic to the architecture, not to
your specific code).
"""

import socket, subprocess, sys, time, random, errno


def main():
    binary = sys.argv[1]
    port = random.randint(20000, 60000)
    server = subprocess.Popen([binary, str(port)],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE)
    try:
        # wait for bind via real client A
        deadline = time.monotonic() + 5.0
        a = None
        while time.monotonic() < deadline:
            if server.poll() is not None:
                print("FAIL: server died at startup"); return 1
            try:
                a = socket.create_connection(("127.0.0.1", port), timeout=0.2)
                break
            except OSError:
                time.sleep(0.1)
        if a is None:
            print("FAIL: server never came up"); return 1

        # B: slow peer, small recv buffer to fill quickly
        b = socket.socket()
        b.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2048)
        b.connect(("127.0.0.1", port))
        c = socket.create_connection(("127.0.0.1", port))
        time.sleep(0.2)

        # Drain C's startup messages (it should have received B's and... wait,
        # C is the latest, so C received nothing on its own arrival). Just
        # make sure C is connected and ready.

        # Have A flood. Each line gets fanned out to B and C. B never reads,
        # so its TCP buffer fills and the server's send-to-B blocks.
        a.setblocking(True)
        line = b"x" * 1000 + b"\n"
        try:
            for _ in range(2000):
                a.sendall(line)
        except (BrokenPipeError, ConnectionResetError):
            pass

        # A closes. Leave broadcast should go to C.
        a.close()

        # Read C with a short timeout. If server is stuck in send-to-B,
        # C will not see the leave within the window.
        c.settimeout(2.0)
        got = b""
        leave = b"server: client 0 just left\n"
        try:
            while leave not in got:
                chunk = c.recv(65536)
                if not chunk:
                    break
                got += chunk
        except socket.timeout:
            pass
        except OSError:
            pass

        stuck = leave not in got
        if stuck:
            print(f"STUCK: C never saw the leave broadcast within 2s.")
            print(f"  This is the blocking-send risk: server is frozen on send() to B.")
            print(f"  C received {len(got)} bytes total, last 80: {got[-80:]!r}")
            return 1
        print("PASS: C received the leave broadcast even with a slow peer present.")
        return 0
    finally:
        try: b.close()
        except Exception: pass
        try: c.close()
        except Exception: pass
        server.terminate()
        try: server.wait(timeout=2)
        except subprocess.TimeoutExpired: server.kill()


if __name__ == "__main__":
    sys.exit(main())
