"""Unified basketball entry point; preserve the legacy EuroLeague interface."""
from basketball_runner import main

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
