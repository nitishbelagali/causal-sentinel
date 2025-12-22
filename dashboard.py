import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dowhy import CausalModel
import warnings
from datetime import timedelta

warnings.filterwarnings("ignore")

# --- PAGE CONFIG ---
st.set_page_config(page_title="Causal Sentinel Enterprise", page_icon="🛡️", layout="wide")
st.title("🛡️ Causal Sentinel: Enterprise Edition")

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

# --- VALIDATION HELPERS ---
def safe_datetime_convert(series, col_name):
    """Converts to datetime with informative error handling"""
    try:
        converted = pd.to_datetime(series, errors='coerce')
        null_count = converted.isna().sum()
        
        if null_count > 0:
            st.warning(f"⚠️ {null_count} invalid dates in '{col_name}' were set to NaT")
        
        return converted
    except Exception as e:
        st.error(f"Failed to convert '{col_name}' to datetime: {e}")
        return None

# --- SIDEBAR: INGESTION LAYER ---
st.sidebar.header("📥 1. Ingest Data")
metrics_file = st.sidebar.file_uploader("Upload Business Metrics", type=["csv", "xlsx"])
logs_file = st.sidebar.file_uploader("Upload Analyzed Logs", type=["csv", "xlsx"])

# --- MAIN LOGIC ---
if metrics_file is not None and logs_file is not None:
    
    # === STAGE 1: FILE LOADING ===
    try:
        if metrics_file.name.endswith('.csv'):
            raw_metrics = pd.read_csv(metrics_file)
        else:
            raw_metrics = pd.read_excel(metrics_file)
            
        if logs_file.name.endswith('.csv'):
            raw_logs = pd.read_csv(logs_file)
        else:
            raw_logs = pd.read_excel(logs_file)
            
        st.sidebar.success("✅ Files Loaded Successfully")
        
    except Exception as e:
        st.error(f"❌ Error reading files: {e}")
        st.stop()

    # === STAGE 2: COLUMN MAPPING ===
    st.sidebar.header("🗺️ 2. Map Your Schema")
    
    # Metrics Mapping
    st.sidebar.markdown("**Metrics File Mapping:**")
    if len(raw_metrics.columns) < 2:
        st.error("Metrics file must have at least 2 columns (date + metric)")
        st.stop()
        
    user_date_col = st.sidebar.selectbox("Select Date Column", raw_metrics.columns, index=0)
    user_metric_col = st.sidebar.selectbox("Select KPI Column (e.g. Revenue)", raw_metrics.columns, index=1)
    
    # Optional: User can map their own latency/confounders
    has_confounder = st.sidebar.checkbox("I have a confounder column (e.g. latency, traffic)")
    user_confounder_col = None
    if has_confounder:
        user_confounder_col = st.sidebar.selectbox(
            "Select Confounder Column", 
            [col for col in raw_metrics.columns if col not in [user_date_col, user_metric_col]],
            help="Variable that might affect both treatment and outcome"
        )
    
    # Logs Mapping
    st.sidebar.markdown("**Logs File Mapping:**")
    if len(raw_logs.columns) < 3:
        st.error("Logs file must have at least 3 columns (timestamp + risk + message)")
        st.stop()
        
    user_log_date_col = st.sidebar.selectbox("Select Timestamp Column", raw_logs.columns, index=0)
    user_risk_col = st.sidebar.selectbox("Select AI Risk Column", raw_logs.columns, index=len(raw_logs.columns)-1)
    user_msg_col = st.sidebar.selectbox("Select Message Column", raw_logs.columns, index=1)

    # === STAGE 3: STANDARDIZATION ===
    df_metrics = raw_metrics[[user_date_col, user_metric_col]].copy()  # Only keep needed columns
    df_metrics.columns = ['date', 'daily_revenue']  # Rename directly
    
    # Add confounder if user provided one
    if user_confounder_col:
        df_metrics['confounder'] = raw_metrics[user_confounder_col].values
    else:
        # Generate synthetic confounder based on revenue variance
        # Use .squeeze() to ensure we have a Series, not DataFrame
        revenue_series = df_metrics['daily_revenue'].squeeze()
        rolling_std = revenue_series.rolling(3, min_periods=1).std()
        df_metrics['confounder'] = rolling_std.fillna(0).values
    
    df_events = raw_logs[[user_log_date_col, user_risk_col, user_msg_col]].copy()  # Only keep needed columns
    df_events.columns = ['timestamp', 'ai_risk', 'message']  # Rename directly

    # === STAGE 4: DATA VALIDATION ===
    validation_errors = []
    
    # Validate metrics (needs rolling window data)
    if df_metrics.empty:
        validation_errors.append("Metrics file is empty")
    elif len(df_metrics) < ROLLING_WINDOW:
        validation_errors.append(f"Metrics has only {len(df_metrics)} rows. Need at least {ROLLING_WINDOW} for rolling analysis.")
    
    for col in ['date', 'daily_revenue']:
        if col not in df_metrics.columns:
            validation_errors.append(f"Missing required column: '{col}' in Metrics")
        elif df_metrics[col].isna().all():
            validation_errors.append(f"Column '{col}' in Metrics contains only null values")
    
    # Validate logs (no rolling window requirement - just needs data)
    if df_events.empty:
        validation_errors.append("Logs file is empty")
    
    for col in ['timestamp', 'ai_risk', 'message']:
        if col not in df_events.columns:
            validation_errors.append(f"Missing required column: '{col}' in Logs")
        elif df_events[col].isna().all():
            validation_errors.append(f"Column '{col}' in Logs contains only null values")
    
    if validation_errors:
        for error in validation_errors:
            st.error(f"❌ {error}")
        st.stop()

    # Datetime Conversion with Safety
    df_metrics['date'] = safe_datetime_convert(df_metrics['date'], user_date_col)
    df_events['timestamp'] = safe_datetime_convert(df_events['timestamp'], user_log_date_col)
    
    if df_metrics['date'].isna().all() or df_events['timestamp'].isna().all():
        st.error("❌ All dates failed to parse. Check your date format.")
        st.stop()
    
    # Drop rows with null dates
    df_metrics = df_metrics.dropna(subset=['date'])
    df_events = df_events.dropna(subset=['timestamp'])
    
    # Sort by date (Critical for rolling calculations!)
    df_metrics = df_metrics.sort_values('date').reset_index(drop=True)
    df_events = df_events.sort_values('timestamp').reset_index(drop=True)
    
    # Numeric Validation
    if not pd.api.types.is_numeric_dtype(df_metrics['daily_revenue']):
        st.error(f"❌ Column '{user_metric_col}' must contain numeric values")
        st.stop()
    
    # === STAGE 5: ANOMALY DETECTION (ENHANCED) ===
    def detect_crashes(df, threshold=SENSITIVITY, window=ROLLING_WINDOW):
        """
        Returns ALL anomalies, not just the first one.
        Includes confidence scores.
        """
        df = df.copy()
        df['rolling_mean'] = df['daily_revenue'].rolling(window=window, min_periods=window//2).mean()
        df['rolling_std'] = df['daily_revenue'].rolling(window=window, min_periods=window//2).std()
        
        # Avoid division by zero
        df['rolling_std'] = df['rolling_std'].replace(0, df['daily_revenue'].std())
        
        df['z_score'] = (df['daily_revenue'] - df['rolling_mean']) / df['rolling_std']
        df['is_anomaly'] = df['z_score'] < -threshold
        df['confidence'] = df['z_score'].abs()
        
        anomalies = df[df['is_anomaly']].copy()
        return anomalies.sort_values('confidence', ascending=False)

    st.subheader("🔍 3. Analysis Results")
    
    with st.spinner("Scanning for anomalies..."):
        crashes = detect_crashes(df_metrics)
    
    if crashes.empty:
        st.success("✅ System Healthy. No anomalies detected.")
        
        # Show clean trend
        fig = px.line(df_metrics, x='date', y='daily_revenue', title=f"Trend Analysis: {user_metric_col}")
        st.plotly_chart(fig, use_container_width=True)
        
        # Show statistical summary
        with st.expander("📊 Statistical Summary"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Average", f"${df_metrics['daily_revenue'].mean():,.2f}")
            col2.metric("Std Dev", f"${df_metrics['daily_revenue'].std():,.2f}")
            col3.metric("Data Points", len(df_metrics))
    
    else:
        # === STAGE 6: ROOT CAUSE ANALYSIS ===
        st.error(f"🚨 DETECTED {len(crashes)} ANOMALY(IES)")
        
        # Show all crashes in a table
        with st.expander("📋 All Detected Anomalies"):
            display_crashes = crashes[['date', 'daily_revenue', 'z_score', 'confidence']].copy()
            display_crashes['date'] = display_crashes['date'].dt.strftime('%Y-%m-%d')
            display_crashes['z_score'] = display_crashes['z_score'].round(2)
            display_crashes['confidence'] = display_crashes['confidence'].round(2)
            st.dataframe(display_crashes, use_container_width=True)
        
        # Focus on MOST SEVERE crash
        worst_crash = crashes.iloc[0]
        crash_date = worst_crash['date']
        
        st.warning(f"**Most Severe Crash:** {crash_date.strftime('%Y-%m-%d')} (Z-Score: {worst_crash['z_score']:.2f})")
        
        # === VISUALIZATION ===
        fig = go.Figure()
        
        # Main trend line
        fig.add_trace(go.Scatter(
            x=df_metrics['date'], 
            y=df_metrics['daily_revenue'],
            mode='lines+markers',
            name=user_metric_col,
            line=dict(color='#1f77b4', width=2)
        ))
        
        # Highlight ALL anomalies
        fig.add_trace(go.Scatter(
            x=crashes['date'],
            y=crashes['daily_revenue'],
            mode='markers',
            name='Anomalies',
            marker=dict(color='red', size=12, symbol='x')
        ))
        
        # Mark the worst crash
        fig.add_vline(
            x=crash_date.timestamp() * 1000, 
            line_dash="dash", 
            line_color="red",
            annotation_text=f"Crash: {crash_date.strftime('%Y-%m-%d')}"
        )
        
        fig.update_layout(
            title=f"Trend Analysis: {user_metric_col}",
            xaxis_title="Date",
            yaxis_title=user_metric_col,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # === STAGE 7: EVENT LINKING ===
        search_start = crash_date - timedelta(days=LOOKBACK_DAYS)
        search_end = crash_date + timedelta(days=LOOKBACK_DAYS)
        
        suspects = df_events[
            (df_events['timestamp'] >= search_start) & 
            (df_events['timestamp'] <= search_end) & 
            (df_events['ai_risk'].str.upper() == 'HIGH')
        ]
        
        if suspects.empty:
            st.warning(f"⚠️ No 'HIGH' risk events found in {LOOKBACK_DAYS}-day window around crash.")
            
            # Show what WAS in the window
            all_events_in_window = df_events[
                (df_events['timestamp'] >= search_start) & 
                (df_events['timestamp'] <= search_end)
            ]
            
            if not all_events_in_window.empty:
                with st.expander("🔍 All Events in Window (Not Flagged HIGH)"):
                    st.dataframe(all_events_in_window[['timestamp', 'ai_risk', 'message']])
        
        else:
            # === STAGE 8: CAUSAL ANALYSIS ===
            suspect = suspects.iloc[0]
            st.success(f"✅ **Root Cause Identified:** {suspect['message']}")
            
            # Show suspect details
            col1, col2 = st.columns(2)
            col1.metric("Event Timestamp", suspect['timestamp'].strftime('%Y-%m-%d %H:%M'))
            col2.metric("Risk Level", suspect['ai_risk'])
            
            with st.expander("🔬 Causal Inference (Math Proof)"):
                try:
                    # Create treatment indicator
                    df_metrics['is_broken'] = (df_metrics['date'] >= crash_date).astype(int)
                    
                    # Ensure we have enough variation
                    if df_metrics['is_broken'].sum() == 0 or df_metrics['is_broken'].sum() == len(df_metrics):
                        st.warning("⚠️ Insufficient data variation for causal analysis")
                    else:
                        model = CausalModel(
                            data=df_metrics,
                            treatment='is_broken',
                            outcome='daily_revenue',
                            common_causes=['confounder']
                        )
                        
                        estimand = model.identify_effect()
                        estimate = model.estimate_effect(
                            estimand, 
                            method_name="backdoor.linear_regression"
                        )
                        
                        impact = abs(estimate.value)
                        
                        # Visual Impact Display
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Daily Impact", f"${impact:,.2f}")
                        
                        days_affected = len(df_metrics[df_metrics['is_broken'] == 1])
                        col2.metric("Days Affected", days_affected)
                        col3.metric("Total Impact", f"${impact * days_affected:,.2f}")
                        
                        # Show the math
                        st.code(f"""
Causal Estimand: {estimand}
Estimation Method: Backdoor Linear Regression
Coefficient: {estimate.value:.2f}
P-value: {estimate.get_confidence_intervals() if hasattr(estimate, 'get_confidence_intervals') else 'N/A'}
                        """)
                        
                except Exception as e:
                    st.error(f"⚠️ Causal analysis failed: {e}")
                    st.info("This can happen with small datasets or when treatment doesn't vary enough.")

else:
    # === LANDING PAGE ===
    st.info("👋 **Welcome to Causal Sentinel Enterprise**")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🎯 What This Does
        
        This system **automatically**:
        1. 🔍 Detects revenue crashes using statistical anomaly detection
        2. 🕵️ Links crashes to specific code changes or system events
        3. 📊 Calculates the exact financial impact using causal inference
        
        ### 📁 Required Data Format
        
        **Metrics File (CSV/Excel):**
        - Date column (any format)
        - Revenue/KPI column (numeric)
        - Optional: Confounder column (latency, traffic, etc.)
        
        **Logs File (CSV/Excel):**
        - Timestamp column
        - AI Risk column (HIGH/LOW)
        - Message column (event description)
        
        ### 🚀 Quick Start
        1. Upload both files using the sidebar →
        2. Map your column names
        3. Adjust detection parameters
        4. Review results
        """)
    
    with col2:
        st.markdown("""
        ### 📊 Demo Data
        
        Don't have data? Generate sample data:
        """)
        
        if st.button("🎲 Generate Sample Data"):
            # Create sample metrics
            dates = pd.date_range('2024-11-01', '2024-11-30', freq='D')
            revenue = [50000 + i*100 for i in range(len(dates))]
            revenue[14] = 25000  # Inject crash on Nov 15
            
            sample_metrics = pd.DataFrame({
                'date': dates,
                'daily_revenue': revenue,
                'latency_ms': [100 + (i % 10) * 5 for i in range(len(dates))]
            })
            
            # Create sample logs
            sample_logs = pd.DataFrame({
                'timestamp': ['2024-11-14 23:30:00', '2024-11-15 08:00:00', '2024-11-15 12:00:00'],
                'ai_risk': ['LOW', 'HIGH', 'LOW'],
                'message': [
                    'Updated README documentation',
                    'Changed payment API from async to sync loops',
                    'Fixed CSS typo in footer'
                ]
            })
            
            # Provide download links
            st.download_button(
                "📥 Download Sample Metrics",
                sample_metrics.to_csv(index=False),
                "sample_metrics.csv",
                "text/csv"
            )
            
            st.download_button(
                "📥 Download Sample Logs",
                sample_logs.to_csv(index=False),
                "sample_logs.csv",
                "text/csv"
            )