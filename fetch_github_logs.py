import pandas as pd
from github import Github
import os
from dotenv import load_dotenv

# Load env to get API Key (Optional, but increases rate limits)
load_dotenv()
token = os.getenv("GITHUB_TOKEN") 

# If you don't have a token, it will work for public repos but might be slow/limited
g = Github(token)

def fetch_repo_commits(repo_name):
    print(f"🔌 Connecting to GitHub Repo: {repo_name}...")
    
    try:
        repo = g.get_repo(repo_name)
        commits = repo.get_commits()
        
        logs = []
        print(f"📥 Fetching commits (This might take a moment)...")
        
        # We limit to last 100 commits to be safe/fast
        for commit in commits[:100]:
            logs.append({
                "timestamp": commit.commit.author.date, # GitHub Timestamp
                "message": commit.commit.message,       # The Commit Message
                "author": commit.commit.author.name     # The Developer
            })
            
        df = pd.DataFrame(logs)
        
        # Save to CSV
        output_file = "real_github_logs.csv"
        df.to_csv(output_file, index=False)
        print(f"✅ Success! Fetched {len(df)} commits.")
        print(f"📁 Saved to '{output_file}'")
        
        return output_file

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# --- USE YOUR OWN REPO OR A POPULAR ONE ---
# You can try: "facebook/react" or your own "username/causal-sentinel"
if __name__ == "__main__":
    target_repo = input("Enter GitHub Repo (e.g., 'facebook/react' or 'your-user/causal-sentinel'): ")
    fetch_repo_commits(target_repo)