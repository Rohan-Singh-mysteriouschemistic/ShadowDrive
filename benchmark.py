import os
import time
import sqlite3
import hashlib
import sys

# Ensure Client-Logic is in the path to import utils
sys.path.append(os.path.join(os.path.dirname(__file__), "Client-Logic"))
import crypto_utils
import hash_utils
import config

def format_size(size):
    return f"{size / (1024 * 1024):.2f} MB"

def benchmark_delta_sync():
    print("=== Delta Sync Efficiency Benchmark ===")
    file_size = 100 * 1024 * 1024  # 100 MB
    test_file = "test_delta_100MB.bin"
    
    # Create 100MB file
    with open(test_file, "wb") as f:
        f.write(os.urandom(file_size))
        
    start_time = time.perf_counter()
    original_hashes = hash_utils.chunk_and_hash_file(test_file)
    end_time = time.perf_counter()
    
    print(f"Original File Size: {format_size(file_size)}")
    print(f"Total Chunks: {len(original_hashes)}")
    print(f"Time to hash and chunk 100MB: {end_time - start_time:.4f} seconds")
    
    # Modify 1% of the file
    mod_size = int(file_size * 0.01) # 1 MB
    print(f"Modifying {format_size(mod_size)} (1%) of the file...")
    with open(test_file, "r+b") as f:
        # modify somewhat in the middle
        f.seek(file_size // 2)
        f.write(os.urandom(mod_size))
        
    start_time = time.perf_counter()
    new_hashes = hash_utils.chunk_and_hash_file(test_file)
    end_time = time.perf_counter()
    
    changed_chunks = 0
    for i in range(len(original_hashes)):
        if original_hashes[i] != new_hashes[i]:
            changed_chunks += 1
            
    print(f"Time to re-hash modified file: {end_time - start_time:.4f} seconds")
    print(f"Changed Chunks: {changed_chunks} out of {len(original_hashes)}")
    print(f"Redundant transfer reduced by: {100 - (changed_chunks/len(original_hashes)*100):.2f}%")
    
    # Cleanup
    os.remove(test_file)
    print()

def benchmark_encryption():
    print("=== Encryption Overhead Benchmark ===")
    key = crypto_utils.derive_key("password", "test@test.com")
    
    file_size = 100 * 1024 * 1024 # 100 MB
    chunk_size = config.CHUNK_SIZE
    data = os.urandom(chunk_size)
    
    total_chunks = file_size // chunk_size
    if file_size % chunk_size != 0:
        total_chunks += 1
        
    start_time = time.perf_counter()
    for i in range(total_chunks):
        nonce = os.urandom(crypto_utils.NONCE_SIZE)
        _ = crypto_utils.encrypt_chunk(key, data, nonce)
    end_time = time.perf_counter()
    
    duration = end_time - start_time
    throughput = (file_size / (1024 * 1024)) / duration
    print(f"Encrypted 100MB in {duration:.4f} seconds")
    print(f"Encryption Throughput: {throughput:.2f} MB/s")
    print()

def benchmark_metadata():
    print("=== Metadata Engine Performance ===")
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunk_signatures (
            file_path   TEXT,
            chunk_index INTEGER,
            hash        TEXT NOT NULL,
            PRIMARY KEY (file_path, chunk_index)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chunk_signatures_hash ON chunk_signatures (hash)")
    
    # Insert 50K chunks
    num_chunks = 50000
    print(f"Inserting {num_chunks} chunk signatures...")
    
    start_time = time.perf_counter()
    
    # Generate batch data
    batch = [("test_file.bin", i, hashlib.sha256(str(i).encode()).hexdigest()) for i in range(num_chunks)]
    
    cur.executemany("INSERT INTO chunk_signatures (file_path, chunk_index, hash) VALUES (?, ?, ?)", batch)
    conn.commit()
    end_time = time.perf_counter()
    print(f"Insertion Time: {end_time - start_time:.4f} seconds")
    
    # Lookup time
    lookup_hashes = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(0, num_chunks, 10)] # 5000 lookups
    
    start_time = time.perf_counter()
    found = 0
    for h in lookup_hashes:
        cur.execute("SELECT file_path, chunk_index FROM chunk_signatures WHERE hash = ?", (h,))
        if cur.fetchone():
            found += 1
    end_time = time.perf_counter()
    
    print(f"Lookup Time for {len(lookup_hashes)} hashes: {end_time - start_time:.4f} seconds")
    print(f"Average lookup time per hash: {((end_time - start_time) / len(lookup_hashes)) * 1000:.4f} ms")
    
    conn.close()
    print()

if __name__ == "__main__":
    benchmark_delta_sync()
    benchmark_encryption()
    benchmark_metadata()
