import os
import csv
from datetime import datetime
import pandas as pd
import pyodbc
from waterscopequery import waterscope_data
from PIChartFunctions import PiDataRetrival

# Configuration (fixed for FY2023-24)
DATA_DIR      = os.path.join(os.path.dirname(__file__), 'Data')
SITE_FILE     = os.path.join(DATA_DIR, 'sitedata.csv')
START_DATE    = datetime.fromisoformat('2023-07-01')
END_DATE      = datetime.fromisoformat('2024-06-30')
OUTPUT_CSV    = os.path.join(os.path.dirname(__file__), 'site_monthly_loadings.csv')
CONN_STR      = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=SAWpSQL20;DATABASE=WaterScope;Trusted_Connection=yes"
)


def load_sites(site_file):
    """
    Load site metadata from CSV into a DataFrame.
    Expected columns: SamplingPointID, SystemName, Report Name
    """
    rows = []
    with open(site_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                'report_name': row.get('Report Name', '').strip(),
                'samplingpoint_id': row.get('SamplingPointID', '').strip(),
                'system_name': row.get('SystemName', '').strip()
            })
    return pd.DataFrame(rows)


def get_monthly_discharge(system_name, start_dt, end_dt):
    """
    Fetch and sum monthly "Discharge to Environment" (ML).
    For site Bird-In-Hand, lookup as "Bird In Hand" in PI.
    """
    lookup_name = system_name
    if system_name == 'Bird-In-Hand WWTP':
        lookup_name = 'Bird In Hand WWTP'

    raw = PiDataRetrival(lookup_name)
    if raw.empty:
        return pd.DataFrame(columns=['Month', 'Discharge to Environment'])

    raw['Timestamp'] = pd.to_datetime(raw['Timestamp'])
    df = raw.loc[(raw['Timestamp'] >= start_dt) & (raw['Timestamp'] <= end_dt)]
    df['Month'] = df['Timestamp'].dt.to_period('M').dt.to_timestamp()
    monthly = (
        df
        .pivot_table(
            index='Month',
            columns='Attribute',
            values='Value',
            aggfunc='sum'
        )
        .rename(columns={'5 - Discharge to Environment': 'Discharge to Environment'})
        .reset_index()
    )
    if 'Discharge to Environment' not in monthly:
        monthly['Discharge to Environment'] = 0
    return monthly[['Month', 'Discharge to Environment']]


def calculate_loadings(site_df, conn_str, start_dt, end_dt, output_file):
    """
    For each site, component, and month, calculate loading,
    discharge, and concentration over the period.
    Outputs a CSV with Month-level records.
    """
    components = [
        'Biochemical Oxygen Demand',
        'Copper - Total',
        'Lead - Total',
        'Nitrogen - Total',
        'Phosphorus - Total',
        'Suspended Solids',
        'Zinc - Total'
    ]
    records = []
    conn = pyodbc.connect(conn_str, autocommit=True)

    for site in site_df['report_name'].unique():
        subset = site_df[site_df['report_name'] == site]
        pids = subset['samplingpoint_id'].dropna().tolist()
        system_name = subset['system_name'].iloc[0]

        sampling_data = pd.DataFrame([
            {'SamplingPointID': pid, 'ComponentName': comp, 'Site': site}
            for pid in pids for comp in components
        ])

        # Fetch water quality data for FY
        fy_start = START_DATE.year if START_DATE.month >= 7 else START_DATE.year - 1
        raw = waterscope_data(conn, sampling_data, site, fy_start, 1)
        if raw.empty:
            continue
        raw = raw[(raw['Timestamp'] >= start_dt) & (raw['Timestamp'] <= end_dt)]

        # Get monthly discharge (handles Bird-In-Hand mapping)
        monthly_flow = get_monthly_discharge(system_name, start_dt, end_dt)

        for comp in components:
            comp_data = raw[raw['Attribute'] == comp].copy()
            if comp_data.empty:
                continue
            comp_data['Month'] = comp_data['Timestamp'].dt.to_period('M').dt.to_timestamp()
            # Compute monthly average concentration
            conc_month = comp_data.groupby('Month')['Value'].mean().rename('Concentration_mg_L')
            df_month = (
                conc_month.to_frame()
                .reset_index()
                .merge(monthly_flow, on='Month', how='left')
                .fillna(0)
            )
            # Calculate loading per month (tonnes)
            df_month['Loading_tonnes'] = df_month['Concentration_mg_L'] * df_month['Discharge to Environment']

            # Append monthly records
            for _, row in df_month.iterrows():
                records.append({
                    'Site': site,
                    'Component': comp,
                    'Month': row['Month'].strftime('%Y-%m'),
                    'Loading_tonnes': row['Loading_tonnes'],
                    'Discharge_ML': row['Discharge to Environment'],
                    'Concentration_mg_L': row['Concentration_mg_L']
                })

    conn.close()
    pd.DataFrame(records).to_csv(output_file, index=False)
    print(f"Monthly loadings written to {output_file}")


if __name__ == '__main__':
    sites = load_sites(SITE_FILE)
    calculate_loadings(sites, CONN_STR, START_DATE, END_DATE, OUTPUT_CSV)
