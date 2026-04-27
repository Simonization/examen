#!/usr/bin/env python3
"""
Test that ALL error messages are written to stderr, not stdout.

Issues this catches:
  1. write(1, ...) instead of write(2, ...) for "Wrong number of arguments"
  2. printf() being used (outputs to stdout by default)
  3. Any other output leaking to stdout instead of stderr

Failure: if error message appears on stdout instead of stderr.
"""

import subprocess
import sys
import random

def test_wrong_args_to_stderr():
    """Test: 'Wrong number of arguments' goes to stderr."""
    port = random.randint(20000, 60000)
    binary = sys.argv[1]

    # Run with wrong args (too many)
    proc = subprocess.Popen(
        [binary, str(port), "extra_arg"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate()

    if "Wrong number of arguments" in stdout:
        print("FAIL: 'Wrong number of arguments' written to stdout, not stderr")
        print(f"  stdout: {stdout!r}")
        print(f"  stderr: {stderr!r}")
        return 1

    if "Wrong number of arguments" not in stderr:
        print("FAIL: 'Wrong number of arguments' not found in stderr")
        print(f"  stdout: {stdout!r}")
        print(f"  stderr: {stderr!r}")
        return 1

    print("PASS: 'Wrong number of arguments' correctly written to stderr")
    return 0


def test_no_args_to_stderr():
    """Test: 'Wrong number of arguments' when run with no args."""
    binary = sys.argv[1]

    # Run with no args
    proc = subprocess.Popen(
        [binary],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate()

    if "Wrong number of arguments" in stdout:
        print("FAIL: 'Wrong number of arguments' (no args) written to stdout")
        print(f"  stdout: {stdout!r}")
        return 1

    if "Wrong number of arguments" not in stderr:
        print("FAIL: 'Wrong number of arguments' (no args) not in stderr")
        print(f"  stderr: {stderr!r}")
        return 1

    print("PASS: 'Wrong number of arguments' (no args) correctly to stderr")
    return 0


def test_fatal_error_to_stderr():
    """Test: Fatal errors (bad port, etc) go to stderr."""
    binary = sys.argv[1]

    # Try to bind to a port < 1024 (usually requires root, causes "Fatal error")
    # Or use an invalid port number (negative, too large)
    proc = subprocess.Popen(
        [binary, "1"],  # Port 1, likely no permission
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        stdout, stderr = proc.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()
        # If it didn't die, it might have bound successfully. Skip this test.
        print("SKIP: Port 1 binding succeeded (might be running as root)")
        return 0

    # If there's a fatal error, it should be on stderr
    if "Fatal error" in stderr:
        if "Fatal error" in stdout:
            print("FAIL: 'Fatal error' appears on both stdout and stderr")
            return 1
        print("PASS: 'Fatal error' correctly on stderr only")
        return 0

    # If no fatal error, the server might be running on a privileged port
    # (shouldn't happen in test environment)
    print("SKIP: No Fatal error (port 1 might be accessible)")
    return 0


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <binary>", file=sys.stderr)
        sys.exit(2)

    results = [
        ("wrong_args_to_stderr", test_wrong_args_to_stderr),
        ("no_args_to_stderr", test_no_args_to_stderr),
        ("fatal_error_to_stderr", test_fatal_error_to_stderr),
    ]

    failed = 0
    for name, test_func in results:
        try:
            ret = test_func()
            if ret != 0:
                failed += 1
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            failed += 1

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
