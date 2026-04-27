# Testing mini_serv with nc (netcat)

## Setup

Compile and start your server in one terminal:
```bash
gcc -o mini_serv mini_serv.c
./mini_serv 4242
```

The server is now listening on localhost:4242.

## Test 1: Basic Connection & Broadcast

**Terminal 2** (Client A):
```bash
nc 127.0.0.1 4242
```

**Terminal 3** (Client B):
```bash
nc 127.0.0.1 4242
```

In **Terminal 3**, type: `hello from B`

**Expected in Terminal 2:**
```
server: client 1 just arrived
client 1: hello from B
```

✅ If you see both messages, broadcasts work.

---

## Test 2: Multiple Messages in One Line (contains \n)

**Terminal 2**, type:
```
line1
line2
```

**Expected in Terminal 3:**
```
client 0: line1
client 2: line2
```

✅ Each line gets its own broadcast with prefix.

---

## Test 3: Partial Message (no newline yet)

**Terminal 2**, type (without hitting enter):
```
partial
```
(nothing sent to server yet)

**Terminal 3**, type:
```
complete
```

**Expected in Terminal 2:**
```
client 1: complete
```

✅ Partial message is buffered, doesn't broadcast.

Now hit enter on **Terminal 2**:
```
partial
```

**Expected in Terminal 3:**
```
client 0: partial
```

✅ Buffering works correctly.

---

## Test 4: Client Disconnect

**Terminal 2**, press `Ctrl+D` to close.

**Expected in Terminal 3:**
```
server: client 0 just left
```

✅ Leave broadcast works.

---

## Test 5: Slow Client (receiver buffer full)

**Terminal 2**:
```bash
nc 127.0.0.1 4242 > /dev/null
```
(connected but discarding all input)

**Terminal 3**:
```bash
nc 127.0.0.1 4242
```
In this terminal, send many large messages rapidly:
```
message1111111111111111111111111111111111111111111111
message2222222222222222222222222222222222222222222222
message3333333333333333333333333333333333333333333333
...
```

Type `leaving` and hit enter.

**Expected:**
- Server stays responsive
- Terminal 3 receives the broadcasts (not stuck)
- You can send new messages while 2 is slow

✅ If server doesn't hang, non-blocking works.

---

## Test 6: Verify stderr vs stdout

Start server, close it immediately with wrong args:
```bash
./mini_serv
```

**Check:**
```bash
./mini_serv 2>&1 | cat        # Should see "Wrong number..."
./mini_serv 1>/dev/null       # Should still see "Wrong number..." on stderr
./mini_serv 2>/dev/null       # Should NOT see "Wrong number..." (suppressed stderr)
```

✅ If message only appears on stderr, write(2, ...) is correct.

---

## Checklist for Exam

Before submitting, verify with nc:

- [ ] Server starts and listens on given port
- [ ] Multiple clients can connect simultaneously
- [ ] Messages broadcast to all except sender
- [ ] Each line gets the `client %d: ` prefix
- [ ] Partial messages are buffered (no \n = no broadcast)
- [ ] Multiple lines in one recv are handled (each gets prefix)
- [ ] Client disconnect sends "just left" broadcast
- [ ] Errors write to stderr (fd 2), not stdout (fd 1)
- [ ] Server doesn't crash if a client closes abruptly
- [ ] Server stays responsive even with slow clients

---

## Quick Debug Checklist

| Symptom | Check |
|---------|-------|
| "Address already in use" | Wait 30s or use different port |
| Messages don't broadcast | Is sender excluded? Check `send_all(fd)` |
| Extra newlines in output | Check sprintf format (should not have \n at end) |
| Partial messages broadcast | Check extract_message() is in while loop |
| Client removed when not closed | Check recv() return value (should only rm on r <= 0) |
| Server hangs on slow client | Check FD_ISSET(fd, &wfds) in send_all |
| Server crashes on disconnected peer | Check MSG_NOSIGNAL in send() |

---

## Exam Pro Tips

1. **Test arrival/leave first** — if these work, core logic is sound
2. **Test with 3+ clients** — catches issues with maxfd tracking
3. **Send messages with embedded newlines** — tests line splitting
4. **Use `Ctrl+C` to stop server** — cleaner than kill
5. **Redirect nc output to see everything clearly:**
   ```bash
   nc 127.0.0.1 4242 | tee client.log
   ```
6. **If server crashes, check dmesg/stderr for the exact error**

Good luck tomorrow! 🚀
