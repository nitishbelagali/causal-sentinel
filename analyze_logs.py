import pandas as pd
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ ERROR: No API Key found in .env file.")
    print("Please create a .env file with: OPENAI_API_KEY=sk-...")
    exit()

client = OpenAI(api_key=api_key)

def analyze_log(log_message):
    """
    Sends a log message to the LLM to determine if it's a 'Causal Candidate'.
    """
    prompt = f"""
    You are a Senior Site Reliability Engineer (SRE). 
    Analyze this system log entry: "{log_message}"

    Your Goal: Determine if this event could CAUSE a revenue drop or latency spike.
    
    Rules:
    1. documentation, css, typos, and routine maintenance are LOW risk.
    2. database changes, api logic changes, infinite loops, and synchronous calls are HIGH risk.

    Return a JSON object with this exact format:
    {{
        "risk_level": "HIGH" or "LOW",
        "component": "database" or "frontend" or "payment_api" or "other",
        "reasoning": "brief explanation"
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0, 
            response_format={"type": "json_object"} 
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ Error analyzing log: {e}")
        return {"risk_level": "UNKNOWN", "component": "unknown", "reasoning": "API Error"}

# --- MAIN EXECUTION ---
def main():
    print("🕵️  Archaeologist AI: Interactive Mode")
    print("-------------------------------------")
    
    # 1. GET FILE NAME
    while True:
        filename = input("📂 Enter the name of your logs CSV (e.g., real_github_logs.csv): ").strip()
        if os.path.exists(filename):
            break
        print(f"❌ File '{filename}' not found. Try again.")

    # 2. LOAD DATA
    try:
        df_logs = pd.read_csv(filename)
        print(f"✅ Loaded {len(df_logs)} rows.")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    # 3. MAP COLUMNS
    print("\nColumns found:", list(df_logs.columns))
    
    # Ask user for the 'message' column
    msg_col = input("👉 Type the column name containing the Log Message: ").strip()
    while msg_col not in df_logs.columns:
        print("❌ Column not found.")
        msg_col = input(f"👉 Please type exactly one of {list(df_logs.columns)}: ").strip()

    # Ask user for the 'timestamp' column (Optional, but good for saving)
    time_col = input("👉 Type the column name containing the Timestamp: ").strip()
    while time_col not in df_logs.columns:
        print("❌ Column not found.")
        time_col = input(f"👉 Please type exactly one of {list(df_logs.columns)}: ").strip()

    # 4. SAFETY LIMIT (Important for Wallet!)
    print(f"\n⚠️  WARNING: You have {len(df_logs)} logs.")
    limit_input = input("🔢 How many logs should we analyze? (Press Enter for default 50): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 50
    
    # Slice the dataframe
    target_logs = df_logs.head(limit).copy()
    print(f"🚀 Starting AI Analysis on first {limit} rows...")

    results = []
    
    # 5. LOOP AND ANALYZE
    for index, row in target_logs.iterrows():
        message_text = str(row[msg_col]) # Handle non-string data safely
        
        # Simple progress bar
        print(f"[{index+1}/{limit}] Analyzing: {message_text[:40]}...")
        
        analysis = analyze_log(message_text)
        
        # Standardize the output row
        # We keep the original data but add our AI tags
        row_data = row.to_dict()
        row_data['ai_risk'] = analysis.get('risk_level')
        row_data['ai_component'] = analysis.get('component')
        row_data['ai_reasoning'] = analysis.get('reasoning')
        
        results.append(row_data)

    # 6. SAVE RESULTS
    output_filename = "analyzed_events.csv"
    df_analyzed = pd.DataFrame(results)
    
    # Rename user columns to standard names for the dashboard (Optional, but helpful)
    # We rename the user's columns to 'timestamp' and 'message' so the dashboard detects them easier
    df_analyzed.rename(columns={msg_col: 'message', time_col: 'timestamp'}, inplace=True)
    
    df_analyzed.to_csv(output_filename, index=False)
    
    print(f"\n✅ Analysis Complete. Saved to '{output_filename}'")
    
    # Check for High Risk Findings
    high_risk = df_analyzed[df_analyzed['ai_risk'] == 'HIGH']
    if not high_risk.empty:
        print(f"\n🔥 FOUND {len(high_risk)} HIGH RISK EVENTS:")
        print(high_risk[['timestamp', 'message', 'ai_reasoning']].head())
    else:
        print("\n👍 No High Risk events found in this sample.")

if __name__ == "__main__":
    main()