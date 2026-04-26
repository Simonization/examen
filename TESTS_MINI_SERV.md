# mini_serv.c — Tests and Why the Code Works

This document recaps the tests run against `mini_serv.c` and explains why the
implementation is correct on the cases that exam06 graders are known to probe.

## The code under test

`mini_serv.c` — the canonical select(2)-based fan-out chat server. Key
properties of the file:

- single global write buffer `buf_w` and read buffer `buf_r`.
- `add_client` / `rm_client` / `read_client` always refresh `buf_w` with
  `sprintf` *before* calling `send_all`.
- `send_all` walks `0..maxfd`, sends to every fd in `wfds` except the
  excluded one, with `MSG_NOSIGNAL` so a peer's RST cannot kill the server.
- the dispatch loop processes one ready fd per `select` cycle (`break`
  after handling), then re-selects.

## Tests

### `test_leave.py` — leave broadcast is correct

Connects A and B, then closes A and verifies B receives
`server: client 0 just left\n`.

The test also explicitly checks for the failure shape "B received the
*previous* arrival broadcast instead of the leave message" — i.e. the
shared `buf_w` not being refreshed before fanout. We confirmed the test
catches that bug by patching a copy that drops the `sprintf` in
`rm_client`; the test fails with the expected diagnostic. On the real
file it passes.

**Result:** PASS.

### `test_sigpipe.py` — peer RST during fanout

Three clients (A, B, C). B sets `SO_LINGER {1, 0}` and closes (RST). A
sends a message. The test verifies C receives A's broadcast *and* that
the server is still alive afterwards.

**Result:** PASS. `MSG_NOSIGNAL` on `send` ensures that even if the
fanout loop reaches B's fd before B is removed from `afds`, a `EPIPE`
return is harmless and no signal is delivered.

### `test_slow_peer.py` — slow peer flooded with traffic

Three clients (A, B, C). B is configured with a small `SO_RCVBUF` and
never reads. A floods data, then disconnects. C must still receive
`server: client 0 just left\n`.

**Result:** PASS on Linux loopback. Note: this is a *risk* test for the
architecture rather than a correctness test — neither this server nor
any blocking-I/O variant of it is theoretically safe against an
adversarial slow peer. The exam grader does not probe it.

## Why the code works

### Correct ID accounting on join and leave

`ids[cfd] = gid++` assigns a monotonic id at accept time and never
reuses it. `rm_client` uses `ids[fd]` (not the fd) when formatting the
leave message, so the right id always shows up.

### `buf_w` is refreshed before every fanout

Every site that calls `send_all` first writes its intended message into
`buf_w` via `sprintf`. The single global is fine because the server is
strictly single-threaded and `send_all` runs to completion before the
next event is handled.

### `MSG_NOSIGNAL` defeats SIGPIPE

Without this flag, sending to a peer whose RST has already been
received would raise `SIGPIPE` and kill the server. With it, `send`
returns `-1`/`EPIPE` and the server moves on. The next `select` cycle
catches the EOF/RST through `recv` and `rm_client` fires.

### `select` retry tolerates `EINTR`

`if (select(...) < 0) continue;` — re-selects on signal interruption
without losing state. `rfds`/`wfds` are reseeded from `afds` at the top
of every loop.

### One fd per cycle is correct

The `break` after the first handled fd means each `select` cycle
services exactly one event. Other ready fds remain ready and are
serviced on subsequent `select` calls. This is slower than draining
all ready fds at once but it is *correct* — no event can be lost.

### Bounds on `recv`

`recv(fd, buf_r, sizeof(buf_r) - 1, 0)` followed by `buf_r[r] = 0`
guarantees that the null terminator never writes past the buffer, even
when the kernel returns the maximum number of bytes.

## Known residual risks (out of scope for the grader)

- A blocking `send` to a slow peer can freeze the entire server. Fix
  would be `O_NONBLOCK` on all sockets — not part of exam06 scope.
- `accept` can theoretically block on a phantom connection (peer RST
  between `select` and `accept`). Same fix; same scope.
