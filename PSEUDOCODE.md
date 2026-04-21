# Pseudocode — main.c helpers & mini_serv.c

Plain-English version. Read this first, then look at the real `.c` file and match every block back to these notes.

---

## Part 1 — `main.c` helpers

You will **copy these two functions** from `main.c` at the exam. Don't rewrite them. But you must understand them so you know how to *use* them correctly.

### `extract_message(char **buf, char **msg)` — returns int

**Purpose**: take one complete line (ending in `\n`) from `*buf`, hand it back via `*msg`, and leave the rest in `*buf`.

```
set *msg to NULL                       // caller sees NULL if nothing extracted
if *buf is NULL:
    return 0                           // nothing to extract

walk through *buf character by character:
    if current char is '\n':
        allocate a fresh "newbuf" big enough for everything AFTER the '\n'
        if allocation fails:
            return -1                  // malloc error — caller should fatal
        copy the tail (chars after '\n') into newbuf
        hand the ORIGINAL buf to the caller via *msg
        terminate *msg right after the '\n' so caller sees one line
        replace *buf with newbuf (the leftover tail)
        return 1                       // one message extracted

if we walked the whole buf and found no '\n':
    return 0                           // incomplete, try again later
```

**Memory ownership after a successful call (return 1)**:
- `*msg` → newly handed to caller. **Caller must `free` it.**
- `*buf` → points to a brand new allocation (the tail). Caller owns it.
- The original buffer memory is now *inside* `*msg`, so freeing `*msg` frees it.

**Return codes — memorize**:
- `1` → got a message, msg is valid, loop again
- `0` → no full line yet, stop looping
- `-1` → malloc failed, call `fatal()`

**Usage pattern**:
```
while extract_message(&clients_buf, &msg) > 0:
    do something with msg
    free(msg)
```

---

### `str_join(char *buf, char *add)` — returns char*

**Purpose**: concatenate `add` onto `buf`, free the old `buf`, return a fresh allocation. Handles `buf == NULL`.

```
if buf is NULL:
    len = 0
else:
    len = strlen(buf)

allocate newbuf of size (len + strlen(add) + 1)
if allocation fails:
    return NULL                        // caller should fatal

make newbuf an empty string
if buf is not NULL:
    copy buf into newbuf
free the old buf                       // IMPORTANT — caller must NOT free again
append add to newbuf
return newbuf
```

**Memory ownership**:
- The old `buf` is **freed inside str_join**. Do NOT free it yourself.
- Returned pointer is yours. Assign it back: `buf = str_join(buf, add);`
- If it returns NULL → malloc failed → call `fatal()`.

**Usage pattern**:
```
clients_buf = str_join(clients_buf, newly_received_data)
if clients_buf is NULL: fatal()
```

---

## Part 2 — `mini_serv.c` pseudocode

### Section A — Includes + globals

```
INCLUDE: string.h, stdlib.h, unistd.h, stdio.h, sys/socket.h, netinet/in.h, sys/select.h

PASTE: extract_message + str_join (copied from main.c)

GLOBAL sockfd       — the listening socket fd
GLOBAL maxfd        — highest fd we know about (upper bound for select)
GLOBAL gid          — next client id to assign (starts 0, only grows)
GLOBAL ids[65536]   — ids[fd] = the client id for that fd
GLOBAL bufs[65536]  — bufs[fd] = pending receive buffer for that fd (char*, NULL if empty)
GLOBAL afds         — "active" fd_set, the source of truth of who's connected
GLOBAL rfds, wfds   — working copies of afds for each select() call
GLOBAL buf_w        — big char buffer we sprintf outgoing messages into
GLOBAL buf_r        — big char buffer we recv incoming data into
```

**Why globals?** Because helper functions (`send_all`, `add_client`, etc.) need to touch all of them, and passing them around as args would explode the function signatures. Global arrays are fine here — exam code, not production.

**Why `ids[65536]`?** Because we index by fd. A Linux process can have fds up to ~65k. So we size the array to cover any possible fd without needing a map.

---

### Section B — `fatal()`

```
write to stderr (fd 2): "Fatal error\n"  (12 bytes)
exit with status 1
```

**When to call**: socket/bind/listen failure, or any malloc returning NULL.

---

### Section C — `send_all(except)`

```
for each fd from 0 to maxfd:
    if fd is in wfds (select says it's writable right now)
    AND fd is not the sender:
        send(fd, buf_w, strlen(buf_w), 0)
        ignore the return value — if a lazy client can't receive, we don't care
```

**Why check `wfds`?** Because we only send to clients that are (a) connected and (b) ready to accept data — otherwise `send` could block. `select` gives us this for free.

**Why skip `except`?** The subject says broadcasts go to "all the other clients" — sender doesn't see their own message echoed back.

**Why ignore `send` errors?** Subject: "client can be lazy and if they don't read your message you must NOT disconnect them".

---

### Section D — `add_client()`

```
cfd = accept(sockfd, NULL, NULL)
if cfd < 0:
    return                          // accept failure ≠ fatal, just drop this one

if cfd > maxfd:
    maxfd = cfd                     // grow upper bound if needed

ids[cfd] = gid
gid = gid + 1                       // monotonic — ids never reused
bufs[cfd] = NULL                    // no pending data yet
FD_SET(cfd, afds)                   // add to active set

sprintf into buf_w: "server: client <id> just arrived\n"
send_all(except = cfd)              // broadcast to others, not to the newcomer
```

**Why pass NULL to accept?** We don't need the client's address (subject only requires 127.0.0.1 binding on our side).

**Why `gid++`?** Subject: "the first client will receive the id 0 and each new client will receive the last client id + 1". Monotonic counter. Never decremented, never reused.

---

### Section E — `rm_client(fd)`

```
sprintf into buf_w: "server: client <id> just left\n"
send_all(except = fd)               // tell everyone else first, while fd still in wfds? — actually fd is still in wfds here, but send_all skips it via the `!= except` check

free(bufs[fd])                      // release any pending receive buffer
bufs[fd] = NULL                     // defensive, in case fd gets reused
FD_CLR(fd, afds)                    // remove from active set
close(fd)                           // release the fd
```

**Order matters**: broadcast BEFORE closing, because once closed the fd can be reused and `ids[fd]` becomes stale.

**Why `FD_CLR` from `afds` and not also rfds/wfds?** Because `afds` is the source of truth — rfds/wfds are overwritten from `afds` at the top of every loop iteration.

---

### Section F — `read_client(fd)`

```
r = recv(fd, buf_r, sizeof(buf_r) - 1, 0)
if r <= 0:
    rm_client(fd)                   // 0 = clean disconnect, -1 = error — either way, they're gone
    return

buf_r[r] = '\0'                     // null-terminate so we can treat as C string

bufs[fd] = str_join(bufs[fd], buf_r)   // append what we just got to the pending buffer
if bufs[fd] is NULL:
    fatal()

// Now drain any complete lines from the pending buffer:
loop:
    ret = extract_message(&bufs[fd], &msg)
    if ret <= 0: break              // 0 = no complete line yet, -1 = malloc fail (could fatal but safe to just stop)
    sprintf into buf_w: "client <id>: <msg>"      // msg already ends with '\n'
    send_all(except = fd)
    free(msg)
```

**Why accumulate in `bufs[fd]` instead of processing directly?** Because one `recv` might give us a partial line (no `\n`), or multiple lines, or a line split across two recvs. `bufs[fd]` holds the leftover so next recv glues cleanly.

**Why `"client %d: %s"` without `\n`?** Because `extract_message` keeps the `\n` at the end of `msg`. Adding another would produce a blank line.

**Why `recv(..., sizeof(buf_r) - 1, 0)` and not full size?** To leave room for the null terminator we write in the next line.

---

### Section G — `main`

```
if argc != 2:
    write to stderr: "Wrong number of arguments\n" (26 bytes)
    exit 1

sockfd = socket(AF_INET, SOCK_STREAM, 0)
if sockfd < 0: fatal()

build a sockaddr_in:
    zero it out (bzero)
    family = AF_INET
    address = htonl(2130706433)     // 127.0.0.1 — NOT 0.0.0.0
    port    = htons(atoi(argv[1]))

if bind(sockfd, &addr, sizeof addr) < 0: fatal()
if listen(sockfd, 128) < 0: fatal()

FD_ZERO(afds)
FD_SET(sockfd, afds)                // server socket is in the active set from the start
maxfd = sockfd

forever:
    rfds = afds                     // fresh copies — select() modifies them
    wfds = afds
    if select(maxfd + 1, &rfds, &wfds, NULL, NULL) < 0:
        continue                    // interrupted? try again
    
    for fd from 0 to maxfd:
        if fd is not in rfds: continue     // nothing to do on this fd
        
        if fd == sockfd:
            add_client()             // new connection arriving
        else:
            read_client(fd)          // data from an existing client
        
        break                        // handle one fd per iteration — simpler, still correct
```

**Why `rfds = wfds = afds` every iteration?** `select()` MUTATES its fd_set arguments — it clears bits for fds that are NOT ready. We need `afds` preserved as the source of truth, so we copy before every select.

**Why `select(maxfd + 1, ...)`?** Because select takes the number of fds to watch, which is `highest_fd + 1`. That's just the API.

**Why `break` after handling one fd?** Two reasons:
1. `add_client()` modifies `maxfd`, so continuing the loop with a stale bound is confusing.
2. `rm_client()` closes an fd, which could change which fds are valid.

It's simpler to just handle one event per select and let the next `select` call pick up the rest on the next iteration. Correct, just slightly slower — fine for an exam.

**Why `htonl(2130706433)` for 127.0.0.1?** Because `inet_addr` is NOT in the allowed functions list. `2130706433` = `0x7F000001` = `127.0.0.1` in host byte order, and `htonl` converts to network byte order.

**Why `listen(sockfd, 128)`?** Backlog of 128 pending connections. Any reasonable number works; exam doesn't care about the exact value.

---

## Part 3 — The seven "chunks" to write in order

When you're rewriting blank, write in this exact order. Every chunk is short:

1. **Includes + paste helpers from main.c** (~65 lines — free)
2. **Globals** (~5 lines)
3. **`fatal`** (~4 lines)
4. **`send_all`** (~5 lines)
5. **`add_client`** (~12 lines)
6. **`rm_client`** (~8 lines)
7. **`read_client`** (~20 lines)
8. **`main`** (~40 lines)

Total new code (after pasting helpers): ~100 lines.

If any chunk feels unclear, come back to this file, re-read that section, and convince yourself of every "why".
