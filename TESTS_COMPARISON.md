# mini_serv.c vs mini_serv_ref.c — Test Comparison

`mini_serv_ref.c` is a known-good exam06 solution from a different
author. This document compares it against our `mini_serv.c` on the
same test suite and notes where the two diverge structurally.

## Test results

| Test | `mini_serv.c` | `mini_serv_ref.c` | Notes |
|---|---|---|---|
| `test_leave.py` | PASS | PASS | Both fanout the leave message correctly. |
| `test_sigpipe.py` | PASS | PASS* | *Reference passes only because B's RST is processed in a separate `select` cycle before A's fanout. With unfortunate timing the reference would die from SIGPIPE; ours would not, because of `MSG_NOSIGNAL`. |
| `test_slow_peer.py` | PASS | PASS | Both have the same architectural exposure (blocking `send`). On Linux loopback with the parameters used, neither got wedged. |

## Structural differences

| # | Aspect | `mini_serv.c` | `mini_serv_ref.c` | Verdict |
|---|---|---|---|---|
| 1 | `send` flag | `MSG_NOSIGNAL` | `0` | **Ours is safer.** SIGPIPE protection. |
| 2 | Dispatch loop | `break` after one fd | processes all ready fds | Both correct. Reference is slightly faster; ours slightly more deterministic. |
| 3 | `select()` error | `continue` (retry) | `exit_err` (die) | Ours tolerates `EINTR`. |
| 4 | `recv` size | `sizeof(buf_r) - 1` | `1024` into `rbuf[1024]` then `rbuf[r] = 0` | **Reference has a one-byte OOB write when `r == 1024`.** Ours is safe. |
| 5 | Extract loop | `while (... > 0)` | `while (...)` (treats `-1` as truthy) | Reference would infinite-loop on `calloc` failure. Edge case. |
| 6 | Fanout shape | one `send` per fd with full message | two `send`s per fd (`"client X: "` then body) | With concurrent traffic the reference can interleave bytes from two different broadcasts. Standard exam06 grader does not test this. |
| 7 | `wbuf` size | `200000` | `42` | Reference is tight but fits `"server: client 9999 just arrived\n"` (33 bytes). |

## Risks evaluated

The two architectural risks we identified for any blocking-I/O variant
of mini_serv:

1. **`send()` blocks on a slow peer** — entire server freezes; pending
   disconnect detection and broadcasts are delayed indefinitely. Both
   files share this risk equally. `test_slow_peer.py` exercises it but
   could not wedge either server with default Linux loopback buffers.

2. **`accept()` blocks on a phantom connection** — between `select`
   reporting `sockfd` readable and the server calling `accept`, the
   peer can RST the connection. On Linux the `accept` may then block.
   Reproducing this from userland is non-deterministic; not tested.
   Both files share this risk equally.

## Conclusion

On every divergence that matters, `mini_serv.c` is at least as safe as
the reference, and strictly safer on SIGPIPE handling, OOB bounds,
EINTR tolerance, and broadcast atomicity. The reference passes the
grader because the grader does not probe those corners. Reproducing
`mini_serv.c` as the exam solution is the recommended path.
