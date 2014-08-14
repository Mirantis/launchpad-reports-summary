# This is a wrapper, which converts launchpad bug structure into a internal bug object.
#
# When you get certain properties of the bug (e.g. assignee), it usually does additional query to LP.
# This wrapper avoids doing any calls to Launchpad by going into internal representation of the object and grabbing the info from JSON.

import string
import lpdata

FIELDS_TO_COPY = [
    "date_assigned",
    "date_closed",
    "date_confirmed",
    "date_created",
    "date_fix_committed",
    "date_fix_released",
    "date_in_progress",
    "date_incomplete",
    "date_left_closed",
    "date_left_new",
    "date_triaged",
    "importance",
    "status"
]

FIELDS_TO_COPY_FROM_JSON = [
    "assignee_link",
    "milestone_link",
    "title",
    "web_link"
]

class Bug():

    # I'm too lazy to deal with UTF-8 at this point
    # need this make sure the bugs from Chinese people don't cause exceptions
    def sanitize_string(self, s):
        return filter(lambda x: x in string.printable, s)

    def __init__(self, lpbug):
        
        # straight copy fields from the lpbug object. this do not make any calls to LP
        for name in FIELDS_TO_COPY:
            setattr(self, name, getattr(lpbug, name))

        # copy fields from JSON internals to avoid additional "lazy init" queries to LP (as it would kill performance)
        for name in FIELDS_TO_COPY_FROM_JSON:
            setattr(self, name, lpbug._wadl_resource.representation[name])

        # extract assignee (i.e. https://api.launchpad.net/1.0/~dshulyak -> dshulyak)
        self.assignee = str(self.assignee_link).rsplit('~', 1)[-1]
        self.assignee_link = "https://launchpad.net/~" + self.assignee
        if (self.assignee is None) or (self.assignee == "None"):
            self.assignee = ""
            self.assignee_link = ""

        # extract milestone (i.e. https://api.launchpad.net/1.0/fuel/+milestone/4.1 -> 4.1)
        self.milestone = str(self.milestone_link).rsplit('/', 1)[-1]

        # extract title (i.e. Bug #1247284 in Fuel for OpenStack: "Verify Networks doesn't wait long enough for dhcp response")
        self.title = self.sanitize_string(self.title).split(':', 1)[1].strip(" \"")

        # extract id from web link (i.e. https://bugs.launchpad.net/fuel/+bug/1247284 -> 1247284)
        self.id = str(self.web_link).rsplit('/', 1)[-1]

    def get_status_changes(self):
        # Bug statuses:
        # * Incomplete -> date_incomplete
        # * New (not targeted to any release)  ->  date_created
        # * Open        -> date_triaged (date_confirmed, date_left_new, date_assigned)
        # * In Progress -> date_in_progress
        # * Resolved    -> date_fix_committed
        # * Verified    -> date_fix_released

        # if the bug is "New", it should not be displayed on the chart
        if self.status in lpdata.LaunchpadData.BUG_STATUSES["New"]:
            return []

        # list of dates
        result = []

        # When the bug was assigned to the release
        date_open = min(d for d in [self.date_triaged, self.date_confirmed, self.date_left_new, self.date_assigned] if d is not None)
        result.append( {"date": date_open, "type": "Open", "matches": [s for s in lpdata.LaunchpadData.BUG_STATUSES["Open"] if s != "In Progress"]} )

        # When the bug went to in progress state
        date_in_progress = self.date_in_progress
        result.append( {"date": date_in_progress, "type": "In Progress", "matches": ["In Progress"]} )

        # When the bug was resolved or closed (e.g. as invalid)
        date_resolved = next((d for d in [self.date_fix_committed, self.date_closed] if d is not None), None)
        result.append( {"date": date_resolved, "type": "Resolved", "matches": [s for s in lpdata.LaunchpadData.BUG_STATUSES["Closed"] if s != "Fix Released"]} )

        # When the bug was verified
        date_verified = self.date_fix_released
        result.append( {"date": date_verified, "type": "Verified", "matches": ["Fix Released"]} )

        # When the bug was set as incomplete
        date_incomplete = self.date_incomplete
        result.append( {"date": date_incomplete, "type": "Incomplete", "matches": lpdata.LaunchpadData.BUG_STATUSES["Incomplete"]} )

        # Remove all entries which have date as "None"
        result = [e for e in result if e["date"] is not None]

        # Filter dates and statuses which are out of line
        for i in range(0, len(result)):
            for j in range (i + 1, len(result)):
                if result[i]["date"] > result[j]["date"]:
                    result[i]["obsolete"] = True

        # Remove all obsoleted entries
        result = [e for e in result if not "obsolete" in e]

        # Find the first element which matches our bug status
        idx = -1
        for i in range(0, len(result)):
            if self.status in result[i]["matches"]:
                idx = i
                break

        # The date for our status is not found. Not sure if it can happen
        if idx < 0:
            return []

        # Get the corresponding prefix of result, so it ends with the right status (the status in which our bug is in)
        result = result[:idx+1]

        return result
