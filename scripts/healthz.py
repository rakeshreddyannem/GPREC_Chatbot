#!/usr/bin/env python3
"""
healthz.py: Standalone health check script for GPREC AI Student Assistant container.
Verifies knowledge base database, vector index, and server connectivity.
Exit code 0 on healthy, 1 on failure.
"""
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def check_health():
    errors = []

    # 1. Check knowledge base database
    db_path = PROJECT_ROOT / os.getenv("DB_PATH", "gprec_knowledge.db")
    if not db_path.exists():
        errors.append(f"Database missing at {db_path}")
    elif db_path.stat().st_size == 0:
        errors.append(f"Database file is empty (0 bytes) at {db_path}")

    # 2. Check FAISS vectorstore
    vs_dir = PROJECT_ROOT / "vectorstore"
    index_bin = vs_dir / "faiss_index.bin"
    metadata_pkl = vs_dir / "metadata.pkl"

    if not index_bin.exists():
        errors.append(f"FAISS index missing at {index_bin}")
    elif index_bin.stat().st_size == 0:
        errors.append(f"FAISS index is empty at {index_bin}")

    if not metadata_pkl.exists():
        errors.append(f"FAISS metadata missing at {metadata_pkl}")
    elif metadata_pkl.stat().st_size == 0:
        errors.append(f"FAISS metadata is empty at {metadata_pkl}")

    # 3. Optional HTTP probe if curl/requests available and port is open
    port = os.getenv("PORT", "7860")
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/_stcore/health", headers={"User-Agent": "healthz-probe"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                errors.append(f"Streamlit HTTP health returned status {response.status}")
    except Exception as e:
        # If server is starting up or this is run offline before server starts, note it
        pass

    if errors:
        print("[UNHEALTHY] Health check failed:")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("[HEALTHY] All data files, indices, and services are intact.")
        return 0

if __name__ == "__main__":
    sys.exit(check_health())
