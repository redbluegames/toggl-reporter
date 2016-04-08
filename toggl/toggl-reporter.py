#!/usr/local/bin/python
# toggl-reporter.py
# Helper script to run toggl reports

from __future__ import print_function
from datetime import date, datetime
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
outf = open(config['report_file'], 'w+')

# Parameters for Toggl Request
user = config['user']
workspace = config['workspace']
user_ids = ''
since = ''
until = ''
api_key = config['api_key']
headers = {'Authorization': api_key}

# API Endpoints
GET_DETAILS = 'https://toggl.com/reports/api/v2/details'
SUMMARY_URL = ("https://www.toggl.com/app/reports/summary/" +
               "{0}/from/{1}/to/{2}/users/{3}/billable/both")

# "Consts"
HTTP_OK = 200
BILLABLE_TAG = "Billable"
ALL_EMPS = "All Employees"
USERIDS_NAMES = {"1947788": "Kevin", "219293": "Lucas",
                 "129932": "Edward", ALL_EMPS: "All Employees"}


def main(argv):
    if len(sys.argv) != 4:
        print_usage()
        sys.exit(2)

    # Set our request params
    global user_ids
    user_ids = sys.argv[1]
    global since
    since = sys.argv[2]
    global until
    until = sys.argv[3]

    global summary_url
    summary_url = SUMMARY_URL.format(workspace, since, until, user_ids)

    togglData = get_toggl_details_data(user_ids, since, until)

    run_report(togglData, user_ids)

    # print "Validating entries..."
    # validate_entries(response.json())

    # print "\nDaily Report..."
    # print_daily_report(response.json())
    outf.close


def print_usage():
    print("Usage: ")
    print("py toggl-reporter.py [user_ids] [start_time] [end_time]")
    print("  [user_ids] user id obtained from toggl")
    print("  [start_time] beginning of report range in YYYY-MM-DD format")
    print("  [end_time] beginning of report range in YYYY-MM-DD format")
    print("\nex: python toggl-reporter.py 235725,572628 2016-03-01 2016-03-15")


def get_toggl_details_data(user_ids, since, until):
    # Set up our payload
    payload = {
        'user_agent': user,
        'workspace_id': workspace,
        'user_ids': user_ids,
        'since': since,
        'until': until,
        'page': 1
        }

    # Get first page
    response = get_toggl_details_response(payload)
    json = response.json()
    togglData = json['data']

    isMoreThanOnePage = json['total_count'] > json['per_page']
    if isMoreThanOnePage:
        totalPages = json['total_count'] / json['per_page'] + 1
        for nextPage in range(2, totalPages+1):
            payload['page'] = nextPage
            response = get_toggl_details_response(payload)
            togglData += response.json()['data']

    return togglData


def get_toggl_details_response(payload):
    response = requests.get(GET_DETAILS, params=payload, headers=headers)
    if response.status_code == HTTP_OK:
        print("Toggl Response OK")
        print("Running report for user: " + user)
    else:
        print("Error running API Request")
        print("Status_code: " + str(response.status_code))
        print(response.text)
    return response


def run_report(response, user_ids):
    output = "<html>"
    output += "\n<h2>Summary Timesheet Report for All Employees<br/>"
    output += "\nfrom {0} to {1}</h2>".format(since, until)
    output += ("\nA similar report for this date range can be viewed " +
               "<a href='{0}'>here</a>.<br/><br/>".format(summary_url))
    print(output, file=outf)

    # First print out All Employees report
    billableTime = get_billable_by_project(response, user_ids)
    write_billable_time_to_file(billableTime, ALL_EMPS, outf)

    print("<br/><br/><br/>Additional reports below...<br/><br/>", file=outf)

    users = user_ids.split(',')
    for user in users:
        billableTime = get_billable_by_project(response, user)
        write_billable_time_to_file(billableTime, user, outf)

    print("</html>", file=outf)


def validate_entries(togglData):
    for entry in togglData:
        entryStartTime = iso8601.parse_date(entry['start'])
        entryEndTime = iso8601.parse_date(entry['end'])
        for otherentry in togglData:
            otherStartTime = iso8601.parse_date(otherentry['start'])
            otherEndTime = iso8601.parse_date(otherentry['end'])

            startTimeOverlaps = (otherStartTime < entryEndTime and
                                 otherStartTime > entryStartTime)
            endTimeOverlaps = (otherEndTime < entryEndTime and
                               otherStartTime > entryStartTime)

            if entry == otherentry:
                continue
            elif startTimeOverlaps or endTimeOverlaps:
                overlapMsg = ("Overlapping time entries found: " +
                              "\n{0}\nand\n{1}")
                print(overlapMsg.format(get_short_summary(entry),
                                        get_short_summary(otherentry)))


def print_daily_report(togglData):
    earliestTime = None
    for entry in togglData:
        entryTime = iso8601.parse_date(entry['start'])
        if (earliestTime is None or entryTime < earliestTime):
            earliestTime = iso8601.parse_date(entry['start'])
            earliestEntry = entry

    print("Clocked in at {0}".format(earliestTime))
    print("Entry: {0}".format(earliestEntry['description']))


def get_billable_by_project(json, user_id):
    projectTimes = {}
    for entry in json:
        # Short-circuit entries for other users
        if str(entry['uid']) not in user_id:
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


def write_billable_time_to_file(projectTimes, user_id, out):
    # Print our header
    output = "\n____________________________ <br/>"
    output += "\n<h3>Timesheet Report for {0} ({1}-{2})</h3>".format(
             lookup_name(user_id), since, until)

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


def lookup_name(user_id):
    name = "Unknown ({0})".format(str(user_id))
    for user in USERIDS_NAMES:
        if user == user_id:
            name = USERIDS_NAMES[user]
    return name


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
