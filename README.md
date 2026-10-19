<<<<<<< HEAD
## EPA Annual Reporting Documentation ##
v1.0 12/05/2025 - Kyll Hutchens
#### To Do ####
- Currently system relies on reading and writing to local spreadsheets. Move these to databases
- Fix SAAM query so that its automatic 
- Investigate moving sharepoint list across using Python 
- Integrate site details from the WWTPs Site Details on Aquanet, rather than the manual table integration at the moment

### Introduction ###
Annually post the FY ending the Production and Treatment Wastewater team alongside environmental compliance request data on every site relating to flows, sampling results and incidents. 
This data is compiled into one report per treatment site created by the Operations data, technology and performance team which is then given to the EPA for comment.

This report is generated using python 3.x utilising the flask library and utilises a mix of python, html and css languages for the front end and automation of the report.
The data comes from the following sources
- PI Asset Framework, utilising the reported monthly figures
- Waterscope - [vwCrystalResults] table , currently on the SQL20 database
- SAAM - The organisations incident and hazard management and reporting system
- Raw data excel tables manipulated by the front end of the program. 

### How to run the reports ###

Below are step by step instructions on how to run the python script and initate the front end of the reporting tool.
Make sure you have the Sampling compliance data downloaded from external source and in the folder with the EPA reports.
Firstly, if you require the files and are reading this in DevOps, navigate to the top level of the EPA-Annual-Reporting folder and select the download as zip button. Unzip the required file.
Once this is completed put this file in a location of your choice and open up either command prompt or your coding IDE of choice. You will need to navigate to this folder using the `cd` function. This will look something like `cd c:\thepathway\towhereyousaved\thefile`
Then assuming you have python installed on your PC, have activated the virtual enviornment (if your not sure how see below notes on Python installtion) and you are **not** on the VPN you should be able to run 
> `python app.py` 

in the console, which should firstly install any required packages then return 

> * Serving Flask app 'app'
> * Debug mode: on
> WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
> * Running on http://127.0.0.1:5000
> Press CTRL+C to quit
> * Restarting with stat
> * Debugger is active!
> * Debugger PIN: 477-280-594

If working on a SAW PC and you are not familar with how python works and how virtual envionments work then see the *SAW Python installation instructions.docx* in this EPA-Annual-Reporting folder.

From here navigate to the url provided next to running on in the console, in my case that was http://127.0.0.1:5000 (A local web server, cannot be shared) which should present to you the front end of the EPA reporting tool. All work required should be able to be done from here.

### Updating Incident data and Wastewater Treatment Comments ###

For the most up to date data, there is currently some manual updates requred. 
*Please ignore this section if new version doesnt require manual interventions*

> For SAAM Incident data: 
> In the directory for the project go to `Data > SAAM Cube data.xlsx` inside here is a pivot table. If you have the correct permissions should be able to just right click and refresh.
> From here highlight all the data, no need to adjust any filters and copy.
> Paste data over the top of SAAMData.csv, removing all the old data. And hit save

> For Treatment Comments: 
> Visit https://sawater.sharepoint.com/sites/PTSOperationPerf/Lists/WWTP%20Quarterly%20Review%20Comments/AllItems.aspx?.
> Top toolbar select Export > Export as csv
> Within the directory for the project inside `Data > WWTP Quarterly Review Comments.csv` 
> Paste the data from the downloaded csv over the top of the data in WWTP Quarterly Review Comments.csv

### Utilising the front end ###
The web page that launches when you start the code should have four options 
* Add site:
        &nbsp; This is used when a new water treatment site comes online or one is missing from the list
        &nbsp; Report Name: This is what the EPA report will be called, do not include suffix WWTP
        &nbsp; Location Type: This is whether the site sampling point being used is Discharge to Environment or reuse
        &nbsp; Site Name (SAAM): This is the name as present in SAAM Location Description field
        &nbsp; System Name (Waterscope): This is the name given to the site in Waterscope most often {Site Name} WWTP
        &nbsp; SamplingPoint ID of Final Effluent: This is the EPA required sampling point used to calculate loading values

* Report & Process Details:
        &nbsp; This is the data that feeds into the landing page of the report. 
        &nbsp; Consulting with the Wastewater treatment team is recommended to assist in gaining all the fields
        &nbsp; I **strongly** recommend that all fields are filled out in one go. As having multiple rows for one site may not work as intended

* Upload Schematics: 
        &nbsp; This tab is used to manage the schematics on the last tab of the spreadsheet.
        &nbsp; Using the *Replace existing file if it exists* allows for updating with new versions
        &nbsp; Files can be deleted within the `Data > Schematic Images` folder in the project directory
        &nbsp; All schematics can also be viewed on this page

* Run Report
        &nbsp; Once all the other tabs are complete, the report for *One* or *All* sites reports can be generated
        &nbsp; For the date range, always select first of financial year 01/07/YYYY to end of FY 30/06/YYYY
        &nbsp; All files are created and saved in the `Reports` folder within the project directory
=======
# EPA_Reporting
>>>>>>> c1180a718ae5795c4c738ee3016ed43f2b937640
