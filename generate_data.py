import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DAYS = 60
START_DATE = datetime(2024, 10, 1)
INCIDENT_DATE = datetime(2024, 11, 15)

# --- 1. METRICS GENERATION (Revenue & Latency) ---
dates = [START_DATE + timedelta(days=i) for i in range(DAYS)]
metrics_data = []

print("⚙️ Generating Business Metrics...")

for d in dates:
    # BASELINE: Normal behavior
    latency = np.random.normal(200, 15)  # Avg 200ms
    revenue = np.random.normal(50000, 2000) # Avg $50k
    
    # THE INCIDENT: After Nov 15, latency goes up, revenue goes down
    if d >= INCIDENT_DATE:
        latency += 400  # Jump to ~600ms
        # Causal Impact: Revenue drops because of latency
        revenue -= (latency - 200) * 40 
        
    metrics_data.append({
        "date": d.strftime("%Y-%m-%d"),
        "avg_latency_ms": int(latency),
        "daily_revenue": int(revenue)
    })

df_metrics = pd.DataFrame(metrics_data)
df_metrics.to_csv("business_metrics.csv", index=False)
print("✅ Created 'business_metrics.csv'")

# --- 2. LOGS GENERATION (The Digital Exhaust) ---
print("⚙️ Generating System Logs...")

logs_data = []
# Different teams creating noise
authors = ["dev_team", "marketing_bot", "db_admin", "sre_bot"]
actions = [
    "Optimized image assets", 
    "Updated copyright year", 
    "Ran vacuum on DB", 
    "Restarted cache node", 
    "Updated CSS for landing page"
]

for d in dates:
    # 1. Generate random "Noise" logs (Safe stuff)
    for _ in range(random.randint(2, 5)):
        logs_data.append({
            "timestamp": d.strftime("%Y-%m-%d") + f" {random.randint(9,17)}:{random.randint(10,59)}:00",
            "author": random.choice(authors),
            "message": random.choice(actions)
        })

    # 2. THE SMOKING GUN (The specific bad code change)
    if d == INCIDENT_DATE:
        logs_data.append({
            "timestamp": d.strftime("%Y-%m-%d") + " 10:15:00",
            "author": "dev_team",
            # This is what the LLM will need to catch later:
            "message": "feat: switched payment API to synchronous validation loop" 
        })

# Sort by time
df_logs = pd.DataFrame(logs_data).sort_values("timestamp")
df_logs.to_csv("system_logs.csv", index=False)
print("✅ Created 'system_logs.csv'")

print("\n🚀 PHASE 1 COMPLETE.")
print(f"Stats: {len(df_metrics)} days of metrics, {len(df_logs)} log entries.")