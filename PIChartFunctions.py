import pandas as pd
import PIconnect as PI
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
from plotformating import line_chart_formatting
import warnings
warnings.filterwarnings("ignore")


# PI AF connection settings
SERVER_NAME   = "SAWPAF01"
DATABASE_NAME = "PT Wastewater Performance"

def PiDataRetrival(site_name_to_retrieve, end_date=None):
    """
    Returns a DataFrame of raw PI values for the given site,
    with columns ['Site','Attribute','Timestamp','Value'].
    
    Parameters:
    -----------
    site_name_to_retrieve : str
        The name of the site to retrieve data for
    end_date : datetime, optional
        The reporting end date. If None, uses current time.
        Data retrieval starts at the beginning of the earliest financial year
        needed to calculate the rolling 5-full-FY baseline.
    """
    attributes_of_interest = [
        "1 - Influent", "2 - Effluent",
        "3 - Reuse", "5 - Discharge to Environment"
    ]
    data_rows = []

    try:
        with PI.PIAFDatabase(server=SERVER_NAME, database=DATABASE_NAME) as database:
            wastewater = database.descendant("Wastewarter Treatment")
            if not wastewater:
                return pd.DataFrame(data_rows)

            specific_site = wastewater.children.get(site_name_to_retrieve)
            if not specific_site:
                return pd.DataFrame(data_rows)

            monthly = specific_site.children.get("Monthly Summary") or \
                      specific_site.children.get("Monthly Summary (Contractor)")
            if not monthly:
                return pd.DataFrame(data_rows)

            for attr in attributes_of_interest:
                attribute = monthly.attributes.get(attr)
                if not attribute:
                    continue

                # Use provided end_date or default to current time.
                # The 5-year average uses the five full FYs prior to the report FY,
                # so fetch from the earliest required FY start.
                end_time = pd.Timestamp(end_date) if end_date is not None else pd.Timestamp.now()
                asof_fy_end_year = (end_time - pd.Timedelta(days=1)).to_period('Y-JUN').year
                latest_full_fy_end_year = asof_fy_end_year - 1
                start_time = pd.Timestamp(year=latest_full_fy_end_year - 5, month=7, day=1)
                recorded = attribute.recorded_values(start_time=start_time, end_time=end_time)
                for ts, val in recorded.items():
                    data_rows.append({
                        "Site":      site_name_to_retrieve,
                        "Attribute": attr,
                        "Timestamp": ts,
                        "Value":     val
                    })
    except AttributeError:
        return pd.DataFrame(data_rows)

    df = pd.DataFrame(data_rows)
    if df.empty:
        return df

    # Clean up Timestamp & Value columns
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce', utc=True)
    df = df.dropna(subset=['Timestamp'])
    ad_tz = pytz.timezone('Australia/Adelaide')
    df['Timestamp'] = df['Timestamp'].dt.tz_convert(ad_tz).dt.date
    df['Value']     = pd.to_numeric(df['Value'], errors='coerce')
    return df

def calculate_5_year_average(df, end_date=None):
    """
    Given a DataFrame from PiDataRetrival, returns monthly averages calculated
    from exactly five complete financial years (Jul-Jun), dynamically anchored
    to end_date.

    Parameters:
    -----------
    df : DataFrame
        Raw PI data from PiDataRetrival
    end_date : datetime, optional
        The reporting end date. If None, uses current time.
        The five FYs used are the five complete FYs prior to the FY containing
        end_date.
    """
    df = df.copy()
    if df.empty:
        return pd.DataFrame(columns=['Attribute', 'Month', 'Value'])

    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce', utc=True)
    df = df.dropna(subset=['Timestamp'])

    end_dt = pd.to_datetime(end_date, utc=True) if end_date else pd.Timestamp.now(tz='UTC')

    # Anchor to end_dt - 1 day so 1 July belongs to the new report FY,
    # then use the five complete FYs before that report FY.
    asof_fy_end_year = (end_dt - pd.Timedelta(days=1)).to_period('Y-JUN').year
    full_fy_end_years = list(range(asof_fy_end_year - 5, asof_fy_end_year))

    df['FYEndYear'] = df['Timestamp'].dt.to_period('Y-JUN').dt.year
    df = df[df['FYEndYear'].isin(full_fy_end_years)]

    if df.empty:
        return pd.DataFrame(columns=['Attribute', 'Month', 'Value'])

    df.loc[:, 'Month'] = df['Timestamp'].dt.month
    return df.groupby(['Attribute','Month'])['Value'].mean().reset_index()


def PiFlowsChart(summary_df, attribute, attributetitle, site_name, five_year_avg_df):
    # Ensure the 'Timestamp' column is in UTC to avoid comparison issues
    summary_df['Timestamp'] = pd.to_datetime(summary_df['Timestamp'], utc=True)

    # Filter current year and 5-year average data for the selected attribute
    current_year_start = pd.to_datetime('2023-07-01', utc=True)
    df_attr = summary_df[(summary_df['Attribute'] == attribute) & (summary_df['Timestamp'] >= current_year_start)].copy()
    df_avg_attr = five_year_avg_df[five_year_avg_df['Attribute'] == attribute].copy()

    if df_attr.empty:
        print(f"No data available for {site_name}: {attributetitle}")
        return None

    # Generate a date range for July to June (but without specific year)
    x_axis_dates = pd.date_range(start='2023-07-01', end='2024-06-30', freq='MS').strftime('%b')

    # Handle cases where the 5-year average is missing
    if df_avg_attr.empty:
        print(f"No 5-year average available for {site_name}: {attributetitle}")
        avg_values = [None] * 12
    else:
        # Ensure 'Month' exists and group data by month to calculate the average for each month (July to June)
        df_avg_attr.loc[:, 'Month'] = df_avg_attr['Month'].astype(int)
        avg_values_per_month = df_avg_attr.groupby('Month')['Value'].sum()  # Use sum instead of mean

        # Create a full list of month numbers (7 to 12 for July to December, 1 to 6 for January to June)
        full_months = list(range(7, 13)) + list(range(1, 7))

        # Reindex to make sure we have values for all months
        avg_values = avg_values_per_month.reindex(full_months).fillna(0)  # Fill missing months with 0

    # Ensure 'Timestamp' exists and handle the warning by using .loc[]
    df_attr.loc[:, 'Month'] = df_attr['Timestamp'].dt.month
    df_attr.loc[:, 'Month_Label'] = df_attr['Timestamp'].dt.strftime('%b')

    # Aggregate the data by month using sum
    df_attr_agg = df_attr.groupby('Month_Label')['Value'].sum().reindex(x_axis_dates, fill_value=0)

    # Create the figure
    fig = go.Figure()

    # Main line for the current year
    fig.add_trace(go.Scatter(
        x=df_attr_agg.index,
        y=df_attr_agg.values,
        mode='lines+markers',
        line=dict(color='#4E79A7', width=4),
        marker=dict(size=10, symbol='circle', color='#4E79A7'),
        name=f"{site_name} 2023-24"
    ))

    # 5-year average line
    fig.add_trace(go.Scatter(
        x=x_axis_dates,
        y=avg_values,
        mode='lines+markers',
        line=dict(color='red', dash='dash', width=4),
        marker=dict(size=10, symbol='circle', color='red'),
        name="5-Year Average"
    ))

    # Apply custom formatting
    fig = line_chart_formatting(fig, f"{site_name}: {attributetitle}")
    print(f"Returning Chart for {site_name}")
    return fig



attribute_mapping = {
    '1 - Influent': 'Influent',
    '3 - Reuse': 'Reuse',
    '5 - Discharge to Environment': 'Discharge to Environment'
}
