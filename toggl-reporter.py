#!/usr/local/bin/python
# toggl-reporter.py
# Helper script to generate toggl reports

from __future__ import print_function
from datetime import date, datetime
from requests.auth import HTTPBasicAuth
import argparse
import getopt
import iso8601
import math
import requests
import sys
import yaml

# Load YAML configs
f = open('config.yaml')
config = yaml.safe_load(f)
f.close()

# Parameters for Toggl Request (from config file)
user = config['user']
workspace = config['workspace']
user_ids = config['reportees'].keys()
api_token = config['api_token']
headers = {}

# Command Line Arguments
parser = argparse.ArgumentParser(description=
                "Generates a Toggl report using configuration file and " +
                "provided parameters. ex: python toggl-reporter.py -vp " +
                "2016-03-01 2016-03-15")
parser.add_argument("since", help="start date in (YYYY-MM-DD) format")
parser.add_argument("until", help="end date in (YYYY-MM-DD) format")
parser.add_argument("-p", "--pdf",
                    help="export pdf report instead of json",
                    action="store_true")
parser.add_argument("-v", "--verbose",
                    help="increase output verbosity",
                    action="store_true")
args = parser.parse_args()

# API Endpoints
GET_DETAILS = 'https://toggl.com/reports/api/v2/details'
GET_DETAILS_PDF = 'https://toggl.com/reports/api/v2/details.pdf'
SUMMARY_URL = ("https://www.toggl.com/app/reports/summary/" +
               "{0}/from/{1}/to/{2}/users/{3}/billable/both")

# "Consts"
HTTP_OK = 200
BILLABLE_TAG = "Billable"
ALL_EMPS = "All Employees"


def main(argv):
    # Set our request params
    global payload
    payload = {
        'user_agent': user,
        'workspace_id': workspace,
        'user_ids': ','.join(str(id) for id in user_ids),
        'since': args.since,
        'until': args.until,
        'page': 1
        }

    global summary_url
    summary_url = SUMMARY_URL.format(workspace, args.since, args.until, user_ids)

    togglDetails = get_toggl_details()
    print_report_file(togglDetails)

    # Commenting out since this report is basically deprecated.
    # generate_cortina_report(togglDetails)


def get_toggl_details():
    if args.pdf:
        togglDetails = get_toggl_details_pdf()
    else:
        togglDetails = get_toggl_details_json()
    return togglDetails


def print_report_file(reportContent):
    if args.pdf:
        outf = open('report.pdf', 'w+')
    else:
        outf = open('report.json', 'w+')
    print(reportContent, file=outf)
    outf.close


def get_toggl_details_pdf():
    response = get_toggl_details_response(GET_DETAILS_PDF, payload, pageNum=1)
    return response.content


def get_toggl_details_json():
    # Get first page
    response = get_toggl_details_response(GET_DETAILS, payload, 1)
    json = response.json()
    togglData = json['data']

    isMoreThanOnePage = json['total_count'] > json['per_page']
    if isMoreThanOnePage:
        totalPages = int(json['total_count'] / json['per_page']) + 1
        for nextPage in range(2, totalPages+1):
            payload['page'] = nextPage
            response = get_toggl_details_response(payload, nextPage)
            togglData += response.json()['data']

    return response.content


def get_toggl_details_response(url, payload, pageNum):
    if args.verbose:
        print("Sending GET Request to: " + url)
        print("Headers:" + str(headers))
        print("Payload: " + str(payload))
        print("...")

    response = requests.get(url, auth=(api_token, 'api_token'),
                            params=payload, headers=headers)

    msg = "Getting report page {0} for user(s): {1}"
    print(msg.format(pageNum, payload['user_ids']))

    if response.status_code == HTTP_OK:
        print("Toggl Response OK")
    else:
        print("Error running API Request")
        print("Status_code: " + str(response.status_code))
        print(response.text)
    return response


def generate_cortina_report(response):
    summary_url = SUMMARY_URL.format(workspace, args.since,
                                     args.until, payload['user_ids'])
    output = "<html>"
    output += "\n<h2>Summary Timesheet Report for All Employees<br/>"
    output += "\nfrom {0} to {1}</h2>".format(args.since, args.until)
    output += ("\nA similar report for this date range can be viewed " +
               "<a href='{0}'>here</a>.<br/><br/>".format(summary_url))
    print(output, file=outf)

    # First print out All Employees report
    billableTime = get_billable_by_project(response, user_ids)
    write_billable_time_to_file(billableTime, ALL_EMPS, outf)

    print("<br/><br/><br/>Additional reports below...<br/><br/>", file=outf)

    reportees = config['reportees']
    for user in reportees:
        userDict = {user}
        billableTime = get_billable_by_project(response, userDict)
        write_billable_time_to_file(billableTime, reportees[user], outf)

    print("</html>", file=outf)


def get_billable_by_project(json, user_ids):
    projectTimes = {}
    for entry in json:
        # Short-circuit entries for other users
        for user in user_ids:
            if entry['uid'] != user:
                continue

        entryProject = entry['project']

        # Add our time to the correct entry in the project
        if entryProject not in projectTimes:
            projectTimes[entryProject] = [0, 0, 0]

        # First add it to total
        projectTimes[entryProject][0] += entry['dur']

        # Then add time to the corresponding billable/nonbillable bucket
        if BILLABLE_TAG in entry['tags']:
            projectTimes[entryProject][1] += entry['dur']
        elif BILLABLE_TAG not in entry['tags']:
            projectTimes[entryProject][2] += entry['dur']

    return projectTimes


def write_billable_time_to_file(projectTimes, reporteeName, out):
    # Print our header
    output = "\n____________________________ <br/>"
    output += "\n<h3>Timesheet Report for {0} ({1}-{2})</h3>".format(
             reporteeName, since, until)

    for project in projectTimes:
        # Calculate our totals
        millisToMinsToHours = 1000.0 * 60 * 60
        totalHours = projectTimes[project][0] / millisToMinsToHours
        billableHours = projectTimes[project][1] / millisToMinsToHours
        discountedHours = projectTimes[project][2] / millisToMinsToHours

        # Write project name and totals
        output += "\n<br/><b>{0}</b><br/>".format(project)
        output += "\n&nbsp;&nbsp;Total: {:.2f}h<br/>".format(totalHours)
        output += ("\n&nbsp;&nbsp;<b style='color:blue;'>" +
                   "Billable: {:.2f}h</b><br/>".format(billableHours))
        output += ("\n&nbsp;&nbsp;Discounted: {:.2f}h<br/>".format(
                   discountedHours))

    print(output, file=out)


def get_time(datetimeToConvert):
    return datetime.strftime(datetimeToConvert, "%I:%M %p")


def get_short_summary(entry):
    formatStr = "{0} from {1} to {2}"
    description = entry['description']
    start = iso8601.parse_date(entry['start'])
    end = iso8601.parse_date(entry['end'])
    return formatStr.format(description, get_time(start), get_time(end))


if __name__ == "__main__":
    main(sys.argv[1:])
