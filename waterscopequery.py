import pandas as pd
import pyodbc
import pytz
adtz = pytz.timezone("Australia/Adelaide")
import warnings
warnings.filterwarnings("ignore")


# Sampling points that replaced another mid-year. sitedata.csv lists `new`; results
# for `old` before `effective` (Adelaide local) are reported under `new`, `old`
# results from that date onward are ignored, and `new` results before it are ignored.
# Add a tuple here for any future swap.
SAMPLING_POINT_SWAPS = [
    # (old_id, new_id, effective_date)
    ("93749", "93752", "2025-11-14"),   # Wirrina WWTP
]


def to_utc(ts):
    ts = pd.Timestamp(ts)
    # If no tz info → assume Adelaide local time, then convert to UTC
    if ts.tzinfo is None:
        ts = ts.tz_localize(adtz)
    else:
        ts = ts.tz_convert(adtz)
    return ts.tz_convert(pytz.UTC)



def waterscope_data(conn, sampling_data, site, start_year, num_years):
    start_date = pd.Timestamp(f"{start_year}-07-01")
    # Exclusive upper bound: 1 July 00:00 so all of 30 June is included
    end_date   = pd.Timestamp(f"{start_year + num_years}-07-01")

    # Normalise incoming bounds to Adelaide tz
    start_date = to_utc(start_date)
    end_date   = to_utc(end_date)
         

    cursor = conn.cursor()
    cursor.execute("CREATE TABLE #TempSamplingPoints (SamplingPointID INT, ComponentName VARCHAR(255))")

    # DEBUG: Check what's being inserted into temp table
    print("\n=== DEBUG: Temp Sampling Points Table ===")
    print(f"Total rows being inserted: {len(sampling_data)}")
    tds_rows = sampling_data[sampling_data['ComponentName'] == 'Total Dissolved Solids (by EC)']
    print(f"Rows for 'Total Dissolved Solids (by EC)': {len(tds_rows)}")
    if not tds_rows.empty:
        print("Sample TDS rows:")
        print(tds_rows.head())

    # also query the former points, borrowing the current point's components
    alias_rows = [
        {**r, 'SamplingPointID': old}
        for old, new, _ in SAMPLING_POINT_SWAPS
        for r in sampling_data[sampling_data['SamplingPointID'].astype(str) == new]
                              .to_dict('records')
    ]
    query_data = pd.concat([sampling_data, pd.DataFrame(alias_rows)], ignore_index=True) \
        if alias_rows else sampling_data

    for _, row in query_data.iterrows():
        cursor.execute(
            "INSERT INTO #TempSamplingPoints (SamplingPointID, ComponentName) VALUES (?, ?)",
            row['SamplingPointID'], row['ComponentName']
        )

    # DEBUG: Verify temp table contents
    cursor.execute("SELECT * FROM #TempSamplingPoints WHERE ComponentName LIKE '%Dissolved Solids%'")
    temp_table_tds = cursor.fetchall()
    print(f"TDS rows in actual temp table: {len(temp_table_tds)}")
    if temp_table_tds:
        print("Temp table TDS rows:", temp_table_tds[:3])

    query = f"""
    SELECT
        CASE
            WHEN SUBSTRING(vw.[ResultChar],1,1) = '<' AND vw.[ResultValue] <> 0
                 THEN vw.[ResultValue] / 2
            ELSE vw.[ResultValue]
        END AS [ResultValue],
        vw.[SampledDate],
        vw.[SamplingPointID],
        vw.[ComponentName],
        vw.[SamplingPointDescription]
    FROM [WaterScope].[dbo].[vwCrystalResults] AS vw
    WHERE vw.[SampledDate] >= ? AND vw.[SampledDate] < ?
      AND NOT (ISNULL(vw.[ResultPublishStatusName], '') = 'Withdrawn (cancelled)' AND vw.[ResultChar] IS NULL)
      AND EXISTS (
          SELECT 1
          FROM #TempSamplingPoints t
          WHERE vw.[SamplingPointID] = t.SamplingPointID
            AND vw.[ComponentName] COLLATE SQL_Latin1_General_CP1_CI_AS = t.ComponentName
      )
    ORDER BY vw.[SampledDate] ASC
    """

    df = pd.read_sql_query(query, conn, params=[start_date, end_date])

    # DEBUG: Check query results
    print(f"\nQuery returned {len(df)} total rows")
    if not df.empty:
        tds_in_result = df[df['ComponentName'].str.contains('Dissolved Solids', case=False, na=False)]
        print(f"Rows with 'Dissolved Solids' in ComponentName: {len(tds_in_result)}")
        if not tds_in_result.empty:
            print("Sample results:")
            print(tds_in_result[['SamplingPointID', 'ComponentName', 'SampledDate', 'ResultValue']].head())

    cursor.execute("DROP TABLE #TempSamplingPoints")

    if df.empty:
        return pd.DataFrame()

    # merge in site info and clean up
    df['SamplingPointID'] = df['SamplingPointID'].astype(str)
    sampling_data['SamplingPointID'] = sampling_data['SamplingPointID'].astype(str)
    df['SampledDate'] = pd.to_datetime(df['SampledDate'])

    # apply mid-year sampling point swaps: old point before the date, new point from it,
    # all reported under the new (sitedata.csv) ID
    for old, new, effective in SAMPLING_POINT_SWAPS:
        cutoff = pd.Timestamp(effective)
        sampled = pd.to_datetime(df['SampledDate'], utc=True).dt.tz_convert(adtz).dt.tz_localize(None)
        drop = ((df['SamplingPointID'] == old) & (sampled >= cutoff)) | \
               ((df['SamplingPointID'] == new) & (sampled < cutoff))
        df = df[~drop].copy()
        df.loc[df['SamplingPointID'] == old, 'SamplingPointID'] = new

    if df.empty:
        return pd.DataFrame()
    df = pd.merge(df, sampling_data, on=['SamplingPointID','ComponentName'], how='left')
    df.rename(columns={
        'ResultValue':'Value',
        'SampledDate':'Timestamp',
        'ComponentName':'Attribute'
    }, inplace=True)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce', utc=True).dt.tz_convert(adtz)

    return df[df['Site'] == site]
