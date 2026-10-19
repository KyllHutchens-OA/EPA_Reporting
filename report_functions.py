# report_functions.py
import calendar

import os
import csv
import pandas as pd
from datetime import datetime,timedelta
import io
import pandas as pd
import plotly.graph_objects as go
from waterscopequery import waterscope_data
import pyodbc
import pytz
import warnings
warnings.filterwarnings("ignore")

# Paths to your Data folder and CSVs
BASE_DIR     = os.path.dirname(__file__)
DATA_DIR     = os.path.join(BASE_DIR, 'Data')
SITE_FILE    = os.path.join(DATA_DIR, 'sitedata.csv')
DETAILS_FILE = os.path.join(DATA_DIR, 'reportdetails.csv')
SAAM_FILE  = os.path.join(DATA_DIR, 'SAAMData.csv')

def load_sites():
    """
    Read sitedata.csv into a list of dicts, sorted by report_name alphabetically.
    Each dict has keys: samplingpoint_id, system_name, location_type, report_name, saam_name
    """
    sites = []
    if not os.path.exists(SITE_FILE):
        return sites

    with open(SITE_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sites.append({
                'samplingpoint_id': (row.get('SamplingPointID') or '').strip(),
                'system_name':       (row.get('SystemName') or '').strip(),
                'location_type':     (row.get('Location Type') or '').strip(),
                'report_name':       (row.get('Report Name') or '').strip(),
                'saam_name':         (row.get('SAAM Name') or '').strip()
            })

    sites.sort(key=lambda s: s['report_name'].lower())
    return sites

def create_flow_charts(pi_name, start_dt, end_dt, report_name, ys, ye):
    """
    Returns:
      df_table: DataFrame with columns Month, Influent, Effluent, Reuse, Discharge
      images:   dict mapping each metric to a BytesIO PNG
    """
    import io
    import pandas as pd
    import plotly.graph_objects as go
    import pytz
    from PIChartFunctions import PiDataRetrival, calculate_5_year_average # The 5 year data has a cut-off '2023-07-01' ?????

    adtz = pytz.timezone("Australia/Adelaide")
    def to_adtz(ts):
        ts = pd.Timestamp(ts)
        return ts.tz_localize(adtz) if ts.tzinfo is None else ts.tz_convert(adtz)
    # 1) fetch raw PI data

    if pi_name.strip().lower() == 'mount burr wwtp':
        pi_name = 'Mount Burr WWWTP'

    raw = PiDataRetrival(pi_name)

        
    raw["Timestamp"] = pd.to_datetime(raw["Timestamp"])

    # 2) Replacement data for Attribute = 3 - Reuse

    TARGET_SITE = "Finger Point WWTP"
    # Only build/apply reuse adjustments when we are on the target site
    if pi_name == TARGET_SITE:
        reuse_data = pd.DataFrame({
            "Site": [TARGET_SITE] * 8,
            "Attribute": ["3 - Reuse"] * 8,
            "Timestamp": ["2024-07-01", "2024-12-01", "2025-04-01", "2025-06-01","2023-11-01","2023-12-01","2024-01-01","2024-02-01"],
            "Value": [0.14, 0.42, 0.01, 0.03,0.25,0.25,0.25,0.25]
        })
        reuse_data["Timestamp"] = pd.to_datetime(reuse_data["Timestamp"])

        # Step 1: replace "3 - Reuse" for this site at those timestamps
        ts_match = set(reuse_data["Timestamp"])
        mask_old_reuse = (
            (raw["Site"] == TARGET_SITE) &
            (raw["Attribute"] == "3 - Reuse") &
            (raw["Timestamp"].isin(ts_match))
        )
        raw = raw[~mask_old_reuse]
        raw = pd.concat([raw, reuse_data], ignore_index=True)

        # Step 2: subtract reuse from "5 - Discharge to Environment" (match on Site+Timestamp)
        mask_discharge = (
            (raw["Site"] == TARGET_SITE) &
            (raw["Attribute"] == "5 - Discharge to Environment")
        )
        sub = (
            raw.loc[mask_discharge, ["Site", "Timestamp", "Value"]]
            .merge(reuse_data[["Site", "Timestamp", "Value"]]
                    .rename(columns={"Value": "ReuseValue"}),
                    on=["Site", "Timestamp"], how="left")
        )
        raw.loc[mask_discharge, "Value"] = (sub["Value"] - sub["ReuseValue"].fillna(0)).values
    else:
        # Not the Finger Point dataset: skip any reuse adjustments entirely
        pass


    TARGET_SITE2 = "Normanville WWTP"
    # Only build/apply reuse adjustments when we are on the target site
    if pi_name == TARGET_SITE2:
        reuse_data_norm = pd.DataFrame({
            "Site": [TARGET_SITE2] * 10,
            "Attribute": ["3 - Reuse"] * 10,
            "Timestamp": ["2024-07-01","2024-08-01","2024-09-01","2024-10-01","2024-11-01","2024-12-01","2025-01-01","2025-02-01","2025-03-01","2025-04-01"],
            "Value": [14.25,14.23,14.44,15.79,14.79,16.11,18.6,13.22,14.84,15.72]

        })
        reuse_data_norm["Timestamp"] = pd.to_datetime(reuse_data_norm["Timestamp"])

        # Step 1: replace "3 - Reuse" for this site at those timestamps
        ts_match = set(reuse_data_norm["Timestamp"])
        mask_old_reuse = (
            (raw["Site"] == TARGET_SITE2) &
            (raw["Attribute"] == "3 - Reuse") &
            (raw["Timestamp"].isin(ts_match))
        )
        raw = raw[~mask_old_reuse]
        raw = pd.concat([raw, reuse_data_norm], ignore_index=True)

        # Step 2: subtract reuse from "5 - Discharge to Environment" (match on Site+Timestamp)
        mask_discharge = (
            (raw["Site"] == TARGET_SITE2) &
            (raw["Attribute"] == "5 - Discharge to Environment")
        )
        sub = (
            raw.loc[mask_discharge, ["Site", "Timestamp", "Value"]]
            .merge(reuse_data_norm[["Site", "Timestamp", "Value"]]
                    .rename(columns={"Value": "ReuseValue"}),
                    on=["Site", "Timestamp"], how="left")
        )
        raw.loc[mask_discharge, "Value"] = (sub["Value"] - sub["ReuseValue"].fillna(0)).values
    else:
        # Not the Finger Point dataset: skip any reuse adjustments entirely
        pass


    if raw.empty:
        empty = pd.DataFrame(columns=['Month','Influent','Effluent','Reuse','Discharge'])
        empty2 = pd.DataFrame(columns=['Financial Year','Influent','Effluent','Reuse','Discharge'])
        return empty, empty2,{},{}

    # 2) define fiscal months in order
    month_order = ['Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun']

    # # Normalise incoming bounds to Adelaide tz
    start_dt = to_adtz(start_dt)
    end_dt   = to_adtz(end_dt)

    # 3) prepare current‐year pivot
    # raw['Timestamp'] = pd.to_datetime(raw['Timestamp'])
    raw['Timestamp'] = pd.to_datetime(raw['Timestamp'], errors='coerce', utc=True).dt.tz_convert(adtz)
    mask = (raw['Timestamp'] >= start_dt) & (raw['Timestamp'] < end_dt + pd.Timedelta(days=1))  # include all of 30 June
    cur  = raw.loc[mask].copy()
    cur['MonthNum']   = cur['Timestamp'].dt.month
    cur['MonthLabel'] = cur['Timestamp'].dt.strftime('%b')

    rename_map = {
      '1 - Influent':                 'Influent',
      '2 - Effluent':                 'Effluent',
      '3 - Reuse':                    'Reuse',
      '5 - Discharge to Environment': 'Discharge'
    }

    df_cur = (
      cur
      .pivot_table(
        index='MonthLabel',
        columns='Attribute',
        values='Value',
        aggfunc='sum'
      )
      .rename(columns=rename_map)
      .reindex(month_order, fill_value=0)
      .reset_index()
    )

    # ensure all four metrics in current year
    for col in ['Influent','Effluent','Reuse','Discharge']:
        if col not in df_cur:
            df_cur[col] = 0

    print("df_cur")
    print(df_cur)

    # Last 5 FY totals (FY ends June)
    raw['FY_period'] = raw['Timestamp'].dt.to_period('Y-JUN')             # FY 2025 = 2024-07-01..2025-06-30
    raw['Financial Year'] = raw['FY_period'].apply(lambda p: f"{p.year-1}-{p.year}")


    # Anchor to end_dt - 1 day so 1 July doesn’t spill into the next FY
    asof_fy_end_year = (end_dt - pd.Timedelta(days=1)).to_period('Y-JUN').year
    last5 = [f"{y-1}-{y}" for y in range(asof_fy_end_year-6, asof_fy_end_year+1)]

    data_5_year = raw[raw['Financial Year'].isin(last5)].copy()


    data_5_year['Month'] = data_5_year['Timestamp'].dt.to_period('M').dt.to_timestamp()


    df_data_5_flow = (data_5_year.pivot_table(index=['Financial Year','Month'], columns='Attribute', values='Value', aggfunc='sum')
                                   .rename(columns=rename_map)
                                   .reset_index())

    df_data_5_year = (data_5_year.pivot_table(index=['Financial Year'], columns='Attribute', values='Value', aggfunc='sum')
                                   .rename(columns=rename_map)
                                   .reset_index())

    # ensure all four metrics in current year
    for col in ['Influent','Effluent','Reuse','Discharge']:
        if col not in df_data_5_flow:
            df_data_5_flow[col] = 0
            df_data_5_year[col] = 0

                 
    # Order FY chronologically + ensure all metrics exist
    fy_cat = pd.Categorical(df_data_5_year['Financial Year'], categories=last5, ordered=True)
    df_data_5_year = (df_data_5_year.assign(**{'Financial Year': fy_cat})
                                 .sort_values('Financial Year')
                                 .reset_index(drop=True))
    for col in ['Influent','Effluent','Reuse','Discharge']:
        if col not in df_data_5_year:
            df_data_5_year[col] = 0


    # 4) prepare 5-year average pivot
    avg5 = calculate_5_year_average(raw)
    has_avg = not avg5.empty and avg5['Value'].ne(0).any()
    avg5['MonthLabel'] = avg5['Month'].apply(
        lambda m: pd.to_datetime(m, format='%m').strftime('%b')
    )
    # avg5.Month is integer 1–12

    df_avg5 = (
      avg5
      .pivot_table(
        index='MonthLabel',
        columns='Attribute',
        values='Value',
        aggfunc='mean'
      )
      .rename(columns=rename_map)
      .reindex(month_order, fill_value=0)
      .reset_index()
    )
    for col in ['Influent','Effluent','Reuse','Discharge']:
        if col not in df_avg5:
            df_avg5[col] = 0

    # 5) generate charts
    images = {}
    for metric in ['Influent','Effluent','Reuse','Discharge']:
        fig = go.Figure()
        # current FY
        fig.add_trace(go.Scatter(
            x=month_order,
            y=df_cur[metric],
            mode='lines+markers',
            name=f"{ys}-{ye} FY",
            line=dict(color='#1f77b4', width=3)
        ))
        # 5-year avg
        if has_avg:
            fig.add_trace(go.Scatter(
                x=month_order, y=df_avg5[metric],
                mode='lines+markers',
                name='5-Year Avg',
                line=dict(color='red', dash='dash', width=2)
            ))
        fig.update_layout(
            template='simple_white',
            title=f"{report_name} WWTP: {metric} (ML/Month)",
            margin=dict(l=10, r=10, t=30, b=10),
            height=400, width=800,
            xaxis=dict(
                title=None,
                categoryorder='array',
                categoryarray=month_order
            ),
            yaxis=dict(title='ML/Month', showgrid=False, range=[0, max(df_cur[metric].max(), df_avg5[metric].max()) * 1.1])
        )

        buf = io.BytesIO()
        fig.write_image(buf, format='png')
        buf.seek(0)
        images[metric] = buf




    # 5) generate 5 year charts
    images_5y = {}
    fy_order = (
        list(df_data_5_year['Financial Year'].cat.categories)
        if hasattr(df_data_5_year['Financial Year'], "cat")
        else list(df_data_5_year['Financial Year'])
    )
    current_fy_label = fy_order[-1] if fy_order else "Current FY"

    for metric in ['Influent', 'Effluent', 'Reuse', 'Discharge']:
        fig = go.Figure()

        # Bars per FY
        fig.add_trace(go.Bar(
            x=df_data_5_year['Financial Year'].astype(str),  # cast for nicer axis labels
            y=df_data_5_year[metric],
            name=current_fy_label,  # legend label; bars represent each FY total
            marker=dict(line=dict(width=0.5))  # subtle outline (optional)
        ))

        ymax = float(df_data_5_year[metric].max())
        # if has_avg:
        #     ymax = max(ymax, float(df_avg5[metric].max()))
        ymax = ymax * 1.1 if ymax > 0 else 1

        fig.update_layout(
            template='simple_white',
            title=f"{report_name} WWTP: {metric} (ML/FY)",
            margin=dict(l=10, r=10, t=30, b=10),
            height=400,
            width=800,
            xaxis=dict(
                title=None,
                categoryorder='array',
                categoryarray=[str(v) for v in fy_order] if fy_order else None
            ),
            yaxis=dict(title='ML/FY', showgrid=False, range=[0, ymax]),
            showlegend=False  # bars per FY already clear; turn on if you add the avg line
        )

        buf = io.BytesIO()
        fig.write_image(buf, format='png')  # requires 'kaleido'
        buf.seek(0)
        images_5y[metric] = buf



    # 6) final table
    df_table = df_cur[['MonthLabel','Influent','Effluent','Reuse','Discharge']].copy()
    df_table = df_table.rename(columns={'MonthLabel':'Month'})

    df_data_5_year = df_data_5_year[['Financial Year','Influent','Effluent','Reuse','Discharge']].copy()

    return df_table.round(2), df_data_5_flow.round(2), images, images_5y,df_data_5_year


def load_report_details():
    """Read reportdetails.csv into a list of dicts (one per row)."""
    details = []
    if not os.path.exists(DETAILS_FILE):
        return details

    with open(DETAILS_FILE, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Clean up header names (e.g., remove leading/trailing spaces)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]

        for row in reader:
            # --- NEW: Clean the Report Name to ensure reliable matching ---
            if 'Report Name' in row and row['Report Name']:
                row['Report Name'] = row['Report Name'].strip()
            # --- END NEW ---
            details.append(row)
    return details

def get_monthly_flow_data(report_name: str,
                          start_date: datetime,
                          end_date:   datetime) -> pd.DataFrame:
    """
    Fetch PI flow data and pivot to monthly sums.
    Only imports PIChartFunctions when called, so nothing runs on import.
    Returns a DataFrame with columns: Month, Influent, Reuse, Discharge to Environment
    """
    from PIChartFunctions import PiDataRetrival

    df = PiDataRetrival(report_name)
    if df.empty:
        return pd.DataFrame()

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    mask = (df['Timestamp'] >= start_date) & (df['Timestamp'] < pd.Timestamp(end_date) + pd.Timedelta(days=1))  # include all of 30 June
    df = df.loc[mask]

    df['Month'] = df['Timestamp'].dt.to_period('M').dt.to_timestamp()
    monthly = (
        df
        .pivot_table(
            index='Month',
            columns='Attribute',
            values='Value',
            aggfunc='sum'
        )
        .reset_index()
    )

    rename_map = {
        '1 - Influent':                 'Influent',
        '3 - Reuse':                    'Reuse',
        '5 - Discharge to Environment': 'Discharge to Environment'
    }
    monthly = monthly.rename(columns=rename_map)
    for col in rename_map.values():
        if col not in monthly:
            monthly[col] = 0

    return monthly[['Month'] + list(rename_map.values())]

def get_site_information(report_name: str,
                         start_date: datetime,
                         end_date:   datetime) -> pd.DataFrame:
    """Stub for Site Information sheet. Returns an empty DataFrame."""
    return pd.DataFrame()

def write_site_information(writer, report_name, start_dt, end_dt):
    from report_functions import load_report_details

    wb = writer.book
    ws = wb.add_worksheet('Site Information')
    writer.sheets['Site Information'] = ws

    # Formats
    title_cell_fmt = wb.add_format({'bold': True, 'font_size': 15, 'font': 'Century Gothic'})
    title_fmt      = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#003c69', 'font': 'Century Gothic'})
    header_fmt     = wb.add_format({'bold': True, 'bg_color': '#E0E0E0', 'border': 1, 'font': 'Century Gothic'})
    light_fmt      = wb.add_format({'bg_color': '#F9F9F9', 'border': 1, 'font': 'Century Gothic'})
    dark_fmt       = wb.add_format({'bg_color': '#FFFFFF', 'border': 1, 'font': 'Century Gothic'})
    wrap_fmt       = wb.add_format({'text_wrap': True, 'valign': 'top', 'border': 1, 'font': 'Century Gothic'})


    details = next((r for r in load_report_details() if r.get('Report Name') == report_name), {})

    ws.set_column('A:A', 40)
    ws.set_column('B:B', 100)
    ws.write('A1', 'Site Information', title_cell_fmt)
    row = 2

    # Section: Design Capacity
    ws.merge_range(row, 0, row, 1, 'Design Capacity', title_fmt); row += 1
    design_fields = ['Population Served', 'Hydraulic Design Capacity', 'Loading Design Capacity']
    for i, field in enumerate(design_fields):
        fmt = dark_fmt if i % 2 == 0 else light_fmt
        ws.write(row, 0, field, header_fmt)
        ws.write(row, 1, details.get(field, ''), fmt)
        row += 1

    # Section: Treatment Process
    ws.merge_range(row, 0, row, 1, 'Treatment Process', title_fmt); row += 1
    treatment_fields = ['Primary Treatment', 'Secondary Treatment', 'Disinfection']
    for i, field in enumerate(treatment_fields):
        fmt = dark_fmt if i % 2 == 0 else light_fmt
        ws.write(row, 0, field, header_fmt)
        ws.write(row, 1, details.get(field, ''), fmt)
        row += 1

    # Section: Discharge/Reuse
    ws.merge_range(row, 0, row, 1, 'Discharge/Reuse', title_fmt); row += 1
    discharge_fields = ['Effluent Discharge', 'Effluent Reuse', 'Sludge Treatment/Management']
    for i, field in enumerate(discharge_fields):
        fmt = dark_fmt if i % 2 == 0 else light_fmt
        ws.write(row, 0, field, header_fmt)
        ws.write(row, 1, details.get(field, ''), wrap_fmt)
        row += 1

    # Section: Internal Effluent Quality Targets
    ws.merge_range(row, 0, row, 1, 'Internal Effluent Quality Targets', title_fmt); row += 1
    target_fields = [
        'BOD Internal Monitoring Target',
        'Ammonia as N Target',
        'Suspended Solids Target',
        'Total Nitrogen Target',
        'Total Phosphorus Target'
    ]
    for i, field in enumerate(target_fields):
        fmt = dark_fmt if i % 2 == 0 else light_fmt
        ws.write(row, 0, field, header_fmt)
        ws.write(row, 1, details.get(field, ''), fmt)
        row += 1

                              
def get_testing_components_data(report_name: str,
                                start_date: datetime,
                                end_date:   datetime):
    """
    Return (df, images) for the "Testing Components Data" sheet.

    • Millicent and Murray Bridge:
        – One table per component (aggregated across its two PIDs, pseudo-PID 'ALL')
        – Concentration columns are averaged across sampling points
        – Loading columns, discharge flow, and 5-year avg loads are summed
        – Charts: 2 monthly-concentration lines (one per real PID) + 1 summed-loading bar set

    • Other sites: behaviour unchanged (one table per PID per component).
    """
    # -------------------------------------------------------------------- imports
    import calendar, io, pyodbc
    import pandas as pd
    import plotly.graph_objects as go
    from waterscopequery import waterscope_data

    # -------------------------------------------------------------------- constants / flags
    components = [
        'Phosphorus - Total', 'Suspended Solids', 'Biochemical Oxygen Demand',
        'Zinc - Total', 'Lead - Total', 'Copper - Total',
        'Nitrogen - Total', 'Ammonia as N', 'Total Dissolved Solids (by EC)'
    ]
    MONTHS_FY   = ['Jul','Aug','Sep','Oct','Nov','Dec',
                   'Jan','Feb','Mar','Apr','May','Jun']
    IS_MILLICENT_MURRAY = report_name.strip().lower() in ['millicent','murray bridge']
    flow_col      = 'Discharge to Environment'

    # -------------------------------------------------------------------- site / PID list
    sites_df      = pd.read_csv(SITE_FILE, dtype=str)
    site_rows_all = sites_df[sites_df['Report Name'] == report_name]

    site_rows = site_rows_all[site_rows_all['Location Type'].str.lower() != 'reuse']
    if site_rows.empty:
        site_rows = site_rows_all.copy()

    pids           = site_rows['SamplingPointID'].dropna().tolist()
    orig_pid_list  = pids[:]                     # keep for Millicent and Murray Bridge line plotting
    has_discharge  = site_rows['Location Type'].str.lower().eq('discharge to environment').any()
    pi_name        = site_rows['SystemName'].iloc[0] if not site_rows.empty else ''

    # -------------------------------------------------------------------- WaterScope query list
    sampling_data = pd.DataFrame(
        [{'SamplingPointID': pid, 'ComponentName': comp, 'Site': report_name}
         for pid in pids for comp in components],
        columns=['SamplingPointID', 'ComponentName', 'Site']
    )

    # -------------------------------------------------------------------- retrieve data (current FY & 5-yr)
    fy_start = start_date.year if start_date.month >= 7 else start_date.year - 1
    conn     = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=SAWpSQL20;DATABASE=WaterScope;Trusted_Connection=yes",
        autocommit=True
    )
    raw_curr = waterscope_data(conn, sampling_data, report_name, fy_start,     1)
    raw_5yr  = waterscope_data(conn, sampling_data, report_name, fy_start - 4, 5)
    conn.close()

    # DEBUG: Check what components were retrieved
    print("\n=== DEBUG: Components retrieved from database ===")
    if not raw_curr.empty:
        print("Current FY unique Attributes:", raw_curr['Attribute'].unique())
        tds_check = raw_curr[raw_curr['Attribute'] == 'Total Dissolved Solids (by EC)']
        print(f"Total Dissolved Solids (by EC) records in raw_curr: {len(tds_check)}")
    else:
        print("raw_curr is EMPTY!")

    for df_raw in (raw_curr, raw_5yr):
        if not df_raw.empty:
            df_raw['Timestamp']       = pd.to_datetime(df_raw['Timestamp'])
            df_raw['SamplingPointID'] = df_raw['SamplingPointID'].astype(str)

    # -------------------------------------------------------------------- current FY monthly averages
    full_month_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    if not raw_curr.empty:
        raw_curr['Month'] = raw_curr['Timestamp'].dt.to_period('M').dt.to_timestamp()
        curr_mon = (raw_curr
                    .groupby(['Month', 'SamplingPointID', 'Attribute'])['Value']
                    .mean().reset_index())
        df_pivot = curr_mon.pivot_table(
            index=['Month', 'SamplingPointID'],
            columns='Attribute', values='Value'
        )
        master_index = pd.MultiIndex.from_product(
            [full_month_range, pids], names=['Month', 'SamplingPointID']
        )
        df_curr = df_pivot.reindex(master_index).reset_index()
    else:
        df_curr = pd.DataFrame(
            pd.MultiIndex.from_product(
                [full_month_range, pids], names=['Month', 'SamplingPointID']
            ).to_frame(index=False)
        )

    df_curr['MonthStr'] = df_curr['Month'].dt.strftime('%b')
    df_curr.drop(columns='Month', inplace=True)

 

    # -------------------------------------------------------------------- 5-year averages (per PID)
    if not raw_5yr.empty:
        raw_5yr['MonthNum'] = raw_5yr['Timestamp'].dt.month
        past5_mon = (raw_5yr
                     .groupby(['MonthNum', 'SamplingPointID', 'Attribute'])['Value']
                     .mean().reset_index())
        df_5yr = past5_mon.pivot_table(
            index=['MonthNum', 'SamplingPointID'],
            columns='Attribute', values='Value'
        ).reset_index()
        df_5yr['MonthStr'] = df_5yr['MonthNum'].apply(lambda m: calendar.month_abbr[m])
        df_5yr.drop(columns='MonthNum', inplace=True)
    else:
        df_5yr = pd.DataFrame(columns=['MonthStr', 'SamplingPointID'])

    # -------------------------------------------------------------------- flow (discharge) data
    if pi_name.strip().lower() == 'mount burr wwwtp':
        pi_name = 'Mount Burr WWTP'
    ys, ye = start_date.year, end_date.year

    if has_discharge:
        flow_df,flow_df5, _,_,_ = create_flow_charts(pi_name, start_date, end_date, report_name, ys, ye)
        flow_df = flow_df[['Month', 'Discharge']] \
                    .rename(columns={'Month':'MonthStr', 'Discharge':flow_col})
    else:
        flow_df = pd.DataFrame({'MonthStr': df_curr['MonthStr'].unique()})

    # -------------------------------------------------------------------- merge (curr + 5yr + flow)
    if has_discharge:
        df_full = (df_curr
                   .merge(flow_df, on='MonthStr', how='left')
                   .merge(df_5yr, on=['MonthStr','SamplingPointID'],
                          how='left', suffixes=('', '_5yr')))
    else:
        df_full = (df_curr
                   .merge(df_5yr, on=['MonthStr','SamplingPointID'],
                          how='left', suffixes=('', '_5yr')))

    # category -> ensure fiscal order
    df_full['MonthStr'] = pd.Categorical(df_full['MonthStr'],
                                         categories=MONTHS_FY, ordered=True)
    df_full = df_full.sort_values(['SamplingPointID', 'MonthStr'])


    # -------------------------------------------------------------------- compute loading columns (all rows)
    if has_discharge:
        for comp in components:
            df_full[f"{comp} Loading"] = df_full[comp].fillna(0) * df_full[flow_col].fillna(0)
            col5 = f"{comp}_5yr"
            if col5 in df_full.columns:
                df_full[f"{comp} 5yr Avg Load"] = (
                    df_full[col5].fillna(0) * df_full[flow_col].fillna(0)
                )

    # keep a copy for line plotting
    df_per_pid = df_full.copy()

    # -------------------------------------------------------------------- Millicent and Murray Bridge aggregation
    if IS_MILLICENT_MURRAY:
        # Identify which columns to average vs sum
        # Concentration columns: component names and their _5yr versions
        conc_cols = []
        for comp in components:
            if comp in df_full.columns:
                conc_cols.append(comp)
            if f"{comp}_5yr" in df_full.columns:
                conc_cols.append(f"{comp}_5yr")

        # All other numeric columns (loadings, discharge, etc.) will be summed
        numeric_cols = df_full.select_dtypes(include='number').columns.tolist()
        sum_cols = [col for col in numeric_cols if col not in conc_cols]

        # Aggregate: average concentrations, sum everything else
        agg_dict = {col: 'mean' for col in conc_cols}
        agg_dict.update({col: 'sum' for col in sum_cols})

        df_agg = (
            df_full.groupby('MonthStr')
                .agg(agg_dict)
                .reset_index()
        )
        df_agg['SamplingPointID'] = 'ALL'
        df_agg['MonthStr'] = pd.Categorical(df_agg['MonthStr'],
                                            categories=MONTHS_FY, ordered=True)
        df_agg = df_agg.sort_values('MonthStr')
        df_return      = df_agg
        pids_for_table = ['ALL']
    else:
        df_return      = df_full
        pids_for_table = sorted(df_full['SamplingPointID'].unique())

    # -------------------------------------------------------------------- nice PID → description map
    pid_to_desc = {}
    if not IS_MILLICENT_MURRAY:
        req_df = load_monitoring_plan_requirements(
            f"{str(start_date.year)[-2:]}{str(end_date.year)[-2:]}"
        )
        pid_to_desc = (req_df.drop_duplicates(subset=['SamplingPointID'])
                             .set_index('SamplingPointID')['SamplePointDescription']
                             .to_dict())
        


    # -------------------------------------------------------------------- chart generation
    images = {}
    if has_discharge:    
        for pid in pids_for_table:
            if IS_MILLICENT_MURRAY:
                df_table = df_agg
                desc     = 'Sum of both sampling points'
            else:
                df_table = df_full[df_full['SamplingPointID'] == pid]
                desc     = pid_to_desc.get(pid, )

            for comp in components:
                if comp not in df_table.columns or df_table[comp].isna().all():
                    continue

                fig = go.Figure()

                # bars (loading) for sites with discharge
                if has_discharge:
                    fig.add_bar(
                        x=df_table['MonthStr'],
                        y=df_table[f"{comp} Loading"],
                        name=f"{ys}-{ye} Loading",
                        marker_color='#4E79A7',
                        yaxis='y1'
                    )
                    bar5_col = f"{comp} 5yr Avg Load"
                    if bar5_col in df_table.columns and df_table[bar5_col].notna().any():
                        fig.add_bar(
                            x=df_table['MonthStr'],
                            y=df_table[bar5_col],
                            name="5-Year Avg Loading",
                            marker_color='#F28E2B',
                            yaxis='y1'
                        )

                # monthly concentration lines
                line_pids = orig_pid_list if IS_MILLICENT_MURRAY else [pid]
                for lp in line_pids:
                    df_line = df_per_pid[df_per_pid['SamplingPointID'] == lp]
                    if df_line.empty or comp not in df_line.columns:
                        continue
                    fig.add_scatter(
                        x=df_line['MonthStr'],
                        y=df_line[comp],
                        mode='lines+markers',
                        name=f"{lp} Conc (mg/L)",
                        yaxis='y2'
                    )

                fig.update_layout(
                    template='simple_white',
                    title=(f"{report_name} WWTP: {comp}"
                        if not IS_MILLICENT_MURRAY else f"{report_name} WWTP: {comp} ({report_name})"),
                    legend=dict(orientation='h', y=-0.25, x=0.5, font=dict(size=9)),
                    yaxis=dict(title='Loading (kg/month)', rangemode='tozero'),
                    yaxis2=dict(title='Concentration (mg/L)', overlaying='y', side='right'),
                    barmode='group',
                    margin=dict(l=40, r=40, t=60, b=100),
                    width=900, height=500
                )

                buf = io.BytesIO()
                fig.write_image(buf, format='png')
                buf.seek(0)
                images[(comp, pid)] = buf
    else:    
        for pid in pids_for_table:
            if IS_MILLICENT_MURRAY:
                df_table = df_agg
                desc     = 'Sum of both sampling points'
            else:
                df_table = df_full[df_full['SamplingPointID'] == pid]
                desc     = pid_to_desc.get(pid, )

            for comp in components:
                if comp not in df_table.columns or df_table[comp].isna().all():
                    continue

                fig = go.Figure()

                # # bars (loading) for sites with discharge
                # if has_discharge:
                #     fig.add_bar(
                #         x=df_table['MonthStr'],
                #         y=df_table[f"{comp} Loading"],
                #         name=f"{ys}-{ye} Loading",
                #         marker_color='#4E79A7',
                #         yaxis='y1'
                #     )
                #     bar5_col = f"{comp} 5yr Avg Load"
                #     if bar5_col in df_table.columns and df_table[bar5_col].notna().any():
                #         fig.add_bar(
                #             x=df_table['MonthStr'],
                #             y=df_table[bar5_col],
                #             name="5-Year Avg Loading",
                #             marker_color='#F28E2B',
                #             yaxis='y1'
                #         )

                # monthly concentration lines
                line_pids = orig_pid_list if IS_MILLICENT_MURRAY else [pid]
                for lp in line_pids:
                    df_line = df_per_pid[df_per_pid['SamplingPointID'] == lp]
                    if df_line.empty or comp not in df_line.columns:
                        continue
                    fig.add_scatter(
                        x=df_line['MonthStr'],
                        y=df_line[comp],
                        mode='lines+markers',
                        name=f"{lp} Conc (mg/L)"
                    )

                fig.update_layout(
                    template='simple_white',
                    title=(f"{report_name} WWTP: {comp}"
                        if not IS_MILLICENT_MURRAY else f"{report_name} WWTP: {comp} ({report_name})"),
                    legend=dict(orientation='h', y=-0.25, x=0.5, font=dict(size=9)),
                    yaxis=dict(title='Concentration (mg/L)', overlaying='y', side='left'),
                    barmode='group',
                    margin=dict(l=40, r=40, t=60, b=100),
                    width=900, height=500
                )

                buf = io.BytesIO()
                fig.write_image(buf, format='png')
                buf.seek(0)
                images[(comp, pid)] = buf    


    # -------------------------------------------------------------------- 5 Financial yearly totals
    # full_month_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    raw_5yr_copy = pd.concat([raw_5yr, raw_curr], ignore_index=True, sort=False)
    raw_5yr_copy['Month'] = raw_5yr_copy['Timestamp'].dt.to_period('M').dt.to_timestamp()
    print("raw_5yr_copy")
    print(raw_5yr)

    raw_5yr_copy['FY_period'] = raw_5yr_copy['Timestamp'].dt.to_period('Y-JUN')             # FY 2025 = 2024-07-01..2025-06-30
    raw_5yr['Financial Year'] = raw_5yr_copy['FY_period'].apply(lambda p: f"{p.year-1}-{p.year}")
    
    if not raw_5yr_copy.empty:
        raw_5yr_copy['FY_period'] = raw_5yr_copy['Timestamp'].dt.to_period('Y-JUN')             # FY 2025 = 2024-07-01..2025-06-30
        raw_5yr_copy['Financial Year'] = raw_5yr_copy['FY_period'].apply(lambda p: f"{p.year-1}-{p.year}")
        data_5_year = (raw_5yr_copy
                    .groupby(['Financial Year','Month', 'SamplingPointID', 'Attribute'])['Value']
                    .mean().reset_index())
        df_pivot_5y = data_5_year.pivot_table(
            index=['Financial Year','Month', 'SamplingPointID'],
            columns='Attribute', values='Value'
        )
        df_data_5_year = df_pivot_5y.reset_index()


    # -------------------------------------------------------------------- flow (discharge) data
    if pi_name.strip().lower() == 'mount burr wwwtp':
        pi_name = 'Mount Burr WWTP'
    ys, ye = start_date.year, end_date.year

    if has_discharge:
        
        _,flow_df5, _,_,_ = create_flow_charts(pi_name, start_date, end_date, report_name, ys, ye)    

        flow_df5 = flow_df5[['Financial Year',"Month", 'Discharge']] \
                    .rename(columns={'Discharge':flow_col})
    else:
        flow_df5 = pd.DataFrame(columns=['Financial Year',"Month", 'Discharge'])       




    # -------------------------------------------------------------------- merge (curr + 5yr + flow)

    df_full_5y = (df_data_5_year.merge(flow_df5, on=['Financial Year','Month'], how='left'))

    # -------------------------------------------------------------------- compute 5 yearly loading columns (all rows)
    
  
    if has_discharge:
        for comp in components:
            df_full_5y[f"{comp} Loading"] = df_full_5y[comp].fillna(0) * df_full_5y[flow_col].fillna(0)
    else:
        for comp in components:
            df_full_5y[f"{comp} Loading"] = 0
    
                

    # keep a copy for line plotting
    df_per_pid_5y = df_full_5y.copy() 


        # -------------------------------------------------------------------- Millicent and Murray Brigge aggregation 5 years
    if IS_MILLICENT_MURRAY:
        # Identify which columns to average vs sum (same logic as monthly)
        # Concentration columns: component names (no _5yr suffix in this dataset)
        conc_cols_5y = []
        for comp in components:
            if comp in df_full_5y.columns:
                conc_cols_5y.append(comp)

        # All other numeric columns (loadings, discharge, etc.) will be summed
        numeric_cols = df_full_5y.select_dtypes(include='number').columns.tolist()
        sum_cols_5y = [col for col in numeric_cols if col not in conc_cols_5y]

        # Aggregate: average concentrations, sum everything else
        agg_dict_5y = {col: 'mean' for col in conc_cols_5y}
        agg_dict_5y.update({col: 'sum' for col in sum_cols_5y})

        df_agg_5y = (
            df_full_5y.groupby('Financial Year')
                .agg(agg_dict_5y)
                .reset_index()
        )
        df_agg_5y['SamplingPointID'] = 'ALL'
        df_agg_5y['Financial Year'] = pd.Categorical(df_agg_5y['Financial Year'], ordered=True)
        df_agg_5y = df_agg_5y.sort_values('Financial Year')
        df_return_5y      = df_agg_5y
        # pids_for_table = ['ALL']
    else:

        numeric_cols = df_full_5y.select_dtypes(include='number').columns.tolist()
        df_return_5y = (
            df_full_5y.groupby(['Financial Year','SamplingPointID'])[numeric_cols]
                .sum()
                .reset_index()
        )
        # df_return_5y      = df_full_5y
        # pids_for_table = sorted(df_full_5y['SamplingPointID'].unique())

    # df_return_5y = df_full_5y.copy()

    # 5) generate 5 year charts
    fy_order = (
        list(df_return_5y['Financial Year'].cat.categories)
        if hasattr(df_return_5y['Financial Year'], "cat")
        else list(df_return_5y['Financial Year'])
    )
    current_fy_label = fy_order[-1] if fy_order else "Current FY"
    
    images_5y = {}
    for pid in pids_for_table:
        for comp in components:
            fig = go.Figure()
            if has_discharge:            

                # Bars per FY
                fig.add_trace(go.Bar(
                    x=df_return_5y['Financial Year'].astype(str),  # cast for nicer axis labels
                    y=df_return_5y[f'{comp} Loading'],
                    name=current_fy_label,  # legend label; bars represent each FY total
                    marker=dict(line=dict(width=0.5))  # subtle outline (optional)
                ))

                ymax = float(df_return_5y[f'{comp} Loading'].max())
                # if has_avg:
                #     ymax = max(ymax, float(df_avg5[metric].max()))
                ymax = ymax * 1.1 if ymax > 0 else 1

                fig.update_layout(
                    template='simple_white',
                    title=f"{report_name} WWTP: {f'{comp} Loading'} (kg/FY)",
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=500,
                    width=900,
                    xaxis=dict(
                        title=None,
                        categoryorder='array',
                        categoryarray=[str(v) for v in fy_order] if fy_order else None
                    ),
                    yaxis=dict(title='kg/FY', showgrid=False, range=[0, ymax]),
                    showlegend=False  # bars per FY already clear; turn on if you add the avg line
                )

                buf = io.BytesIO()
                # fig.show()
                fig.write_image(buf, format='png')  # requires 'kaleido'
                buf.seek(0)
                images_5y[(comp, pid)] = buf

    # -------------------------------------------------------------------- finish
    # df_return = df_return.rename(columns={'MonthStr': 'Month'}).round(2)
    # return df_return, images

    df_return = df_return.rename(columns={'MonthStr': 'Month'})
    
    
    return df_return, images,df_return_5y,images_5y    



def get_comments_data(report_name: str,
                      start_date: datetime,
                      end_date:   datetime) -> pd.DataFrame:
    import os
    import pandas as pd

    # 1) Load the raw commentary CSV
    commentary_file = os.path.join(DATA_DIR, 'WWTP Quarterly Review Comments.csv')
    df = pd.read_csv(commentary_file, dtype=str)

    # 2) Filter by site (Site column is e.g. "Finger Point WWTP")
    site_key = f"{report_name} WWTP"
    df = df.loc[df['Site'] == site_key].copy()

    # 3) Filter by financial year (format "YYYY/YYYY")
    fy_str = f"{start_date.year}/{end_date.year}"
    df = df.loc[df['Financial Year'] == fy_str]

    # 4) Pivot all comment‐type columns into rows
    #    Drop the columns we don’t want to pivot
    id_cols      = ['Quarter']
    drop_cols    = ['Title','Site','Financial Year','Quarter']
    comment_cols = [c for c in df.columns if c not in drop_cols]

    df_long = df.melt(
        id_vars=id_cols,
        value_vars=comment_cols,
        var_name='Comment Type',
        value_name='Comment'
    )

    # 5) Drop any empty or whitespace‐only comments
    df_long = df_long.loc[
        df_long['Comment'].notna() &
        (df_long['Comment'].str.strip() != '')
    ]

    # 6) Return only the three columns requested
    return df_long[['Quarter','Comment Type','Comment']]
def _load_filtered_incidents(report_name: str,
                              start_date: datetime,
                              end_date:   datetime) -> pd.DataFrame:
    """
    Shared filtering logic for site incidents: date range, site match, and
    classification/TARP relevance. Keeps the 'TARP' column so callers that
    need it (e.g. summary counts) don't have to re-filter from scratch.
    """
    from report_functions import load_sites

    # 1) load all incidents, parse the 'Incident Date Time' column
    df = pd.read_csv(
        SAAM_FILE,
        parse_dates=['Incident Date Time'],
        dayfirst=False,  # adjust if needed
        infer_datetime_format=True
    )

    # 2) filter by the datetime range
    mask = (
        (df['Incident Date Time'] >= pd.to_datetime(start_date)) &
        (df['Incident Date Time'] < pd.to_datetime(end_date) + pd.Timedelta(days=1))
    )
    df = df.loc[mask].copy()

    # 3) find this site’s SAAM Name via sitedata.csv
    sites    = load_sites()
    saam = next((s['saam_name']
                 for s in sites
                 if s['report_name'] == report_name),
                None)

    # filter by Location Description matching that SAAM Name
    if saam:
        df = df[df['Location Description'] == saam]
    valid_cls = ['Priority Type 1', 'Type 1', 'Type 2','Type 3']
    mask_cls  = df['Primary Incident Classification'].isin(valid_cls)
    mask_tarp = df['TARP'].notna() & df['TARP'].astype(str).str.strip().ne('')
    df = df[mask_cls | mask_tarp]
    return df

def get_site_incidents_data(report_name: str,
                            start_date: datetime,
                            end_date:   datetime) -> pd.DataFrame:

    df = _load_filtered_incidents(report_name, start_date, end_date)
    df = df.drop(columns=['TARP', 'Incident Count'])

    # the source 'Date' column is actually the incident's financial year
    # (e.g. "2023-2024"), so label it accordingly rather than "Date"
    df = df.rename(columns={'Date': 'FY'})

    # 4) return same columns / order as the source file
    return df

def get_site_incidents_summary(report_name: str,
                                start_date: datetime,
                                end_date:   datetime) -> dict:
    """
    Counts of incidents by classification/TARP for the summary table at the
    top of the Site Incidents sheet, over the same filtered set of incidents
    shown in the table below it.
    """
    df = _load_filtered_incidents(report_name, start_date, end_date)
    cls = df['Primary Incident Classification']
    mask_tarp = df['TARP'].notna() & df['TARP'].astype(str).str.strip().ne('')

    return {
        'Priority Type 1': int((cls == 'Priority Type 1').sum()),
        'Type 1':          int((cls == 'Type 1').sum()),
        'Type 2':          int((cls == 'Type 2').sum()),
        'TARP':            int(mask_tarp.sum()),
    }
def load_monitoring_plan_requirements(fy_tag: str) -> pd.DataFrame:
    required = {'FY', 'SAMPLING_POINT', 'REPORTED_NAME', 'DESCRIPTION'}
    file_path = os.path.join(DATA_DIR, '2324MonitoringProgram.csv')

    try:
        df = pd.read_csv(file_path, dtype=str, usecols=lambda c: c.upper() in required)
    except Exception:
        return pd.DataFrame(columns=['SamplingPointID', 'SamplePointDescription', 'Analyte', 'Min_Samples'])

    if not required.issubset({col.upper() for col in df.columns}):
        return pd.DataFrame(columns=['SamplingPointID', 'SamplePointDescription', 'Analyte', 'Min_Samples'])

    # Report requirements for a replaced sampling point under its current ID
    from waterscopequery import SAMPLING_POINT_SWAPS
    df['SAMPLING_POINT'] = df['SAMPLING_POINT'].replace(
        {old: new for old, new, _ in SAMPLING_POINT_SWAPS})

    df['REPORTED_NAME'] = df['REPORTED_NAME'].replace({
        'Biochemical Oxygen Demand - Total': 'Biochemical Oxygen Demand',
        'TKN as N': 'TKN as Nitrogen',
        'Chlorine': 'Chlorine - Total',
        'Algal Count - Partial': 'Algal Biovolume',
    })

    unwanted = [
        'Sodium Adsorption Ratio',
        'Metal Preparation - Total',
        'Metal Preparation - Soluble',
        'Batch Charge Metals Analyses'
    ]
    df = df[~df['REPORTED_NAME'].isin(unwanted)]

    df['FY'] = (
        df['FY']
        .str.replace(r'[^0-9]', '', regex=True)
        .str.zfill(4)
    )

    df = df[df['FY'] == fy_tag].copy()

    df['Min_Samples'] = (
        df.groupby(['SAMPLING_POINT', 'REPORTED_NAME'])['REPORTED_NAME'].transform('count')
    )  
    return (
        df.drop_duplicates(subset=['SAMPLING_POINT', 'REPORTED_NAME'])
          .rename(columns={
              'SAMPLING_POINT': 'SamplingPointID',
              'REPORTED_NAME': 'Analyte',
              'DESCRIPTION': 'SamplePointDescription'
          })
          [['SamplingPointID', 'SamplePointDescription', 'Analyte', 'Min_Samples']]
    )

def query_compliance_counts(conn, req_df: pd.DataFrame, fy_start: int) -> pd.DataFrame:
    """
    Return a count of samples taken per SamplingPointID/ComponentName
    for the given financial year.

    Parameters
    ----------
    conn      : open pyodbc connection
    req_df    : requirements for the site/FY (cols SamplingPointID, Analyte, …)
    fy_start  : full calendar year that the FY begins, e.g. 2025 for FY25/26
    """
    if req_df.empty:
        return pd.DataFrame(columns=['SamplingPointID', 'ComponentName', 'Taken_Samples'])

    # ── build VALUES list ──────────────────────────────────────────────────────
    # rows = []
    # for r in req_df.itertuples(index=False):
    #     sp   = int(r.SamplingPointID)
    #     comp = r.Analyte.replace("'", "''")          # escape single quotes
    #     rows.append(f"({sp}, N'{comp}')")
    # values_clause = ",\n        ".join(rows)


    rows = []
    for r in req_df.itertuples(index=False):
        sp = int(r.SamplingPointID)
        comp = r.Analyte.replace("'", "''")  # escape single quotes

        if comp == "Conductivity & Total Dissolved Solids":
            # Split into 2 rows
            rows.append(f"({sp}, N'Conductivity')")
            rows.append(f"({sp}, N'Total Dissolved Solids')")
        else:
            rows.append(f"({sp}, N'{comp}')")

    # Mid-year sampling point swaps: also look up the former point, count its samples
    # under the current ID before the effective date, and ignore it after
    from waterscopequery import SAMPLING_POINT_SWAPS
    swap_case, swap_where = "vw.SamplingPointID", ""
    for old, new, eff in SAMPLING_POINT_SWAPS:
        for r_ in req_df[req_df['SamplingPointID'].astype(str) == new].itertuples(index=False):
            comp = r_.Analyte.replace("'", "''")
            for c in (["Conductivity", "Total Dissolved Solids"]
                      if comp == "Conductivity & Total Dissolved Solids" else [comp]):
                rows.append(f"({int(old)}, N'{c}')")
        swap_case = f"CASE WHEN vw.SamplingPointID = {int(old)} THEN {int(new)} ELSE {swap_case} END"
        swap_where += (f" AND NOT (vw.SamplingPointID = {int(old)} AND vw.SampledDate >= '{eff}')"
                       f" AND NOT (vw.SamplingPointID = {int(new)} AND vw.SampledDate < '{eff}')")
    values_clause = ",\n        ".join(rows)


    # ── inline table via sub-select over VALUES ───────────────────────────────
    # Note: Conductivity and Total Dissolved Solids are measured on the SAME
    # physical sample, so once their component names are harmonised back into
    # the single "Conductivity & Total Dissolved Solids" requirement, the
    # GROUP BY / COUNT must operate on that harmonised name (and count unique
    # sample dates) — otherwise the two components each get counted and
    # grouped separately, producing two duplicate rows for one requirement
    # with the sample count split across them.
    sql = f"""
    WITH TempSamplingPoints AS (
        SELECT *
        FROM (VALUES
            {values_clause}
        ) AS v(SamplingPointID, ComponentName)
    ),
    Mapped AS (
        SELECT
            {swap_case} AS SamplingPointID,
            vw.SampledDate,
            CASE
                WHEN vw.[ComponentName] LIKE '%Conductivity%'
                     OR vw.[ComponentName] LIKE '%Dissolved Solids%'
                THEN 'Conductivity & Total Dissolved Solids'
                ELSE vw.[ComponentName]
            END AS [ComponentName]
        FROM [WaterScope].[dbo].[vwCrystalResults] AS vw
        INNER JOIN TempSamplingPoints AS t
            ON vw.SamplingPointID = t.SamplingPointID
           AND vw.ComponentName   COLLATE SQL_Latin1_General_CP1_CI_AS
                                 = t.ComponentName
        WHERE vw.SampledDate >= ? AND vw.SampledDate < ?
          AND NOT (ISNULL(vw.ResultPublishStatusName, '') = 'Withdrawn (cancelled)' AND vw.ResultChar IS NULL){swap_where}
    )
    SELECT
        SamplingPointID,
        ComponentName,
        COUNT(DISTINCT SampledDate) AS Taken_Samples
    FROM Mapped
    GROUP BY
        SamplingPointID,
        ComponentName
    ORDER BY
        SamplingPointID,
        ComponentName;
    """

    start_date = f"{fy_start}-07-01"
    end_date   = f"{fy_start + 1}-07-01"   # SampledDate < 1 July, so all of 30 June is included
    print("SQL being executed:\n", sql)
    print("Params:", start_date, end_date)

    return pd.read_sql(sql, conn, params=[start_date, end_date])


def debug_compliance_counts(conn, req_df: pd.DataFrame, fy_start: int) -> pd.DataFrame:
    """
    Wrapper around query_compliance_counts that prints diagnostics so you can
    spot why no rows are matching.
    """
    print("=== DEBUG: Monitoring-Program Compliance ===")
    print(f"FY start-year: {fy_start}  (date range {fy_start}-07-01 → {fy_start+1}-06-30)")
    print(f"req_df rows (unique pairs): {req_df[['SamplingPointID','Analyte']].drop_duplicates().shape[0]}")
    print(req_df[['SamplingPointID','Analyte']].drop_duplicates().head(10))

    # Run the real query
    taken_df = query_compliance_counts(conn, req_df, fy_start)
    print(f"taken_df rows returned from SQL: {len(taken_df)}")
    print(taken_df.head(10))

    # Quick mismatch audit
    req_pairs   = req_df.rename(columns={'Analyte':'ComponentName'})[['SamplingPointID','ComponentName']].drop_duplicates()
    sql_pairs   = taken_df[['SamplingPointID','ComponentName']].drop_duplicates()

    missing = (
        req_pairs
        .merge(sql_pairs, on=['SamplingPointID','ComponentName'], how='left', indicator=True)
        .query("_merge=='left_only'")
        .drop(columns='_merge')
    )
    if not missing.empty:
        print(f"Pairs present in requirements but missing in SQL results: {len(missing)}")
        print(missing.head(20))
    else:
        print("All required SamplingPointID+Analyte pairs were found in SQL results.")

    return taken_df

def write_monitoring_program_sheet(
        writer,
        site_name:      str,
        fy_tag_curr:    str,   # e.g. "2324"
        fy_start_curr:  int,   # e.g. 2023
        req_curr:       pd.DataFrame
):
    """
    Create the “Monitoring Program” sheet with:
      • Compliance table for the current FY
      • Changes to min-sample requirements (prev ↔ curr, curr ↔ next)

    Headings now read:
      “Changes to the program from FYxx-yy to FYxx-yy”
    """

    sheet_name = 'Monitoring Program'
    if sheet_name in writer.sheets:              # sheet was made by the first call
        return                                   # skip the second call cleanly
    wb = writer.book

    ws = wb.add_worksheet(sheet_name)            # ← original line (unchanged)
    writer.sheets[sheet_name] = ws               # keep the writer-sheet mapping

    # Formats -----------------------------------------------------------------
    t_fmt = wb.add_format({
        'bold': True, 'font_size': 14,
        'font_color': 'white', 'bg_color': '#003c69',
        'font': 'Century Gothic',
    })
    h_fmt  = wb.add_format({'bold': True, 'border': 1, 'bg_color': '#dedbd2','font': 'Century Gothic'})
    c_fmt  = wb.add_format({'border': 1,'font': 'Century Gothic'})
    title_fmt = wb.add_format({'bold': True, 'font_size': 15, 'font': 'Century Gothic','text_wrap': True})
    note_fmt  = wb.add_format({'font_size': 11, 'font': 'Century Gothic', 'text_wrap': True, 'valign': 'top'})

    # Helper for FY text e.g. "2324" → "23-24"
    fmt = lambda tag: f"{tag[:2]}-{tag[2:]}"

    # Layout ------------------------------------------------------------------
    ws.set_column('B:B', 37)
    ws.set_column('C:C', 42)
    ws.set_column('D:D', 32)
    ws.set_column('E:F', 29)

    ws.merge_range('A1:F1', 'Monitoring program', title_fmt)
    ws.set_row(1, 30)
    ws.merge_range(
        'A2:F2',
        'The approved monitoring plan pertaining to this site was adhered to during the '
        'reporting period except where highlighted in the table below. Comments and '
        'actions taken for these instances are provided.',
        note_fmt
    )
    ws.merge_range('A4:F4', f'Monitoring plan compliance – FY {fy_tag_curr}', t_fmt)

    # ---------------------------------------------------------------- current
    site_ids = [s['samplingpoint_id']
                for s in load_sites()
                if s['report_name'] == site_name]
    req_curr = req_curr[req_curr['SamplingPointID'].isin(site_ids)].copy()

    # DB query – taken samples
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=SAWpSQL20;DATABASE=WaterScope;Trusted_Connection=yes",
        autocommit=True
    )
    taken_df = query_compliance_counts(conn, req_curr, fy_start_curr)
    conn.close()

    # Merge requirements with taken counts
    req_curr['SamplingPointID'] = req_curr['SamplingPointID'].astype(str)
    taken_df['SamplingPointID'] = taken_df['SamplingPointID'].astype(str)
    req_curr['Analyte']         = req_curr['Analyte'].astype(str)
    taken_df['ComponentName']   = taken_df['ComponentName'].astype(str)

    # Planned samples = required count rounded to the nearest standard frequency
    # (4 quarterly, 12 monthly, 26 fortnightly, 52 weekly). Ties round up.
    planned_levels = [4, 12, 26, 52]
    def to_planned(n):
        return min(planned_levels, key=lambda p: (abs(p - n), -p))

    comp = (
        req_curr.rename(columns={'Analyte': 'ComponentName'})
                .merge(taken_df, on=['SamplingPointID', 'ComponentName'], how='left')
                .fillna({'Taken_Samples': 0})
                .rename(columns={'ComponentName': 'Analyte'})
                .assign(Min_Samples=lambda d: d['Min_Samples'].astype(int))
                .assign(Planned_Samples=lambda d: d['Min_Samples'].map(to_planned))
                [['SamplingPointID', 'SamplePointDescription',
                  'Analyte', 'Min_Samples', 'Planned_Samples', 'Taken_Samples']]
    )

    # Write compliance table
    headers = ['Sampling Point Number', 'Sample Point Description',
               'Analyte', 'Number of Samples Required',
               'Planned Samples', 'Number of Samples Taken']
    start_r = 5
    for c, h in enumerate(headers):
        ws.write(start_r, c, h, h_fmt)
    for r, row in enumerate(comp.itertuples(index=False), start=start_r + 1):
        ws.write_row(r, 0, row, c_fmt)

    # ---------------------------------------------------------------- changes
    fy_tag_next  = f"{int(fy_tag_curr) + 101:04d}"   # e.g. 2324 → 2425
    fy_tag_prev  = f"{int(fy_tag_curr) - 101:04d}"   # e.g. 2324 → 2223

    print ("fy_tag_next,fy_tag_prev")
    print (fy_tag_next,fy_tag_prev)

    # Helper to load & filter monitoring program CSVs
    def req_for(tag):
        df = load_monitoring_plan_requirements(tag)     
        return df[df['SamplingPointID'].isin(site_ids)].rename(columns={'Analyte': 'ComponentName'})

    req_next = req_for(fy_tag_next)
    req_prev = req_for(fy_tag_prev)

    # --- Curr → Next ---------------------------------------------------------
    delta_next = (
        req_curr.rename(columns={'Analyte': 'ComponentName'})
                [['SamplingPointID', 'ComponentName', 'Min_Samples']]
                .merge(req_next[['SamplingPointID', 'ComponentName', 'Min_Samples']],
                       on=['SamplingPointID', 'ComponentName'],
                       suffixes=('_curr', '_next'))
    )
    delta_next = delta_next[delta_next.Min_Samples_curr != delta_next.Min_Samples_next]

    start = start_r + 2 + len(comp)
    ws.merge_range(
        start, 0, start, 5,
        f"Changes to the program from FY{fmt(fy_tag_curr)} to FY{fmt(fy_tag_next)}",
        t_fmt
    )

    if delta_next.empty:
        ws.write(start + 1, 0, 'No changes to the monitoring program this year', c_fmt)
        next_end = start + 2
    else:
        dh = ['SamplingPointID', 'Analyte', 'Curr Min', 'Next Min']
        for c, h in enumerate(dh):
            ws.write(start + 1, c, h, h_fmt)
        for i, row in enumerate(delta_next.itertuples(index=False), start=start + 2):
            ws.write(i, 0, row.SamplingPointID,  c_fmt)
            ws.write(i, 1, row.ComponentName,    c_fmt)
            ws.write(i, 2, row.Min_Samples_curr, c_fmt)
            ws.write(i, 3, row.Min_Samples_next, c_fmt)
        next_end = start + 2 + len(delta_next) + 1

    # --- Prev → Curr ---------------------------------------------------------
    delta_prev = (
        req_prev[['SamplingPointID', 'ComponentName', 'Min_Samples']]
                .merge(req_curr.rename(columns={'Analyte': 'ComponentName'})
                               [['SamplingPointID', 'ComponentName', 'Min_Samples']],
                       on=['SamplingPointID', 'ComponentName'],
                       suffixes=('_prev', '_curr'))
    )
    delta_prev = delta_prev[delta_prev.Min_Samples_prev != delta_prev.Min_Samples_curr]

    start_prev = next_end + 1
    ws.merge_range(
        start_prev, 0, start_prev, 5,
        f"Changes to the program from FY{fmt(fy_tag_prev)} to FY{fmt(fy_tag_curr)}",
        t_fmt
    )

    if delta_prev.empty:
        ws.write(start_prev + 1, 0, 'No changes to the monitoring program this year', c_fmt)
    else:
        dh = ['SamplingPointID', 'Analyte', 'Previous Year Requirement', 'New Requirement']
        for c, h in enumerate(dh):
            ws.write(start_prev + 1, c, h, h_fmt)
        for i, row in enumerate(delta_prev.itertuples(index=False), start=start_prev + 2):
            ws.write(i, 0, row.SamplingPointID,   c_fmt)
            ws.write(i, 1, row.ComponentName,     c_fmt)
            ws.write(i, 2, row.Min_Samples_prev,  c_fmt)
            ws.write(i, 3, row.Min_Samples_curr,  c_fmt)