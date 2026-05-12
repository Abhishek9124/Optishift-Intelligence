# Optishift Intelligence

Optishift Intelligence is a Streamlit-based leave analytics and forecasting system. It cleans leave data, builds calendar-aware forecasting features, loads trained model artifacts, and serves an interactive dashboard for workforce planning.

## Primary App

The main runnable app in this repository is:

- `streamlit_app.py`

Supporting runtime files used by that app:

- `requirements.txt`
- `indian_calendar.py`
- `retrain_model.py`
- `main.py`
- `tests/`

## What To Push To GitHub

Push these files and folders:

- `streamlit_app.py`
- `requirements.txt`
- `indian_calendar.py`
- `retrain_model.py`
- `main.py`
- `tests/`
- `README/` if you want to keep the project notes and data-cleaning documentation
- `generalized_model/`
- `.gitignore`
- `README.md`

## What Not To Push

These are local, generated, or too large / environment-specific and should usually stay out of GitHub:

- `.venv/`
- `.vscode/`
- `__pycache__/`
- `artifacts/`
- `output/`
- `Images/`
- `Data/`
- `Employee_Leave_Data/`
- `employee-leave-forecasting-system/` if it is only an old nested copy
- large top-level `.csv` and `.xlsx` files unless you intentionally want to distribute sample data

## Important Runtime Inputs

The main app expects these files at runtime:

- `Data/Combined_All_Leave_Data.csv`
- `Employee Master - Feb 2026 Team Member.xlsx`
- trained model files inside `artifacts/`

The app reads them from these paths:

- `Data/Combined_All_Leave_Data.csv`
- `Employee Master - Feb 2026 Team Member.xlsx`
- `artifacts/leave_forecasting_*.pkl` and matching metadata files

Because your current `.gitignore` excludes `Data/`, `artifacts/`, and `*.xlsx`, the receiving machine will not get them from GitHub unless you:

1. Upload them separately after clone.
2. Store them with Git LFS.
3. Share them through cloud storage and place them in the expected folders.

## Fresh Installation

Important: installation on the other side will work only if the required data files and model artifact files are pasted into this project after cloning. GitHub will not provide those files with the current `.gitignore` rules.

### 1. Clone the repository

```powershell
git clone <your-repo-url>
cd "Optishift Intelligence"
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Add the required data and model files

Create the runtime folders if they do not already exist:

```powershell
mkdir Data
mkdir artifacts
```

Then place these files manually:

- `Data/Combined_All_Leave_Data.csv`
- `Employee Master - Feb 2026 Team Member.xlsx`
- the latest trained model `.pkl` file in `artifacts/`
- the matching model metadata `.pkl` file in `artifacts/`

You must paste these files into the project folders exactly as listed above before running the app.

Recommended artifact pair:

- `artifacts/leave_forecasting_xgboost_20260417_042602.pkl`
- `artifacts/leave_forecasting_xgboost_20260417_042602_metadata.pkl`

The app is already written to auto-pick the latest versioned model from `artifacts/` when those files are present.

### 5. Run the dashboard

```powershell
streamlit run streamlit_app.py
```

## Optional: Retrain The Model

If the receiving machine has the source dataset, it can generate fresh artifacts locally:

```powershell
python retrain_model.py
```

After retraining, run:

```powershell
streamlit run streamlit_app.py
```

## Recommended GitHub Structure

For a clean installable repository, keep this structure:

```text
Optishift Intelligence/
|-- README.md
|-- .gitignore
|-- requirements.txt
|-- streamlit_app.py
|-- indian_calendar.py
|-- retrain_model.py
|-- main.py
|-- tests/
|-- README/
|-- generalized_model/
|-- Data/                       # local or separately shared
|-- artifacts/                  # local or separately shared
```

## Notes

- `streamlit_app.py` is the best entry point for the current system.
- `streamlit_app_1.py` looks like an alternate copy, not the main deployment target.
- `generalized_model/` is included in the repository as an additional workflow/module set.
- On the receiving machine, the data files and model files must be pasted manually into `Data/` and `artifacts/` unless you distribute them separately through Git LFS or shared storage.
- If you want the project to work immediately after `git clone`, you should either commit sample data and artifacts intentionally, or provide a download link and setup script.
