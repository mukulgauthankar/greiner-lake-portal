import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os
from PIL import Image

st.set_page_config(
    page_title="Greiner Lake Limnological Portal",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Academic Factsheets & Layout
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e2e8f0;
        padding: 12px 18px;
        border-radius: 8px;
    }
    div[data-testid="metric-container"] label {
        font-size: 13.5px !important;
        font-weight: 600;
        color: #475569;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        font-size: 23px !important;
        color: #0f172a;
    }
    .framework-card {
        background-color: #fcfcfd;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 14px;
    }
    .framework-card h4 {
        margin-top: 0;
        margin-bottom: 8px;
        font-size: 15px;
        color: #1e293b;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
    }
    .framework-item {
        font-size: 13.5px;
        line-height: 1.55;
        margin-bottom: 5px;
        color: #334155;
    }
    .framework-item strong {
        color: #0f172a;
    }
    .pheno-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        text-align: left;
    }
    .pheno-table th {
        padding: 8px 10px;
        color: #1e293b;
        background-color: #f1f5f9;
        border-bottom: 2px solid #cbd5e1;
    }
    .pheno-table td {
        padding: 7px 10px;
        border-bottom: 1px solid #e2e8f0;
        color: #334155;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_csv("greiner_lake_daily_summary.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["deployment_cycle"] = df["deployment_cycle"].replace({"2026-2027": "2025-2026"})

    if "hydro_doy" not in df.columns:
        def calc_hydro_doy(dt):
            cycle_start_year = dt.year if dt.month >= 8 else dt.year - 1
            return (dt - pd.Timestamp(year=cycle_start_year, month=8, day=1)).days + 1
        df["hydro_doy"] = df["timestamp"].apply(calc_hydro_doy)
    return df

df = load_data()

# Site Coordinates
GREINER_LAT = 69.177067
GREINER_LON = -104.931431

# Title & Station Header
st.title("🧊 Greiner Lake High-Arctic Limnological Observatory")
st.markdown(
    "**Long-term continuous autonomous mooring time series (2017–2026).**\n\n"
    "*Station: Greiner Lake (69°10'37.44'' N, 104°55'53.15'' W | Cambridge Bay / Iqaluktuuttiaq, Victoria Island, Nunavut)*"
)

# Sidebar Observational Controls
st.sidebar.header("🎛️ Observational Controls")

available_cycles = sorted([c for c in df["deployment_cycle"].dropna().unique() if c != "2026-2027"])
selected_cycles = st.sidebar.multiselect(
    "Deployment Cycles to Compare:",
    options=available_cycles,
    default=available_cycles[-4:] if len(available_cycles) >= 4 else available_cycles
)

depth_filter = st.sidebar.radio(
    "Mooring Layer (for Main Overview):",
    options=["Both Layers", "Surface", "Bottom"]
)

param_choice = st.sidebar.selectbox(
    "Parameter:",
    options=[
        ("do_mg_l", "Dissolved Oxygen (mg/L)"),
        ("do_sat_pct", "Dissolved Oxygen Saturation (%)"),
        ("temperature_c", "Water Temperature (°C)"),
        ("spec_cond_us_cm", "Specific Conductivity (µS/cm)"),
        ("par_umol_m2_s", "PAR (µmol/m²/s)"),
        ("depth_m", "Sensor Depth (m)")
    ],
    format_func=lambda x: x[1]
)

month_ticks = [1, 32, 62, 93, 123, 154, 185, 213, 244, 274, 305, 335]
month_labels = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"]

# Filter Data for Selected Cycles
df_cycles = df[df["deployment_cycle"].isin(selected_cycles)].copy() if selected_cycles else pd.DataFrame()
df_filtered = df_cycles.copy()
if not df_filtered.empty and depth_filter != "Both Layers":
    df_filtered = df_filtered[df_filtered["mooring_position"] == depth_filter]

# Submerged records (depth > 1.5 m) to strictly exclude deck handling
df_submerged = df_filtered[df_filtered["depth_m"] > 1.5] if not df_filtered.empty else pd.DataFrame()

# ----------------- 1. TOP BENCHMARK RIBBON (DIRECTLY AT TOP) -----------------
with st.expander("📊 Limnological Diagnostics & Multi-Year Extremes", expanded=True):
    if df_submerged.empty:
        st.info("👈 Select one or more deployment cycles from the sidebar to view diagnostics.")
    else:
        c1, c2, c3, c4 = st.columns(4)

        # 1. Dissolved Oxygen Range
        min_do = df_submerged["do_mg_l"].min()
        max_do = df_submerged["do_mg_l"].max()
        c1.metric(
            "DO Extremes",
            f"{min_do:.2f} – {max_do:.2f} mg/L" if pd.notnull(min_do) else "N/A",
            help="Dissolved Oxygen range (mg/L). Captures seasonal minimum drawdown and spring hyper-oxygenation."
        )

        # 2. Water Temperature Range (Submerged only)
        min_temp = df_submerged["temperature_c"].min()
        max_temp = df_submerged["temperature_c"].max()
        c2.metric(
            "Water Temp Range",
            f"{min_temp:.1f} – {max_temp:.1f} °C" if pd.notnull(min_temp) else "N/A",
            help="True submerged water temperature range (°C; depth > 1.5 m), strictly excluding deck handling."
        )

        # 3. Peak Submerged PAR
        max_par = df_submerged["par_umol_m2_s"].max()
        c3.metric(
            "Peak PAR",
            f"{max_par:.1f} µmol/m²/s" if pd.notnull(max_par) else "N/A",
            help="Maximum submerged Photosynthetically Active Radiation recorded during open-water summer / early melt."
        )

        # 4. Total Observations
        total_days = df_filtered["timestamp"].nunique()
        c4.metric(
            "Days Logged",
            f"{total_days:,} Days",
            help="Total continuous daily summary observations analyzed for selected cycles."
        )

# ----------------- 2. PRIMARY NAVIGATION TABS -----------------
tab_map, tab_doy, tab_time, tab_strat = st.tabs([
    "🗺️ Geographic Setting & Lake Framework",
    "❄️ Annual Limnological Cycle (Aug → Jul)",
    "📈 Continuous Multi-Year Series",
    "🔬 Vertical Stratification (Surface − Bottom)"
])

# ----------------- TAB 1: GEOGRAPHIC SETTING & LAKE FRAMEWORK -----------------
with tab_map:
    col_map, col_chars = st.columns([1.1, 0.9])

    with col_map:
        st.subheader("Station Location & Regional Setting")
        m = folium.Map(
            location=[GREINER_LAT, GREINER_LON],
            zoom_start=9,
            tiles="CartoDB positron"
        )
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Satellite Imagery",
            overlay=False
        ).add_to(m)
        folium.Marker(
            location=[GREINER_LAT, GREINER_LON],
            popup="<b>Greiner Lake Long-Term Mooring</b><br>69°10'37.44'' N, 104°55'53.15'' W<br>Surface & Benthic autonomous logging array",
            tooltip="Greiner Lake Mooring (69°10'37.44'' N, 104°55'53.15'' W)",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)
        folium.CircleMarker(
            location=[69.1167, -105.0500],
            radius=6,
            popup="Cambridge Bay (Iqaluktuuttiaq)",
            color="blue",
            fill=True,
            fill_color="blue"
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, height=460, width=None)
        st.caption("📍 Red Pin: Greiner Lake Mooring (69°10'37.44'' N, 104°55'53.15'' W) | Blue Circle: Cambridge Bay Townsite")

        st.markdown("---")
        st.subheader("Lake Basin Bathymetry & Mooring Station")

        bathy_paths = [
            "GRL BATHY  PNG.png",
            "GRL BATHY PNG.png",
            "GRL_BATHY_PNG.png",
            "C:/Users/mrgauthank/Downloads/GRL BATHY  PNG.png",
            "C:/Users/mrgauthank/Downloads/GRL BATHY PNG.png"
        ]

        found_img = None
        for p in bathy_paths:
            if os.path.exists(p):
                try:
                    found_img = Image.open(p)
                    break
                except Exception:
                    continue

        if found_img is not None:
            st.image(
                found_img,
                caption="Figure: Greiner Lake Bathymetric Contours & Deep Basin Mooring Array (~12.3 m max depth zone).",
                use_container_width=True
            )
        else:
            st.info("Bathymetry image not found. Ensure 'GRL BATHY  PNG.png' is in your Greiner folder.")

    with col_chars:
        st.subheader("Environmental & Limnological Profile")

        html_cards = """
<div class="framework-card">
    <h4>📍 Geography & Morphometry</h4>
    <div class="framework-item"><strong>Coordinates:</strong> 69°10'37.44'' N, 104°55'53.15'' W (Southern Victoria Island near Cambridge Bay / Iqaluktuuttiaq, Nunavut)</div>
    <div class="framework-item"><strong>Surface Area:</strong> 3,874 ha (38.74 km²) | <strong>Watershed:</strong> 1,500 km² (1,016 upstream lakes)</div>
    <div class="framework-item"><strong>Depth Profile:</strong> Mean 3.0 m (~39% of area &lt; 2.0 m) | Max 12.0 m (deep basin)</div>
    <div class="framework-item"><strong>Residence Time:</strong> 111 days (theoretical)</div>
</div>

<div class="framework-card">
    <h4>🧊 Thermal & Ice Phenology</h4>
    <div class="framework-item"><strong>Mixing Regime:</strong> Cold monomictic (continuous open-water mixing; brief, episodic stratification)</div>
    <div class="framework-item"><strong>Summer Temperature:</strong> Peaks in August, typically &lt; 15°C</div>
    <div class="framework-item"><strong>Winter Water Column:</strong> Inversely stratified (~0°C beneath ice to ~1.9°C near bottom)</div>
    <div class="framework-item"><strong>Ice Duration:</strong> 7–9 months (freeze-up late Sept; break-up early/mid-July)</div>
    <div class="framework-item"><strong>Maximum Ice Thickness:</strong> ~215 cm (reached in early June)</div>
</div>

<div class="framework-card">
    <h4>☀️ Light, Optics & Productivity</h4>
    <div class="framework-item"><strong>Optical Clarity (K<sub>d</sub>):</strong> Mean diffuse attenuation coefficient = 0.57 – 0.67 m⁻¹</div>
    <div class="framework-item"><strong>Polar Night:</strong> 42 days (Dec 1 – Jan 12; sun below horizon, low diffuse twilight)</div>
    <div class="framework-item"><strong>Primary Production:</strong> Littoral microbial mats (29.35 mg C m⁻² h⁻¹) | Planktonic (4.46 mg C m⁻³ h⁻¹)</div>
</div>

<div class="framework-card">
    <h4>🌦️ Regional Climate Setting</h4>
    <div class="framework-item"><strong>Climate Type:</strong> Polar semi-arid to desert (continuous permafrost, treeless tundra)</div>
    <div class="framework-item"><strong>Air Temperature:</strong> -13.3°C annual mean (winter &lt; -30°C; summer ~9°C)</div>
    <div class="framework-item"><strong>Precipitation:</strong> ~140 mm annual (concentrated Jul–Oct up to 75.2 mm; winter/spring &lt; 15 mm/month)</div>
</div>

<div class="framework-card">
    <h4>📅 Mooring Deployment Depths & Ice Phenology</h4>
    <div style="overflow-x: auto;">
        <table class="pheno-table">
            <thead>
                <tr>
                    <th>Hydrological Year</th>
                    <th>Ice-in Date</th>
                    <th>Ice-out Date</th>
                    <th>Surface Depth</th>
                    <th>Bottom Depth</th>
                </tr>
            </thead>
            <tbody>
                <tr><td><strong>2017–2018</strong></td><td>31 Oct 2017 (deployed)</td><td>—</td><td>3.42 m</td><td>—</td></tr>
                <tr><td><strong>2018–2019</strong></td><td>20 Sep 2018</td><td>—</td><td>3.42 m</td><td>—</td></tr>
                <tr><td><strong>2019–2020</strong></td><td>29 Sep 2019</td><td>—</td><td>2.24 m</td><td>7.32 m</td></tr>
                <tr><td><strong>2020–2021</strong></td><td>07 Oct 2020</td><td>—</td><td>3.63 m</td><td>8.02 m</td></tr>
                <tr><td><strong>2021–2022</strong></td><td>11 Oct 2021</td><td>—</td><td>2.81 m</td><td>7.38 m</td></tr>
                <tr><td><strong>2022–2023</strong></td><td>28 Sep 2022</td><td>—</td><td>3.30 m</td><td>7.64 m</td></tr>
                <tr><td><strong>2023–2024</strong></td><td>09 Oct 2023</td><td>—</td><td>3.15 m</td><td>7.85 m</td></tr>
                <tr><td><strong>2024–2025</strong></td><td>13 Oct 2024</td><td>—</td><td>3.86 m</td><td>7.50 m</td></tr>
            </tbody>
        </table>
    </div>
</div>
"""
        st.markdown(html_cards, unsafe_allow_html=True)

# ----------------- OBSERVATIONAL PLOTS TABS -----------------
if not selected_cycles:
    st.sidebar.warning("⚠️ Select at least one deployment cycle to display observational data.")
    with tab_doy:
        st.info("👈 Please select one or more deployment cycles from the sidebar to visualize time series.")
    with tab_time:
        st.info("👈 Please select one or more deployment cycles from the sidebar to visualize time series.")
    with tab_strat:
        st.info("👈 Please select one or more deployment cycles from the sidebar to calculate vertical stratification.")
else:
    # ----------------- TAB 2: ANNUAL LIMNOLOGICAL CYCLE -----------------
    with tab_doy:
        st.subheader(f"1. Integrated Interannual View: {param_choice[1]}")
        st.caption("All selected cycles aligned from August 1 through July 31 across the full ice season.")

        df_main_plot = df_filtered.sort_values(
            by=["deployment_cycle", "mooring_position", "hydro_doy"]
        ).copy()

        fig_main = px.line(
            df_main_plot,
            x="hydro_doy",
            y=param_choice[0],
            color="deployment_cycle",
            line_dash="mooring_position" if depth_filter == "Both Layers" else None,
            labels={
                "hydro_doy": "Month of Limnological Cycle (Starting August)",
                param_choice[0]: param_choice[1],
                "deployment_cycle": "Deployment",
                "mooring_position": "Depth Layer"
            },
            template="plotly_white"
        )
        fig_main.update_xaxes(tickmode="array", tickvals=month_ticks, ticktext=month_labels, range=[1, 365])
        fig_main.update_layout(height=480, hovermode="x unified")
        st.plotly_chart(fig_main, width="stretch")

        st.markdown("---")
        st.subheader(f"2. Side-by-Side Stratum Comparison: {param_choice[1]}")
        st.caption("Direct comparison of Surface vs. Bottom (Benthic) layers across the exact same annual timeline.")

        col_surf, col_bot = st.columns(2)

        y_min = df_cycles[param_choice[0]].min()
        y_max = df_cycles[param_choice[0]].max()
        y_pad = (y_max - y_min) * 0.05 if pd.notnull(y_max) and pd.notnull(y_min) else 1
        y_range = [y_min - y_pad, y_max + y_pad] if pd.notnull(y_min) else None

        with col_surf:
            st.markdown("#### 🌊 Surface Mooring (~2.5–3.5 m)")
            df_surf = df_cycles[df_cycles["mooring_position"] == "Surface"].sort_values(
                by=["deployment_cycle", "hydro_doy"]
            )
            if not df_surf.empty:
                fig_surf = px.line(
                    df_surf,
                    x="hydro_doy",
                    y=param_choice[0],
                    color="deployment_cycle",
                    labels={"hydro_doy": "Month", param_choice[0]: param_choice[1], "deployment_cycle": "Cycle"},
                    template="plotly_white"
                )
                fig_surf.update_xaxes(tickmode="array", tickvals=month_ticks, ticktext=month_labels, range=[1, 365])
                if y_range:
                    fig_surf.update_yaxes(range=y_range)
                fig_surf.update_layout(height=420, showlegend=True, hovermode="x unified")
                st.plotly_chart(fig_surf, width="stretch")
            else:
                st.info("No Surface records for the selected cycles.")

        with col_bot:
            st.markdown("#### ⚓ Bottom (Benthic) Mooring (~7.5–9.2 m)")
            df_bot = df_cycles[df_cycles["mooring_position"] == "Bottom"].sort_values(
                by=["deployment_cycle", "hydro_doy"]
            )
            if not df_bot.empty:
                fig_bot = px.line(
                    df_bot,
                    x="hydro_doy",
                    y=param_choice[0],
                    color="deployment_cycle",
                    labels={"hydro_doy": "Month", param_choice[0]: param_choice[1], "deployment_cycle": "Cycle"},
                    template="plotly_white"
                )
                fig_bot.update_xaxes(tickmode="array", tickvals=month_ticks, ticktext=month_labels, range=[1, 365])
                if y_range:
                    fig_bot.update_yaxes(range=y_range)
                fig_bot.update_layout(height=420, showlegend=True, hovermode="x unified")
                st.plotly_chart(fig_bot, width="stretch")
            else:
                st.info("No Bottom records for the selected cycles.")

    # ----------------- TAB 3: CONTINUOUS TIME SERIES -----------------
    with tab_time:
        st.subheader(f"Continuous Multi-Year Record ({param_choice[1]})")
        fig_time = px.line(
            df_filtered,
            x="timestamp",
            y=param_choice[0],
            color="mooring_position",
            labels={"timestamp": "Date", param_choice[0]: param_choice[1], "mooring_position": "Depth Layer"},
            template="plotly_white"
        )
        fig_time.update_layout(height=480, hovermode="x unified")
        st.plotly_chart(fig_time, width="stretch")

    # ----------------- TAB 4: STRATIFICATION ANALYSIS -----------------
    with tab_strat:
        st.subheader("Vertical Stratification Gradients (Surface − Bottom)")

        df_pivot = df[df["deployment_cycle"].isin(selected_cycles)].pivot_table(
            index=["timestamp", "deployment_cycle", "hydro_doy"],
            columns="mooring_position",
            values=["temperature_c", "do_mg_l"]
        ).dropna()

        if not df_pivot.empty and ("Surface" in df_pivot["temperature_c"] and "Bottom" in df_pivot["temperature_c"]):
            df_pivot["delta_temp"] = df_pivot["temperature_c"]["Surface"] - df_pivot["temperature_c"]["Bottom"]
            df_pivot["delta_do"] = df_pivot["do_mg_l"]["Surface"] - df_pivot["do_mg_l"]["Bottom"]

            df_diff = df_pivot.reset_index()
            df_diff.columns = [
                col[0] if col[1] == "" else f"{col[0]}_{col[1]}"
                for col in df_diff.columns
            ]

            fig_diff = px.area(
                df_diff,
                x="timestamp",
                y="delta_temp",
                title="Thermal Stratification: Surface Temp − Bottom Temp (°C)",
                labels={"timestamp": "Date", "delta_temp": "Δ Temperature (°C)"},
                template="plotly_white",
                color_discrete_sequence=["#2b83ba"]
            )
            fig_diff.add_hline(y=0, line_color="black", line_width=1)
            st.plotly_chart(fig_diff, width="stretch")

            fig_diff_do = px.area(
                df_diff,
                x="timestamp",
                y="delta_do",
                title="Oxygen Stratification: Surface DO − Bottom DO (mg/L)",
                labels={"timestamp": "Date", "delta_do": "Δ Dissolved Oxygen (mg/L)"},
                template="plotly_white",
                color_discrete_sequence=["#2ca25f"]
            )
            fig_diff_do.add_hline(y=0, line_color="black", line_width=1)
            st.plotly_chart(fig_diff_do, width="stretch")
        else:
            st.info("Stratification calculations require overlapping Surface and Bottom records for the selected years.")

# Data Export Section
st.markdown("---")
st.subheader("📥 Export Filtered Limnological Records")
if not df_filtered.empty:
    csv_data = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Selected Dataset (CSV)",
        data=csv_data,
        file_name="greiner_lake_filtered_data.csv",
        mime="text/csv"
    )
