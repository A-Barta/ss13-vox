#!/usr/bin/env python3
"""
Wrapper script for backwards compatibility.
Use `ss13-vox` command or `python -m ss13vox.cli` instead.
"""

from ss13vox.cli import main

if __name__ == "__main__":
    main()
