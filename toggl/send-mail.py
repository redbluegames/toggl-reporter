#!/usr/local/bin/python
# send-mail.py
# Sends email

import yaml
# Import smtplib for the actual sending function
import smtplib
# Import the email modules we'll need
from email.mime.text import MIMEText

# Load YAML configs
f = open('config.yaml')
config = yaml.safe_load(f)
f.close()

# Open a plain text file for reading.  For this example, assume that
# the text file contains only ASCII characters.
fp = open("report.txt", 'rb')
# Create a text/plain message
msg = MIMEText(fp.read())
fp.close()

me = config['email']
you = config['recipients']
msg['Subject'] = 'The contents of %s' % "report.txt"
msg['From'] = config['from']
msg['To'] = config['to']

# Send the message via our own SMTP server, but don't include the
# envelope header.
server = smtplib.SMTP(config['server'])
server.ehlo()
server.starttls()

server.login(config['login'], config['app_password'])
server.sendmail(me, you, msg.as_string())
server.quit()
