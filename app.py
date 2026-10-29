import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os
import calendar
import base64
from io import BytesIO
from PIL import Image, ImageChops, ImageDraw

st.set_page_config(
    page_title="Greiner Lake Limnological Portal",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
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
    .profile-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 22px 18px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        height: 520px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
    }
    .team-avatar-img {
        width: 250px;
        height: 250px;
        border-radius: 50%;
        object-fit: cover;
        margin: 0 auto 12px auto;
        display: block;
        border: 3px solid #e2e8f0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .lab-link-btn {
        display: inline-block;
        padding: 6px 16px;
        background-color: #f1f5f9;
        color: #0f172a !important;
        text-decoration: none !important;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid #cbd5e1;
        transition: all 0.2s ease;
    }
    .lab-link-btn:hover {
        background-color: #e2e8f0;
        border-color: #94a3b8;
    }
    [data-testid="stImage"] {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    [data-testid="stImage"] > img {
        margin: 0 auto;
        display: block;
        max-height: 380px;
        object-fit: contain;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- HIGH-RESOLUTION 600 DPI PLOT EXPORT CONFIG -----------------
PLOT_EXPORT_CONFIG = {
    "toImageButtonOptions": {
        "format": "png",
        "filename": "greiner_lake_observatory_figure",
        "height": 900,
        "width": 1800,
        "scale": 4  # 4x supersampling produces ~7200x3600 px (600 DPI equivalent)
    },
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"]
}

# ----------------- CHRONOLOGICAL YEAR ORDER -----------------
CHRONOLOGICAL_YEAR_ORDER = [
    "2017-2018", "2018-2019", "2019-2020", "2020-2021",
    "2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"
]

# ----------------- LAKE DOY & TICK LOGIC -----------------
ANCHOR_MONTH = 8
ANCHOR_DAY = 1

def lake_doy(dt):
    if pd.isna(dt):
        return float("nan")
    anchor = pd.Timestamp(year=dt.year, month=ANCHOR_MONTH, day=ANCHOR_DAY)
    if dt < anchor:
        anchor = pd.Timestamp(year=dt.year - 1, month=ANCHOR_MONTH, day=ANCHOR_DAY)
    delta = dt - anchor
    return delta.days + delta.seconds / 86400.0

def lake_month_ticks(ref_year=2021):
    ticks, labels = [], []
    months = list(range(ANCHOR_MONTH, 13)) + list(range(1, ANCHOR_MONTH))
    years = [ref_year] * len(range(ANCHOR_MONTH, 13)) + [ref_year + 1] * len(range(1, ANCHOR_MONTH))
    for m, y in zip(months, years):
        dt0 = pd.Timestamp(y, m, 1)
        ticks.append(lake_doy(dt0))
        labels.append(calendar.month_abbr[m])
    ticks.append(lake_doy(pd.Timestamp(ref_year + 1, ANCHOR_MONTH, 1)))
    labels.append("Aug")
    return ticks, labels

LAKE_TICKS, LAKE_TICK_LABELS = lake_month_ticks()

# Exact verified deployment boundaries:
DEPLOYMENT_BOUNDARIES = {
    ("2017-2018", "Surface"): ("2017-10-31", "2018-07-31"),
    ("2018-2019", "Surface"): ("2018-08-15", "2019-07-15"),
    ("2019-2020", "Surface"): ("2019-08-11", "2020-07-31"),
    ("2019-2020", "Bottom"):  ("2019-08-11", "2020-07-31"),
    ("2020-2021", "Surface"): ("2020-09-23", "2021-07-31"),
    ("2020-2021", "Bottom"):  ("2020-09-23", "2021-07-31"),
    ("2021-2022", "Surface"): ("2021-08-27", "2022-07-31"),
    ("2021-2022", "Bottom"):  ("2021-08-27", "2022-07-31"),
    ("2022-2023", "Surface"): ("2022-08-17", "2023-07-31"),
    ("2022-2023", "Bottom"):  ("2022-08-17", "2023-07-31"),
    ("2023-2024", "Surface"): ("2023-10-04", "2024-07-31"),
    ("2023-2024", "Bottom"):  ("2023-10-04", "2024-07-31"),
    ("2024-2025", "Surface"): ("2024-09-01", "2025-04-12"),
    ("2024-2025", "Bottom"):  ("2024-09-01", "2025-04-12"),
    ("2025-2026", "Surface"): ("2025-08-20", "2026-07-31"),
    ("2025-2026", "Bottom"):  ("2025-08-20", "2026-07-31"),
}

@st.cache_data
def load_data():
    df = pd.read_csv("greiner_lake_daily_summary.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["deployment_cycle"] = df["deployment_cycle"].replace({"2026-2027": "2025-2026"})

    masks = []
    for (cycle, pos), (start_s, end_s) in DEPLOYMENT_BOUNDARIES.items():
        m = (
            (df["deployment_cycle"] == cycle) &
            (df["mooring_position"] == pos) &
            (df["timestamp"] >= pd.Timestamp(start_s)) &
            (df["timestamp"] <= pd.Timestamp(end_s))
        )
        masks.append(m)

    if masks:
        df = df[np.logical_or.reduce(masks)].copy()

    if "temperature_c" in df.columns:
        df = df[df["temperature_c"] <= 16.5].copy()

    df["lake_doy"] = df["timestamp"].map(lake_doy)
    return df

df = load_data()

# Uniform Logo & Asset Loader:
@st.cache_data
def get_standardized_logo(path_candidates, target_canvas=(1600, 700), pad_ratio=0.88):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = None

    for p in path_candidates:
        fname = os.path.basename(p)
        test_paths = [
            p,
            os.path.join(base_dir, p),
            os.path.join(base_dir, "assets", "team", fname),
            os.path.join(base_dir, "assets", "logos", fname),
            os.path.join(base_dir, "assets", "logos", fname.replace(" ", "")),
            os.path.join(base_dir, "assets", fname),
            os.path.join(base_dir, "logos", fname),
            os.path.join(base_dir, fname)
        ]
        for tp in test_paths:
            if os.path.exists(tp):
                target_path = tp
                break
        if target_path:
            break

    if not target_path:
        return None

    try:
        im = Image.open(target_path).convert("RGBA")

        alpha = im.split()[-1]
        bbox_alpha = alpha.getbbox()

        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        diff = ImageChops.difference(im, bg)
        diff_gray = diff.convert("L").point(lambda p: 255 if p > 15 else 0)
        bbox_nonwhite = diff_gray.getbbox()

        bbox = None
        if bbox_nonwhite and bbox_alpha:
            bbox = (
                max(bbox_nonwhite[0], bbox_alpha[0]),
                max(bbox_nonwhite[1], bbox_alpha[1]),
                min(bbox_nonwhite[2], bbox_alpha[2]),
                min(bbox_nonwhite[3], bbox_alpha[3])
            )
        elif bbox_nonwhite:
            bbox = bbox_nonwhite
        elif bbox_alpha:
            bbox = bbox_alpha

        if bbox and (bbox[2] > bbox[0]) and (bbox[3] > bbox[1]):
            pad = int(max(im.size) * 0.015)
            w, h = im.size
            b_expanded = (
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(w, bbox[2] + pad),
                min(h, bbox[3] + pad)
            )
            im = im.crop(b_expanded)

        max_w = int(target_canvas[0] * pad_ratio)
        max_h = int(target_canvas[1] * pad_ratio)
        im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", target_canvas, (255, 255, 255, 0))
        offset = ((target_canvas[0] - im.width) // 2, (target_canvas[1] - im.height) // 2)
        canvas.paste(im, offset, im)
        return canvas
    except Exception:
        return target_path

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

available_cycles = [c for c in CHRONOLOGICAL_YEAR_ORDER if c in df["deployment_cycle"].dropna().unique()]
selected_cycles = st.sidebar.multiselect(
    "Deployment Cycles to Compare:",
    options=available_cycles,
    default=available_cycles
)

depth_filter = st.sidebar.radio(
    "Mooring Layer (for Overview Plots):",
    options=["Both Layers", "Surface", "Bottom"]
)

# Clean Parameter Selector (Core verified parameters)
param_choice = st.sidebar.selectbox(
    "Parameter:",
    options=[
        ("temperature_c", "Temperature (°C)"),
        ("do_mg_l", "Dissolved O₂ concentration (mg/L)"),
        ("do_sat_pct", "Dissolved O₂ saturation (%)"),
        ("spec_cond_us_cm", "Specific conductivity (µS/cm)")
    ],
    format_func=lambda x: x[1]
)

# Filter Data for Selected Cycles
df_cycles = df[df["deployment_cycle"].isin(selected_cycles)].copy() if selected_cycles else pd.DataFrame()
df_filtered = df_cycles.copy()
if not df_filtered.empty and depth_filter != "Both Layers":
    df_filtered = df_filtered[df_filtered["mooring_position"] == depth_filter]

# ----------------- PRIMARY NAVIGATION TABS (4 Clean Tabs) -----------------
tab_map, tab_doy, tab_time, tab_team = st.tabs([
    "🗺️ Geographic Setting & Lake Framework",
    "❄️ Annual Limnological Cycle (Aug → Aug)",
    "📈 Continuous Multi-Year Series & Annual Panels",
    "👥 Research Team & Institutional Partners"
])

# ----------------- TAB 1: GEOGRAPHIC SETTING & LAKE FRAMEWORK -----------------
with tab_map:
    col_map, col_chars = st.columns([1.1, 0.9])

    with col_map:
        st.subheader("Station Location & Regional Setting")

        m = folium.Map(
            location=[GREINER_LAT, GREINER_LON],
            zoom_start=9,
            tiles=None
        )

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="🛰️ Satellite Imagery",
            overlay=False,
            control=True
        ).add_to(m)

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
            attr="Esri Topographic, USGS",
            name="🏔️ Topographic / Watershed",
            overlay=False,
            control=True
        ).add_to(m)

        folium.TileLayer(
            tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="&copy; OpenStreetMap contributors",
            name="🗺️ OpenStreetMap (Town & Roads)",
            overlay=False,
            control=True
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

        folium.LayerControl(position="topright", collapsed=True).add_to(m)
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

    # --- FULL-WIDTH SIDE-BY-SIDE EXPANDER STRETCHED ACROSS THE PAGE ---
    st.markdown("---")
    with st.expander("🔍 Click to Expand: RBR maestro³ Sensor & Sub-Surface Mooring Architecture"):
        exp_col1, exp_col2 = st.columns(2)

        with exp_col1:
            st.markdown("#### 1. RBR maestro³ Sensor Architecture")
            st.markdown("Exploded component schematic of the autonomous multiparameter logger recording high-frequency time series.")

            sensor_paths = [
                "ede28e9d-98ae-4aa9-93f5-0267526055bc.png",
                "assets/ede28e9d-98ae-4aa9-93f5-0267526055bc.png",
                "rbr_sensor.png",
                "rbr_maestro_exploded.png"
            ]
            sensor_img = None
            for sp in sensor_paths:
                full_sp = sp if os.path.isabs(sp) else os.path.join(os.path.dirname(os.path.abspath(__file__)), sp)
                if os.path.exists(full_sp):
                    try:
                        sensor_img = Image.open(full_sp)
                        break
                    except Exception:
                        continue

            if sensor_img is not None:
                st.image(
                    sensor_img,
                    caption="Figure: RBR maestro³ exploded view (1-8).",
                    use_container_width=True
                )
            else:
                st.info("Sensor exploded diagram image not found.")

        with exp_col2:
            st.markdown("#### 2. Dual-Depth Mooring Setup")
            st.markdown("Architectural layout of the autonomous mooring array deployed at Surface (~3 m) and Benthic (~7 m) strata.")

            mooring_paths = [
                "Mooring setup.png",
                "assets/Mooring setup.png",
                "mooring_setup.png",
                "mooring_rig.png"
            ]
            mooring_img = None
            for mp in mooring_paths:
                full_mp = mp if os.path.isabs(mp) else os.path.join(os.path.dirname(os.path.abspath(__file__)), mp)
                if os.path.exists(full_mp):
                    try:
                        mooring_img = Image.open(full_mp)
                        break
                    except Exception:
                        continue

            if mooring_img is not None:
                # Balanced height constraint matching the left exploded view
                st.image(
                    mooring_img,
                    caption="Figure: Sub-surface mooring array architecture.",
                    width=420
                )
            else:
                st.info("Mooring setup diagram image not found.")

# ----------------- OBSERVATIONAL PLOTS TABS -----------------
if not selected_cycles:
    st.sidebar.warning("⚠️ Select at least one deployment cycle to display observational data.")
    with tab_doy:
        st.info("👈 Please select one or more deployment cycles from the sidebar to visualize time series.")
    with tab_time:
        st.info("👈 Please select one or more deployment cycles from the sidebar to visualize time series.")
else:
    # ----------------- TAB 2: ANNUAL LIMNOLOGICAL CYCLE (LAKE-YEAR AUG -> AUG) -----------------
    with tab_doy:
        st.subheader(f"1. Integrated Interannual View: {param_choice[1]}")
        st.caption("Lake-year timeline (Aug 1 → Aug 1). Curves start at actual deployment dates and stop at true retrieval without looping.")

        df_main_plot = df_filtered.sort_values(
            by=["deployment_cycle", "mooring_position", "lake_doy"]
        ).copy()

        fig_main = px.line(
            df_main_plot,
            x="lake_doy",
            y=param_choice[0],
            color="deployment_cycle",
            color_discrete_sequence=px.colors.qualitative.Plotly,
            line_dash="mooring_position" if depth_filter == "Both Layers" else None,
            labels={
                "lake_doy": "Lake-year (Aug → Aug)",
                param_choice[0]: param_choice[1],
                "deployment_cycle": "Year",
                "mooring_position": "Layer"
            },
            template="plotly_white"
        )
        fig_main.update_traces(connectgaps=False, line=dict(width=1.8))
        fig_main.update_xaxes(
            tickmode="array",
            tickvals=LAKE_TICKS,
            ticktext=LAKE_TICK_LABELS,
            range=[0, 366],
            showgrid=False
        )
        fig_main.update_yaxes(showgrid=False)
        fig_main.update_layout(height=480, hovermode="x unified")
        st.plotly_chart(fig_main, width="stretch", config=PLOT_EXPORT_CONFIG)

        st.markdown("---")
        st.subheader(f"2. Side-by-Side Stratum Comparison: {param_choice[1]}")
        st.caption("Direct comparison of Surface vs. Bottom (Benthic) layers across the identical Lake-year scale.")

        col_surf, col_bot = st.columns(2)

        y_min = df_cycles[param_choice[0]].min()
        y_max = df_cycles[param_choice[0]].max()
        y_pad = (y_max - y_min) * 0.05 if pd.notnull(y_max) and pd.notnull(y_min) else 1
        y_range = [y_min - y_pad, y_max + y_pad] if pd.notnull(y_min) else None

        with col_surf:
            st.markdown("#### 🌊 Surface Mooring (~2.5–3.5 m)")
            df_surf = df_cycles[df_cycles["mooring_position"] == "Surface"].sort_values(
                by=["deployment_cycle", "lake_doy"]
            )
            if not df_surf.empty:
                fig_surf = px.line(
                    df_surf,
                    x="lake_doy",
                    y=param_choice[0],
                    color="deployment_cycle",
                    color_discrete_sequence=px.colors.qualitative.Plotly,
                    labels={"lake_doy": "Lake-year (Aug → Aug)", param_choice[0]: param_choice[1], "deployment_cycle": "Year"},
                    template="plotly_white"
                )
                fig_surf.update_traces(connectgaps=False, line=dict(width=1.8))
                fig_surf.update_xaxes(tickmode="array", tickvals=LAKE_TICKS, ticktext=LAKE_TICK_LABELS, range=[0, 366], showgrid=False)
                fig_surf.update_yaxes(showgrid=False)
                if y_range:
                    fig_surf.update_yaxes(range=y_range)
                fig_surf.update_layout(height=420, showlegend=True, hovermode="x unified")
                st.plotly_chart(fig_surf, width="stretch", config=PLOT_EXPORT_CONFIG)
            else:
                st.info("No Surface records for the selected cycles.")

        with col_bot:
            st.markdown("#### ⚓ Bottom (Benthic) Mooring (~7.5–9.2 m)")
            df_bot = df_cycles[df_cycles["mooring_position"] == "Bottom"].sort_values(
                by=["deployment_cycle", "lake_doy"]
            )
            if not df_bot.empty:
                fig_bot = px.line(
                    df_bot,
                    x="lake_doy",
                    y=param_choice[0],
                    color="deployment_cycle",
                    color_discrete_sequence=px.colors.qualitative.Plotly,
                    labels={"lake_doy": "Lake-year (Aug → Aug)", param_choice[0]: param_choice[1], "deployment_cycle": "Year"},
                    template="plotly_white"
                )
                fig_bot.update_traces(connectgaps=False, line=dict(width=1.8))
                fig_bot.update_xaxes(tickmode="array", tickvals=LAKE_TICKS, ticktext=LAKE_TICK_LABELS, range=[0, 366], showgrid=False)
                fig_bot.update_yaxes(showgrid=False)
                if y_range:
                    fig_bot.update_yaxes(range=y_range)
                fig_bot.update_layout(height=420, showlegend=True, hovermode="x unified")
                st.plotly_chart(fig_bot, width="stretch", config=PLOT_EXPORT_CONFIG)
            else:
                st.info("No Bottom records for the selected cycles.")

    # ----------------- TAB 3: CONTINUOUS TIME SERIES & ANNUAL PANELS -----------------
    with tab_time:
        st.subheader(f"1. Continuous Multi-Year Series: {param_choice[1]}")
        st.caption("Gap-aware time series. Data gaps between deployment recovery and relaunch are kept broken (no false straight-line interpolation).")

        clean_series_list = []
        for pos in ["Surface", "Bottom"]:
            df_pos = df_filtered[df_filtered["mooring_position"] == pos].sort_values("timestamp")
            if not df_pos.empty:
                full_dates = pd.date_range(df_pos["timestamp"].min(), df_pos["timestamp"].max(), freq="D")
                df_reindexed = df_pos.set_index("timestamp").reindex(full_dates)
                df_reindexed["mooring_position"] = pos
                df_reindexed = df_reindexed.reset_index().rename(columns={"index": "timestamp"})
                clean_series_list.append(df_reindexed)

        if clean_series_list:
            df_clean_cont = pd.concat(clean_series_list, ignore_index=True)
            fig_time = px.line(
                df_clean_cont,
                x="timestamp",
                y=param_choice[0],
                color="mooring_position",
                color_discrete_map={"Surface": "#2b83ba", "Bottom": "#d7191c"},
                labels={"timestamp": "Observation Date", param_choice[0]: param_choice[1], "mooring_position": "Depth Stratum"},
                template="plotly_white"
            )
            fig_time.update_traces(connectgaps=False, line=dict(width=1.6))
            fig_time.update_layout(height=460, hovermode="x unified")
            st.plotly_chart(fig_time, width="stretch", config=PLOT_EXPORT_CONFIG)
        else:
            st.info("No records match the current filter selection.")

        st.markdown("---")
        st.subheader("2. Annual Cycle Decomposition (Dedicated Multi-Year Grid)")
        st.caption("Each deployment cycle displayed in its own dedicated card showing Surface and Bottom strata simultaneously.")

        valid_cycles = [c for c in CHRONOLOGICAL_YEAR_ORDER if c in selected_cycles and c in df["deployment_cycle"].values]

        for i in range(0, len(valid_cycles), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(valid_cycles):
                    cycle_name = valid_cycles[idx]
                    df_year = df[df["deployment_cycle"] == cycle_name].sort_values("timestamp")

                    with cols[j]:
                        st.markdown(f"#### 📅 Cycle: {cycle_name}")

                        if not df_year.empty:
                            fig_panel = px.line(
                                df_year,
                                x="timestamp",
                                y=param_choice[0],
                                color="mooring_position",
                                color_discrete_map={"Surface": "#2b83ba", "Bottom": "#d7191c"},
                                labels={"timestamp": "Date", param_choice[0]: param_choice[1], "mooring_position": "Stratum"},
                                template="plotly_white"
                            )
                            fig_panel.update_traces(connectgaps=False, line=dict(width=1.6))
                            fig_panel.update_layout(
                                height=300,
                                margin=dict(l=20, r=20, t=30, b=20),
                                showlegend=True,
                                hovermode="x unified"
                            )
                            st.plotly_chart(fig_panel, width="stretch", config=PLOT_EXPORT_CONFIG)
                        else:
                            st.info(f"No records available for {cycle_name}.")

# ----------------- TAB 4: RESEARCH TEAM & INSTITUTIONAL PARTNERS -----------------
with tab_team:
    st.subheader("Scientific Research Team")
    st.caption("Autonomous mooring operations, sensor harmonization, and High-Arctic limnological research.")

    col_t1, col_t2, col_t3 = st.columns(3)

    def get_initials(name):
        clean = name.replace("Prof. ", "").replace("Dr. ", "").strip()
        parts = clean.split()
        return f"{parts[0][0]}{parts[-1][0]}".upper()

    def get_circular_avatar_base64(img_paths, size=300, zoom=0.75, top_offset=0.30):
        target_path = None
        base_dir = os.path.dirname(os.path.abspath(__file__))

        for p in img_paths:
            fname = os.path.basename(p)
            test_paths = [
                p,
                os.path.join(base_dir, p),
                os.path.join(base_dir, "assets", "team", fname),
                os.path.join(base_dir, "assets", "logos", fname),
                os.path.join(base_dir, "assets", "logos", fname.replace(" ", "")),
                os.path.join(base_dir, "assets", "team", fname.replace(" ", "%20")),
                os.path.join(base_dir, "assets", fname)
            ]
            for tp in test_paths:
                if os.path.exists(tp):
                    target_path = tp
                    break
            if target_path:
                break

        if not target_path:
            return None

        try:
            im = Image.open(target_path).convert("RGBA")
            w, h = im.size

            min_side = min(w, h)
            crop_size = int(min_side * zoom)
            left = (w - crop_size) // 2
            top = max(0, int((h - crop_size) * top_offset))
            right = left + crop_size
            bottom = top + crop_size

            if bottom > h:
                bottom = h
                top = h - crop_size

            im_square = im.crop((left, top, right, bottom))
            im_square = im_square.resize((size, size), Image.Resampling.LANCZOS)

            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            output.paste(im_square, (0, 0), mask)

            buffered = BytesIO()
            output.save(buffered, format="PNG")
            encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
        except Exception:
            return None

    def display_member(col, name, role, inst, bio, img_keys, zoom=0.75, top_offset=0.30, link_url=None, link_label="Visit Lab Website ↗"):
        with col:
            avatar_b64 = get_circular_avatar_base64(img_keys, zoom=zoom, top_offset=top_offset)

            if avatar_b64:
                avatar_html = f'<img src="{avatar_b64}" class="team-avatar-img" alt="{name}">'
            else:
                initials = get_initials(name)
                avatar_html = f'<div style="background-color:#e2e8f0; border-radius:50%; width:250px; height:250px; margin:0 auto 12px auto; display:flex; align-items:center; justify-content:center; font-size:32px; font-weight:600; color:#475569;">{initials}</div>'

            if link_url:
                btn_element = f'<a href="{link_url}" target="_blank" class="lab-link-btn" style="font-size:12px; font-weight:600;">{link_label}</a>'
            else:
                btn_element = '<div style="height:32px;"></div>'

            card_html = (
                '<div class="profile-card">'
                '<div>'
                f'{avatar_html}'
                f'<div style="font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">{name}</div>'
                f'<div style="font-size: 14px; font-weight: 600; color: #0284c7; margin-bottom: 4px;">{role}</div>'
                f'<div style="font-size: 12.5px; font-weight: 500; color: #475569; margin-bottom: 10px;">{inst}</div>'
                '</div>'
                f'<div style="font-size: 12px; font-weight: 400; color: #64748b; line-height: 1.55; text-align: left; border-top: 1px solid #f1f5f9; paddingTop: 10px; flex-grow: 1;">{bio}</div>'
                f'<div style="margin-top: 10px;">{btn_element}</div>'
                '</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    # Individual custom zoom controls: zoom=0.75 for Mukund & Milla, zoom=0.88 (zoomed out a bit) for Catherine
    display_member(
        col_t1,
        "Mukund R. Gauthankar",
        "Lead Researcher & Ph.D. Candidate",
        "Université du Québec à Chicoutimi (UQAC) / GRIL",
        "Leads autonomous mooring time-series processing, under-ice hydrodynamics, oxygen balance modeling, and microbial food web dynamics.",
        ["Mukund Ramesh Gauthankar.jpg", "mukund.jpg", "mukund.png", "assets/team/Mukund Ramesh Gauthankar.jpg", "assets/team/Mukund%20Ramesh%20Gauthankar.jpg", "assets/mukund.jpg"],
        zoom=0.75, top_offset=0.28
    )

    display_member(
        col_t2,
        "Prof. Milla Rautio",
        "Principal Investigator & Supervisor",
        "UQAC / GRIL / CEN / Canada Research Chair",
        "Senior aquatic ecologist directing the High-Arctic limnological research program in Greiner Lake, focusing on cold-water biogeochemistry and carbon dynamics.",
        ["Milla Rautio.avif", "milla.jpg", "milla.png", "assets/team/Milla Rautio.avif", "assets/team/Milla%20Rautio.avif", "assets/milla.jpg"],
        zoom=0.75, top_offset=0.28,
        link_url="https://www.rautioaqualab.com/",
        link_label="Rautio AquaLab ↗"
    )

    display_member(
        col_t3,
        "Prof. Catherine Girard",
        "Co-Supervisor & Co-Direction",
        "Université Laval / GRIL / Institut nordique du Québec",
        "Specializes in Arctic microbial ecology, environmental genomics, and contaminant bioaccumulation across northern polar aquatic systems.",
        ["Catherine Girard.avif", "catherine.jpg", "catherine.png", "assets/team/Catherine Girard.avif", "assets/team/Catherine%20Girard.avif", "assets/catherine.jpg"],
        zoom=0.88, top_offset=0.22,  # Zoomed out a bit more matching user request
        link_url="https://patrimoinemicrobien.ca/",
        link_label="Patrimoine Microbien ↗"
    )

    st.markdown("---")
    st.subheader("Institutional Affiliations & Research Partners")
    st.caption("Collaborative universities, research groups, laboratories, and polar programs supporting the observatory:")

    def render_native_logo(col, candidate_paths, caption_label):
        with col:
            logo_obj = get_standardized_logo(candidate_paths)
            if logo_obj is not None:
                st.image(logo_obj, caption=caption_label, use_container_width=True)
            else:
                st.info(caption_label)

    # Row 1: Academic & University Consortium (3 Equal Columns)
    r1_c1, r1_c2, r1_c3 = st.columns(3)
    render_native_logo(
        r1_c1,
        ["assets/logos/UQAC_Primary_Logo.png", "assets/logos/uqac.png", "UQAC_Primary_Logo.png"],
        "UQAC (Host Academic Institution)"
    )
    render_native_logo(
        r1_c2,
        ["assets/logos/logo-ulaval.png", "assets/logos/ulaval.png", "logo-ulaval.png"],
        "Université Laval (Co-Direction Partner)"
    )
    render_native_logo(
        r1_c3,
        ["assets/logos/AquaLab Logo.png", "assets/AquaLab Logo.png", "AquaLab Logo.png"],
        "Rautio AquaLab (Limnology & Aquatic Ecology)"
    )

    # Row 2: Specialized Laboratories & Research Consortia (3 Equal Columns)
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    render_native_logo(
        r2_c1,
        ["assets/logos/logo_web_lpm_bleu-1hhh.png", "assets/logos/logo_web_lpm_bleu-1hhh.png", "logo_web_lpm_bleu-1hhh.png"],
        "Laboratoire de patrimoine microbien (Girard Lab)"
    )
    render_native_logo(
        r2_c2,
        ["assets/logos/gril.png", "gril.png"],
        "GRIL (Limnology Research Group)"
    )
    render_native_logo(
        r2_c3,
        ["assets/logos/logo-cen-couleur-color.png", "assets/logos/cen.png", "logo-cen-couleur-color.png"],
        "Centre d'études nordiques (CEN)"
    )

    # Row 3: Polar Operations, Networks & FROST (3 Equal Columns)
    r3_c1, r3_c2, r3_c3 = st.columns(3)
    render_native_logo(
        r3_c1,
        ["assets/logos/polar.png", "assets/logos/polar.webp", "polar.png", "polar.webp"],
        "Polar Knowledge Canada (POLAR / CHARS)"
    )
    render_native_logo(
        r3_c2,
        ["assets/logos/arcticnet.png", "arcticnet.png"],
        "ArcticNet (Network of Centres of Excellence)"
    )
    render_native_logo(
        r3_c3,
        [
            "assets/logos/FROST Logo Sami.avif",
            "assets/logos/FROST Logo Sami.png",
            "assets/logos/frost.png",
            "FROST Logo Sami.avif",
            "FROST Logo Sami.png"
        ],
        "FROST Research Program"
    )

    st.markdown("---")
    st.markdown("#### 🏛️ Canadian High Arctic Research Station (CHARS Campus)")

    chars_paths = [
        "assets/logos/chars-campus.png",
        "assets/logos/chars-campus.jpg",
        "assets/logos/chars.jpg",
        "chars-campus.png",
        "chars-campus.jpg"
    ]
    chars_img = None
    for cp in chars_paths:
        fname = os.path.basename(cp)
        test_cp = [
            cp,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), cp),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logos", fname),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logos", fname.replace(" ", "")),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logos", fname.replace(" ", "%20")),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", fname)
        ]
        for tp in test_cp:
            if os.path.exists(tp):
                try:
                    chars_img = Image.open(tp)
                    break
                except Exception:
                    continue
        if chars_img:
            break

    if chars_img is not None:
        st.image(
            chars_img,
            caption="Canadian High Arctic Research Station (CHARS) Campus, Cambridge Bay (Iqaluktuuttiaq), Nunavut — Base of operations for Greiner Lake limnological campaigns.",
            use_container_width=True
        )

    st.markdown("""
<div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-top: 10px; margin-bottom: 14px;">
    <div style="font-size: 14.5px; font-weight: 600; color: #0f172a; margin-bottom: 4px;">
        Canadian High Arctic Research Station (CHARS)
    </div>
    <div style="font-size: 12.5px; color: #0284c7; font-weight: 600; margin-bottom: 8px;">
        📍 1 Uvajuq Rd., Cambridge Bay (Iqaluktuuttiaq), Nunavut X0B 0C0, Canada
    </div>
    <div style="font-size: 13px; color: #475569; line-height: 1.55;">
        Operated by <strong>Polar Knowledge Canada (POLAR)</strong>. Serves as the primary operational base and year-round staging campus for Greiner Lake limnological campaigns, providing specialized cold-room analytical laboratories, sensor calibration facilities, and winter snowmobile/open-water boat transit logistics across the Kitikmeot Region.
    </div>
</div>
""", unsafe_allow_html=True)
