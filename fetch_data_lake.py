import os
import pandas as pd
from dotenv import load_dotenv
from github import Github, Auth
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from jira import JIRA
from datetime import datetime, timedelta
import argparse
from pathlib import Path

# --- CONFIGURATION ---
load_dotenv()

# Credentials
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Targets (from .env or defaults)
REPO_NAME = os.getenv("TARGET_REPO", "facebook/react-native")
SLACK_CHANNEL = os.getenv("TARGET_SLACK_CHANNEL", "general")
JIRA_PROJECT = os.getenv("TARGET_JIRA_PROJECT", "KAN")

# Output directory
OUTPUT_DIR = Path("ingested_logs")
OUTPUT_DIR.mkdir(exist_ok=True)


def fetch_github(days_back=30, max_commits=500):
    """
    Ingests Commit History from GitHub
    
    Args:
        days_back: Number of days to look back (default: 30)
        max_commits: Maximum number of commits to fetch (default: 500)
    """
    print(f"\n🐙 [GITHUB] Connecting to {REPO_NAME}...")
    
    if not GITHUB_TOKEN:
        print("⚠️  [GITHUB] GITHUB_TOKEN not set. Skipping.")
        return None
    
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Calculate date threshold
        since_date = datetime.now() - timedelta(days=days_back)
        commits = repo.get_commits(since=since_date)
        
        logs = []
        count = 0
        
        for commit in commits:
            if count >= max_commits:
                break
            
            # Extract commit details
            commit_data = {
                "timestamp": commit.commit.author.date,
                "message": commit.commit.message.split('\n')[0],  # First line only
                "full_message": commit.commit.message,
                "author": commit.commit.author.name,
                "sha": commit.sha[:7],  # Short SHA
                "files_changed": commit.stats.total,
                "additions": commit.stats.additions,
                "deletions": commit.stats.deletions,
                "source_file": "github_logs.csv",
                "source_type": "GitHub"
            }
            logs.append(commit_data)
            count += 1
        
        if logs:
            df = pd.DataFrame(logs)
            output_path = OUTPUT_DIR / "github_logs.csv"
            df.to_csv(output_path, index=False)
            print(f"✅ [GITHUB] Saved {len(logs)} commits to {output_path}")
            return df
        else:
            print("⚠️  [GITHUB] No commits found in date range.")
            return None
            
    except Exception as e:
        print(f"❌ [GITHUB] Failed: {e}")
        return None


def fetch_slack(days_back=30, max_messages=500):
    """
    Ingests Chat History from Slack
    
    Args:
        days_back: Number of days to look back (default: 30)
        max_messages: Maximum number of messages to fetch (default: 500)
    """
    print(f"\n💬 [SLACK] Connecting to #{SLACK_CHANNEL}...")
    
    if not SLACK_TOKEN:
        print("⚠️  [SLACK] SLACK_BOT_TOKEN not set. Skipping.")
        return None
    
    try:
        client = WebClient(token=SLACK_TOKEN)
        
        # 1. Find Channel ID
        channel_id = None
        response = client.conversations_list(types="public_channel,private_channel")
        
        for ch in response["channels"]:
            if ch["name"] == SLACK_CHANNEL.replace("#", ""):
                channel_id = ch["id"]
                break
        
        if not channel_id:
            print(f"❌ [SLACK] Channel '{SLACK_CHANNEL}' not found.")
            return None
        
        # 2. Calculate oldest timestamp
        oldest = (datetime.now() - timedelta(days=days_back)).timestamp()
        
        # 3. Fetch Messages with pagination
        logs = []
        cursor = None
        
        while len(logs) < max_messages:
            result = client.conversations_history(
                channel=channel_id,
                limit=100,
                oldest=str(oldest),
                cursor=cursor
            )
            
            for msg in result["messages"]:
                # Filter: only user messages (no bots, no system messages)
                if "text" in msg and "subtype" not in msg and "bot_id" not in msg:
                    logs.append({
                        "timestamp": datetime.fromtimestamp(float(msg["ts"])),
                        "message": msg["text"][:500],  # Truncate long messages
                        "author": msg.get("user", "Unknown"),
                        "has_thread": "thread_ts" in msg,
                        "reaction_count": len(msg.get("reactions", [])),
                        "source_file": "slack_logs.csv",
                        "source_type": "Slack"
                    })
            
            # Check if there are more messages
            if not result.get("has_more", False):
                break
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        
        if logs:
            df = pd.DataFrame(logs)
            output_path = OUTPUT_DIR / "slack_logs.csv"
            df.to_csv(output_path, index=False)
            print(f"✅ [SLACK] Saved {len(logs)} messages to {output_path}")
            return df
        else:
            print("⚠️  [SLACK] No messages found in date range.")
            return None
            
    except SlackApiError as e:
        print(f"❌ [SLACK] API Error: {e.response['error']}")
        return None
    except Exception as e:
        print(f"❌ [SLACK] Failed: {e}")
        return None


def fetch_jira(days_back=30, max_issues=500):
    """
    Ingests Ticket History from Jira
    
    Args:
        days_back: Number of days to look back (default: 30)
        max_issues: Maximum number of issues to fetch (default: 500)
    """
    print(f"\n🎫 [JIRA] Connecting to project {JIRA_PROJECT}...")
    
    if not all([JIRA_SERVER, JIRA_EMAIL, JIRA_API_TOKEN]):
        print("⚠️  [JIRA] Credentials not set. Skipping.")
        return None
    
    try:
        jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        
        # Calculate date threshold
        since_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # JQL query with date filter
        jql = f"project = {JIRA_PROJECT} AND created >= '{since_date}' ORDER BY created DESC"
        issues = jira.search_issues(jql, maxResults=max_issues, fields="summary,created,reporter,status,priority,issuetype")
        
        logs = []
        for issue in issues:
            logs.append({
                "timestamp": issue.fields.created,
                "message": f"[{issue.key}] {issue.fields.summary}",
                "ticket_key": issue.key,
                "author": str(issue.fields.reporter),
                "status": str(issue.fields.status),
                "priority": str(issue.fields.priority),
                "issue_type": str(issue.fields.issuetype),
                "source_file": "jira_logs.csv",
                "source_type": "Jira"
            })
        
        if logs:
            df = pd.DataFrame(logs)
            output_path = OUTPUT_DIR / "jira_logs.csv"
            df.to_csv(output_path, index=False)
            print(f"✅ [JIRA] Saved {len(logs)} tickets to {output_path}")
            return df
        else:
            print("⚠️  [JIRA] No issues found in date range.")
            return None
            
    except Exception as e:
        print(f"❌ [JIRA] Failed: {e}")
        return None


def create_master_log(dataframes):
    """
    Combines all sources into a single master log file
    """
    print("\n🔗 [MASTER] Combining all sources...")
    
    combined = []
    for name, df in dataframes.items():
        if df is not None and not df.empty:
            combined.append(df)
    
    if combined:
        master_df = pd.concat(combined, ignore_index=True)
        
        # --- FIX: Handle Mixed Timezones ---
        # 1. Force everything to UTC first
        master_df['timestamp'] = pd.to_datetime(master_df['timestamp'], utc=True)
        
        # 2. Remove timezone info (make it "naive") so it's clean for Excel/Streamlit
        master_df['timestamp'] = master_df['timestamp'].dt.tz_localize(None)
        # -----------------------------------
        
        # Sort by timestamp
        master_df = master_df.sort_values('timestamp').reset_index(drop=True)
        
        # Save
        output_path = OUTPUT_DIR / "master_logs.csv"
        master_df.to_csv(output_path, index=False)
        print(f"✅ [MASTER] Combined {len(master_df)} total events → {output_path}")
        
        # Summary stats
        print("\n📊 Summary:")
        for source_type in master_df['source_type'].unique():
            count = len(master_df[master_df['source_type'] == source_type])
            print(f"   {source_type}: {count} events")
        
        return master_df
    else:
        print("⚠️  [MASTER] No data to combine.")
        return None


def main():
    """Main orchestration function with CLI support"""
    
    parser = argparse.ArgumentParser(description="Ingest logs from GitHub, Slack, and Jira")
    parser.add_argument("--days", type=int, default=30, help="Days to look back (default: 30)")
    parser.add_argument("--max-commits", type=int, default=500, help="Max GitHub commits (default: 500)")
    parser.add_argument("--max-messages", type=int, default=500, help="Max Slack messages (default: 500)")
    parser.add_argument("--max-issues", type=int, default=500, help="Max Jira issues (default: 500)")
    parser.add_argument("--sources", nargs="+", choices=["github", "slack", "jira", "all"], 
                       default=["all"], help="Which sources to fetch (default: all)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 CAUSAL SENTINEL - DATA LAKE INGESTION")
    print("=" * 60)
    print(f"\n⚙️  Configuration:")
    print(f"   Lookback: {args.days} days")
    print(f"   Output: {OUTPUT_DIR}")
    print(f"   Sources: {', '.join(args.sources)}")
    
    # Collect dataframes
    dataframes = {}
    
    # Run orchestrators based on arguments
    sources = args.sources if "all" not in args.sources else ["github", "slack", "jira"]
    
    if "github" in sources:
        dataframes['github'] = fetch_github(args.days, args.max_commits)
    
    if "slack" in sources:
        dataframes['slack'] = fetch_slack(args.days, args.max_messages)
    
    if "jira" in sources:
        dataframes['jira'] = fetch_jira(args.days, args.max_issues)
    
    # Create master log
    master_df = create_master_log(dataframes)
    
    print("\n" + "=" * 60)
    print("✨ INGESTION COMPLETE")
    print("=" * 60)
    print(f"\n📁 Files saved to: {OUTPUT_DIR}/")
    print("\nNext steps:")
    print("   1. Run: python analyze_logs.py")
    print("   2. Upload analyzed logs to dashboard.py")
    
    return master_df


if __name__ == "__main__":
    main()