import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def main():
    print("🎢 Generating Multi-Crash Revenue Data...")

    # --- CONFIGURATION ---
    # 1. The specific days you want to "Blame"
    # Based on your log snippet:
    CRASH_DATES = [
        "2025-12-12", # Image prefetch thread-safe issue
        "2025-12-17", # Binary FormData uploads / Sync RCTNative
        "2025-12-19", # Fix build for unknown annotation
        "2025-12-22"  # Synchronous updates to AnimatedProps
    ]
    
    # 2. Setup the Timeline
    # We start a few days before the first crash and end a few days after the last
    START_DATE = datetime(2025, 12, 1) 
    DAYS = 30
    
    metrics_data = []
    current_date = START_DATE
    
    # Track if we are currently in a "Crashed State"
    active_crash_days_remaining = 0

    for i in range(DAYS):
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Base Baseline (Normal Business)
        base_revenue = 50000
        base_latency = 200
        
        # NOISE: Add random variation so it looks real
        revenue = np.random.normal(base_revenue, 2000)
        latency = np.random.normal(base_latency, 20)

        # --- CRASH LOGIC ---
        # 1. Check if TODAY is a new crash start date
        if date_str in CRASH_DATES:
            print(f"   💥 Injecting Crash on {date_str}")
            active_crash_days_remaining = 2 # The crash lasts 2 days
        
        # 2. Apply the Crash Effect if active
        if active_crash_days_remaining > 0:
            revenue = revenue * 0.6  # Drop to 60%
            latency = latency + 300  # Latency spikes
            active_crash_days_remaining -= 1
        
        metrics_data.append({
            "date": date_str,
            "daily_revenue": int(revenue),
            "latency_ms": int(latency)
        })
        
        current_date += timedelta(days=1)

    # --- SAVE ---
    df = pd.DataFrame(metrics_data)
    df.to_csv("business_metrics.csv", index=False)
    print(f"\n✅ Generated 'business_metrics.csv' with {len(CRASH_DATES)} distinct crashes.")
    print("Upload this file to the dashboard alongside your Facebook logs.")

if __name__ == "__main__":
    main()