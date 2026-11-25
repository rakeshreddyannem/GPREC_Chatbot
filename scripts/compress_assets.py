import gzip
import shutil
import time
import os
from pathlib import Path

def compress_file(src_path: Path, dst_path: Path):
    t0 = time.time()
    with open(src_path, 'rb') as f_in, gzip.open(dst_path, 'wb', compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    elapsed = time.time() - t0
    orig_mb = os.path.getsize(src_path) / (1024 * 1024)
    gz_mb = os.path.getsize(dst_path) / (1024 * 1024)
    print(f"Compressed {src_path.name}: {orig_mb:.1f} MB -> {gz_mb:.1f} MB in {elapsed:.2f}s")

if __name__ == "__main__":
    compress_file(Path("gprec_knowledge.db"), Path("gprec_knowledge.db.gz"))
    compress_file(Path("vectorstore/metadata.pkl"), Path("vectorstore/metadata.pkl.gz"))
