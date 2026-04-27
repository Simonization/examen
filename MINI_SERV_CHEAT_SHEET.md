# mini_serv Function Signatures & What They Do

## `send_all(int except)` — broadcast `buf_w` to everyone but `except`

```c
void send_all(int except)
{
    for (int fd = 0; fd <= maxfd; fd++)
        if (FD_ISSET(fd, &wfds) && fd != except)
            send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL);
}
```

- `FD_ISSET(fd, &wfds)` → "is this fd writable right now?" `wfds` was just filled by `select`. Skipping non-writable fds is what makes us non-blocking — we never wait on a slow client.
- `&&` not `&` (bitwise AND would still work numerically but wrong intent).
- `send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL)` — push `strlen(buf_w)` bytes to fd. `MSG_NOSIGNAL` prevents the kernel from raising `SIGPIPE` if the peer already closed; instead `send` just returns `-1` with `EPIPE` and we ignore it.
- `except` is the fd we want to skip: the sender (in `read_client`) or the leaver (in `rm_client`).

## `add_client(void)` — accept new connection

```c
void add_client(void)
{
    int cfd = accept(sockfd, NULL, NULL);
    if (cfd < 0) return;
    if (cfd > maxfd) maxfd = cfd;
    ids[cfd] = gid++;
    bufs[cfd] = NULL;
    FD_SET(cfd, &afds);
    sprintf(buf_w, "server: client %d just arrived\n", ids[cfd]);
    send_all(cfd);
}
```

- `accept(sockfd, NULL, NULL)` → kernel pulls a completed handshake off the listener's queue, returns a *new* fd for that connection. NULL/NULL because we don't care about the peer's address.
- `if (cfd > maxfd) maxfd = cfd;` — needed so `select(maxfd+1, ...)` will watch this new fd.
- `ids[cfd] = gid++` — assign the next sequential client id (0, 1, 2…) and bump the global counter.
- `bufs[cfd] = NULL` — reset the per-fd accumulator (might have leftovers from a previous client that used the same fd number).
- `FD_SET(cfd, &afds)` — add to master set so future `select`s watch it.
- `send_all(cfd)` — announce arrival to everyone *except* the new client.

## `rm_client(int fd)` — disconnect cleanup

```c
void rm_client(int fd)
{
    sprintf(buf_w, "server: client %d just left\n", ids[fd]);
    send_all(fd);
    free(bufs[fd]);
    bufs[fd] = NULL;
    FD_CLR(fd, &afds);
    close(fd);
}
```

- Order matters: `sprintf` + `send_all` *before* `close`, otherwise you lose the id reference and you'd be sending on a closed fd.
- `free(bufs[fd])` — release any partial line still buffered (subject forbids leaks).
- `FD_CLR(fd, &afds)` — remove from master set so `select` stops watching.
- `close(fd)` — kernel sends FIN to peer and reclaims the fd number.

## `read_client(int fd)` — receive + dispatch

```c
void read_client(int fd)
{
    int r = recv(fd, buf_r, sizeof(buf_r) - 1, 0);
    if (r <= 0) { rm_client(fd); return; }
    buf_r[r] = 0;
    bufs[fd] = str_join(bufs[fd], buf_r);
    if (!bufs[fd]) fatal();
    char *msg;
    while (extract_message(&bufs[fd], &msg) > 0)
    {
        sprintf(buf_w, "client %d: %s", ids[fd], msg);
        send_all(fd);
        free(msg);
    }
}
```

- `recv(fd, buf_r, sizeof(buf_r) - 1, 0)` — pull bytes the kernel already buffered for this socket. `-1` reserves a byte for the null terminator.
- `r == 0`: peer closed (FIN). `r < 0`: error. Both → remove client.
- `str_join(bufs[fd], buf_r)` — *append* this chunk to whatever was already buffered for this fd, returning a fresh malloc'd buffer (frees the old one internally). TCP is a byte stream, so you must accumulate.
- `extract_message(&bufs[fd], &msg)` — peel one complete `\n`-terminated line into `msg`, leaving the remainder in `bufs[fd]`. Returns `1` on success, `0` if no full line yet, `-1` on alloc failure.
- Format `"client %d: %s"` with **no extra `\n`** — `msg` already ends with one.
- `send_all(fd)` — broadcast except the sender.
- `free(msg)` — extract_message gave you ownership.

## `main` — bootstrap + event loop

```c
sockfd = socket(AF_INET, SOCK_STREAM, 0);
// fill struct sockaddr_in addr with AF_INET, htonl(2130706433), htons(atoi(av[1]))
bind(sockfd, (const struct sockaddr *)&addr, sizeof(addr));
listen(sockfd, 128);

FD_ZERO(&afds);
FD_SET(sockfd, &afds);
maxfd = sockfd;

while (1)
{
    rfds = wfds = afds;
    if (select(maxfd + 1, &rfds, &wfds, NULL, NULL) < 0)
        continue;
    for (int fd = 0; fd <= maxfd; fd++)
    {
        if (!FD_ISSET(fd, &rfds))
            continue;
        if (fd == sockfd)
            add_client();
        else
            read_client(fd);
        break;
    }
}
```

**Order to memorize: ZERO before SET** (zero the set, then add sockfd). You had them swapped.

- `socket(AF_INET, SOCK_STREAM, 0)` — IPv4 + TCP. Returns the listening fd.
- `htonl(2130706433)` = 127.0.0.1 in network byte order (subject mandates loopback only).
- `htons(atoi(av[1]))` — port from argv, host→network short.
- `listen(sockfd, 128)` — turn into passive socket; `128` is the backlog queue size.
- `FD_ZERO(&afds)` — clear master set. Takes **one** arg.
- `FD_SET(sockfd, &afds)` — add listener. Takes **(fd, &set)**.
- `maxfd = sockfd` — initial highest watched fd.
- `rfds = wfds = afds;` — `select` overwrites its sets, so reload every iteration.
- `select(maxfd + 1, &rfds, &wfds, NULL, NULL)` — block until at least one fd is read- or write-ready. `+1` because the first arg is "highest fd number + 1". `NULL` timeout = wait forever.
- `if (... < 0) continue;` — on error, restart loop (which reloads rfds/wfds). Use `if`, not `while`.
- `FD_ISSET(fd, &rfds)` — note: you check **read** readiness here (`rfds`), not `wfds`. `wfds` is only consulted inside `send_all`.
- `fd == sockfd` → new connection waiting. Otherwise → client data (or close).
- `break` — handlers mutate `afds`/`maxfd`, so we restart the outer loop instead of trusting the stale snapshot.

## Two things to burn in memory

1. `&` vs `&&` in `FD_ISSET(fd, &wfds) && fd != except` — needs logical `&&`.
2. `FD_ISSET(fd, &rfds)` vs `FD_ISSET(fd, &wfds)` — different sets, different purposes:
   - `rfds` answers "can I `recv`/`accept` without blocking?"
   - `wfds` answers "can I `send` without blocking?"
