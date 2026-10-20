# 🧊 Greiner Lake High-Arctic Limnological Observatory

An interactive, web-based limnological observatory dashboard visualizing multi-year continuous autonomous mooring time series (2017–2026) from Greiner Lake (*Iqaluktuuttiaq* / Cambridge Bay, Victoria Island, Nunavut, Canada).

---

## 📌 Observatory Station Overview
* **Coordinates:** 69°10'37.44'' N, 104°55'53.15'' W
* **System Type:** High-Arctic Cold Monomictic Lake
* **Max Depth:** ~12.0–12.3 m (Main Basin Mooring Station)
* **Mean Depth:** 3.0 m (~39% of lake area < 2.0 m)
* **Ice Cover Duration:** 7–9 months annually (late September to mid-July; peak thickness ~215 cm)

---

## 🔬 Core Capabilities
* **Geographic & Morphometric Setting:** Interactive satellite station mapping coupled with high-resolution lake basin bathymetry and environmental factsheets.
* **Annual Limnological Progression:** Inter-annual day-of-year cycle overlay tracking under-ice dynamics across the hydrological year (August 1 to July 31).
* **Multi-Parameter Mooring Records:** Continuous time series of Dissolved Oxygen (mg/L, % sat), In Situ Water Temperature (°C), Specific Conductivity (µS/cm), Depth (m), and PAR (µmol/m²/s).
* **Vertical Stratification Gradients:** Dual-layer surface vs. bottom differential analysis ($\Delta T$, $\Delta \text{DO}$) evaluating inverse winter thermal stratification and seasonal benthic oxygen drawdown.
* **Data Export:** Integrated portal export allowing researchers to download filtered multi-year subsets.

---

## 📂 Repository Architecture
* `app.py`: Main Streamlit application and interactive visualization interface.
* `greiner_lake_daily_summary.csv`: Consolidated, QC-cleaned daily mean mooring time series (2017–2026).
* `GRL BATHY  PNG.png`: High-resolution bathymetric contour chart and mooring station array.
* `requirements.txt`: Python package dependencies for cloud deployment.

---

## 🚀 Local Execution
To run this dashboard locally:
```bash
git clone [https://github.com/](https://github.com/)<YOUR_GITHUB_USERNAME>/greiner-lake-portal.git
cd greiner-lake-portal
pip install -r requirements.txt
streamlit run app.py
