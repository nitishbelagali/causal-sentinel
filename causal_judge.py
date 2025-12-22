import pandas as pd
import numpy as np
import dowhy
from dowhy import CausalModel
import warnings

warnings.filterwarnings("ignore")

def main():
    print("⚖️  The Causal Judge is entering the courtroom (Attempt 2)...")

    # --- 1. DATA PREPARATION ---
    df_metrics = pd.read_csv("business_metrics.csv")
    df_events = pd.read_csv("analyzed_events.csv")
    
    # Sort metrics by date to be safe
    df_metrics = df_metrics.sort_values("date")
    
    # Find the specific date where the Bad Code was pushed
    high_risk_events = df_events[df_events['ai_risk'] == 'HIGH']
    
    if high_risk_events.empty:
        print("❌ CRITICAL: No HIGH risk events found in analyzed_events.csv. Check Phase 2.")
        return

    # Get the first date a bad event happened (The "Trigger")
    first_bad_date = high_risk_events['timestamp'].str.slice(0, 10).min()
    print(f"🔥 Incident Start Date identified: {first_bad_date}")
    
    # --- THE LOGIC FIX ---
    # Instead of just marking that ONE day, we mark that day AND ALL FUTURE days as "Compromised"
    # Logic: If date >= bad_date, then active_bug = 1
    df_metrics['is_system_broken'] = df_metrics['date'].apply(lambda x: 1 if x >= first_bad_date else 0)
    
    # Rename for the model
    data = df_metrics.copy()
    
    print(f"📊 Dataset ready. Comparing {len(data[data['is_system_broken']==0])} Normal Days vs {len(data[data['is_system_broken']==1])} Broken Days.")

    # --- 2. DEFINE THE CAUSAL MODEL ---
    # We ask: Does 'is_system_broken' cause 'daily_revenue'?
    model = CausalModel(
        data=data,
        treatment='is_system_broken',
        outcome='daily_revenue',
        common_causes=['avg_latency_ms']
    )
    
    # --- 3. IDENTIFY & ESTIMATE ---
    identified_estimand = model.identify_effect()
    
    estimate = model.estimate_effect(
        identified_estimand,
        method_name="backdoor.linear_regression"
    )
    
    print("\n📉 Step 3: ESTIMATION COMPLETE")
    print(f"Causal Estimate: {estimate.value}")
    
    # --- 4. REFUTE (Stress Test) ---
    print("\n🛡️  Step 4: Stress Testing...")
    refutation = model.refute_estimate(
        identified_estimand,
        estimate,
        method_name="placebo_treatment_refuter",
        simulations=10 # Run 10 times for speed
    )
    
    print(f"Placebo Effect (Should be small): {refutation.new_effect}")
    print(f"p-value: {refutation.refutation_result['p_value']}")

    # Verdict Logic
    # The estimate should be massive (thousands of dollars). The placebo should be small (dozens of dollars).
    if abs(estimate.value) > abs(refutation.new_effect) * 2:
        print("\n✅ VERDICT: GUILTY. The broken state CAUSALLY drove the revenue drop.")
        print(f"💰 Estimated Loss per Day: ${round(abs(estimate.value), 2)}")
    else:
        print("\n❌ VERDICT: INCONCLUSIVE.")

if __name__ == "__main__":
    main()