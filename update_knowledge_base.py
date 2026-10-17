import subprocess
import time
import sys

def run_update():
    print("========================================")
    print("GPREC AI Assistant - Knowledge Base Update")
    print("========================================")
    
    start_time = time.time()
    
    try:
        print("\n[1/2] Running Web Crawler for Change Detection...")
        subprocess.run([sys.executable, "src/crawler.py"], check=True)
        
        print("\n[2/2] Running Vector Embedding and Ingestion...")
        subprocess.run([sys.executable, "ingest.py"], check=True)
        
        elapsed = time.time() - start_time
        print(f"\nUpdate Complete! Total time: {elapsed:.2f} seconds.")
    except subprocess.CalledProcessError as e:
        print(f"\nUpdate Failed with exit code {e.returncode}")
        
if __name__ == "__main__":
    run_update()
