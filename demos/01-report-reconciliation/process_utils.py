"""Subprocess cleanup that tolerates a child exiting during timeout handling."""
import os


def signal_group(pid, signal):
    try:
        os.killpg(pid, signal)
    except ProcessLookupError:
        pass  # The group exited between the timeout and the signal.
