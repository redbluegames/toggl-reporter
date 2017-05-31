#!/usr/local/bin/python
# toggl-reporter.py
# Helper script to generate toggl reports

from __future__ import print_function
import argparse
import requests
import yaml

# Load YAML configs
CONFIG_FILE = open('config.yaml')
CONFIG = yaml.safe_load(CONFIG_FILE)
CONFIG_FILE.close()

# Parameters for Toggl Request (from config file)
USER = CONFIG['user']
WORKSPACE = CONFIG['workspace']
USER_IDS = CONFIG['reportees'].keys()
API_TOKEN = CONFIG['api_token']
HEADERS = {}

# Command Line Arguments
PARSER = argparse.ArgumentParser(description=
                                 "Generates a Toggl report using configuration file and " +
                                 "provided parameters. ex: python toggl-reporter.py -vp " +
                                 "2016-03-01 2016-03-15")
PARSER.add_argument("since", help="start date in (YYYY-MM-DD) format")
PARSER.add_argument("until", help="end date in (YYYY-MM-DD) format")
PARSER.add_argument("-c", "--client_ids", default=None, help="comma-separated list of client ids")
PARSER.add_argument("-p", "--pdf",
                    help="export pdf report instead of json",
                    action="store_true")
PARSER.add_argument("-v", "--verbose",
                    help="increase output verbosity",
                    action="store_true")
ARGS = PARSER.parse_args()

# API Endpoints
GET_DETAILS = 'https://toggl.com/reports/api/v2/details'
GET_DETAILS_PDF = 'https://toggl.com/reports/api/v2/details.pdf'
SUMMARY_URL = ("https://www.toggl.com/app/reports/summary/" +
               "{0}/from/{1}/to/{2}/users/{3}/billable/both")

# "Consts"
HTTP_OK = 200
BILLABLE_TAG = "Billable"
ALL_EMPS = "All Employees"

def main():
    """Run our Toggl requests and print out the report"""
    # Set our request params
    payload = {
        'user_agent': USER,
        'workspace_id': WORKSPACE,
        'user_ids': ','.join(str(id) for id in USER_IDS),
        'since': ARGS.since,
        'until': ARGS.until,
        'client_ids': ARGS.client_ids,
        'page': 1
        }

    toggl_details = get_toggl_details(payload)
    print_report_file(toggl_details)

    # Commenting out since this report is basically deprecated.
    # generate_cortina_report(togglDetails)


def get_toggl_details(payload):
    """Get the Toggl Detailed report, either a PDF or JSON."""
    if ARGS.pdf:
        toggl_details = get_toggl_details_pdf(payload)
    else:
        toggl_details = get_toggl_details_json(payload)
    return toggl_details


def print_report_file(report_content):
    """Print out the report file into PDF or JSON format."""
    if ARGS.pdf:
        outf = open('report.pdf', 'w+')
    else:
        outf = open('report.json', 'w+')
    print(report_content, file=outf)


def get_toggl_details_pdf(payload):
    """Hit the Toggl API and return the Detailed Report PDF."""
    response = get_toggl_details_response(GET_DETAILS_PDF, payload)
    return response.content


def get_toggl_details_json(payload):
    """Hit the Toggl API for Detailed JSON, repeat if more pages needed."""
    # Get first page
    response = get_toggl_details_response(GET_DETAILS, payload, 1)
    json = response.json()
    toggl_data = json['data']

    is_more_than_one_page = json['total_count'] > json['per_page']
    if is_more_than_one_page:
        total_pages = int(json['total_count'] / json['per_page']) + 1
        for next_page in range(2, total_pages+1):
            payload['page'] = next_page
            response = get_toggl_details_response(GET_DETAILS, payload, next_page)
            toggl_data += response.json()['data']

    return response.content


def get_toggl_details_response(url, payload, page_num=1):
    """Send the Request to Toggl, return the response or print error text."""
    if ARGS.verbose:
        print("Sending GET Request to: " + url)
        print("Headers:" + str(HEADERS))
        print("Payload: " + str(payload))
        print("...")

    response = requests.get(url, auth=(API_TOKEN, 'api_token'),
                            params=payload, headers=HEADERS)

    msg = "Getting report page {0} for user(s): {1}"
    print(msg.format(page_num, payload['user_ids']))

    if response.status_code == HTTP_OK:
        print("Toggl Response OK")
    else:
        print("Error running API Request")
        print("Status_code: " + str(response.status_code))
        print(response.text)
    return response


def generate_cortina_report(response):
    """Generate a special HTML report for Cortina, tracking non-billed time."""
    SUMMARY_URL.format(WORKSPACE, ARGS.since, ARGS.until, USER_IDS)
    output = "<html>"
    output += "\n<h2>Summary Timesheet Report for All Employees<br/>"
    output += "\nfrom {0} to {1}</h2>".format(ARGS.since, ARGS.until)
    output += ("\nA similar report for this date range can be viewed " +
               "<a href='{0}'>here</a>.<br/><br/>".format(SUMMARY_URL))
    outf = open('cortina-report.html', 'w+')
    print(output, file=outf)

    # First print out All Employees report
    billable_time = get_billable_by_project(response, USER_IDS)
    write_billable_time_to_file(billable_time, ALL_EMPS, outf)

    print("<br/><br/><br/>Additional reports below...<br/><br/>", file=outf)

    reportees = CONFIG['reportees']
    for user in reportees:
        user_dict = {user}
        billable_time = get_billable_by_project(response, user_dict)
        write_billable_time_to_file(billable_time, reportees[user], outf)

    print("</html>", file=outf)


def get_billable_by_project(json, user_ids):
    """Build a dictionary of project time totals, broken down by projects."""
    project_times = {}
    for entry in json:
        # Short-circuit entries for other users
        for user in user_ids:
            if entry['uid'] != user:
                continue

        entry_project = entry['project']

        # Add our time to the correct entry in the project
        if entry_project not in project_times:
            project_times[entry_project] = [0, 0, 0]

        # First add it to total
        project_times[entry_project][0] += entry['dur']

        # Then add time to the corresponding billable/nonbillable bucket
        if BILLABLE_TAG in entry['tags']:
            project_times[entry_project][1] += entry['dur']
        elif BILLABLE_TAG not in entry['tags']:
            project_times[entry_project][2] += entry['dur']

    return project_times


def write_billable_time_to_file(project_times, reportee_name, out):
    """Create an HTML timesheet for easy viewing of billable time."""
    # Print our header
    output = "\n____________________________ <br/>"
    output += "\n<h3>Timesheet Report for {0} ({1}-{2})</h3>".format(
        reportee_name, ARGS.since, ARGS.until)

    for project in project_times:
        # Calculate our totals
        millis_to_mins_to_hours = 1000.0 * 60 * 60
        total_hours = project_times[project][0] / millis_to_mins_to_hours
        billable_hours = project_times[project][1] / millis_to_mins_to_hours
        discounted_hours = project_times[project][2] / millis_to_mins_to_hours

        # Write project name and totals
        output += "\n<br/><b>{0}</b><br/>".format(project)
        output += "\n&nbsp;&nbsp;Total: {:.2f}h<br/>".format(total_hours)
        output += ("\n&nbsp;&nbsp;<b style='color:blue;'>" +
                   "Billable: {:.2f}h</b><br/>".format(billable_hours))
        output += ("\n&nbsp;&nbsp;Discounted: {:.2f}h<br/>".format(
            discounted_hours))

    print(output, file=out)


if __name__ == "__main__":
    main()
