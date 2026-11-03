"""Keep machine-readable command output UTF-8 on Windows as well as macOS/Linux."""
import sys


def configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
