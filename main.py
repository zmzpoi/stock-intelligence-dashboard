"""Convenience entry point; Streamlit Cloud continues to use app.py."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run",
                 str(Path(__file__).resolve().parent / "app.py"),
                 "--server.address", "127.0.0.1"]))
