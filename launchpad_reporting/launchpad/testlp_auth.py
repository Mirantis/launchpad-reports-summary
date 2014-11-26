import json, time
from launchpadlib.credentials import Credentials
from lazr.restfulclient.errors import HTTPError

credentials = Credentials("launchpad-reporting-www")
request_token_info = credentials.get_request_token(web_root="production")
print request_token_info

print '**** *** sleeping (while you validate token in the browser) *** ***'

time.sleep(15)

print '**** *** continuing *** ***'

credentials.exchange_request_token_for_access_token(web_root="production")

print json.dumps(credentials)

