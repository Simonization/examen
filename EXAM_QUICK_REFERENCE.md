# mini_serv Exam Quick Reference

## Critical Don't-Forgets

```c
// 1. ERROR OUTPUT: fd 2 (stderr), not fd 1 (stdout)
write(2, "Wrong number of arguments\n", 26);  // NOT write(1, ...)

// 2. FD_ZERO before FD_SET
FD_ZERO(&afds);                              // FIRST
FD_SET(sockfd, &afds);                       // SECOND

// 3. Check readable with &rfds, NOT &afds
if (!FD_ISSET(fd, &rfds)) continue;          // NOT &afds

// 4. Check writable with &wfds, NOT &afds
if (FD_ISSET(fd, &wfds) && fd != except)    // NOT &afds
    send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL);

// 5. Error checks: use < 0, not != 0
if (sockfd < 0) fatal();                     // NOT == -1
if (bind(...) < 0) fatal();

// 6. Buffer initialization in add_client
bufs[cfd] = NULL;                            // Initialize!

// 7. Message format: NO extra \n
sprintf(buf_w, "client %d: %s", ids[fd], msg);  // msg already has \n

// 8. MSG_NOSIGNAL prevents SIGPIPE
send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL);   // Critical!
```

---

## Skeleton Code (given in main.c)

```c
int extract_message(char **buf, char **msg)   // GIVEN
char *str_join(char *buf, char *add)          // GIVEN
```

DO NOT rewrite these. Copy them as-is from main.c.

---

## Your Code Must Have

```c
int	sockfd, maxfd, gid;
int	ids[65536];
char	*bufs[65536];
fd_set	afds, rfds, wfds;
char	buf_w[200000], buf_r[200000];

void	fatal(void)
void	send_all(int except)
void	add_client(void)
void	rm_client(int fd)
void	read_client(int fd)
int	main(int ac, char **av)
```

---

## Main Loop Structure

```c
FD_ZERO(&afds);
FD_SET(sockfd, &afds);
maxfd = sockfd;

while (1) {
    rfds = wfds = afds;                    // Reload sets every iteration
    if (select(maxfd + 1, &rfds, &wfds, NULL, NULL) < 0)
        continue;                          // if error, restart loop
    
    for (int fd = 0; fd <= maxfd; fd++) {
        if (!FD_ISSET(fd, &rfds))
            continue;                      // Skip non-readable
        
        if (fd == sockfd)
            add_client();                  // New connection
        else
            read_client(fd);               // Client data
        
        break;                             // Restart after any change
    }
}
```

---

## Test with nc

```bash
gcc -o mini_serv mini_serv.c
./mini_serv 4242

# Terminal 2:
nc 127.0.0.1 4242

# Terminal 3:
nc 127.0.0.1 4242
# type: hello
# Terminal 2 should see: client 1: hello
```

---

## Common Mistakes to Avoid

| Mistake | Result | Fix |
|---------|--------|-----|
| `write(1, ...)` for errors | Grader fails | Use `write(2, ...)` |
| `FD_SET` before `FD_ZERO` | Undefined behavior | Swap order |
| Check `&afds` in dispatch loop | Server hangs on recv() | Use `&rfds` |
| Check `&afds` in send_all | Server blocks on slow peer | Use `&wfds` |
| `!= 0` error check | Rejects valid returns | Use `< 0` |
| Forget `bufs[cfd] = NULL` in add_client | Buffer leakage on fd reuse | Add initialization |
| `sprintf(..., "%s\n", msg)` | Extra blank lines | msg already has \n |
| Forget `MSG_NOSIGNAL` | Server dies on peer disconnect | Add flag |
| `while(select...<0)` instead of `if` | Undefined fd_set state | Use `if` |

---

## Performance Requirement

Subject says: **"send the messages as fast as you can"**

✅ Expected: < 50ms per message  
⚠️ Acceptable: < 200ms  
❌ Broken: > 2000ms (blocking)

If your server is slow, check for:
- Unnecessary buffering
- Multiple select() calls
- Blocking on slow clients (missing FD_ISSET check)

---

## If Something Breaks

```bash
# Compile with all warnings
gcc -Wall -Wextra -Werror mini_serv.c -o mini_serv

# Run tests
python3 test_stderr.py ./mini_serv      # Check stderr
python3 test_afds_bug.py ./mini_serv    # Check performance
python3 test_sigpipe.py ./mini_serv     # Check MSG_NOSIGNAL

# Manual test
nc 127.0.0.1 4242                       # Connect
# Type a few messages, check broadcasts
```

---

## What Gets You 100%

1. ✅ Compiles with `-Wall -Wextra -Werror`
2. ✅ All 6 tests pass (test_*.py)
3. ✅ Messages broadcast to all except sender
4. ✅ Each line gets `client %d: ` prefix
5. ✅ Errors go to stderr
6. ✅ Handles 3+ concurrent clients
7. ✅ Buffering works (partial messages don't broadcast)
8. ✅ Non-blocking (doesn't hang on slow clients)
9. ✅ No memory leaks
10. ✅ No SIGPIPE crashes

---

**Good luck! You've got this.** 🚀
