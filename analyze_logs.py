import pandas as pd
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# --- CONFIGURATION ---
# 1. Set your API Key here (or better, use an environment variable)
# For now, you can paste it directly between quotes, but don't push this specific line to GitHub if you do!

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_log(log_message):
    """
    Sends a log message to the LLM to determine if it's a 'Causal Candidate'.
    """
    # THEPROMPT: This is where we "program" the AI's behavior.
    # We force it to return JSON so our Python code can read it.
    prompt = f"""
    You are a Senior Site Reliability Engineer (SRE). 
    Analyze this system log entry: "{log_message}"

    Your Goal: Determine if this event could CAUSE a revenue drop or latency spike.
    
    Rules:
    1. documentation, css, typos, and routine maintenance are LOW risk.
    2. database changes, api logic changes, and loops are HIGH risk.

    Return a JSON object with this exact format:
    {{
        "risk_level": "HIGH" or "LOW",
        "component": "database" or "frontend" or "payment_api" or "other",
        "reasoning": "brief explanation"
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Cheap, fast, smart enough
            messages=[{"role": "user", "content": prompt}],
            temperature=0, # 0 = Strict/Deterministic. We don't want creativity.
            response_format={"type": "json_object"} # Force JSON mode
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ Error analyzing log: {e}")
        return {"risk_level": "UNKNOWN", "component": "unknown", "reasoning": "API Error"}

# --- MAIN EXECUTION ---
def main():
    print("🕵️  Archaeologist AI is waking up...")
    
    # 1. Load the raw logs
    df_logs = pd.read_csv("system_logs.csv")
    print(f"📄 Loaded {len(df_logs)} logs.")

    # 2. Filter for efficiency (Optional: In real life, we scan everything. 
    # For this demo, let's look closely at the incident date to save your tokens/money)
    # Let's inspect the logs around the incident date we set in Phase 1 ( Nov 15)
    mask = df_logs['timestamp'].str.contains("2024-11-15")
    target_logs = df_logs[mask].copy()
    
    print(f"🔍 Deep scanning {len(target_logs)} logs from the incident day...")

    results = []
    
    # 3. Loop through logs and ask the AI
    for index, row in target_logs.iterrows():
        print(f"   Analyzing: {row['message'][:50]}...")
        
        analysis = analyze_log(row['message'])
        
        # Combine the original log with the AI's new insights
        row['ai_risk'] = analysis.get('risk_level')
        row['ai_component'] = analysis.get('component')
        row['ai_reasoning'] = analysis.get('reasoning')
        
        results.append(row)

    # 4. Save the "Enriched" Data
    df_analyzed = pd.DataFrame(results)
    df_analyzed.to_csv("analyzed_events.csv", index=False)
    
    print("\n✅ Analysis Complete.")
    print("Check 'analyzed_events.csv'. Look for the HIGH risk event.")
    
    # Preview the "Smoking Gun" if found
    high_risk = df_analyzed[df_analyzed['ai_risk'] == 'HIGH']
    if not high_risk.empty:
        print("\n🔥 CAUSAL CANDIDATE FOUND:")
        print(high_risk[['timestamp', 'message', 'ai_reasoning']])

if __name__ == "__main__":
    main()