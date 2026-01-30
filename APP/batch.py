import time
import os
import cv2
import numpy as np
import easyocr
import torch

def benchmark_batch_processing():
    # 1. Hardware Detection
    gpu_available = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if gpu_available else "CPU Only"
    
    print("="*60)
    print(" HARDWARE BATCH PERFORMANCE BENCHMARK ")
    print("="*60)
    print(f"Device detected: {device_name}")
    print(f"GPU Available for EasyOCR: {gpu_available}")
    print("="*60)

    # 2. Setup Dummy Data
    # We create a dummy 200x50 image with some text-like noise to simulate pet names
    dummy_img = np.zeros((50, 200, 3), dtype=np.uint8)
    cv2.putText(dummy_img, "HUGE CAT", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    batch_sizes = [1, 2, 4, 8, 10, 16]
    results = []

    # 3. Initialize Reader
    print("\nInitializing EasyOCR Reader...")
    # We test both GPU and CPU if possible
    modes = [True] if gpu_available else [False]
    if gpu_available: modes.append(False) # Test CPU fallback too

    for use_gpu in modes:
        mode_label = "GPU" if use_gpu else "CPU"
        print(f"\n--- Testing {mode_label} Mode ---")
        
        try:
            reader = easyocr.Reader(['en'], gpu=use_gpu)
        except Exception as e:
            print(f"Failed to init {mode_label} reader: {e}")
            continue

        # Warmup
        print(f"Performing warmup inference...")
        reader.readtext(dummy_img)

        for size in batch_sizes:
            # Create a batch list of images
            batch = [dummy_img] * size
            
            print(f"Testing Batch Size: {size}...", end="\r")
            
            start_time = time.perf_counter()
            
            # Note: EasyOCR readtext doesn't have a native 'batch' method for multiple images 
            # in one call but we can simulate the parallel overhead.
            # Real batching in EasyOCR is usually done by passing a list of image paths 
            # or using the internal recognition module. 
            # Here we simulate the processing of 'N' images.
            for img in batch:
                reader.readtext(img)
                
            end_time = time.perf_counter()
            
            total_time = end_time - start_time
            img_per_sec = size / total_time
            avg_latency = (total_time / size) * 1000 # in ms
            
            results.append({
                "mode": mode_label,
                "batch_size": size,
                "total_sec": round(total_time, 4),
                "fps": round(img_per_sec, 2),
                "latency_ms": round(avg_latency, 2)
            })

    # 4. Display Results
    print("\n" + "="*60)
    print(f"{ 'MODE':<6} | { 'BATCH':<6} | { 'TOTAL (s)':<10} | { 'IMG/SEC':<8} | { 'LATENCY (ms)':<12}")
    print("-" * 60)
    
    for res in results:
        print(f"{res['mode']:<6} | {res['batch_size']:<6} | {res['total_sec']:<10} | {res['fps']:<8} | {res['latency_ms']:<12}")
    
    print("="*60)
    print("\nRECOMMENDATION:")
    # Find the size with the highest IMG/SEC
    best = max(results, key=lambda x: x['fps'])
    print(f"Optimal Batch Size: {best['batch_size']} ({best['mode']} mode)")
    print(f"Peak Throughput: {best['fps']} images per second.")
    print("="*60)

if __name__ == "__main__":
    benchmark_batch_processing()
