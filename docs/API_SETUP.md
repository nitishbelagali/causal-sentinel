# 🔑 API Setup Guide

Complete guide to obtaining and configuring API credentials for Causal Sentinel.

---

## 📋 Overview

Causal Sentinel integrates with multiple data sources. Here's what you need:

| Service | Required? | Purpose | Setup Time |
|---------|-----------|---------|------------|
| **OpenAI** | ✅ Yes | Log analysis (GPT-4o) | 2 min |
| **GitHub** | ⚠️ Optional | Commit history | 3 min |
| **Slack** | ⚠️ Optional | Chat messages | 5 min |
| **Jira** | ⚠️ Optional | Ticket tracking | 3 min |

---

## 🤖 OpenAI API Setup (Required)

### Step 1: Create Account
1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Add payment method (required for API access)

### Step 2: Generate API Key
1. Navigate to [API Keys](https://platform.openai.com/api-keys)
2. Click **"Create new secret key"**
3. Name it: `causal-sentinel`
4. Copy the key (starts with `sk-proj-...`)
5. **Save it immediately** - you won't see it again!

### Step 3: Add to .env
```bash
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

### Pricing
- **Model used**: `gpt-4o-mini`
- **Cost**: ~$0.50 per 1,000 log entries
- **Typical usage**: $5-20/month for active projects

---

## 🐙 GitHub API Setup (Optional)

### Step 1: Create Personal Access Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Configure:
   - **Name**: `causal-sentinel`
   - **Expiration**: 90 days (or custom)
   - **Scopes** (select these):
     - ✅ `repo` - Full control of repositories
     - ✅ `read:org` - Read org and team membership (if analyzing org repos)

4. Click **"Generate token"**
5. Copy the token (starts with `ghp_...`)

### Step 2: Add to .env
```bash
GITHUB_TOKEN=ghp_your-token-here
TARGET_REPO=your-username/your-repo
```

### Finding Your Repository Name
- Format: `owner/repo`
- Example: `facebook/react` or `nitishbelagali/my-project`
- Find it in your GitHub URL: `github.com/owner/repo`

### Step 3: Test Connection
```bash
python ingest_data.py --sources github --days 7
```

**Expected output:**
```
✅ [GITHUB] Saved 100 commits to ingested_logs/github_logs.csv
```

---

## 💬 Slack API Setup (Optional)

### Step 1: Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Configure:
   - **App Name**: `Causal Sentinel`
   - **Workspace**: Select your workspace

### Step 2: Add Bot Permissions

1. In your app settings, go to **"OAuth & Permissions"**
2. Scroll to **"Bot Token Scopes"**
3. Click **"Add an OAuth Scope"**
4. Add these scopes:

   **Public Channels:**
   - ✅ `channels:history` - View messages in public channels
   - ✅ `channels:read` - View basic channel info

   **Private Channels (optional):**
   - ✅ `groups:history` - View messages in private channels
   - ✅ `groups:read` - View private channel info

### Step 3: Install App to Workspace

1. Scroll up to **"OAuth Tokens for Your Workspace"**
2. Click **"Install to Workspace"**
3. Authorize the app
4. Copy the **"Bot User OAuth Token"** (starts with `xoxb-...`)

### Step 4: Invite Bot to Channel

In Slack, type in the channel:
```
/invite @Causal Sentinel
```

Or:
1. Click channel name → **Integrations**
2. Click **Add apps**
3. Select **Causal Sentinel**

### Step 5: Add to .env
```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
TARGET_SLACK_CHANNEL=incidents
```

**Channel name format:**
- Use channel name without `#` (e.g., `incidents` not `#incidents`)
- For private channels, ensure bot is invited first

### Step 6: Test Connection
```bash
python ingest_data.py --sources slack --days 7
```

**Expected output:**
```
✅ [SLACK] Saved 50 messages to ingested_logs/slack_logs.csv
```

---

## 🎫 Jira API Setup (Optional)

### Step 1: Create API Token

1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **"Create API token"**
3. Label it: `causal-sentinel`
4. Click **"Create"**
5. Copy the token (you won't see it again!)

### Step 2: Find Your Jira URL

Your Jira URL looks like:
```
https://your-company.atlassian.net
```

Find it by:
- Looking at your browser when on Jira
- Checking your Jira login email

### Step 3: Find Your Project Key

1. Go to your Jira board
2. Look at any ticket ID (e.g., `PROJ-123`, `KAN-45`)
3. The project key is the prefix (`PROJ`, `KAN`, etc.)

### Step 4: Add to .env
```bash
JIRA_SERVER=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
TARGET_JIRA_PROJECT=PROJ
```

### Step 5: Test Connection
```bash
python ingest_data.py --sources jira --days 7
```

**Expected output:**
```
✅ [JIRA] Saved 30 tickets to ingested_logs/jira_logs.csv
```

---

## 🔐 Security Best Practices

### 1. Never Commit .env File
```bash
# Already in .gitignore, but double-check:
echo ".env" >> .gitignore
git rm --cached .env  # If accidentally committed
```

### 2. Use Environment-Specific Keys
```bash
# Development
.env.dev

# Production
.env.prod

# Load with:
python-dotenv --dotenv .env.prod
```

### 3. Rotate Keys Regularly
- **OpenAI**: Monthly
- **GitHub**: Quarterly
- **Slack**: Yearly
- **Jira**: Yearly

### 4. Use Minimal Permissions
Only grant scopes that are actually needed:
- GitHub: `repo` only (not admin)
- Slack: History + read only (not write)
- Jira: Read only (not edit)

---

## 🧪 Testing Your Setup

### Test All Services
```bash
# Test everything at once
python ingest_data.py --days 7 --sources all

# Expected output:
✅ [GITHUB] Saved 100 commits
✅ [SLACK] Saved 50 messages
✅ [JIRA] Saved 30 tickets
✨ INGESTION COMPLETE
```

### Test Individual Services
```bash
# Test GitHub only
python ingest_data.py --sources github --days 7

# Test Slack only
python ingest_data.py --sources slack --days 7

# Test Jira only
python ingest_data.py --sources jira --days 7
```

---

## ❌ Troubleshooting

### OpenAI Errors

**Error: `Incorrect API key provided`**
```bash
# Solution: Check your key format
echo $OPENAI_API_KEY  # Should start with sk-proj-

# Regenerate key if needed
```

**Error: `Rate limit exceeded`**
```bash
# Solution: You've hit API limits
# Wait 1 minute or upgrade your plan
```

### GitHub Errors

**Error: `Bad credentials`**
```bash
# Solution: Token expired or incorrect
# Generate new token at github.com/settings/tokens
```

**Error: `Not Found`**
```bash
# Solution: Repository doesn't exist or private
# Check TARGET_REPO format: owner/repo
# Ensure token has 'repo' scope for private repos
```

### Slack Errors

**Error: `channel_not_found`**
```bash
# Solution: Bot not invited to channel
# In Slack: /invite @Causal Sentinel
```

**Error: `missing_scope`**
```bash
# Solution: Add required scopes
# Go to api.slack.com/apps → Your App → OAuth & Permissions
# Add: channels:history, channels:read
# Reinstall app to workspace
```

### Jira Errors

**Error: `Unauthorized`**
```bash
# Solution: Check credentials
# Verify JIRA_EMAIL matches your Atlassian account
# Regenerate API token if needed
```

**Error: `Project does not exist`**
```bash
# Solution: Verify project key
# Check ticket IDs in Jira (e.g., PROJ-123)
# Use the prefix (PROJ) as TARGET_JIRA_PROJECT
```

---

## 📊 Cost Calculator

### Monthly Costs (Typical Usage)

| Service | Logs/Month | API Cost | Total |
|---------|-----------|----------|-------|
| **OpenAI** | 1,000 logs | $0.50 | $0.50 |
| **GitHub** | Unlimited | Free | $0 |
| **Slack** | Unlimited | Free | $0 |
| **Jira** | Unlimited | Free | $0 |
| **Total** | - | - | **$0.50** |

### High-Volume Usage (10K logs/month)

| Service | Cost |
|---------|------|
| OpenAI (10K logs) | $5 |
| Data sources | $0 |
| **Total** | **$5/month** |

**Compare to Dynatrace: $4,000-40,000/month** 💸

---

## 🆘 Need Help?

- 🐛 [Report Setup Issues](https://github.com/nitishbelagali/causal-sentinel/issues)
- 💬 [Ask in Discussions](https://github.com/nitishbelagali/causal-sentinel/discussions)
- 📧 Email: nitish.belagali@gmail.com

---

## ✅ Next Steps

Once your APIs are configured:

1. **Ingest data**: `python ingest_data.py --days 30`
2. **Analyze logs**: `python analyze_logs.py`
3. **Launch dashboard**: `streamlit run dashboard.py`

Happy analyzing! 🚀