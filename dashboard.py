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
    value=3,
    help="How many days before/after crash to search for suspect events"
)
ROLLING_WINDOW = st.sidebar.slider(
    "Rolling Average Window (Days)", 
    min_value=3, 
    max_value=21, 
    value=7,
    help="Window size for statistical baseline calculation"
)

# --- HELPER: ROBUST SYNTHETIC GENERATOR ---
def generate_synthetic_metrics_from_logs(logs_df, timestamp_col='timestamp', risk_col='ai_risk'):
    """
    Generates a revenue dataset based on the uploaded logs with 60-day history.
    """
    if logs_df is None or logs_df.empty:
        return None

    try:
        # Ensure timestamp is datetime
        logs_df = logs_df.copy()
        logs_df[timestamp_col] = pd.to_datetime(logs_df[timestamp_col], errors='coerce', utc=True).dt.tz_localize(None)
        logs_df = logs_df.dropna(subset=[timestamp_col])
        
        if logs_df.empty:
            st.error("All timestamps in logs are invalid")
            return None
        
        last_log_date = logs_df[timestamp_col].max()
        first_log_date = logs_df[timestamp_col].min()
        
        # Create 60 days of history before first log
        start_date = first_log_date - timedelta(days=60)
        end_date = last_log_date + timedelta(days=7)
        
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Identify crash dates (HIGH risk events)
        crash_dates = set()
        for _, row in logs_df.iterrows():
            risk_val = str(row.get(risk_col, 'LOW')).strip().upper()
            if risk_val == 'HIGH' and pd.notnull(row[timestamp_col]):
                crash_dates.add(row[timestamp_col].date())
        
        # Generate revenue data
        base_revenue = 50000
        revenues = []
        current_crash_effect = 0
        
        for d in dates:
            daily_noise = np.random.normal(0, 2000)
            
            # Trigger crash
            if d.date() in crash_dates:
                current_crash_effect = -30000  # 60% drop
            
            # Gradual recovery
            if current_crash_effect < 0:
                current_crash_effect += 5000  # Recovers over ~6 days
                if current_crash_effect > 0:
                    current_crash_effect = 0
            
            final_revenue = base_revenue + daily_noise + current_crash_effect
            revenues.append(max(1000, final_revenue))  # Minimum $1k
        
        return pd.DataFrame({
            "date": dates,
            "daily_revenue": revenues
        })
    
    except Exception as e:
        st.error(f"Error generating synthetic metrics: {e}")
        return None


def safe_datetime_convert(series, col_name):
    """Robust datetime converter with error handling"""
    try:
        # Clean string data
        series = series.astype(str).str.strip()
        series = series.str.replace('"', '').str.replace("'", "")
        series = series.str.replace(r'\+00:00$', '', regex=True)
        
        # Convert to datetime
        converted = pd.to_datetime(series, errors='coerce', utc=True).dt.tz_localize(None)
        
        null_count = converted.isna().sum()
        if null_count > 0:
            st.warning(f"⚠️ {null_count} invalid dates in '{col_name}' were ignored")
        
        return converted
    
    except Exception as e:
        st.error(f"❌ Failed to convert '{col_name}': {e}")
        return None


# --- SIDEBAR: INGESTION LAYER ---
st.sidebar.header("📥 1. Ingest Data")

# A. METRICS UPLOAD (Optional)
metrics_file = st.sidebar.file_uploader(
    "Upload Business Metrics (Optional)", 
    type=["csv", "xlsx"],
    help="CSV/Excel with date and revenue columns"
)

# B. MULTI-FILE LOG UPLOAD
log_files = st.sidebar.file_uploader(
    "Upload Analyzed Logs (Jira/Slack/GitHub)", 
    type=["csv", "xlsx"], 
    accept_multiple_files=True,
    help="Upload analyzed_logs.csv or multiple source files"
)

# --- MAIN LOGIC ---
if log_files:
    # === STAGE 1: MERGE ALL LOG FILES ===
    all_logs = []
    
    for file in log_files:
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Tag source if missing
            if 'source_file' not in df.columns:
                df['source_file'] = file.name
            
            all_logs.append(df)
            
        except Exception as e:
            st.error(f"❌ Error reading {file.name}: {e}")
            continue
    
    if not all_logs:
        st.error("❌ No valid log files loaded")
        st.stop()
    
    df_master_logs = pd.concat(all_logs, ignore_index=True)
    st.sidebar.success(f"✅ Loaded {len(df_master_logs)} events from {len(log_files)} file(s)")
    
    # === STAGE 2: SCHEMA DETECTION & MAPPING ===
    log_cols = df_master_logs.columns.tolist()
    
    # Check for standard schema
    has_standard_schema = {'timestamp', 'ai_risk', 'message'}.issubset(df_master_logs.columns)
    
    if has_standard_schema:
        st.sidebar.info("✨ Standard schema detected")
        ts_col, risk_col, msg_col = 'timestamp', 'ai_risk', 'message'
    else:
        with st.sidebar.expander("🗺️ 2. Map Log Schema", expanded=True):
            st.warning("⚠️ Standard columns not found. Please map manually.")
            
            # Smart defaults
            default_ts = next((i for i, c in enumerate(log_cols) if 'time' in c.lower() or 'date' in c.lower()), 0)
            default_risk = next((i for i, c in enumerate(log_cols) if 'risk' in c.lower()), min(len(log_cols)-1, 2))
            default_msg = next((i for i, c in enumerate(log_cols) if 'message' in c.lower() or 'msg' in c.lower()), 1)
            
            ts_col = st.selectbox("Timestamp Column", log_cols, index=default_ts)
            risk_col = st.selectbox("Risk Level Column", log_cols, index=default_risk)
            msg_col = st.selectbox("Message Column", log_cols, index=default_msg)
    
    # Standardize column names
    df_master_logs = df_master_logs.rename(columns={
        ts_col: 'timestamp', 
        risk_col: 'ai_risk', 
        msg_col: 'message'
    })
    
    # Convert timestamps
    df_master_logs['timestamp'] = safe_datetime_convert(df_master_logs['timestamp'], 'timestamp')
    df_master_logs = df_master_logs.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    
    if df_master_logs.empty:
        st.error("❌ No valid timestamps found in logs")
        st.stop()
    
    # === STAGE 3: METRICS HANDLING ===
    df_metrics = None
    
    if metrics_file:
        # User provided custom metrics
        try:
            if metrics_file.name.endswith('.csv'):
                raw_metrics = pd.read_csv(metrics_file)
            else:
                raw_metrics = pd.read_excel(metrics_file)
            
            st.sidebar.success("✅ Custom metrics loaded")
            
            # Map metrics schema
            with st.sidebar.expander("🗺️ 3. Map Metrics Schema", expanded=False):
                m_cols = raw_metrics.columns.tolist()
                
                default_date = next((i for i, c in enumerate(m_cols) if 'date' in c.lower() or 'time' in c.lower()), 0)
                default_rev = next((i for i, c in enumerate(m_cols) if 'revenue' in c.lower() or 'sales' in c.lower() or 'value' in c.lower()), 1)
                
                d_col = st.selectbox("Date Column", m_cols, index=default_date)
                r_col = st.selectbox("Revenue/KPI Column", m_cols, index=default_rev)
            
            df_metrics = raw_metrics[[d_col, r_col]].copy()
            df_metrics.columns = ['date', 'daily_revenue']
            
        except Exception as e:
            st.error(f"❌ Error processing metrics: {e}")
            df_metrics = None
    
    else:
        # === AUTO-GENERATE METRICS ===
        st.info("💡 **No metrics uploaded** - Generating synthetic data from logs...")
        
        with st.spinner("Analyzing logs and generating revenue data..."):
            generated_metrics = generate_synthetic_metrics_from_logs(df_master_logs)
            
            if generated_metrics is not None:
                st.session_state['generated_metrics'] = generated_metrics
                st.success(f"✅ Generated {len(generated_metrics)} days of data (60-day history)")
            else:
                st.error("❌ Failed to generate metrics")
        
        if 'generated_metrics' in st.session_state:
            df_metrics = st.session_state['generated_metrics']
            
            # Preview option
            with st.expander("👁️ Preview Generated Data"):
                st.dataframe(df_metrics.head(10))
            
            # Download option
            csv = df_metrics.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Generated Metrics",
                csv,
                "generated_metrics.csv",
                "text/csv"
            )
    
    # === STAGE 4: ANALYSIS ===
    if df_metrics is not None and not df_master_logs.empty:
        
        # Convert dates
        df_metrics['date'] = safe_datetime_convert(df_metrics['date'], 'date')
        df_metrics = df_metrics.dropna(subset=['date']).sort_values('date').reset_index(drop=True)
        
        # Validate
        if len(df_metrics) < ROLLING_WINDOW:
            st.error(f"❌ Need at least {ROLLING_WINDOW} rows for analysis. Got {len(df_metrics)}")
            st.stop()
        
        if not pd.api.types.is_numeric_dtype(df_metrics['daily_revenue']):
            st.error("❌ Revenue column must be numeric")
            st.stop()
        
        # Add confounder
        revenue_series = df_metrics['daily_revenue'].squeeze()
        rolling_std = revenue_series.rolling(3, min_periods=1).std()
        df_metrics['confounder'] = rolling_std.fillna(df_metrics['daily_revenue'].std()).values
        
        # === ANOMALY DETECTION ===
        st.divider()
        st.subheader("🔍 Analysis Results")
        
        with st.spinner("Detecting anomalies..."):
            # Calculate rolling statistics
            df_metrics['rolling_mean'] = df_metrics['daily_revenue'].rolling(
                window=ROLLING_WINDOW, 
                min_periods=max(1, ROLLING_WINDOW//2)
            ).mean()
            
            df_metrics['rolling_std'] = df_metrics['daily_revenue'].rolling(
                window=ROLLING_WINDOW, 
                min_periods=max(1, ROLLING_WINDOW//2)
            ).std()
            
            # Prevent division by zero
            df_metrics['rolling_std'] = df_metrics['rolling_std'].replace(0, df_metrics['daily_revenue'].std())
            df_metrics['rolling_std'] = df_metrics['rolling_std'].fillna(1)
            
            # Calculate Z-score
            df_metrics['z_score'] = (df_metrics['daily_revenue'] - df_metrics['rolling_mean']) / df_metrics['rolling_std']
            
            # Detect crashes
            crashes = df_metrics[df_metrics['z_score'] < -SENSITIVITY].copy()
        
        # === VISUALIZATION ===
        fig = go.Figure()
        
        # Revenue line
        fig.add_trace(go.Scatter(
            x=df_metrics['date'], 
            y=df_metrics['daily_revenue'],
            mode='lines',
            name='Revenue',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='%{x}<br>$%{y:,.0f}<extra></extra>'
        ))
        
        # Anomalies
        if not crashes.empty:
            fig.add_trace(go.Scatter(
                x=crashes['date'],
                y=crashes['daily_revenue'],
                mode='markers',
                name='Anomalies',
                marker=dict(color='red', size=12, symbol='x'),
                hovertemplate='Crash: %{x}<br>$%{y:,.0f}<extra></extra>'
            ))
        
        fig.update_layout(
            title="Revenue Trend with Anomaly Detection",
            xaxis_title="Date",
            yaxis_title="Daily Revenue ($)",
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # === ROOT CAUSE ANALYSIS ===
        if crashes.empty:
            st.success("✅ **System Healthy** - No anomalies detected")
            
            with st.expander("📊 Statistical Summary"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Average Revenue", f"${df_metrics['daily_revenue'].mean():,.2f}")
                col2.metric("Std Deviation", f"${df_metrics['daily_revenue'].std():,.2f}")
                col3.metric("Data Points", len(df_metrics))
        
        else:
            st.error(f"🚨 **Detected {len(crashes)} Anomaly(ies)**")
            
            # Show all crashes
            with st.expander("📋 All Detected Anomalies"):
                display = crashes[['date', 'daily_revenue', 'z_score']].copy()
                display['date'] = display['date'].dt.strftime('%Y-%m-%d')
                display['daily_revenue'] = display['daily_revenue'].apply(lambda x: f"${x:,.2f}")
                display['z_score'] = display['z_score'].round(2)
                st.dataframe(display, use_container_width=True)
            
            # Focus on worst crash
            worst_crash = crashes.sort_values('z_score').iloc[0]
            crash_date = worst_crash['date']
            
            st.warning(f"**Primary Incident:** {crash_date.strftime('%Y-%m-%d')} (Z-Score: {worst_crash['z_score']:.2f})")
            
            # === EVENT LINKING ===
            search_start = crash_date - timedelta(days=LOOKBACK_DAYS)
            search_end = crash_date + timedelta(days=1)
            
            suspects = df_master_logs[
                (df_master_logs['timestamp'] >= search_start) & 
                (df_master_logs['timestamp'] <= search_end) & 
                (df_master_logs['ai_risk'].str.upper() == 'HIGH')
            ]
            
            if suspects.empty:
                st.warning(f"⚠️ No HIGH risk events found between {search_start.date()} and {search_end.date()}")
                
                # Show what was in window
                all_events = df_master_logs[
                    (df_master_logs['timestamp'] >= search_start) & 
                    (df_master_logs['timestamp'] <= search_end)
                ]
                
                if not all_events.empty:
                    with st.expander("🔍 All Events in Window"):
                        st.dataframe(all_events[['timestamp', 'source_file', 'ai_risk', 'message']])
            
            else:
                st.success(f"✅ **Root Causes Identified:** {len(suspects)} suspect event(s)")
                
                # Group by source
                for source in suspects['source_file'].unique():
                    source_events = suspects[suspects['source_file'] == source]
                    
                    with st.expander(f"🔴 {source} ({len(source_events)} event(s))", expanded=True):
                        for idx, row in source_events.iterrows():
                            st.markdown(f"""
                            **Time:** {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}  
                            **Message:** {row['message']}  
                            **AI Reasoning:** {row.get('ai_reasoning', 'N/A')}  
                            **Component:** {row.get('ai_component', 'N/A')}
                            """)
                            st.divider()
                
                # === CAUSAL INFERENCE (UPDATED BUSINESS-GRADE VERSION) ===
                st.divider()
                st.subheader("🔬 Causal Impact Analysis")
                
                try:
                    df_metrics['is_broken'] = (df_metrics['date'] >= crash_date).astype(int)
                    
                    # Validate variation
                    if df_metrics['is_broken'].sum() == 0 or df_metrics['is_broken'].sum() == len(df_metrics):
                        st.warning("⚠️ Insufficient variation for causal analysis")
                    elif len(df_metrics) < 10:
                        st.warning("⚠️ Not enough data points for reliable causal inference")
                    else:
                        model = CausalModel(
                            data=df_metrics,
                            treatment='is_broken',
                            outcome='daily_revenue',
                            common_causes=['confounder']
                        )
                        
                        estimand = model.identify_effect()
                        estimate = model.estimate_effect(estimand, method_name="backdoor.linear_regression")
                        
                        if estimate.value is not None:
                            impact = abs(estimate.value)
                            days_affected = len(df_metrics[df_metrics['is_broken'] == 1])
                            total_loss = impact * days_affected
                            
                            # 1. TOP LEVEL METRICS (With Help Tooltips)
                            col1, col2, col3 = st.columns(3)
                            col1.metric(
                                "Daily Financial Impact", 
                                f"-${impact:,.2f}", 
                                delta="Lost per day", 
                                delta_color="inverse",
                                help="The average amount of revenue lost for every single day the system was in a broken state, isolated from natural market fluctuations."
                            )
                            col2.metric(
                                "Duration of Incident", 
                                f"{days_affected} Days",
                                help="The number of days between the first 'High Risk' event and the system recovery."
                            )
                            col3.metric(
                                "Total Estimated Loss", 
                                f"-${total_loss:,.2f}", 
                                delta="Total Damage", 
                                delta_color="inverse",
                                help="Daily Impact × Days Affected. This is the total estimated cost of this specific incident."
                            )

                            st.divider()

                            # 2. EXPLANATION (Verbal & Mathematical)
                            st.markdown("### 🧠 How did the AI calculate this?")
                            
                            tab1, tab2 = st.tabs(["📖 Verbal Explanation", "➗ Mathematical Proof"])
                            
                            with tab1:
                                st.markdown(f"""
                                The system performed a **Counterfactual Analysis**. It asked the question: 
                                *"What would our revenue have been if this bug never happened?"*
                                
                                1. **The Method:** We used a statistical technique called **Backdoor Linear Regression**.
                                2. **The Adjustment:** We mathematically removed the "Noise" (Random market volatility, modeled as `{estimand.get_backdoor_variables()[0] if estimand.get_backdoor_variables() else 'Standard Deviation'}`).
                                3. **The Result:** We found that the presence of the bug causes a **negative shift** of **${impact:,.2f}** in daily revenue, regardless of other factors.
                                """)
                                
                                st.info(f"**Conclusion:** If we had prevented the event on {crash_date.strftime('%Y-%m-%d')}, we would have saved **${total_loss:,.2f}**.")

                            with tab2:
                                st.markdown("The model calculates the **Average Treatment Effect (ATE)** using the following equation:")
                                
                                st.latex(r'''
                                \text{Impact} = E[\text{Revenue} \mid \text{do}(\text{Bug Present})] - E[\text{Revenue} \mid \text{do}(\text{Bug Absent})]
                                ''')
                                
                                st.markdown(f"""
                                **Where:**
                                * $E[...]$ is the Expected Value (statistical average).
                                * $do(...)$ represents the causal intervention (forcing the bug to exist or not).
                                * **Coefficient ($\psi$):** `{estimate.value:.2f}` (This is the slope of the regression line).
                                """)
                                
                                st.markdown("---")
                                st.markdown("**Raw DoWhy Output (Debug):**")
                                st.code(f"{estimand}", language="text")

                        else:
                            st.warning("⚠️ Causal model could not calculate specific dollar impact")
                
                except Exception as e:
                    st.error(f"⚠️ Causal analysis error: {str(e)[:200]}")

else:
    # === LANDING PAGE ===
    st.info("👋 **Welcome to Causal Sentinel v2.0**")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🎯 How It Works
        
        **1. Upload Logs** (Jira/Slack/GitHub)
        - Drag & drop `analyzed_logs.csv`
        - Or upload multiple source files
        
        **2. Auto-Generate Metrics** (Optional)
        - System creates synthetic revenue data
        - Based on HIGH risk events in your logs
        - Includes 60-day baseline for accurate detection
        
        **3. Root Cause Analysis**
        - Detects revenue crashes using Z-score
        - Links crashes to specific events
        - Calculates financial impact with causal inference
        
        ### 📊 Supported Sources
        - 🐙 GitHub commits
        - 💬 Slack messages  
        - 🎫 Jira tickets
        - 🔧 Jenkins builds
        """)
    
    with col2:
        st.markdown("""
        ### 🚀 Quick Start
        
        **Option 1:** Demo Mode
        ```bash
        # Generate sample data
        python ingest_data.py --demo
        python analyze_logs.py
        ```
        
        **Option 2:** Real Data
        ```bash
        # Configure .env file
        python ingest_data.py --days 30
        python analyze_logs.py
        ```
        
        Then upload the generated  
        `analyzed_logs.csv` here!
        """)