# mini_serv.c — Exact Lines by Category

## 1. Select Functions (FD_*)

```c
FD_ZERO(&afds);
FD_SET(sockfd, &afds);
FD_SET(cfd, &afds);
FD_CLR(fd, &afds);
if (FD_ISSET(fd, &wfds) && fd != except)
if (!FD_ISSET(fd, &rfds))
```

**What they do:**
- `FD_ZERO(&afds)` — clear the entire fd_set
- `FD_SET(sockfd, &afds)` — add fd to set (takes fd and &set)
- `FD_CLR(fd, &afds)` — remove fd from set
- `FD_ISSET(fd, &wfds)` — test if fd is in set (used in send_all with wfds for writable)
- `FD_ISSET(fd, &rfds)` — test if fd is in set (used in main loop with rfds for readable)

## 2. Kernel & Helper Functions (send, accept, recv, close, select, str_join, extract_message)

```c
add_client:         int cfd = accept(sockfd, NULL, NULL);
read_client:        int r = recv(fd, buf_r, sizeof(buf_r) - 1, 0);
read_client:        bufs[fd] = str_join(bufs[fd], buf_r);
read_client:        while (extract_message(&bufs[fd], &msg) > 0)
send_all:           send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL);
rm_client:          close(fd);
main:               if (select(maxfd + 1, &rfds, &wfds, NULL, NULL) < 0)
```

**What they do:**
- `accept(sockfd, NULL, NULL)` — pull completed handshake, return new fd
- `recv(fd, buf_r, sizeof(buf_r) - 1, 0)` — pull bytes from socket, return count (≤0 = error/close)
- `str_join(char *buf, char *add)` — append `add` to `buf`, return fresh malloc'd buffer (given in main.c)
- `extract_message(char **buf, char **msg)` — extract one `\n`-terminated line into `msg`, leave remainder in `buf` (given in main.c)
- `send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL)` — push bytes to socket, no SIGPIPE on broken pipe
- `close(fd)` — close socket fd, kernel sends FIN
- `select(maxfd + 1, &rfds, &wfds, NULL, NULL)` — wait for readability on rfds or writability on wfds; returns count of ready fds

## 3. IF-Conditions

```c
if (cfd < 0)
    return;

if (cfd > maxfd)
    maxfd = cfd;

if (r <= 0)
{
    rm_client(fd);
    return;
}

if (!bufs[fd])
    fatal();

if (select(maxfd + 1, &rfds, &wfds, NULL, NULL) < 0)
    continue;

if (!FD_ISSET(fd, &rfds))
    continue;

if (fd == sockfd)
    add_client();
else
    read_client(fd);

if (FD_ISSET(fd, &wfds) && fd != except)
    send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL);
```

**What they check:**
- `if (cfd < 0)` — accept failed, skip this iteration
- `if (cfd > maxfd)` — update maxfd for select bounds
- `if (r <= 0)` — recv closed/errored, remove client
- `if (!bufs[fd])` — str_join malloc failed, fatal error
- `if (select(...) < 0)` — select errored, retry (continue restores rfds/wfds)
- `if (!FD_ISSET(fd, &rfds))` — fd not readable, skip to next fd
- `if (fd == sockfd)` — listener ready = new connection, else = client data
- `if (FD_ISSET(fd, &wfds) && fd != except)` — fd is writable AND not the sender, send the message
