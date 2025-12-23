import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dowhy import CausalModel
import warnings
from datetime import timedelta

warnings.filterwarnings("ignore")

# --- PAGE CONFIG ---
st.set_page_config(page_title="Causal Sentinel v2.0", page_icon="🛡️", layout="wide")
st.title("🛡️ Causal Sentinel: Enterprise Commander v2.0")
# --- DEBUGGING: PASTE THIS UNDER st.title ---
if st.checkbox("Show Raw Data for Debugging"):
    st.write("Current Session State:", st.session_state)

# --- CONFIGURATION PANEL ---
st.sidebar.header("⚙️ Detection Parameters")
SENSITIVITY = st.sidebar.slider(
    "Anomaly Sensitivity (Z-Score)", 
    min_value=1.5, 
    max_value=3.0, 
    value=2.0, 
    step=0.1,
    help="Lower = More sensitive (more alerts). Higher = Less sensitive."
)
LOOKBACK_DAYS = st.sidebar.slider(
    "Event Lookback Window (Days)", 
    min_value=1, 
    max_value=7, 
    value=2,
    help="How many days before/after crash to search for suspect events"
)
ROLLING_WINDOW = st.sidebar.slider(
    "Rolling Average Window (Days)", 
    min_value=3, 
    max_value=14, 
    value=7,
    help="Window size for statistical baseline calculation"
)

# --- HELPER: GENERATE METRICS FROM LOGS ---
def generate_synthetic_metrics_from_logs(logs_df, timestamp_col='timestamp', risk_col='ai_risk'):
    """
    Scans the uploaded logs, finds the date range and 'High Risk' dates,
    and generates a matching business metrics file with crashes.
    """
    # 1. Ensure datetime
    logs_df[timestamp_col] = pd.to_datetime(logs_df[timestamp_col], errors='coerce')
    logs_df = logs_df.dropna(subset=[timestamp_col])
    
    # 2. Determine Date Range (add buffer days)
    start_date = logs_df[timestamp_col].min() - timedelta(days=7)
    end_date = logs_df[timestamp_col].max() + timedelta(days=7)
    
    # 3. Find Crash Dates (High Risk Events)
    high_risk_events = logs_df[logs_df[risk_col].str.upper() == 'HIGH']
    crash_dates = high_risk_events[timestamp_col].dt.date.unique()
    
    # 4. Generate Revenue Data
    dates = pd.date_range(start_date, end_date, freq='D')
    metrics = []
    
    active_crash_countdown = 0
    
    for date in dates:
        base_revenue = 50000
        noise = np.random.normal(0, 2000)
        
        # Check if this date has a HIGH risk event
        if date.date() in crash_dates:
            active_crash_countdown = 3  # Crash effect lasts 3 days
        
        revenue = base_revenue + noise
        
        # Apply crash effect
        if active_crash_countdown > 0:
            crash_severity = 0.4 + (0.1 * active_crash_countdown)  # 50-60% drop
            revenue = revenue * crash_severity
            active_crash_countdown -= 1
        
        metrics.append({
            "date": date,
            "daily_revenue": int(revenue),
            "latency_ms": int(np.random.normal(150, 30) if active_crash_countdown > 0 else np.random.normal(100, 10))
        })
    
    return pd.DataFrame(metrics)

def safe_datetime_convert(series, col_name):
    """
    Robust converter that handles ISO8601, UTC offsets, and mixed formats.
    """
    try:
        # 1. Force to string first (fixes "mixed type" errors)
        series = series.astype(str)
        
        # 2. Clean common dirt (spaces, quotes)
        series = series.str.strip().str.replace('"', '').str.replace("'", "")
        
        # 3. TRICK: Remove the '+00:00' manually if Pandas is choking on it
        # This turns "2025-12-22 20:25:44+00:00" into "2025-12-22 20:25:44"
        series = series.str.replace(r'\+00:00$', '', regex=True)
        
        # 4. Convert with UTC=True, then strip timezone
        converted = pd.to_datetime(series, errors='coerce', utc=True)
        
        # 5. Remove timezone info (make it "naive") so it compares with everything
        converted = converted.dt.tz_localize(None)
        
        # Check for failure
        null_count = converted.isna().sum()
        if null_count > 0:
            # Show the first failed value to help debug
            first_fail = series[converted.isna()].iloc[0]
            st.warning(f"⚠️ {null_count} dates failed in '{col_name}'. Sample failure: '{first_fail}'")
        
        return converted

    except Exception as e:
        st.error(f"Critical error converting '{col_name}': {e}")
        return None

# --- SIDEBAR: INGESTION LAYER ---
st.sidebar.header("📥 1. Ingest Data")

# A. METRICS UPLOAD (Optional)
metrics_file = st.sidebar.file_uploader(
    "Upload Business Metrics (Optional)", 
    type=["csv", "xlsx"],
    help="If not provided, we can generate synthetic data from your logs"
)

# B. MULTI-FILE LOG UPLOAD
log_files = st.sidebar.file_uploader(
    "Upload Analyzed Logs (Jira/Slack/GitHub/Jenkins)", 
    type=["csv", "xlsx"], 
    accept_multiple_files=True,
    help="You can upload multiple log files from different sources"
)

# --- MAIN LOGIC ---
if log_files:
    # === STAGE 1: MERGE ALL LOG FILES ===
    all_logs = []
    
    for file in log_files:
        try:
            # Read file
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Tag source
            df['source_file'] = file.name
            all_logs.append(df)
            
        except Exception as e:
            st.error(f"❌ Error reading {file.name}: {e}")
            continue
    
    if all_logs:
        df_master_logs = pd.concat(all_logs, ignore_index=True)
        st.sidebar.success(f"✅ Merged {len(log_files)} file(s) → {len(df_master_logs)} total events")
        
        # === STAGE 2: LOG SCHEMA MAPPING ===
        with st.sidebar.expander("🗺️ 2. Map Log Schema", expanded=False):
            log_cols = df_master_logs.columns.tolist()
            
            # Smart defaults
            default_ts = next((i for i, col in enumerate(log_cols) if 'time' in col.lower() or 'date' in col.lower()), 0)
            default_risk = next((i for i, col in enumerate(log_cols) if 'risk' in col.lower()), len(log_cols)-2 if len(log_cols) > 2 else 1)
            default_msg = next((i for i, col in enumerate(log_cols) if 'message' in col.lower() or 'msg' in col.lower()), 1)
            
            ts_col = st.selectbox("Timestamp Column", log_cols, index=default_ts)
            risk_col = st.selectbox("Risk Column", log_cols, index=default_risk)
            msg_col = st.selectbox("Message Column", log_cols, index=default_msg)
        
        # Standardize
        df_master_logs = df_master_logs[[ts_col, risk_col, msg_col, 'source_file']].copy()
        df_master_logs.columns = ['timestamp', 'ai_risk', 'message', 'source_file']
        
        # Convert timestamps
        df_master_logs['timestamp'] = safe_datetime_convert(df_master_logs['timestamp'], ts_col)
        df_master_logs = df_master_logs.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
        
        # === STAGE 3: METRICS HANDLING ===
        df_metrics = None
        
        if metrics_file:
            # User provided metrics
            try:
                if metrics_file.name.endswith('.csv'):
                    raw_metrics = pd.read_csv(metrics_file)
                else:
                    raw_metrics = pd.read_excel(metrics_file)
                
                st.sidebar.success("✅ Custom Metrics Loaded")
                
                # Map metrics schema
                with st.sidebar.expander("🗺️ 3. Map Metrics Schema", expanded=False):
                    m_cols = raw_metrics.columns.tolist()
                    
                    default_date = next((i for i, col in enumerate(m_cols) if 'date' in col.lower() or 'time' in col.lower()), 0)
                    default_revenue = next((i for i, col in enumerate(m_cols) if 'revenue' in col.lower() or 'sales' in col.lower() or 'value' in col.lower()), 1)
                    
                    d_col = st.selectbox("Date Column", m_cols, index=default_date)
                    r_col = st.selectbox("Revenue/KPI Column", m_cols, index=default_revenue)
                    
                    # Optional confounder
                    has_confounder = st.checkbox("I have a confounder column")
                    user_confounder_col = None
                    if has_confounder:
                        remaining_cols = [col for col in m_cols if col not in [d_col, r_col]]
                        if remaining_cols:
                            user_confounder_col = st.selectbox("Confounder Column", remaining_cols)
                
                # Standardize
                df_metrics = raw_metrics[[d_col, r_col]].copy()
                df_metrics.columns = ['date', 'daily_revenue']
                
                # Add confounder
                if has_confounder and user_confounder_col:
                    df_metrics['confounder'] = raw_metrics[user_confounder_col].values
                else:
                    revenue_series = df_metrics['daily_revenue'].squeeze()
                    rolling_std = revenue_series.rolling(3, min_periods=1).std()
                    df_metrics['confounder'] = rolling_std.fillna(0).values
                
            except Exception as e:
                st.error(f"❌ Error processing metrics file: {e}")
                df_metrics = None
        
        else:
            # === AUTO-GENERATE OPTION ===
            st.info("💡 **No Business Metrics Uploaded**")
            st.markdown("""
            Since you've uploaded log files, I can generate matching revenue data for you!
            
            **How it works:**
            1. Scans your logs for HIGH risk events
            2. Creates a timeline covering your log dates (±7 days)
            3. Simulates revenue crashes on HIGH risk dates
            """)
            
            if st.button("⚡ Generate Synthetic Metrics from Logs", type="primary"):
                with st.spinner("Analyzing logs and generating metrics..."):
                    try:
                        generated_metrics = generate_synthetic_metrics_from_logs(df_master_logs)
                        st.session_state['generated_metrics'] = generated_metrics
                        st.success(f"✅ Generated {len(generated_metrics)} days of revenue data!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"❌ Generation failed: {e}")
            
            # Use generated metrics if they exist
            if 'generated_metrics' in st.session_state:
                df_metrics = st.session_state['generated_metrics']
                
                # Preview
                with st.expander("👁️ Preview Generated Data"):
                    st.dataframe(df_metrics.head(10))
                
                # Download option
                csv = df_metrics.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Generated Metrics", 
                    csv, 
                    "generated_metrics.csv", 
                    "text/csv",
                    help="Save this file to use in future analyses"
                )
        
        # === STAGE 4: ANALYSIS (IF BOTH ARE READY) ===
        if df_metrics is not None and not df_master_logs.empty:
            
            # Convert and clean metrics dates
            df_metrics['date'] = safe_datetime_convert(df_metrics['date'], 'date')
            df_metrics = df_metrics.dropna(subset=['date']).sort_values('date').reset_index(drop=True)
            
            # Validation
            if len(df_metrics) < ROLLING_WINDOW:
                st.error(f"❌ Metrics has only {len(df_metrics)} rows. Need at least {ROLLING_WINDOW} for analysis.")
                st.stop()
            
            if not pd.api.types.is_numeric_dtype(df_metrics['daily_revenue']):
                st.error("❌ Revenue column must contain numeric values")
                st.stop()
            
            # === ANOMALY DETECTION ===
            st.divider()
            st.subheader("🔍 Analysis Results")
            
            with st.spinner("Detecting anomalies..."):
                df_metrics['rolling_mean'] = df_metrics['daily_revenue'].rolling(window=ROLLING_WINDOW, min_periods=ROLLING_WINDOW//2).mean()
                df_metrics['rolling_std'] = df_metrics['daily_revenue'].rolling(window=ROLLING_WINDOW, min_periods=ROLLING_WINDOW//2).std()
                df_metrics['rolling_std'] = df_metrics['rolling_std'].replace(0, df_metrics['daily_revenue'].std())
                df_metrics['z_score'] = (df_metrics['daily_revenue'] - df_metrics['rolling_mean']) / df_metrics['rolling_std']
                
                crashes = df_metrics[df_metrics['z_score'] < -SENSITIVITY].copy()
            
            # === VISUALIZATION ===
            fig = go.Figure()
            
            # Main trend
            fig.add_trace(go.Scatter(
                x=df_metrics['date'], 
                y=df_metrics['daily_revenue'],
                mode='lines',
                name='Revenue',
                line=dict(color='#1f77b4', width=2)
            ))
            
            # Anomalies
            if not crashes.empty:
                fig.add_trace(go.Scatter(
                    x=crashes['date'],
                    y=crashes['daily_revenue'],
                    mode='markers',
                    name='Anomalies',
                    marker=dict(color='red', size=12, symbol='x')
                ))
            
            fig.update_layout(
                title="Revenue Trend with Anomaly Detection",
                xaxis_title="Date",
                yaxis_title="Daily Revenue",
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # === ROOT CAUSE ANALYSIS ===
            if crashes.empty:
                st.success("✅ **System Healthy** - No anomalies detected")
                
                with st.expander("📊 Statistical Summary"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Average Revenue", f"${df_metrics['daily_revenue'].mean():,.2f}")
                    col2.metric("Std Dev", f"${df_metrics['daily_revenue'].std():,.2f}")
                    col3.metric("Data Points", len(df_metrics))
            
            else:
                st.error(f"🚨 **Detected {len(crashes)} Anomaly(ies)**")
                
                # Show all crashes
                with st.expander("📋 All Detected Anomalies"):
                    display = crashes[['date', 'daily_revenue', 'z_score']].copy()
                    display['date'] = display['date'].dt.strftime('%Y-%m-%d')
                    display['z_score'] = display['z_score'].round(2)
                    st.dataframe(display, use_container_width=True)
                
                # Focus on worst crash
                worst_crash = crashes.sort_values('z_score').iloc[0]
                crash_date = worst_crash['date']
                
                st.warning(f"**Most Severe:** {crash_date.strftime('%Y-%m-%d')} (Z={worst_crash['z_score']:.2f})")
                
                # === EVENT LINKING (MULTI-SOURCE) ===
                search_start = crash_date - timedelta(days=LOOKBACK_DAYS)
                search_end = crash_date + timedelta(days=LOOKBACK_DAYS)
                
                suspects = df_master_logs[
                    (df_master_logs['timestamp'] >= search_start) & 
                    (df_master_logs['timestamp'] <= search_end) & 
                    (df_master_logs['ai_risk'].str.upper() == 'HIGH')
                ]
                
                if suspects.empty:
                    st.warning(f"⚠️ No HIGH risk events in {LOOKBACK_DAYS}-day window")
                    
                    # Show what was there
                    all_events = df_master_logs[
                        (df_master_logs['timestamp'] >= search_start) & 
                        (df_master_logs['timestamp'] <= search_end)
                    ]
                    
                    if not all_events.empty:
                        with st.expander("🔍 All Events in Window"):
                            st.dataframe(all_events[['timestamp', 'source_file', 'ai_risk', 'message']])
                
                else:
                    st.success(f"✅ **Root Causes Identified:** {len(suspects)} suspect(s) from {suspects['source_file'].nunique()} source(s)")
                    
                    # Group by source file
                    for source in suspects['source_file'].unique():
                        source_events = suspects[suspects['source_file'] == source]
                        
                        with st.expander(f"🔴 {source} ({len(source_events)} event(s))", expanded=True):
                            for idx, row in source_events.iterrows():
                                st.markdown(f"""
                                **Timestamp:** {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}  
                                **Message:** {row['message']}  
                                **Risk:** {row['ai_risk']}
                                """)
                                st.divider()
                    
                    # === CAUSAL INFERENCE ===
                    with st.expander("🔬 Causal Impact Analysis"):
                        try:
                            df_metrics['is_broken'] = (df_metrics['date'] >= crash_date).astype(int)
                            
                            if df_metrics['is_broken'].sum() > 0 and df_metrics['is_broken'].sum() < len(df_metrics):
                                model = CausalModel(
                                    data=df_metrics,
                                    treatment='is_broken',
                                    outcome='daily_revenue',
                                    common_causes=['confounder']
                                )
                                
                                estimand = model.identify_effect()
                                estimate = model.estimate_effect(estimand, method_name="backdoor.linear_regression")
                                    
                                    # --- FIX START ---
                                    # Check if the model actually returned a number
                                if estimate.value is None:
                                    st.warning("⚠️ The Causal Model could not calculate a numerical impact (Result was None).")
                                    st.info("This often happens if there is 'Perfect Collinearity' (e.g., revenue is 0 every time the bug happens) or not enough data points.")
                                
                                else:
                                    impact = abs(estimate.value)
                                    days_affected = len(df_metrics[df_metrics['is_broken'] == 1])
                                        
                                    # Metrics
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric("Daily Impact", f"${impact:,.2f}")
                                    col2.metric("Days Affected", days_affected)
                                    col3.metric("Total Impact", f"${impact * days_affected:,.2f}")
                                        
                                    st.code(f"""
Causal Estimand: {estimand}
Method: Backdoor Linear Regression
Coefficient: {estimate.value:.2f}
                                        """)
                            else:
                                st.warning("⚠️ Insufficient data variation for causal analysis")
                                
                        except Exception as e:
                            st.error(f"⚠️ Causal analysis failed: {e}")

else:
    # === LANDING PAGE ===
    st.info("👋 **Welcome to Causal Sentinel v2.0**")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🎯 What's New in v2.0
        
        **Multi-Source Log Analysis:**
        - Upload Jira tickets, Slack messages, GitHub commits, Jenkins logs **all at once**
        - System automatically merges and analyzes them together
        - Track root causes across your entire DevOps pipeline
        
        **Auto-Generate Metrics:**
        - Don't have revenue data? No problem!
        - Upload logs → Click "Generate" → Get matching metrics
        - Perfect for testing and demos
        
        **Intelligent Linking:**
        - Detects crashes in your business metrics
        - Links to HIGH risk events from ANY source
        - Shows which system/tool had the smoking gun
        
        ### 🚀 Quick Start
        
        1. **Upload Logs** (Jira/Slack/GitHub/Jenkins) - multiple files OK!
        2. **Upload Metrics** OR click "Generate Synthetic Metrics"
        3. **Map Columns** (if needed)
        4. **View Analysis** - crashes linked to root causes
        """)
    
    with col2:
        st.markdown("""
        ### 📊 Demo Mode
        
        Try it with sample data:
        """)
        
        if st.button("🎲 Generate Demo Files"):
            # Sample metrics
            dates = pd.date_range('2024-12-01', '2024-12-30', freq='D')
            revenue = [50000 + i*100 + np.random.normal(0, 2000) for i in range(len(dates))]
            revenue[14] = 25000  # Crash on Dec 15
            revenue[15] = 30000
            
            demo_metrics = pd.DataFrame({
                'date': dates,
                'daily_revenue': revenue,
                'latency_ms': [100 + (i % 10) * 5 for i in range(len(dates))]
            })
            
            # Sample logs
            demo_logs = pd.DataFrame({
                'timestamp': ['2024-12-14 22:00:00', '2024-12-15 09:00:00', '2024-12-16 10:00:00'],
                'ai_risk': ['LOW', 'HIGH', 'LOW'],
                'message': [
                    'Updated README.md',
                    'Deployed payment service v2.0 with synchronous processing',
                    'Fixed typo in footer'
                ],
                'ai_component': ['documentation', 'payment_api', 'frontend']
            })
            
            st.download_button(
                "📥 Download Demo Metrics",
                demo_metrics.to_csv(index=False),
                "demo_metrics.csv",
                "text/csv"
            )
            
            st.download_button(
                "📥 Download Demo Logs",
                demo_logs.to_csv(index=False),
                "demo_logs.csv",
                "text/csv"
            )