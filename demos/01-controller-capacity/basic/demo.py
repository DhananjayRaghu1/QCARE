"""Compatibility entry point for the explicitly deterministic onramping sample.

The former investigation/repair presentation is superseded by onramp.py.
"""
from onramp import main
import sys

if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] in {"all", "investigate", "repair"}:
        print("The earlier repair demo is superseded. Showing the labeled local context sample.")
        sys.argv[1:] = ["--sample"]
    raise SystemExit(main())
