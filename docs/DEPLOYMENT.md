# 🚀 Deployment Guide

This guide covers deploying Causal Sentinel to various platforms.

---

## Table of Contents
1. [Local Development](#local-development)
2. [Streamlit Cloud (Free)](#streamlit-cloud)
3. [Docker Deployment](#docker-deployment)
4. [AWS EC2](#aws-ec2)
5. [Heroku](#heroku)

---

## Local Development

### Quick Start
```bash
# 1. Setup
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your OpenAI API key

# 3. Run
streamlit run dashboard.py
```

---

## Streamlit Cloud

**Best for:** Quick demos, portfolios, small teams  
**Cost:** Free tier available  
**Time:** 5 minutes

### Steps

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/causal-sentinel.git
git push -u origin main
```

2. **Deploy on Streamlit Cloud**
- Go to [share.streamlit.io](https://share.streamlit.io)
- Click "New app"
- Connect your GitHub repo
- Set main file: `dashboard.py`

3. **Add Secrets**
In Streamlit Cloud dashboard:
- Click "Settings" → "Secrets"
- Add:
```toml
OPENAI_API_KEY = "sk-proj-..."
```

4. **Deploy!**
- Click "Deploy"
- Wait ~2 minutes
- Get public URL: `https://yourusername-causal-sentinel.streamlit.app`

### Limitations
- 1 GB RAM limit (sufficient for most use cases)
- App sleeps after inactivity (wakes up automatically)
- Public by default (can enable password protection)

---

## Docker Deployment

**Best for:** Consistent environments, complex setups  
**Cost:** Depends on hosting  
**Time:** 15 minutes

### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run app
ENTRYPOINT ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  causal-sentinel:
    build: .
    ports:
      - "8501:8501"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### 3. Deploy

```bash
# Build
docker-compose build

# Run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 4. Push to Registry (Optional)

```bash
# Build
docker build -t yourusername/causal-sentinel:latest .

# Push to Docker Hub
docker login
docker push yourusername/causal-sentinel:latest

# Deploy anywhere
docker run -d -p 8501:8501 \
  -e OPENAI_API_KEY=sk-proj-... \
  yourusername/causal-sentinel:latest
```

---

## AWS EC2

**Best for:** Full control, enterprise deployments  
**Cost:** ~$10-50/month (t3.micro to t3.medium)  
**Time:** 30 minutes

### 1. Launch EC2 Instance

```bash
# Instance type: t3.small (2 vCPU, 2 GB RAM)
# AMI: Ubuntu 22.04 LTS
# Security Group: Allow ports 22 (SSH), 8501 (Streamlit)
```

### 2. Connect and Setup

```bash
# SSH into instance
ssh -i your-key.pem ubuntu@your-instance-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Clone repo
git clone https://github.com/yourusername/causal-sentinel.git
cd causal-sentinel

# Setup virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
nano .env
# Add: OPENAI_API_KEY=sk-proj-...
```

### 3. Run with systemd (Production)

Create service file:
```bash
sudo nano /etc/systemd/system/causal-sentinel.service
```

Add:
```ini
[Unit]
Description=Causal Sentinel Dashboard
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/causal-sentinel
Environment="PATH=/home/ubuntu/causal-sentinel/venv/bin"
ExecStart=/home/ubuntu/causal-sentinel/venv/bin/streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable causal-sentinel
sudo systemctl start causal-sentinel
sudo systemctl status causal-sentinel
```

### 4. Setup Nginx (Optional - for HTTPS)

```bash
# Install Nginx
sudo apt install -y nginx

# Configure
sudo nano /etc/nginx/sites-available/causal-sentinel
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/causal-sentinel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup SSL with Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 5. Monitor

```bash
# View logs
journalctl -u causal-sentinel -f

# Check resource usage
htop

# Restart service
sudo systemctl restart causal-sentinel
```

---

## Heroku

**Best for:** Easy deployments, quick prototypes  
**Cost:** ~$7/month (Eco Dyno)  
**Time:** 10 minutes

### 1. Prepare Files

Create `Procfile`:
```
web: streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0
```

Create `runtime.txt`:
```
python-3.11.7
```

Create `.streamlit/config.toml`:
```toml
[server]
headless = true
port = $PORT
enableCORS = false
```

### 2. Deploy

```bash
# Install Heroku CLI
brew install heroku/brew/heroku  # macOS
# or download from heroku.com

# Login
heroku login

# Create app
heroku create causal-sentinel-your-name

# Set environment variables
heroku config:set OPENAI_API_KEY=sk-proj-...

# Deploy
git push heroku main

# Open app
heroku open

# View logs
heroku logs --tail
```

### 3. Scale (if needed)

```bash
# Check current dyno
heroku ps

# Scale up
heroku ps:scale web=1:standard-1x  # 512 MB RAM
```

---

## Environment Variables Reference

All platforms need these environment variables:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | Yes | OpenAI API key | `sk-proj-...` |
| `OPENAI_MODEL` | No | Model to use | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | No | Sampling temperature | `0` |
| `MAX_TOKENS` | No | Max response tokens | `500` |

---

## Performance Optimization

### For Large Datasets

1. **Increase Rolling Window Cache**
```python
# In dashboard.py, add:
@st.cache_data(ttl=3600)
def detect_crashes(df, threshold, window):
    # existing code
```

2. **Use Sampling for Visualization**
```python
# Only plot every Nth point for large datasets
if len(df_metrics) > 1000:
    sample_rate = len(df_metrics) // 1000
    df_plot = df_metrics[::sample_rate]
else:
    df_plot = df_metrics
```

3. **Optimize Log Analysis**
```python
# In analyze_logs.py, batch API calls:
# Instead of 1 call per log, send 10 logs per call
```

---

## Security Best Practices

### 1. API Key Management
```bash
# Never commit .env to Git
echo ".env" >> .gitignore

# Use secrets management
# - AWS Secrets Manager
# - HashiCorp Vault
# - Kubernetes Secrets
```

### 2. Input Validation
Already implemented in dashboard.py:
- ✅ File size limits
- ✅ Column validation
- ✅ Data type checking

### 3. Rate Limiting
Add to dashboard.py:
```python
from streamlit import session_state as state
import time

if 'last_request' not in state:
    state.last_request = 0

now = time.time()
if now - state.last_request < 2:  # 2 seconds between requests
    st.warning("Please wait before analyzing again")
    st.stop()
state.last_request = now
```

---

## Monitoring & Logging

### 1. Application Logs

```python
# Add to dashboard.py
import logging

logging.basicConfig(
    filename='causal_sentinel.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Log key events
logging.info(f"User uploaded file: {metrics_file.name}")
logging.warning(f"Anomaly detected: {crash_date}")
```

### 2. Error Tracking (Sentry)

```bash
pip install sentry-sdk
```

```python
# Add to dashboard.py
import sentry_sdk
sentry_sdk.init(dsn="your-sentry-dsn")
```

### 3. Analytics (Google Analytics)

Add to `.streamlit/config.toml`:
```toml
[browser]
gatherUsageStats = true
```

---

## Troubleshooting Deployment

### Issue: App crashes on startup
```bash
# Check logs
streamlit run dashboard.py --logger.level=debug

# Common causes:
# - Missing dependencies
# - Wrong Python version
# - Port already in use
```

### Issue: Out of memory
```bash
# Reduce data processing
# - Limit file upload size
# - Use sampling
# - Increase server RAM
```

### Issue: Slow performance
```bash
# Enable caching
@st.cache_data
def expensive_function():
    pass

# Use st.spinner() for long operations
with st.spinner("Processing..."):
    result = long_computation()
```

---

## Cost Estimates

| Platform | Setup | Monthly | Pros | Cons |
|----------|-------|---------|------|------|
| Streamlit Cloud | Free | Free | Easy, fast | Limited resources |
| AWS EC2 t3.small | $0 | ~$15 | Full control | Requires setup |
| Heroku Eco | $0 | $7 | Easy deployment | Sleeps after inactivity |
| Docker + DigitalOcean | $0 | $6 | Flexible | Manual setup |

**OpenAI API Costs:**
- Log analysis: ~$0.50 per 1000 logs
- With 10,000 logs/month: ~$5/month

**Total Monthly Cost:**
- Hobby: ~$10-20
- Small business: ~$50-100
- Enterprise: $200+

---

## Next Steps

1. **Choose your platform** based on needs and budget
2. **Follow the relevant guide** above
3. **Test thoroughly** with sample data
4. **Monitor performance** and optimize as needed
5. **Scale up** when ready

---

## Support

Need help? Check:
- [GitHub Issues](https://github.com/yourusername/causal-sentinel/issues)
- [Streamlit Docs](https://docs.streamlit.io)
- [Discord Community](#)

---

**Happy Deploying! 🚀**