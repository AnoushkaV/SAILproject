
# SAIL2025 Crowd Monitoring Dashboard

## Project overview

SAIL Amsterdam is a large public event that draws many visitors. Monitoring pedestrian flows can help crowd managers identify busy locations and respond to sudden changes in crowd conditions.

This project analyses pedestrian counts collected during SAIL2025 (20–24 August 2025) and develops an interactive dashboard to visualise crowd patterns at selected sensor locations. The dashboard needs to help crowd managers during an event and the evaluation of crowd conditions afterwards.

## Research objective and questions

The objective is to develop a dashboard that helps crowd managers identify peak pedestrian flows and sudden changes in pedestrian flows at sensor locations during SAIL2025.

The subresearch questions are:

1.  Peaks: At which locations and times were the highest pedestrian flows recorded during SAIL2025,     in absolute terms and per metre of effective walking width?
2.  Temporal patterns: How did pedestrian flows change across event days and periods of the day?
3.  Sudden changes: Where and when did sudden increases or decreases in pedestrian flow occur,          compared with the preceding 15 minutes at each sensor, and how useful are these signals?
4.  Decision support: How can these patterns and sudden changes be presented so that crowd managers     can quickly and correctly see where and when attention is needed?


## Data and analysis

The project uses LVMA pedestrian counts recorded at three-minute intervals and a sensor-location dataset containing sensor coordinates and effective pedestrian widths.

The analysis includes inspecting and cleaning the measurements, linking pedestrian counts to sensor locations, calculating flow indicators, identifying peaks and sudden changes, and presenting the results in the dashboard.

The datasets and preprocessing notebooks are in `Data/`. The notebook for calculating indicators is in `step4/`.

## Repository structure

```text
SAILproject/
│
├── README.md                       # General project information
│
├── project_proposal.ipynb          # Project proposal and research plan
├── project_proposal.pdf            # PDF version of the project proposal
│
├── final_report.ipynb              # Final project report and analysis
├── final_report.pdf                # PDF version of the final report
│
├── Data/                           # Datasets and data-cleaning notebooks
│
├── step4/                          # Pedestrian-flow indicator calculations
│
└── Dashboard/                      # Interactive dashboard and Python code
    ├── README.md                   # Detailed dashboard documentation
    ├── app.py                      # Dashboard application
    └── requirements.txt            # Python dependencies
```

## How to run the project

The analysis is documented in the Jupyter notebooks in the repository. Start with the notebooks in `Data/` for data preparation and then use `step4/SAIL2025_indicators_step4.ipynb` for the flow indicators.

To start the interactive dashboard, open a terminal in the repository's main folder and run:

```bash
python -m pip install -r Dashboard/requirements.txt
cd Dashboard
python app.py
```

Then open http://127.0.0.1:8050 in your browser.

For the dashboard's features, settings, alternative running modes and known limitations, see the [Dashboard README](Dashboard/README.md).

## Project team

- Anoushka Verhoeven
- Nouschka van der Werff
- Julia Dwarswaard
- Lieve Schrijver
- Laure van der Pouw

Individual contributions are described in the project proposal notebook.

## Notes

The dashboard uses historical SAIL2025 measurements for replay and evaluation. Its live mode does not automatically connect to a real-time data feed. This would need an appropriate live data source.
