# EXAM06 Study Plan — mini_serv

**Exam**: Tuesday 2026-04-14 at 10:00
**Goal**: Reproduce `mini_serv.c` from scratch, cleanly, under pressure.

---

## Sunday 2026-04-12

### Morning — 08:00 → 12:00 · Understand every line

Open `mini_serv.c` side-by-side with `subject.txt` and `main.c`.

- [ ] Read `subject.txt` twice. Highlight every requirement (error messages, exit codes, broadcast format, 127.0.0.1, no `#define`, no leaks).
- [ ] List the allowed functions. Confirm none of our code uses forbidden ones (no `printf`, no `fcntl`, no `inet_addr`).
- [ ] Walk the provided helpers from `main.c`:
  - `extract_message(&buf, &msg)` — pulls one `\n`-terminated line out of `buf`, returns 1/0/-1.
  - `str_join(buf, add)` — appends `add` to `buf`, frees old `buf`, returns new.
  - Understand *exactly* what each returns and who owns the memory.
- [ ] Walk `mini_serv.c` top to bottom. For every line, answer: **why is this line here?** If you can't answer, stop and figure it out.
  - Globals: `sockfd, maxfd, gid, ids[], bufs[], afds/rfds/wfds, buf_w/buf_r`
  - `fatal()` — stderr + exit 1
  - `send_all(except)` — loop wfds, skip sender
  - `add_client()` — accept, assign id, FD_SET, broadcast arrival
  - `rm_client(fd)` — broadcast leave, free, FD_CLR, close
  - `read_client(fd)` — recv → str_join → extract_message loop → broadcast
  - `main()` — arg check, socket, bind(127.0.0.1), listen, select loop

### Afternoon — 14:00 → 17:00 · Pseudocode pass

- [ ] Close `mini_serv.c`. Open a blank file.
- [ ] Write the **entire solution in pseudocode** (plain English or comments). Structure:
  1. includes + helpers (from main.c)
  2. globals
  3. fatal / send_all / add_client / rm_client / read_client
  4. main: args → socket → addr → bind → listen → select loop → dispatch
- [ ] Compare your pseudocode against the real file. Note anything you forgot.

### Evening — 20:00 → 22:00 · First blank write

- [ ] Open a **blank** `.c` file. No peeking at `mini_serv.c`.
- [ ] You *may* copy `extract_message` and `str_join` from `main.c` — that's what you'll do at the exam too.
- [ ] Write everything else from memory.
- [ ] Compile: `gcc -Wall -Wextra -Werror mini_serv.c -o mini_serv`
- [ ] Test: `./mini_serv 8080` + two `nc` clients.
- [ ] `diff` against the reference. Write down **every mistake** in `ERRORS.md`.

---

## Monday 2026-04-13

### Morning — 08:00 → 12:00 · Rewrites + diff

- [ ] **Rewrite #2** from blank. Compile, test, diff.
- [ ] **Rewrite #3** from blank. Compile, test, diff.
- [ ] After each, add any new mistakes to `ERRORS.md`.
- [ ] Re-read `ERRORS.md` before starting each new rewrite.

### Afternoon — 14:00 → 17:00 · Targeted drilling

- [ ] Drill the **3 magic numbers**: `2130706433` (127.0.0.1), `26` (strlen "Wrong number of arguments\n"), `12` (strlen "Fatal error\n").
- [ ] Drill the **broadcast format strings** — exactly:
  - `"server: client %d just arrived\n"`
  - `"server: client %d just left\n"`
  - `"client %d: %s"` (note: `%s` already ends in `\n` because `extract_message` keeps it)
- [ ] Drill the **sockaddr_in setup** until it's automatic.
- [ ] **Rewrite #4**. Time yourself. Target: under 25 minutes.

### Evening — 20:00 → 22:00 · Edge cases + recurrent errors

- [ ] Re-read `ERRORS.md`. For each recurrent error, write the **correct** line 5 times by hand.
- [ ] Test edge cases:
  - Client sends a single `\n` (empty line)
  - Client sends multi-line message in one `recv`
  - Client sends partial line (no `\n`), then more
  - Client connects and immediately disconnects
  - Two clients connect simultaneously
- [ ] **Rewrite #5**. Final rehearsal. Sleep by 23:00.

---

## Tuesday 2026-04-14 — Exam Day

### 07:00 · Final blank rewrite
- [ ] Wake up, coffee, no news/social media.
- [ ] **Rewrite #6** from a blank file. Compile clean, test with nc.
- [ ] If anything feels shaky, re-read `ERRORS.md` and that section only.

### 08:30 · Stop coding
- [ ] Close the laptop. Quick review of `ERRORS.md` on paper if helpful.
- [ ] Shower, eat, travel buffer.

### 10:00 · Exam
- [ ] Open main.c. Copy `extract_message` + `str_join` first.
- [ ] Write from top to bottom in the order you practiced: includes → helpers → globals → fatal → send_all → add_client → rm_client → read_client → main.
- [ ] Compile with `-Wall -Wextra -Werror`. Test with `nc`.
- [ ] **Before submitting**: re-read `subject.txt` and verify every requirement.

---

## Critical gotchas (review daily)

1. **127.0.0.1** is `htonl(2130706433)`. NOT `0x00000000` (that's 0.0.0.0 = all interfaces — subject forbids this).
2. **No `printf`** anywhere. Use `sprintf` into a buffer, then `send` or `write`.
3. **Copy fd_sets before select**: `rfds = wfds = afds;` every iteration.
4. `extract_message` returns **1 on success, 0 if no `\n`, -1 on malloc fail** — loop while `> 0`.
5. `str_join` **frees the old buf** — just reassign: `bufs[fd] = str_join(bufs[fd], buf_r);`.
6. After handling one fd, `break` out of the fd loop — keeps logic simple.
7. `"Wrong number of arguments\n"` = **26 bytes**, `"Fatal error\n"` = **12 bytes**. Both to stderr (fd 2), exit 1.
8. `bufs[cfd] = NULL` when a client joins — `str_join` handles `NULL` correctly.
9. Free `bufs[fd]` on disconnect to avoid leaks.
10. Don't `fatal()` on `send` failure — subject says lazy clients must NOT be disconnected.

---

## Daily mantra

> "Includes, helpers, globals, fatal, send_all, add, remove, read, main."

Say it before each rewrite. Nine chunks, in order, no surprises.

Good luck.
