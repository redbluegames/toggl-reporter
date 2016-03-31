#!/usr/local/bin/python
# toggl-reporter.py
# Helper script to run toggl reports

from datetime import date, datetime
import getopt
import iso8601
import requests
import sys
import yaml

# Load YAML configs
f = open('config.yaml')
config = yaml.safe_load(f)
f.close()

# Parameters for Toggl Request
email = config['email']
workspace = config['workspace']
user_id = ''
since = ''
until = ''

api_key = config['api_key']
headers = {'Authorization': api_key}

# API Endpoints
GET_DETAILS = 'https://toggl.com/reports/api/v2/details'

# "Consts"
HTTP_OK = 200
BILLABLE_TAG = "Billable"


def main(argv):
    if len(sys.argv) != 4:
        print_usage()
        sys.exit(2)

    togglData = get_toggl_details_data()
    # print "Validating entries..."
    # validate_entries(response.json())

    # print "\nDaily Report..."
    # print_daily_report(response.json())
    print "\nTimesheet Report for {0} to {1}".format(since, until)
    run_report(togglData)


def print_usage():
    print "Usage: "
    print "py toggl-reporter.py [user_ids] [start_time] [end_time]"
    print "  [user_id] user id obtained from toggl"
    print "  [start_time] beginning of report range in YYYY-MM-DD format"
    print "  [end_time] beginning of report range in YYYY-MM-DD format"
    print "\nex: python toggl-reporter.py 235725,572628 2016-03-01 2016-03-15"


def get_toggl_details_data():
    # Set our request params
    global user_id
    user_id = sys.argv[1]
    global since
    since = sys.argv[2]
    global until
    until = sys.argv[3]

    # Set up our payload
    payload = {
        'user_agent': email,
        'workspace_id': workspace,
        'user_ids': user_id,
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
        remainingPages = json['total_count'] / json['per_page']
        for nextPage in range(2, remainingPages + 2):
            payload['page'] = nextPage
            response = get_toggl_details_response(payload)

    payload['page'] = 2
    response = requests.get(GET_DETAILS, params=payload, headers=headers)
    togglData += response.json()['data']

    return togglData


def get_toggl_details_response(payload):
    response = requests.get(GET_DETAILS, params=payload, headers=headers)
    if response.status_code == HTTP_OK:
        print "Toggl Response OK"
        print "Running report for " + email
    else:
        print "Error running API Request"
        print response.text
        return
    return response


def run_report(response):
    billableTime = get_billable_by_project(response)
    print_billable_time(billableTime)


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
                print overlapMsg.format(get_short_summary(entry),
                                        get_short_summary(otherentry))


def print_daily_report(togglData):
    earliestTime = None
    for entry in togglData:
        entryTime = iso8601.parse_date(entry['start'])
        if (earliestTime is None or entryTime < earliestTime):
            earliestTime = iso8601.parse_date(entry['start'])
            earliestEntry = entry

    print "Clocked in at {0}".format(earliestTime)
    print "Entry: {0}".format(earliestEntry['description'])


def get_billable_by_project(json):
    projectTimes = {}
    for entry in json:
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


def print_billable_time(projectTimes):
    for project in projectTimes:
        print "\n" + project
        millisToMinsToHours = 1000.0 * 60 * 60
        totalHours = projectTimes[project][0] / millisToMinsToHours
        print "  Total: {:.2f}h".format(totalHours)
        billableHours = projectTimes[project][1] / millisToMinsToHours
        print "  Billable: {:.2f}h".format(billableHours)
        discountedHours = projectTimes[project][2] / millisToMinsToHours
        print "  Discounted: {:.2f}h".format(discountedHours)


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
