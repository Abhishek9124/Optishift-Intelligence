# How to Run — OptiShift Intelligence

---

## Prerequisites

- Python 3.10+
- Virtual environment (`.venv`) already set up in the project root

---

## 1. Activate Virtual Environment

Open **PowerShell** and run:

```powershell
cd "c:\Users\ADMIN\OneDrive\Desktop\Optishift Intelligence"
.venv\Scripts\Activate.ps1
```

> **If you get a permission error**, run this first:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

---

## 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

## 3. Run the Main Dashboard

```powershell
streamlit run streamlit_app.py
```

Opens at: **http://localhost:8501**

### Tabs Available:
| # | Tab | Description |
|---|-----|-------------|
| 1 | 📈 Forecasting | Model metrics, holdout evaluation, N-day forecast |
| 2 | 🧭 Executive Intelligence | Daily leave dashboard, staffing planner |
| 3 | 🔵 Special Leave & Comp-Off | Non-operational leave tracking |
| 4 | 🏭 Cost Centre Analysis | Employee segregation by cost centre |
| 5 | 📊 Planned vs Unplanned | Leave planning analysis |
| 6 | 🔍 Leave Reason & Prediction | Leave reasons + prediction context |
| 7 | 📈 Daily CC Leave | Daily employee count by cost centre with slicers |
| 8 | 🗓️ Indian Festival Calendar | Full Indian festival calendar (2020-2030) |

---

## 4. Run the Generalized Model Dashboard

```powershell
cd generalized_model
streamlit run streamlit_app.py
```

Opens at: **http://localhost:8501**

### How to use:
1. Click **📂 Upload Leave CSV** in the sidebar
2. Upload any CSV with columns: `EmpNo`, `From Date`, `To Date`, `Status`
3. Click **🚂 Train Model**
4. View forecast, data explorer, cost centre analysis, festival calendar

---

## 5. Train Generalized Model via CLI (Optional)

```powershell
cd generalized_model
python train_model.py --data "path\to\your\leave_data.csv" --output artifacts --forecast-horizon 30
```

---

## 6. Retrain the Main Model (Optional)

```powershell
python retrain_model.py
```

Or with a specific cutoff date:

```powershell
python retrain_model.py --as-of-date 2026-03-20 --forecast-horizon 60
```

---

## Quick Reference

| What | Command |
|------|---------|
| Activate venv | `.venv\Scripts\Activate.ps1` |
| Run main app | `streamlit run streamlit_app.py` |
| Run generalized app | `cd generalized_model && streamlit run streamlit_app.py` |
| Install deps | `pip install -r requirements.txt` |
| Retrain model | `python retrain_model.py` |
| Train generalized | `python generalized_model\train_model.py --data Data\Combined_All_Leave_Data.csv` |
