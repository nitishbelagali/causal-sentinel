import pandas as pd
import os
from openai import OpenAI
from dotenv import load_dotenv
import json
import time

# --- CONFIGURATION ---
load_dotenv()

# Input: The master file created by your fetch_data_lake.py script
INPUT_FILE = "ingested_logs/master_logs.csv"
# Output: The file you will upload to the dashboard
OUTPUT_FILE = "analyzed_logs.csv"

# API Key Check
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found in .env file! Please add it.")

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_log_batch(logs_text):
    """
    Sends a batch of mixed logs (Jira/Slack/GitHub) to GPT-4o for risk assessment.
    """
    prompt = f"""
    You are a Senior Site Reliability Engineer (SRE). 
    Analyze the following system logs (which may be Git Commits, Jira Tickets, or Slack Messages).
    
    Your goal is to identify operational RISKS.
    
    For each log entry, output a JSON object with:
    1. "ai_risk": "HIGH" (if it implies a crash, downtime, urgent bug, or risky change) or "LOW".
    2. "ai_component": The system component involved (e.g., "Database", "Frontend", "Payment API").
    3. "ai_reasoning": A short, 5-word explanation of why you chose the risk level.

    Input Logs:
    {logs_text}

    Output Format:
    Return ONLY a valid JSON list of objects. No markdown, no explanations.
    Example:
    [
        {{"ai_risk": "HIGH", "ai_component": "Database", "ai_reasoning": "Database lock detected in Slack"}},
        {{"ai_risk": "LOW", "ai_component": "Documentation", "ai_reasoning": "Routine readme update"}}
    ]
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Use "gpt-3.5-turbo" if you want to save money
            messages=[
                {"role": "system", "content": "You are a helpful SRE assistant that outputs strict JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0  # Deterministic output
        )
        
        # Clean the response to ensure valid JSON (remove ```json markers if AI adds them)
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content)
        
    except Exception as e:
        print(f"⚠️ Error analyzing batch: {e}")
        return []

def main():
    print(f"📂 Loading logs from {INPUT_FILE}...")
    
    # 1. Validation
    if not os.path.exists(INPUT_FILE):
        print(f"❌ File not found: {INPUT_FILE}")
        print("   -> Run 'python fetch_data_lake.py' first to generate it!")
        return

    # 2. Load Data
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    print(f"🔍 Found {len(df)} mixed events. Starting AI Analysis...")

    # 3. Prepare AI Columns
    df["ai_risk"] = "LOW"
    df["ai_component"] = "Unknown"
    df["ai_reasoning"] = ""

    # 4. Process in Batches (to respect Context Window & Rate Limits)
    BATCH_SIZE = 10
    total_batches = (len(df) // BATCH_SIZE) + 1

    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i : i + BATCH_SIZE]
        
        # Construct the text prompt for this batch
        logs_text = ""
        # iterate using explicit index to map back correctly
        for idx, row in batch.iterrows():
            # We explicitly tell the AI the source type (e.g., "Slack") so it understands context
            source = row.get('source_type', 'Unknown')
            msg = row.get('message', 'No message')
            logs_text += f"Log ID {idx}: [{source}] {msg}\n"
        
        print(f"🤖 Processing Batch {i//BATCH_SIZE + 1}/{total_batches} ({len(batch)} items)...")
        
        # Call AI
        ai_results = analyze_log_batch(logs_text)
        
        # Map results back to the DataFrame
        # We assume the AI returns the list in the same order. 
        # (For production, we might map by ID, but sequential is usually fine for batches)
        current_idx = i
        for result in ai_results:
            if current_idx < len(df):
                df.at[current_idx, "ai_risk"] = result.get("ai_risk", "LOW")
                df.at[current_idx, "ai_component"] = result.get("ai_component", "Unknown")
                df.at[current_idx, "ai_reasoning"] = result.get("ai_reasoning", "N/A")
                current_idx += 1
        
        # Sleep briefly to avoid hitting OpenAI rate limits
        time.sleep(0.5)

    # 5. Save Result
    df.to_csv(OUTPUT_FILE, index=False)
    print("="*40)
    print(f"✅ Analysis Complete!")
    print(f"📁 Output saved to: {OUTPUT_FILE}")
    print("🚀 Next Step: Drag this file into your Streamlit Dashboard.")

if __name__ == "__main__":
    main()