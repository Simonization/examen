# EXAM06 Study Plan — mini_serv (compressed)

**Now**: Wednesday 2026-04-22, 10:00
**Exam**: Friday 2026-04-24 at 14:00 — ~52 hours, really ~2.5 working days.
**Starting point**: PSEUDOCODE.md read, the 7 chunks (includes+helpers / globals / fatal / send_all / add_client / rm_client / read_client / main) are known.
**Goal**: muscle memory. Reproduce `mini_serv.c` from blank in under 25 min, compile clean, pass nc tests.

The plan is rep-driven. No more "read the code and understand" time — that's done. From here it's rewrite → diff → fix → repeat.

---

## Wednesday 2026-04-22 (today)

### 10:00 → 12:00 · Warm-up rewrite #1 (peek-allowed)

- [ ] Create `ERRORS.md` (empty, you'll fill it as you go).
- [ ] Open a **blank** `.c` file. Paste `extract_message` + `str_join` from `main.c` (this is what you'll do at the exam).
- [ ] Write the rest. If you blank, peek at `PSEUDOCODE.md` (not `mini_serv.c`). Note every peek in `ERRORS.md`.
- [ ] `gcc -Wall -Wextra -Werror mini_serv.c -o mini_serv` → must be clean.
- [ ] Test: `./mini_serv 8080`, two `nc 127.0.0.1 8080` clients, verify arrive/leave/broadcast format.
- [ ] `diff` against `mini_serv.c`. Log every delta in `ERRORS.md`.

### 14:00 → 17:00 · Rewrite #2 + #3 (blank, no peeking)

- [ ] **Rewrite #2** from scratch. No peeking. If you get stuck: stop, re-read `ERRORS.md`, start over.
- [ ] Compile, test with nc, diff. Update `ERRORS.md`.
- [ ] **Rewrite #3**. Same rules. Time yourself — just to baseline, not to hit a target yet.
- [ ] Diff. Update `ERRORS.md`.

### 20:00 → 22:00 · Drill the gotchas + rewrite #4

- [ ] Re-read `ERRORS.md`. Write each recurrent wrong line in its **correct** form 5× by hand.
- [ ] Drill the **3 magic numbers** until automatic:
  - `2130706433` → `127.0.0.1` in host byte order (use with `htonl`).
  - `26` → `strlen("Wrong number of arguments\n")`.
  - `12` → `strlen("Fatal error\n")`.
- [ ] Drill the **3 format strings** verbatim:
  - `"server: client %d just arrived\n"`
  - `"server: client %d just left\n"`
  - `"client %d: %s"` — no trailing `\n`, `extract_message` keeps it.
- [ ] **Rewrite #4**. Target: under 30 minutes. Compile, test, diff.
- [ ] Sleep by 23:30.

---

## Thursday 2026-04-23

### 08:30 → 12:00 · Timed rewrites #5 + #6

- [ ] Re-read `ERRORS.md` before you start.
- [ ] **Rewrite #5** blank. Target: **under 25 minutes**. Compile, test, diff.
- [ ] **Rewrite #6** blank. Same target. If you hit it twice, you're on track.
- [ ] Update `ERRORS.md`. If a mistake reappears for a 3rd time, escalate it: write the correct line 10× and mark it in `ERRORS.md` as "recurrent — check last".

### 14:00 → 17:00 · Edge-case testing + targeted drills

- [ ] On your latest rewrite, run these by hand with `nc`:
  - Client sends a single `\n` (empty line) — broadcast should still happen.
  - Client sends multi-line message in one send — each line broadcast separately.
  - Client sends partial line (no `\n`), waits, then sends the rest — one broadcast only, on completion.
  - Client connects then Ctrl-C immediately — clean rm_client, no leak.
  - Two clients connect back-to-back — ids 0 and 1, both broadcasts land.
  - Kill a reader while server running — `send` failure must NOT crash server (no fatal on send).
- [ ] Drill the **sockaddr_in setup** — bzero, family, htonl(2130706433), htons(atoi(argv[1])) — write it 5× by hand from memory.
- [ ] Drill the **select loop skeleton**: `rfds = wfds = afds;` then `select(maxfd+1, ...)` then `for fd 0..maxfd` then `break` after one event.

### 20:00 → 22:00 · Rewrite #7 (final rehearsal)

- [ ] Re-read `ERRORS.md` — both recurrent items and everything else.
- [ ] **Rewrite #7** blank, timed, target **20 minutes**. Compile, test, diff.
- [ ] If clean diff: you're ready. Close the laptop.
- [ ] If not clean: one more targeted drill on the diff, then stop.
- [ ] Sleep by 23:00.

---

## Friday 2026-04-24 — Exam Day

### 08:00 · Final blank rewrite
- [ ] Coffee. No news, no social media.
- [ ] **Rewrite #8** from a blank file. Compile clean, test with nc, diff.
- [ ] If a mistake pops up, fix it in your head and move on — don't spiral.

### 10:00 · Stop coding
- [ ] Close the laptop. Review `ERRORS.md` on paper if helpful (no keyboard).
- [ ] Eat a real lunch. Travel buffer.

### 14:00 · Exam
- [ ] Open `main.c`. Copy `extract_message` + `str_join` first — don't rewrite them.
- [ ] Write in order: **includes → helpers → globals → fatal → send_all → add_client → rm_client → read_client → main.**
- [ ] Compile with `-Wall -Wextra -Werror`. Test with two `nc` clients.
- [ ] Before submitting: re-read `subject.txt`, verify every requirement (exit codes, error strings, 127.0.0.1, no forbidden functions).

---

## Critical gotchas (glance before each rewrite)

1. **127.0.0.1** → `htonl(2130706433)`. NEVER `0x00000000` (= 0.0.0.0 = all interfaces, forbidden).
2. **No `printf`** anywhere. `sprintf` into `buf_w`, then `send` or `write`.
3. **Copy fd_sets each iteration**: `rfds = wfds = afds;` before every `select`.
4. `extract_message` returns `1` / `0` / `-1`. Loop while `> 0`.
5. `str_join` **frees the old buf**. Just reassign: `bufs[fd] = str_join(bufs[fd], buf_r);`.
6. `break` after handling one fd in the select loop — simpler and correct.
7. `"Wrong number of arguments\n"` = 26 bytes; `"Fatal error\n"` = 12 bytes. Both stderr (fd 2), exit 1.
8. `bufs[cfd] = NULL` on arrival — `str_join` handles NULL.
9. `free(bufs[fd])` on disconnect, set to NULL defensively.
10. **Do NOT `fatal()` on `send` failure** — subject says lazy clients must NOT be disconnected.
11. Broadcast on leave happens **before** `close(fd)` — after close, `ids[fd]` is stale.
12. `recv(fd, buf_r, sizeof(buf_r) - 1, 0)` — leave room for `'\0'`.

---

## Mantra (say it before each rewrite)

> "Includes, helpers, globals, fatal, send_all, add, remove, read, main."

Nine chunks, always the same order. Reps are the whole plan from here.
