"""
监控数据配置页面 - 支持上传CSV文件作为伪实时数据
"""
import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.data_loader import (
    inject_csv_as_realtime,
    list_realtime_data,
    clear_realtime_cache,
    get_realtime_data,
    get_all_services,
    FAULT_DATA_MAP,
)


def render_monitoring_page():
    """渲染监控数据配置页面"""
    st.header("Monitoring Data Configuration")
    st.markdown("Upload CSV files as pseudo real-time monitoring data for RCA analysis.")

    # 初始化session state
    if "uploaded_data_info" not in st.session_state:
        st.session_state.uploaded_data_info = None

    # 两列布局
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Upload Monitoring Data")
        
        # 文件上传
        uploaded_file = st.file_uploader(
            "Choose a CSV file",
            type="csv",
            help="CSV should contain 'time' column and service metric columns (e.g., frontend_cpu)"
        )

        # 故障类型选择
        fault_type_option = st.selectbox(
            "Fault type (auto-detect if not specified)",
            ["Auto-detect"] + list(FAULT_DATA_MAP.keys()),
            help="Leave as 'Auto-detect' to infer from data columns"
        )

        # 注入按钮
        if uploaded_file is not None:
            if st.button("Inject as Real-time Data", type="primary", width="stretch"):
                with st.spinner("Processing CSV file..."):
                    fault_type = None if fault_type_option == "Auto-detect" else fault_type_option
                    success, msg, df = inject_csv_as_realtime(uploaded_file, fault_type)

                    if success:
                        st.success(msg)
                        st.session_state.uploaded_data_info = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "fault_type": fault_type or "auto-detected",
                            "rows": len(df),
                            "columns": len(df.columns),
                            "services": len([c for c in df.columns if c != "time"])
                        }

                        # 显示数据预览
                        st.markdown("**Data Preview (first 5 rows):**")
                        st.dataframe(df.head(), use_container_width=True)

                        # 显示检测到的服务
                        services = get_all_services(df)
                        if services:
                            st.info(f"Detected {len(services)} services: {', '.join(services[:10])}")
                    else:
                        st.error(msg)

                        # 如果验证失败，显示格式说明
                        if "格式验证失败" in msg:
                            st.markdown("---")
                            st.subheader("CSV Format Requirements")
                            st.markdown("""
                            **Required:**
                            - `time` column (numeric timestamp)

                            **Supported column format:**
                            - `{service}_{metric}` e.g., `frontend_cpu`, `checkoutservice_mem`
                            - Supports hyphens: `frontend-external_cpu`

                            **Supported metrics:**
                            - `cpu`, `mem` (resource)
                            - `latency`, `latency-50`, `latency-90` (performance)
                            - `load`, `workload` (traffic)
                            - `error` (error count/rate)

                            **Note:** CSV can have partial metrics (e.g., no `error` column is OK)
                            """)

        # 显示上传信息
        if st.session_state.uploaded_data_info:
            st.markdown("---")
            st.caption("Last Upload Info")
            info = st.session_state.uploaded_data_info
            st.write(f"**Time:** {info['timestamp']}")
            st.write(f"**Type:** {info['fault_type']}")
            st.write(f"**Rows:** {info['rows']}")
            st.write(f"**Columns:** {info['columns']}")

    with col2:
        st.subheader("Current Real-time Data")

        # 列出当前缓存的数据
        realtime_data = list_realtime_data()

        if realtime_data:
            for ft, info in realtime_data.items():
                with st.expander(f"Fault Type: {ft.upper()}", expanded=True):
                    st.write(f"**Rows:** {info['rows']}")
                    st.write(f"**Columns:** {info['columns']}")
                    if info['time_range'][0] and info['time_range'][1]:
                        st.write(f"**Time Range:** {info['time_range'][0]} ~ {info['time_range'][1]}")

                    if info.get('services'):
                        st.write(f"**Sample Services:** {', '.join(info['services'])}")

                    # 预览数据
                    df = get_realtime_data(ft)
                    if df is not None and not df.empty:
                        st.dataframe(df.head(5), use_container_width=True)

                    # 清除按钮
                    if st.button(f"Clear {ft}", key=f"clear_{ft}"):
                        clear_realtime_cache(ft)
                        st.rerun()
        else:
            st.info("No real-time data injected yet.")

        # 批量清除
        if realtime_data:
            st.markdown("---")
            if st.button("Clear All Real-time Data", type="secondary", width="stretch"):
                clear_realtime_cache()
                st.rerun()

    # CSV格式说明
    st.markdown("---")
    st.subheader("CSV Format Requirements")
    st.markdown("""
    Your CSV file should have the following structure:

    | time | service1_cpu | service1_mem | service2_cpu | ... |
    |------|--------------|--------------|--------------|-----|
    | 1000 | 45.2         | 60.1         | 30.5         | ... |
    | 1001 | 47.8         | 61.3         | 31.2         | ... |

    **Requirements:**
    - First column should be `time` (timestamp)
    - Other columns should follow pattern: `{service_name}_{metric_type}`
    - Common metrics: `cpu`, `mem`, `latency`, `disk`, `loss`
    - Data will be injected as pseudo real-time monitoring data
    """)

    # 示例数据下载
    with st.expander("Download Sample CSV Template"):
        sample_data = {
            "time": list(range(1000, 1060)),
            "frontend_cpu": [float(40 + i % 10) for i in range(60)],
            "frontend_mem": [float(50 + i % 5) for i in range(60)],
            "checkoutservice_cpu": [float(30 + i % 8) for i in range(60)],
            "checkoutservice_latency": [float(100 + i * 2) for i in range(60)],
        }
        sample_df = pd.DataFrame(sample_data)
        st.dataframe(sample_df.head(10), use_container_width=True)

        csv = sample_df.to_csv(index=False)
        st.download_button(
            label="Download Sample CSV",
            data=csv,
            file_name="sample_monitoring_data.csv",
            mime="text/csv",
            width="stretch"
        )
