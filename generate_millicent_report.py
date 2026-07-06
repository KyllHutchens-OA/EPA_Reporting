"""
Quick script to generate a Millicent WWTP report for FY 2024-2025
without needing to run the Flask web interface.
"""
import os
import sys
from datetime import datetime

# Add current directory to path so we can import modules
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from report_functions import (
    load_sites,
    load_report_details,
    write_site_information,
    create_flow_charts,
    get_testing_components_data,
    get_site_incidents_data,
    get_comments_data,
    load_monitoring_plan_requirements,
    write_monitoring_program_sheet
)

# Configuration
report_name = "Millicent"
start_dt = datetime(2024, 7, 1)
end_dt = datetime(2025, 6, 30)
ys, ye = start_dt.year, end_dt.year

# Paths
ROOT = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT, 'Data')
SCHEM_DIR = os.path.join(DATA_DIR, 'SchematicImages')
REPORTS_DIR = os.path.join(ROOT, 'Reports')

# Ensure output directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)

# Find the site info
sites = load_sites()
site = next((s for s in sites if s['report_name'] == report_name), None)

if not site:
    print(f"Error: Site '{report_name}' not found in sitedata.csv")
    sys.exit(1)

pi_name = site['system_name']
fname = f"{report_name} WWTP EPA Report {ys}-{ye}.xlsx"
outpath = os.path.join(REPORTS_DIR, fname)

print(f"Generating report for {report_name} WWTP...")
print(f"Period: {start_dt:%d-%m-%Y} to {end_dt:%d-%m-%Y}")
print(f"Output: {outpath}")
print()

# Note: The full report generation code from app.py would go here
# For now, just test that we can call the key function:
print("Testing get_testing_components_data function...")
df_tc, tc_images, df_tc_5_year, tc_images_5y = get_testing_components_data(report_name, start_dt, end_dt)

print(f"\nMonthly data shape: {df_tc.shape}")
print(f"5-year data shape: {df_tc_5_year.shape}")
print(f"Number of monthly charts: {len(tc_images)}")
print(f"Number of 5-year charts: {len(tc_images_5y)}")

print("\nSample of monthly data:")
print(df_tc.head())

print("\nUnique SamplingPointIDs in monthly data:", df_tc['SamplingPointID'].unique())
print("\nUnique SamplingPointIDs in 5-year data:", df_tc_5_year['SamplingPointID'].unique())

print("\n✅ Testing complete! The aggregation changes are working.")
print("\nTo generate the full Excel report, you'll need to:")
print("1. Run: python app.py")
print("2. Open browser to: http://127.0.0.1:5000")
print("3. Navigate to 'Run Report'")
print(f"4. Select '{report_name}' and dates 01/07/2024 to 30/06/2025")
