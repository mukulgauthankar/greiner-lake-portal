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
    /* Exactly Equal Profile Cards */
    .profile-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 22px 18px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        height: 390px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
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

# Helper to normalize logos onto a uniform bounding canvas while preserving native st.image enlarge
@st.cache_data
def get_standardized_logo(path_candidates, target_size=(500, 220)):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = None

    for p in path_candidates:
        fname = os.path.basename(p)
        test_paths = [
            p,
            os.path.join(base_dir, p),
            os.path.join(base_dir, "assets", "logos", fname),
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
        im.thumbnail(target_size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", target_size, (255, 255, 255, 0))
        offset = ((target_size[0] - im.width) // 2, (target_size[1] - im.height) // 2)
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

# ----------------- PRIMARY NAVIGATION TABS (4 Clean Tabs) -----------------
tab_map, tab_doy, tab_time, tab_team = st.tabs([
    "🗺️ Geographic Setting & Lake Framework",
    "❄️ Annual Limnological Cycle (Aug → Jul)",
    "📈 Continuous Multi-Year Series",
    "👥 Research Team & Institutional Partners"
])

# ----------------- TAB 1: GEOGRAPHIC SETTING & LAKE FRAMEWORK -----------------
with tab_map:
    col_map, col_chars = st.columns([1.1, 0.9])

    with col_map:
        st.subheader("Station Location & Regional Setting")

        # Initialize map with tiles=None so custom layers use clean human-readable names
        m = folium.Map(
            location=[GREINER_LAT, GREINER_LON],
            zoom_start=9,
            tiles=None
        )

        # Layer 1: Esri Satellite Imagery
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Satellite Imagery",
            overlay=False,
            control=True
        ).add_to(m)

        # Layer 2: OpenStreetMap (Street & Topographic view)
        folium.TileLayer(
            tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="&copy; OpenStreetMap contributors",
            name="OpenStreetMap (Street/Topo)",
            overlay=False,
            control=True
        ).add_to(m)

        # Markers
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

        # Add clean Layer Switcher (displays 'Satellite Imagery' and 'OpenStreetMap', no raw URLs!)
        folium.LayerControl(position="topright", collapsed=False).add_to(m)

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

# ----------------- TAB 4: RESEARCH TEAM & INSTITUTIONAL PARTNERS -----------------
with tab_team:
    st.subheader("Scientific Research Team")
    st.caption("Autonomous mooring operations, sensor harmonization, and High-Arctic limnological research.")

    col_t1, col_t2, col_t3 = st.columns(3)

    def get_initials(name):
        clean = name.replace("Prof. ", "").replace("Dr. ", "").strip()
        parts = clean.split()
        return f"{parts[0][0]}{parts[-1][0]}".upper()

    def display_member(col, name, role, inst, bio, img_keys, link_url=None, link_label="Visit Lab Website ↗"):
        with col:
            photo_found = None
            for ik in img_keys:
                if os.path.exists(ik):
                    try:
                        photo_found = Image.open(ik)
                        break
                    except Exception:
                        continue

            # Avatar or Photo
            if photo_found is not None:
                st.image(photo_found, use_container_width=True)
            else:
                initials = get_initials(name)
                st.markdown(
                    f'<div style="background-color:#e2e8f0; border-radius:50%; width:100px; height:100px; margin:0 auto; display:flex; align-items:center; justify-content:center; font-size:32px; font-weight:600; color:#475569;">{initials}</div>',
                    unsafe_allow_html=True
                )

            # Button element or height placeholder
            if link_url:
                btn_element = f'<a href="{link_url}" target="_blank" class="lab-link-btn" style="font-size:12px; font-weight:600;">{link_label}</a>'
            else:
                btn_element = '<div style="height:32px;"></div>'

            card_html = (
                '<div class="profile-card" style="margin-top: 10px;">'
                '<div>'
                f'<div style="font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">{name}</div>'
                f'<div style="font-size: 14px; font-weight: 600; color: #0284c7; margin-bottom: 4px;">{role}</div>'
                f'<div style="font-size: 12.5px; font-weight: 500; color: #475569; margin-bottom: 10px;">{inst}</div>'
                '</div>'
                f'<div style="font-size: 12px; font-weight: 400; color: #64748b; line-height: 1.55; text-align: left; border-top: 1px solid #f1f5f9; padding-top: 10px; flex-grow: 1;">{bio}</div>'
                f'<div style="margin-top: 10px;">{btn_element}</div>'
                '</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    display_member(
        col_t1,
        "Mukund R. Gauthankar",
        "Lead Researcher & Ph.D. Candidate",
        "Université du Québec à Chicoutimi (UQAC) / GRIL",
        "Leads autonomous mooring time-series processing, under-ice hydrodynamics, oxygen balance modeling, and microbial food web dynamics.",
        ["assets/logos/mukund.jpg", "assets/mukund.jpg", "mukund.jpg"]
    )

    display_member(
        col_t2,
        "Prof. Milla Rautio",
        "Principal Investigator & Supervisor",
        "UQAC / GRIL / CEN / Canada Research Chair",
        "Senior aquatic ecologist directing the High-Arctic limnological research program in Greiner Lake, focusing on cold-water biogeochemistry and carbon dynamics.",
        ["assets/logos/milla.jpg", "assets/milla.jpg", "milla.jpg"],
        link_url="https://www.rautioaqualab.com/",
        link_label="Rautio AquaLab ↗"
    )

    display_member(
        col_t3,
        "Prof. Catherine Girard",
        "Co-Supervisor & Co-Direction",
        "Université Laval / GRIL / Institut nordique du Québec",
        "Specializes in Arctic microbial ecology, environmental genomics, and contaminant bioaccumulation across northern polar aquatic systems.",
        ["assets/logos/catherine.jpg", "assets/catherine.jpg", "catherine.jpg"],
        link_url="https://patrimoinemicrobien.ca/",
        link_label="Patrimoine Microbien ↗"
    )

    st.markdown("---")
    st.subheader("Institutional Affiliations & Research Partners")
    st.caption("Collaborative universities, northern research facilities, and scientific programs supporting the observatory:")

    def render_native_logo(col, candidate_paths, caption_label):
        with col:
            logo_obj = get_standardized_logo(candidate_paths)
            if logo_obj is not None:
                st.image(logo_obj, caption=caption_label, use_container_width=True)
            else:
                st.info(caption_label)

    # Row 1: Academic & University Consortium (4 Equal Columns)
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
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
        ["assets/logos/logo-cen-couleur-color.png", "assets/logos/cen.png", "logo-cen-couleur-color.png"],
        "Centre d'études nordiques (CEN)"
    )
    render_native_logo(
        r1_c4,
        ["assets/logos/gril.png", "gril.png"],
        "GRIL (Limnology Research Group)"
    )

    # Row 2: Polar Operations, Networks & FROST (3 Equal Columns)
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    render_native_logo(
        r2_c1,
        ["assets/logos/polar.png", "polar.png"],
        "Polar Knowledge Canada (POLAR / CHARS)"
    )
    render_native_logo(
        r2_c2,
        ["assets/logos/arcticnet.png", "arcticnet.png"],
        "ArcticNet (Network of Centres of Excellence)"
    )
    render_native_logo(
        r2_c3,
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
        "assets/logos/chars-campus.jpg",
        "assets/logos/chars.jpg",
        "chars-campus.jpg"
    ]
    chars_img = None
    for cp in chars_paths:
        fname = os.path.basename(cp)
        test_cp = [
            cp,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), cp),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logos", fname),
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
