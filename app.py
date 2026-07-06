import sys
import subprocess
import pkg_resources
import os
#C:\Data\Python\myenv\Scripts\activate
def _install_requirements():
    req_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    try:
        with open(req_file) as f:
            requirements = [r.strip() for r in f if r.strip() and not r.startswith('#')]
    except FileNotFoundError:
        return

    installed = {pkg.key for pkg in pkg_resources.working_set}
    to_install = []
    for req in requirements:
        pkg = pkg_resources.Requirement.parse(req)
        if pkg.key not in installed:
            to_install.append(req)

    if to_install:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *to_install])

_install_requirements()
import os
import csv
import io
import calendar
import numpy as np
import warnings
warnings.filterwarnings("ignore")


from datetime import datetime
import pandas as pd
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash,
    send_from_directory
)

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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'G5WWE2LWY41T'

# Paths
ROOT         = app.root_path
DATA_DIR     = os.path.join(ROOT, 'Data')
SITE_FILE    = os.path.join(DATA_DIR, 'sitedata.csv')
DETAILS_FILE = os.path.join(DATA_DIR, 'reportdetails.csv')
SCHEM_DIR    = os.path.join(DATA_DIR, 'SchematicImages')
REPORTS_DIR  = os.path.join(ROOT, 'Reports')

# Ensure required directories exist
for d in (DATA_DIR, SCHEM_DIR, REPORTS_DIR):
    os.makedirs(d, exist_ok=True)

# CSV header for reportdetails.csv
DETAILS_FIELDS = [
    'Report Name',
    'Site Name and Address',
    'Licence Number',
    'Certification',
    'Population Served',
    'Hydraulic Design Capacity',      
    'Loading Design Capacity',
    'Primary Treatment',
    'Secondary Treatment',
    'Disinfection',
    'Discharge',
    'Sludge Treatment/Management',
    'Effluent Discharge',
    'Effluent Reuse',
    'BOD Internal Monitoring Target',
    'Ammonia as N Target',
    'Suspended Solids Target',
    'Total Nitrogen Target',
    'Total Phosphorus Target',
    'Monitoring Plan Title',
    'Monitoring Plan Approval Date',
    'Monitoring Plan Compliance',
    'Quality Assurance / Control'
]


@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/add_site', methods=['GET','POST'])
def add_site():
    if request.method == 'POST':
        row = {
            'SamplingPointID': request.form['samplingpoint_id'].strip(),
            'SystemName':       request.form['system_name'].strip(),
            'Location Type':    request.form['location_type'].strip(),
            'Report Name':      request.form['report_name'].strip(),
            'SAAM Name':        request.form['saam_name'].strip()
        }
        with open(SITE_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writerow(row)
        flash('Site added to CSV.', 'success')
        return redirect(url_for('add_site'))

    sites = load_sites()
    return render_template('add_site.html', sites=sites)

"""@app.route('/edit_data', methods=['GET','POST'])
def edit_data():
    sites   = load_sites()
    entries = []  # to fill later
    return render_template('edit_data.html', sites=sites, entries=entries)
"""
@app.route('/upload_schematics', methods=['GET','POST'])
def upload_schematics():
    sites          = load_sites()
    existing_files = sorted(os.listdir(SCHEM_DIR))

    if request.method == 'POST':
        site_name = request.form.get('site_name')
        file      = request.files.get('schematic')
        replace   = bool(request.form.get('replace'))

        if not site_name or not file:
            flash('Select a site and file.', 'danger')
            return redirect(url_for('upload_schematics'))

        site = next((s for s in sites if s['report_name']==site_name), None)
        if not site:
            flash('Invalid site.', 'danger')
            return redirect(url_for('upload_schematics'))

        ext      = file.filename.rsplit('.',1)[-1]
        filename = f"{site['report_name']} WWTP- Draft.{ext}"
        path     = os.path.join(SCHEM_DIR, filename)

        if os.path.exists(path) and not replace:
            flash(f"'{filename}' exists. Tick replace to overwrite.", 'warning')
            return redirect(url_for('upload_schematics'))

        file.save(path)
        flash('Schematic uploaded.', 'success')
        return redirect(url_for('upload_schematics'))

    return render_template(
        'upload_schematics.html',
        sites=sites,
        schematics=existing_files
    )


@app.route('/report_process_details', methods=['GET','POST'])
def report_process_details():
    sites = load_sites()

    # map CSV columns → form fields
    field_map = {
    'Report Name':                      'report_name',
    'Site Name and Address':            'site_address',
    'Licence Number':                   'licence_number',
    'Certification':                    'certification',
    'Population Served':                'population_served',
    'Hydraulic Design Capacity':        'hydraulic_capacity',
    'Loading Design Capacity':          'loading_capacity',
    'Primary Treatment':                'primary_treatment',
    'Secondary Treatment':              'secondary_treatment',
    'Disinfection':                     'disinfection',
    'Discharge':                        'discharge',
    'Sludge Treatment/Management':      'sludge_treatment',
    'Effluent Discharge':               'effluent_discharge',
    'Effluent Reuse':                   'effluent_reuse',
    # new monitoring targets
    'BOD Internal Monitoring Target':   'bod_internal_target',
    'Ammonia as N Target':              'ammonia_n_target',
    'Suspended Solids Target':          'suspended_solids_target',
    'Total Nitrogen':                   'total_nitrogen',
    'Total Phosphorus':                 'total_phosphorus',
    # new plan details
    'Monitoring Plan Title':            'monitoring_plan_title',
    'Monitoring Plan Approval Date':    'monitoring_plan_approval_date',
    'Monitoring Plan Compliance':       'monitoring_plan_compliance',
    'Quality Assurance / Control':      'quality_assurance_control' }
    if request.method == 'POST':
        new_row = {}
        for csv_col, form_field in field_map.items():
            val = request.form.get(form_field)
            if val is None:
                flash(f"Missing field: {form_field}", 'danger')
                return redirect(url_for('report_process_details'))
            new_row[csv_col] = val.strip()

        write_header = not os.path.exists(DETAILS_FILE) or os.stat(DETAILS_FILE).st_size == 0
        with open(DETAILS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(field_map.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(new_row)

        flash('Process details saved.', 'success')
        return redirect(url_for('report_process_details'))

    details = load_report_details()
    return render_template(
        'report_process_details.html',
        sites=sites,
        details=details
    )
@app.route('/run_report', methods=['GET','POST'])
def run_report():
    sites = load_sites()
    download_files = []
    Incomplete_download_files = []

    if request.method == 'POST':
        scope    = request.form['scope']
        start_dt = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        end_dt   = datetime.strptime(request.form['end_date'],   '%Y-%m-%d')

        if scope == 'single':
            sel = request.form.get('site_id')
            if not sel:
                flash('No site selected.', 'danger')
                return redirect(url_for('run_report'))
            selected = [s for s in sites if s['report_name'] == sel]
        else:
            selected = sites

        os.makedirs(REPORTS_DIR, exist_ok=True)
        
        # This set ensures we only generate one report per report_name, even if 'all' is selected.
        processed_report_names = set()

        for s in selected:
            if s['report_name'] in processed_report_names:
                continue # Skip if we've already generated a report for this site name
            
            processed_report_names.add(s['report_name'])

            report_name = s['report_name']
            pi_name     = s['system_name']
            ys, ye      = start_dt.year, end_dt.year
            fname       = f"{report_name} WWTP EPA Report {ys}-{ye}.xlsx"
            outpath     = os.path.join(REPORTS_DIR, fname)

            try:
                with pd.ExcelWriter(outpath, engine='xlsxwriter') as writer:
    # --- Front Page ---
                    fp_ws = writer.book.add_worksheet('Front Page')
                    writer.sheets['Front Page'] = fp_ws

                    # Column widths
                    fp_ws.set_column('A:A', 40)
                    fp_ws.set_column('B:B', 30)
                    fp_ws.set_column('C:C', 20)
                    fp_ws.set_column('D:D', 24)

                    # Row height
                    fp_ws.set_row(0, 40)
                    fp_ws.set_row(5, 100)  # Set height for row 6
                    fp_ws.set_row(8, 70) 
                    # Insert logo
                    logo_path = os.path.join(DATA_DIR, 'SAWLogo.png')
                    fp_ws.insert_image('B1', logo_path, {'x_scale': 0.4, 'y_scale': 0.4})

                    # Formats
                    table_cell_fmt = writer.book.add_format({'font': 'Century Gothic','border': 1, 'align': 'left'})
                    site_fmt = writer.book.add_format({'font_size': 18, 'bold': True, 'font': 'Century Gothic'})
                    report_title_fmt = writer.book.add_format({
                        'font_size': 15, 'bold': True, 'font_color': 'white',
                        'font': 'Century Gothic', 'bg_color': '#003c69'
                    })
                    info_fmt = writer.book.add_format({
                        'font_size': 11, 'bold': True, 'font': 'Century Gothic', 'bg_color': '#dedbd2'
                    })
                    info_fmt_with_border = writer.book.add_format({
                        'font_size': 11,  'font': 'Century Gothic',
                        'bg_color': '#dedbd2', 'border': 1
                    })
                    info_fmt_wrapped = writer.book.add_format({
                        'font_size': 11, 'font': 'Century Gothic',
                        'bg_color': '#dedbd2', 'border': 1,
                        'text_wrap': True, 'valign': 'top'
                    })

                    # Headers
                    fp_ws.write('A1', f'{report_name} WWTP', site_fmt)
                    fp_ws.write('A2', f"{ys} / {ye} EPA Report", report_title_fmt)

                    # Table rows A3:A9 with merged B-D cells and borders
                    from report_functions import load_report_details
                    details = next((r for r in load_report_details() if r.get('Report Name') == report_name), {})

                    labels_and_keys = [
                        ("Site Name", report_name),
                        ("Reporting Period", f"{start_dt:%d-%m-%Y} to {end_dt:%d-%m-%Y}"),
                        ("Report Submission Date", ''),  # Leave blank or populate if known
                        ("Report Objective", "Detail the physical, chemical, biological, and microbiological quality (including concentrations and, where appropriate, mass loads) of treated effluent discharged to the receiving environment. In accordance with the approved EPA licence conditions provide a consolidated report describing the results of the monitoring program and supporting operational context for the Reporting Period."),
                        ("Site Name and Address", details.get("Site Name and Address", "")),
                        ("Licence Number", details.get("Licence Number", "")),
                        ("Certification", details.get("Certification", ""))
                    ]

                    for i, (label, value) in enumerate(labels_and_keys):
                        row = 2 + i
                        fp_ws.write(row, 0, label, info_fmt_with_border)
                        if i == 3 or i == 6:
                            fp_ws.merge_range(row, 1, row, 3, value, info_fmt_wrapped)
                        else:
                            fp_ws.merge_range(row, 1, row, 3, value, info_fmt_with_border)

                    # Version History section
                    fp_ws.write('A10', "Version History", report_title_fmt)
                    fp_ws.write_row(10, 0, ['Version', 'Date', 'Author', 'Comments'], info_fmt)
                    fp_ws.write_row(11, 0, ['0.1', '', 'Kyll Hutchens', 'Automatic Generation'], table_cell_fmt)
                    for i in range(2):
                        fp_ws.write_row(12 + i, 0, ['', '', '', ''], table_cell_fmt)

                    # Reviewers section
                    fp_ws.write('A16', "Reviewers", report_title_fmt)
                    fp_ws.write_row(16, 0, ['Reviewer Name', 'Reviewer Role', 'Signature', 'Date'], info_fmt)
                    for i in range(1):
                        fp_ws.write_row(17 + i, 0, ['Ben Thwaites', 'Mgr Wastewater Treatment Operations', '', ''], table_cell_fmt)

                    # Approvers section
                    fp_ws.write('A20', "Approvers", report_title_fmt)
                    fp_ws.write_row(20, 0, ['Approver Name', 'Approver Role', 'Signature', 'Date'], info_fmt)
                    for i in range(1):
                        fp_ws.write_row(21 + i, 0, ['Angela Dewdney', 'Mgr Environmental Performance and Compliance', '', ''], table_cell_fmt)

                    # Disclaimer
                    fp_ws.write('A25',
                        f"© {ye} SA Water Corporation. All rights reserved. "
                        "This document may contain confidential information of SA Water "
                        "Corporation. Disclosure or dissemination to unauthorised individuals "
                        "is strictly prohibited. Uncontrolled when printed or downloaded."
                    )
                    
                    write_site_information(writer, report_name, start_dt, end_dt)


                    # --- Flows Data ---
                    df_flows, _, flow_images, flow_images_5y,df_flows_5y = create_flow_charts(pi_name, start_dt, end_dt, report_name, ys, ye)
                    df_flows = df_flows.round(2)
                    df_flows.columns = ['Month', 'Influent (ML)', 'Effluent (ML)', 'Reuse (ML)', 'Discharge (ML)']

                    df_flows_5y = df_flows_5y.round(2)
                    df_flows_5y.columns = ['Financial Year', 'Influent (ML)', 'Effluent (ML)', 'Reuse (ML)', 'Discharge (ML)']

                    # Write headers manually for better control
                    ws_flow = writer.book.add_worksheet('Flows Data')
                    writer.sheets['Flows Data'] = ws_flow

                    # Formats
                    title_fmt = writer.book.add_format({'bold': True, 'font_size': 15, 'font': 'Century Gothic'})
                    header_fmt = writer.book.add_format({'bold': True, 'bg_color': '#003c69', 'font_color': 'white', 'border': 1, 'align': 'center', 'font': 'Century Gothic'})
                    cell_fmt = writer.book.add_format({'border': 1, 'align': 'center', 'font': 'Century Gothic'})
                    sum_cell_fmt = writer.book.add_format({'bold': True,'border': 1, 'align': 'center', 'font': 'Century Gothic'})

                    # Set column widths
                    ws_flow.set_column('A:A', 13)
                    ws_flow.set_column('B:E', 16)

                    ws_flow.set_column('I:I', 15)
                    ws_flow.set_column('J:M', 16)
                    
    
                    # Section title
                    ws_flow.write('A1', 'Flow Data', title_fmt)

                    # Write header row
                    for col_idx, col_name in enumerate(df_flows.columns):
                        ws_flow.write(2, col_idx, col_name, header_fmt)

                    # Write data rows
                    for row_idx, row in enumerate(df_flows.itertuples(index=False), start=3):
                        for col_idx, value in enumerate(row):
                            if pd.isna(value) or value in (float('inf'), float('-inf')):
                                ws_flow.write_blank(row_idx, col_idx, None, cell_fmt)
                            else:
                                ws_flow.write(row_idx, col_idx, value, cell_fmt)
                    # Add SUM row
                    sum_row = len(df_flows) + 3
                    ws_flow.write(sum_row, 0, 'SUM', header_fmt)
                    for col_idx in range(1, 5):
                        col_letter = chr(65 + col_idx)  # B, C, D, E
                        formula = f"=SUM({col_letter}4:{col_letter}{sum_row})"
                        ws_flow.write_formula(sum_row, col_idx, formula, sum_cell_fmt)


                    # 5 year data
                    # Write header row
                    for col_idx, col_name in enumerate(df_flows_5y.columns):
                        ws_flow.write(2, col_idx+8, col_name, header_fmt)

                    # Write data rows
                    for row_idx, row in enumerate(df_flows_5y.itertuples(index=False), start=3):
                        for col_idx, value in enumerate(row):
                            if pd.isna(value) or value in (float('inf'), float('-inf')):
                                ws_flow.write_blank(row_idx, col_idx+8, None, cell_fmt)
                            else:
                                ws_flow.write(row_idx, col_idx+8, value, cell_fmt)
                    # Add SUM row
                    sum_row = len(df_flows_5y) + 3
                    ws_flow.write(sum_row, 8, 'SUM', header_fmt)
                    for col_idx in range(1, 5):
                        col_letter = chr(65 + col_idx+8)  # B, C, D, E
                        formula = f"=SUM({col_letter}4:{col_letter}{sum_row})"
                        ws_flow.write_formula(sum_row, col_idx+8, formula, cell_fmt)


                    # --- Graphs ---
                    # Monthly
                    ws_flow.write('A20', 'Graphs', title_fmt)
                    chart_row = 21
                    for idx, metric in enumerate(['Influent', 'Effluent', 'Reuse', 'Discharge']):
                        img = flow_images.get(metric)
                        if not img:
                            continue
                        r = chart_row + (idx // 1) * 20
                        c = (idx % 1) * 9
                        ws_flow.insert_image(r, c, f"{metric}.png", {'image_data': img, 'x_scale': 0.75, 'y_scale': 0.75})
                    
                    # Yearly
                    
                    # ws_flow.write('A20', 'Graphs', title_fmt)
                    chart_row = 21
                    for idx, metric in enumerate(['Influent', 'Effluent', 'Reuse', 'Discharge']):
                        img = flow_images_5y.get(metric)
                        if not img:
                            continue
                        r = chart_row + (idx // 1) * 20
                        c = 8
                        ws_flow.insert_image(r, c, f"{metric}.png", {'image_data': img, 'x_scale': 0.75, 'y_scale': 0.75})                        

                    # --- Testing Components Data ---
                    df_flows = df_flows.copy()
                    df_tc, tc_images,df_tc_5_year,tc_images_5y = get_testing_components_data(report_name, start_dt, end_dt)
                    # df_tc = df_tc.round(2)
                    df_tc = df_tc


                    # df_tc_5_year = df_tc_5_year.round(2)
                    df_tc_5_year = df_tc_5_year.copy()
                    has_discharge = 'Discharge to Environment' in df_tc.columns
                    fy_tag_curr = f"{str(start_dt.year)[-2:]}{str(end_dt.year)[-2:]}"
                    req_df      = load_monitoring_plan_requirements(fy_tag_curr)

                    # PID → description map (for nicer titles)
                    pid_to_desc_map = (
                        req_df.drop_duplicates(subset=['SamplingPointID'])
                            .set_index('SamplingPointID')['SamplePointDescription']
                            .to_dict()
                    )

                    ws_tc = writer.book.add_worksheet('Testing Components Data')
                    writer.sheets['Testing Components Data'] = ws_tc

                    # Formats
                    main_title_fmt = writer.book.add_format({'bold': True, 'font_size': 15, 'font': 'Century Gothic'})
                    title_fmt      = writer.book.add_format({'bold': True, 'font_size': 15,
                                                            'font_color': 'white', 'bg_color': '#003c69',
                                                            'font': 'Century Gothic','text_wrap': True,'align': 'center'})
                    title_fmt2      = writer.book.add_format({'bold': True, 'font_size': 15,
                                                            'font_color': 'white', 'bg_color': '#003c69',
                                                            'font': 'Century Gothic','text_wrap': True,'align': 'center','valign': 'top'})                    

                    header_fmt = writer.book.add_format({
                        'bold': True, 'bg_color': '#E0E0E0', 'border': 1,
                        'align': 'center', 'valign': 'top', 'font': 'Century Gothic',
                        'text_wrap': True
                    })
                    # cell_fmt  = writer.book.add_format({'border': 1, 'align': 'center', 'font': 'Century Gothic'})

                    # Define your base format once
                    base_fmt = {'border': 1, 'align': 'center', 'font': 'Century Gothic'}

                    # Create formats from it
                    cell_fmt = writer.book.add_format(base_fmt)                # generic
                    fmt_0dp = writer.book.add_format({**base_fmt, 'num_format': '0'})
                    fmt_2dp  = writer.book.add_format({**base_fmt, 'num_format': '0.00'})
                    fmt_4dp  = writer.book.add_format({**base_fmt, 'num_format': '0.0000'})

                    # If you also need a generic (text) format, reuse cell_fmt itself
                    fmt_text = cell_fmt  


                    sum_fmt   = writer.book.add_format({'bold': True, 'border': 1, 'align': 'center',
                                                        'font': 'Century Gothic'})

                    ws_tc.set_column('A:A', 12)
                    ws_tc.set_column('B:C', 24)
                    ws_tc.set_column('D:D', 19)
                    ws_tc.set_column('E:F', 22)

                    ws_tc.set_column('H:K', 22)
                    # ws_tc.set_column('J:K', 22)


                    ws_tc.write('A1', 'Sampled Components Data', main_title_fmt)
                    row_cursor = 2

                    components = [
                        'Ammonia as N', 'Nitrogen - Total', 'Phosphorus - Total',
                        'Suspended Solids', 'Biochemical Oxygen Demand',
                        'Copper - Total', 'Lead - Total', 'Total Dissolved Solids (by EC)','Zinc - Total'
                    ]

                    if has_discharge:
                        headers = [
                            'Month',
                            'Average Concentration (mg/L)',
                            '5-yr Average Concentration (mg/L)',
                            'Discharge to Environment (ML)',
                            'Loading (kg/month)',
                            '5-yr Average Loading (kg/month)'
                        ]
                    else:
                        headers = [
                            'Month',
                            'Average Concentration (mg/L)',
                            '5-yr Average Concentration (mg/L)'
                        ]

                    # PIDs that actually have data
                    pids_with_data = sorted(df_tc['SamplingPointID'].unique())

                    for pid in pids_with_data:
                        df_pid_specific = df_tc[df_tc['SamplingPointID'] == pid]


                        for comp in components:
                            # skip components without any data
                            if comp not in df_pid_specific.columns:# or df_pid_specific[comp].fillna(0).sum() == 0:
                                continue

                            section_start = row_cursor
                            desc          = pid_to_desc_map.get(pid, 'Unknown Location')
                            if has_discharge:                            
                                ws_tc.merge_range(
                                    row_cursor, 0, row_cursor, 5,
                                    f"{comp} – {desc} ({pid})",
                                    title_fmt
                                )
                            else:                           
                                ws_tc.merge_range(
                                    row_cursor, 0, row_cursor, 2,
                                    f"{comp} – {desc} ({pid})",
                                    title_fmt2
                                )                                
                            row_cursor += 1

                            # write column headers
                            for col, h in enumerate(headers):
                                ws_tc.write(row_cursor, col, h, header_fmt)
                            row_cursor += 1

                            default_series = pd.Series(0, index=df_pid_specific.index)

                            # build the table with the **discharge** column
                            if has_discharge:
                                table = pd.DataFrame({
                                    'Month': df_pid_specific['Month'],
                                    'Average Concentration (mg/L)': df_pid_specific.get(comp, default_series),
                                    '5-yr Average Concentration (mg/L)': df_pid_specific.get(f'{comp}_5yr', default_series),
                                    'Discharge to Environment (ML)': df_pid_specific.get('Discharge to Environment', default_series),
                                    'Loading (kg/month)': df_pid_specific.get(f'{comp} Loading', default_series),
                                    '5-yr Average Loading (kg/month)': df_pid_specific.get(f'{comp} 5yr Avg Load', default_series)
                                })
                            else:
                                table = pd.DataFrame({
                                    'Month': df_pid_specific['Month'],
                                    'Average Concentration (mg/L)': df_pid_specific.get(comp, default_series),
                                    '5-yr Average Concentration (mg/L)': df_pid_specific.get(f'{comp}_5yr', default_series)
                                })

                            # write rows
                            # for _, row_data in table.iterrows():
                            #     for col_idx, col_name in enumerate(headers):
                            #         val = row_data[col_name]
                            #         if pd.isna(val) or val in (float('inf'), float('-inf')):
                            #             ws_tc.write_blank(row_cursor, col_idx, None, cell_fmt)
                            #         else:
                            #             ws_tc.write(row_cursor, col_idx, val, cell_fmt)

                            for _, row_data in table.iterrows():
                                for col_idx, col_name in enumerate(headers):
                                    val = row_data[col_name]

                                    # blanks / NaN / ±inf
                                    if pd.isna(val) or (isinstance(val, (int, float, np.floating)) and np.isinf(val)):
                                        ws_tc.write_blank(row_cursor, col_idx, None, cell_fmt)

                                    # numbers → 4 dp if |val| < 0.01 else 2 dp
                                    elif isinstance(val, (int, float, np.integer, np.floating)):

                                        if abs(float(val)) == 0:
                                            use_fmt = fmt_0dp
                                        elif  abs(float(val)) < 0.01:
                                            use_fmt=  fmt_4dp   
                                        else:
                                            use_fmt=fmt_2dp

                                        ws_tc.write_number(row_cursor, col_idx, float(val), use_fmt)

                                    # everything else (text, objects, etc.)
                                    else:
                                        ws_tc.write(row_cursor, col_idx, val, cell_fmt)

                                row_cursor += 1

                            # SUM row
                            # ws_tc.write(row_cursor, 0, 'SUM', header_fmt)
                            # for col_idx in range(1, len(headers)):
                            #     col_letter  = chr(65 + col_idx)                  # B … F
                            #     first_row   = row_cursor - len(table) + 1
                            #     last_row    = row_cursor
                            #     ws_tc.write_formula(
                            #         row_cursor, col_idx,
                            #         f"=SUM({col_letter}{first_row}:{col_letter}{last_row})",
                            #         sum_fmt
                            #     )
                            # row_cursor += 23  # blank line after each component

                            # Base style for SUM cells (adjust to your taste)
                            from xlsxwriter.utility import xl_col_to_name
                            base_sum_fmt = {'bold': True,'border': 1, 'align': 'center', 'font': 'Century Gothic'}

                            # Two number formats
                            sum_fmt_0dp = writer.book.add_format({**base_sum_fmt, 'num_format': '0'})
                            sum_fmt_2dp = writer.book.add_format({**base_sum_fmt, 'num_format': '0.00'})
                            sum_fmt_4dp = writer.book.add_format({**base_sum_fmt, 'num_format': '0.0000'})




                            ws_tc.write(row_cursor, 0, 'SUM', header_fmt)

                            for col_idx in range(1, len(headers)):
                                # Target column index on the sheet
                                tgt_col = col_idx
                                col_letter = xl_col_to_name(tgt_col)                     # e.g., 'H', 'AA', ...
                                first_row  = row_cursor - len(table) + 1                 # 1-based row for Excel formula
                                last_row   = row_cursor                                  # 1-based row for Excel formula

                                # Write the SUM formula with default 2dp format
                                ws_tc.write_formula(
                                    row_cursor, tgt_col,
                                    f"=SUM({col_letter}{first_row}:{col_letter}{last_row})",
                                    sum_fmt_2dp
                                )

                                # Apply conditional format to switch to 4dp when |value| < 0.01
                                # Build the cell address for the condition (Excel is 1-based rows)
                                cell_addr = f"{col_letter}{row_cursor + 1}"

                                ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                    'type': 'formula',
                                    'criteria': f"={cell_addr}=0",
                                    'format': sum_fmt_0dp
                                })

                                # < 0.01 (but not 0) → 4 dp
                                ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                    'type': 'formula',
                                    'criteria': f"=AND(ABS({cell_addr})<0.01,{cell_addr}<>0)",
                                    'format': sum_fmt_4dp
                                })

                                # ≥ 0.01 → 2 dp
                                ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                    'type': 'formula',
                                    'criteria': f"=ABS({cell_addr})>=0.01",
                                    'format': sum_fmt_2dp
                                })

                                # ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                #     'type': 'formula',
                                #     'criteria': f"=ABS({cell_addr})<0.1",
                                #     'format': sum_fmt_4dp
                                # })

                            row_cursor += 23  # blank line after each component
                            
                            # Chart
                            img = tc_images.get((comp, pid))
                            if img:
                                ws_tc.insert_image(section_start+17, 1,
                                                f"{comp}_{pid}.png",
                                                {'image_data': img, 'x_scale': 0.75, 'y_scale': 0.75})



                            fy_tag      = f"{str(end_dt.year)[-2:]}{str(end_dt.year+1)[-2:]}"
                            fy_tag_test      = f"{str(end_dt.year-1)[-2:]}{str(end_dt.year)[-2:]}"

                            # print("fy_tag_test")
                            # print(fy_tag_test)
                            # derive full start-year (e.g. "25" → 2025)
                            fy_start    = 2000 + int(fy_tag[:2])
                            fy_tag_curr   = f"{str(start_dt.year)[-2:]}{str(end_dt.year)[-2:]}"   # e.g. 2324
                            # print("fy_tag_curr")
                            # print(fy_tag_curr)   

                            fy_start_curr = start_dt.year  

                            # req_df      = load_monitoring_plan_requirements(fy_tag)
                            req_df      = load_monitoring_plan_requirements(fy_tag_test)
                            # print("fy_tag")
                            # print(fy_tag)

                            # print("req_df")
                            # print(req_df)
                            # write sheet with both tables
                            write_monitoring_program_sheet(writer,
                                                        report_name,
                                                        fy_tag_curr,
                                                        fy_start_curr,
                                                        req_df)                            

                    #---------------------------------------------------------------- write 5 yearly totals
                    if has_discharge:
                        headers = [
                            'Financial Year',
                            'Average Concentration (mg/L)',
                            'Discharge to Environment (ML)',
                            'Loading (kg/FY)'
                        ]


                        # PIDs that actually have data
                        
                        pids_with_data = sorted(df_tc_5_year['SamplingPointID'].unique())
                        row_cursor = 2
                        for pid in pids_with_data:
                            df_pid_specific = df_tc_5_year[df_tc_5_year['SamplingPointID'] == pid]

                            for comp in components:
                                # skip components without any data
                                if comp not in df_pid_specific.columns:# or df_pid_specific[comp].fillna(0).sum() == 0:
                                    continue

                                section_start = row_cursor
                                desc          = pid_to_desc_map.get(pid, 'Unknown Location')
                                ws_tc.merge_range(
                                    row_cursor, 7, row_cursor, 10,
                                    f"{comp} – {desc} ({pid})",
                                    title_fmt
                                )
                                row_cursor += 1

                                # write column headers
                                for col, h in enumerate(headers):
                                    ws_tc.write(row_cursor, col+7, h, header_fmt)
                                row_cursor += 1

                                default_series = pd.Series(0, index=df_pid_specific.index)

                                # build the table with the **discharge** column
                                if has_discharge:
                                    table = pd.DataFrame({
                                        'Financial Year': df_pid_specific['Financial Year'],
                                        'Average Concentration (mg/L)': df_pid_specific.get(comp, default_series),
                                        'Discharge to Environment (ML)': df_pid_specific.get('Discharge to Environment', default_series),
                                        'Loading (kg/FY)': df_pid_specific.get(f'{comp} Loading', default_series),
                                    })
                                else:
                                    table = pd.DataFrame(columns = ['Financial Year','Average Concentration (mg/L)','Discharge to Environment (ML)','Loading (kg/FY)'])
                                #     table = pd.DataFrame({
                                #         'Financial Year': df_pid_specific['Financial Year'],
                                #         'Average Concentration (mg/L)': df_pid_specific.get(comp, default_series),
                                #         '5-yr Average Concentration (mg/L)': df_pid_specific.get(f'{comp}_5yr', default_series)
                                #     })

                                # write rows
                                # for _, row_data in table.iterrows():
                                #     for col_idx, col_name in enumerate(headers):
                                #         val = row_data[col_name]
                                #         if pd.isna(val) or val in (float('inf'), float('-inf')):
                                #             ws_tc.write_blank(row_cursor, col_idx+7, None, cell_fmt)
                                #         else:
                                #             ws_tc.write(row_cursor, col_idx+7, val, cell_fmt)
                                #     row_cursor += 1
                                Sum_format = None
                                for _, row_data in table.iterrows():
                                    for col_idx, col_name in enumerate(headers):
                                        val = row_data[col_name]

                                        # blanks / NaN / ±inf
                                        if pd.isna(val) or (isinstance(val, (int, float, np.floating)) and np.isinf(val)):
                                            ws_tc.write_blank(row_cursor, col_idx+7, None, cell_fmt)

                                        # numbers → 4 dp if |val| < 0.01 else 2 dp
                                        elif isinstance(val, (int, float, np.integer, np.floating)):
                                            if abs(float(val)) == 0:
                                                use_fmt = fmt_0dp
                                            elif  abs(float(val)) < 0.01:
                                                use_fmt=  fmt_4dp   
                                            else:
                                                use_fmt=fmt_2dp

                                            # use_fmt = fmt_4dp if abs(float(val)) < 0.01 else fmt_2dp
                                            ws_tc.write_number(row_cursor, col_idx+7, float(val), use_fmt)

                                        # everything else (text, objects, etc.)
                                        else:
                                            ws_tc.write(row_cursor, col_idx+7, val, cell_fmt)
                                    row_cursor += 1

                                # SUM row

                                # Base style for SUM cells (adjust to your taste)
                                from xlsxwriter.utility import xl_col_to_name
                                base_sum_fmt = {'bold': True,'border': 1, 'align': 'center', 'font': 'Century Gothic'}

                                # Two number formats
                                sum_fmt_0dp = writer.book.add_format({**base_sum_fmt, 'num_format': '0'})
                                sum_fmt_2dp = writer.book.add_format({**base_sum_fmt, 'num_format': '0.00'})
                                sum_fmt_4dp = writer.book.add_format({**base_sum_fmt, 'num_format': '0.0000'})




                                ws_tc.write(row_cursor, 7, 'SUM', header_fmt)

                                for col_idx in range(1, len(headers)):
                                    # Target column index on the sheet
                                    tgt_col = col_idx + 7
                                    col_letter = xl_col_to_name(tgt_col)                     # e.g., 'H', 'AA', ...
                                    first_row  = row_cursor - len(table) + 1                 # 1-based row for Excel formula
                                    last_row   = row_cursor                                  # 1-based row for Excel formula

                                    # Write the SUM formula with default 2dp format
                                    ws_tc.write_formula(
                                        row_cursor, tgt_col,
                                        f"=SUM({col_letter}{first_row}:{col_letter}{last_row})",
                                        sum_fmt_2dp
                                    )

                                    # Apply conditional format to switch to 4dp when |value| < 0.01
                                    # Build the cell address for the condition (Excel is 1-based rows)
                                    cell_addr = f"{col_letter}{row_cursor + 1}"
                                    ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                        'type': 'formula',
                                        'criteria': f"={cell_addr}=0",
                                        'format': sum_fmt_0dp
                                    })

                                    # < 0.01 (but not 0) → 4 dp
                                    ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                        'type': 'formula',
                                        'criteria': f"=AND(ABS({cell_addr})<0.01,{cell_addr}<>0)",
                                        'format': sum_fmt_4dp
                                    })

                                    # ≥ 0.01 → 2 dp
                                    ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                        'type': 'formula',
                                        'criteria': f"=ABS({cell_addr})>=0.01",
                                        'format': sum_fmt_2dp
                                    })

                                    # ws_tc.conditional_format(row_cursor, tgt_col, row_cursor, tgt_col, {
                                    #     'type': 'formula',
                                    #     'criteria': f"=ABS({cell_addr})<0.1",
                                    #     'format': sum_fmt_4dp
                                    # })
                                    


                                # for col_idx in range(1, len(headers)):
                                #     col_letter  = chr(65 + col_idx+7)                  # B … F
                                #     first_row   = row_cursor - len(table) + 1
                                #     last_row    = row_cursor
                                #     ws_tc.write_formula(
                                #         row_cursor, col_idx+7,
                                #         f"=SUM({col_letter}{first_row}:{col_letter}{last_row})",
                                #         sum_fmt
                                #     )
                                row_cursor += 30  # blank line after each component
                                print("teesting")

                                #-------------------------------------------------------------------- 5 Yearly Chart
                                img = tc_images_5y.get((comp, pid))
                                if img:
                                    ws_tc.insert_image(section_start+17, 7,
                                                    f"{comp}_{pid}.png",
                                                    {'image_data': img, 'x_scale': 0.75, 'y_scale': 0.75})
                                

                    # --- Site Incidents ---
                    print("inc_df = get_site_incidents_data(report_name, start_dt, end_dt)")
                    inc_df = get_site_incidents_data(report_name, start_dt, end_dt)
                    
                    inc_df.to_excel(writer,
                                    sheet_name='Site Incidents',
                                    index=False,
                                    startrow=2)

                    ws_inc = writer.sheets['Site Incidents']
                    ws_inc.set_column('A:A', 20)
                    ws_inc.set_column('B:B', 20)
                    ws_inc.set_column('C:C', 25)
                    ws_inc.set_column('D:D', 35)
                    ws_inc.set_column('E:G', 20)
                    
                    header_fmt = writer.book.add_format({
                        'bold': True, 'bg_color': '#dedbd2', 'border': 1,
                        'align': 'center', 'font': 'Century Gothic'
                    })
                    ws_inc.write_row(2, 0, inc_df.columns.tolist(), header_fmt)

                    # overwrite the header row (row index 2) with the format
                    ws_inc.write('A1', 'Site Incidents',
                                writer.book.add_format({'bold': True,
                                                        'font_size': 15,
                                                        'font': 'Century Gothic'}))
                    # --- Comments ---
                    get_comments_data(report_name, start_dt, end_dt) \
                        .to_excel(writer, sheet_name='Comments', index=False, startrow=2)

                    ws_com = writer.sheets['Comments']
                    ws_com.write('A1', 'Comments',
                                writer.book.add_format({'bold': True,
                                                        'font_size': 15,
                                                        'font': 'Century Gothic'}))

                    




                    # --- Site Schematic ---
                    schem_ws = writer.book.add_worksheet('Site Schematic')
                    writer.sheets['Site Schematic'] = schem_ws

                    title_fmt = writer.book.add_format({'bold': True,
                                                        'font_size': 15,
                                                        'font': 'Century Gothic'})
                    schem_ws.write('A1', 'Site Schematic', title_fmt)          # new title
                    schem_file = os.path.join(SCHEM_DIR, f"{report_name} WWTP.png")
                    if os.path.exists(schem_file):
                        from PIL import Image
                        img = Image.open(schem_file)
                        scale = 1600 / img.width
                        schem_ws.insert_image('A3', schem_file,                 # moved from A1 → A3
                                            {'x_scale': scale, 'y_scale': scale})

                                        

                download_files.append(fname)

            except PermissionError:
                flash(
                    f"Cannot write “{fname}”—it appears to be open. "
                    "Close it and try again.",
                    'danger'
                )
                print(PermissionError)
                Incomplete_download_files.append(fname)
                continue

        if download_files:
            if len(download_files) == 1:
                flash(f"Generated report for {download_files[0].split(' WWTP')[0]}", 'success')
            else:
                flash(f"Generated reports for {len(download_files)} sites", 'success')
                flash(f"Reports not generated/incomplete for {len(Incomplete_download_files)} sites", 'success')

    # De-duplicate the list of sites FOR THE TEMPLATE ONLY.
    unique_sites_for_template = list({s['report_name']: s for s in sites}.values())

    return render_template(
        'run_report.html',
        sites=unique_sites_for_template, # Pass the unique list here
        download_files=download_files
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(SCHEM_DIR, filename)

@app.route('/reports/<filename>')
def download_report(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)



