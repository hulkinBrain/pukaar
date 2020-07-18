import httplib2
import os
import base64
import json

from oauth2client import client
from oauth2client import tools
from google.oauth2 import service_account
from oauth2client import client
from oauth2client.client import FlowExchangeError
from googleapiclient import discovery
json_creds = json.loads(base64.b64decode(os.environ["G_AUTH"]).decode())
json_creds2 = json.loads(base64.b64decode(os.environ["GMAIL_AUTH"]).decode())
# print(json_creds2)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    # Add other requested scopes.
]

credentials = service_account.Credentials.from_service_account_info(json_creds, scopes=SCOPES)
# credentials = client.Credentials.from_json(json_creds2)
#
#
# REDIRECT_URI = ""
service = discovery.build('gmail', 'v1', credentials=credentials)
results = service.users().labels().list(userId='me').execute()
labels = results.get('labels', [])
if not labels:
    print("No labels")
else:
    print("labels:")
    for label in labels:
        print(label['name'])