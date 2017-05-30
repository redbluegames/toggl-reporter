# Toggl Reporter
This tool hits the Toggl API and generates reports that I send to the rest
of the team via the helper email script.

Currently it only generates a detailed report broken down by project
for a given user and date range.

# Installation

Install Python

    brew install python

Install Python dependencies

    pip install pyaml
    pip install iso8601
    pip install requests

Install [Linter](https://github.com/AtomLinter/linter-pylint) (if writing code)

    pip install pylint
    apm install linter-pylint

Copy the _empty-config.yaml file_ to _config.yaml_.

    cp empty-config.yaml config.yaml

Modify the new file to include your Toggl and Gmail credentials.

# Usage

You can run this tool from the command line. Many parameters are obtained
from the config file, so make sure you've set that up.

To generate a JOSN report...

    python toggl-reporter.py <since> <until>

To generate a PDF report...

    python toggl-reporter.py -p <since> <until>

To send a report via email...

    python send-mail.py

# Resources

See the [Toggle API docs](https://github.com/toggl/toggl_api_docs) for more details.
