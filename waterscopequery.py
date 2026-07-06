import pandas as pd
import pyodbc
import pytz
adtz = pytz.timezone("Australia/Adelaide")
import warnings
warnings.filterwarnings("ignore")


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
    end_date   = pd.Timestamp(f"{start_year + num_years}-06-30")

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

    for _, row in sampling_data.iterrows():
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
    WHERE vw.[SampledDate] BETWEEN ? AND ?
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
    df = pd.merge(df, sampling_data, on=['SamplingPointID','ComponentName'], how='left')
    df['SampledDate'] = pd.to_datetime(df['SampledDate'])
    df.rename(columns={
        'ResultValue':'Value',
        'SampledDate':'Timestamp',
        'ComponentName':'Attribute'
    }, inplace=True)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce', utc=True).dt.tz_convert(adtz)

    return df[df['Site'] == site]
