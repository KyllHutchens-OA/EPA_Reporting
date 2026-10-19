"""
Generate one site's EPA report for the last full financial year (1 Jul - 30 Jun).

Usage:  python run_report_cli.py "Wirrina"
        python run_report_cli.py --list
"""
import os
import sys
import time
from datetime import date

from app import app, REPORTS_DIR
from report_functions import load_sites


def last_full_fy(today=None):
    today = today or date.today()
    end_year = today.year if today >= date(today.year, 7, 1) else today.year - 1
    return date(end_year - 1, 7, 1), date(end_year, 6, 30)


def main(argv):
    names = sorted({s['report_name'] for s in load_sites()})
    if len(argv) != 2 or argv[1] in ('-h', '--help'):
        print(__doc__)
        return 1
    if argv[1] == '--list':
        print("\n".join(names))
        return 0

    lookup = {n.lower(): n for n in names}
    site = lookup.get(argv[1].strip().lower())
    if not site:
        print(f"Unknown site '{argv[1]}'. Available sites:\n  " + "\n  ".join(names))
        return 1

    start, end = last_full_fy()
    outpath = os.path.join(REPORTS_DIR, f"{site} WWTP EPA Report {start.year}-{end.year}.xlsx")
    print(f"Generating {site} for {start:%d-%m-%Y} to {end:%d-%m-%Y}...")

    started = time.time()
    app.config['PROPAGATE_EXCEPTIONS'] = True   # show the real traceback on failure
    app.test_client().post('/run_report', data={
        'scope': 'single', 'site_id': site,
        'start_date': start.isoformat(), 'end_date': end.isoformat(),
    })

    if os.path.exists(outpath) and os.path.getmtime(outpath) >= started:
        print(f"Done: {outpath}")
        return 0
    print("Report was not generated (is the file open in Excel? see messages above).")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
