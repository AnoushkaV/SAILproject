# SAIL2025 Crowd Monitoring Dashboard

TIL6022 Python Programming – Group 25

## Project overview

SAIL Amsterdam is the largest free maritime event in the world. During SAIL2025 (20–24 August 2025), large crowds gathered along the IJ and in the city centre. Crowd managers need to see quickly where it is getting crowded and when the situation changes.

This project turns the LVMA pedestrian counts of SAIL2025 into indicators of pedestrian pressure (flow per metre of effective walking width) and sudden changes, and presents them in an interactive dashboard for monitoring during an event and for evaluation afterwards.

## Research questions

**Main question:** How can LVMA pedestrian counts be translated into a dashboard that helps crowd managers identify peak flows and sudden changes during SAIL2025?

1. **Peaks:** At which locations and times were the highest pedestrian flows recorded during SAIL2025, in absolute terms and per metre of effective walking width?
2. **Temporal patterns:** How did pedestrian flows change across event days and periods of the day?
3. **Sudden changes:** Where and when did sudden increases or decreases in pedestrian flow occur, compared with the preceding 15 minutes at each sensor, and how useful are these signals?
4. **Decision support:** How can these patterns and sudden changes be presented so that crowd managers can quickly and correctly see where and when attention is needed?

## Data

| File | Content |
|---|---|
| `SAIL2025_LVMA_data_3min_20August-25August2025_flow.csv` | Pedestrian counts per sensor and walking direction, per 3 minutes (20–24 August 2025) |
| `sensor-location.xlsx` | Sensor locations and effective walking widths |

The data was provided by the course (TIL6022, SAIL2025 project data) and is **confidential**. It is therefore **not included** in this repository. To reproduce the analysis, place both files in the `Data/` folder. All other data files are created by the notebooks.

## Repository structure

```text
SAILproject/
├── README.md                          # This file
├── requirements.txt                   # Python packages for all notebooks and the dashboard
├── project_proposal.ipynb / .pdf      # Project proposal
├── final_report.ipynb / .pdf          # Final report (notebook and PDF export)
│
├── Data/
│   ├── SAIL2025_cleaned.ipynb         # Step 1: inspection and cleaning of the counts
│   ├── sensor-location_cleaned.ipynb  # Step 2: cleaning of the sensor locations
│   └── indicators/                    # Output of step 4 (created by the notebook)
│
├── step4/
│   └── SAIL2025_indicators_step4.ipynb   # Step 3–4: flow indicators per sensor and interval
│
├── step8/
│   └── step8_robustness.ipynb         # Step 8: robustness checks (report section 4.8, tables 5.2–5.4)
│
└── Dashboard/                         # Interactive dashboard (Dash/Plotly)
    ├── README.md                      # Dashboard documentation (features, settings, limitations)
    ├── app.py                         # Start the dashboard
    ├── config.py                      # All thresholds, colours and parameters
    ├── sail_data.py                   # Loading data, indicators, data quality
    ├── sail_analysis.py               # Pressure levels, peaks, sudden changes
    ├── figures.py, alerts_tab.py      # Charts and alert pop-ups
    └── check_data.py                  # Quick check of the data without a browser
```

## How to reproduce the analysis

**1. Install the packages** (tested with Python 3.14):

```bash
python -m pip install -r requirements.txt
```

**2. Add the data:** put the two data files in `Data/` (see *Data* above).

**3. Run the notebooks in this order** (each with *Run All*):

1. `Data/SAIL2025_cleaned.ipynb` – creates `Data/SAIL2025_LVMA_cleaned.csv`
2. `Data/sensor-location_cleaned.ipynb`
3. `step4/SAIL2025_indicators_step4.ipynb` – creates the tables in `Data/indicators/`
4. `step8/step8_robustness.ipynb` – reproduces the robustness checks and compares them with the report

**4. Start the dashboard:**

```bash
cd Dashboard
python app.py
```

Then open http://127.0.0.1:8050 in your browser. For the dashboard's features, settings, live mode and known limitations, see the [Dashboard README](Dashboard/README.md).

## Authors

- Anoushka Verhoeven
- Nouschka van der Werff
- Julia Dwarswaard
- Lieve Schrijver
- Laure van der Pouw

The individual contributions are described in the author contribution statement of the final report.

## Notes

The dashboard uses the recorded SAIL2025 measurements in a replay mode that only shows what was known at the selected moment. The live mode re-reads the data source every three minutes, but does not connect to a real-time data feed by itself; that would require a live data source.
