import datetime

from pandas.tseries import offsets

CRITICAL_IMPORTANCE = "Critical"
HIGH_IMPORTANCE = "High"

CONFIRMED_STATUS = "Confirmed"
IN_PROGRESS_STATUS = "In Progress"
TRIAGED_STATUS = "Triaged"

CUSTOMER_FOUND_TAG = "customer-found"


def business_days_ago(days):
    timedelta = datetime.datetime.now() - offsets.BDay(days)
    return timedelta.to_datetime()


class BugCriteria(object):
    def get_hint_text(self, bug, template):
        is_customer_found = CUSTOMER_FOUND_TAG in bug.tags

        if getattr(self, 'threshold', None):
            threshold = self.threshold
        else:
            if bug.importance in [CRITICAL_IMPORTANCE, HIGH_IMPORTANCE]:
                threshold_template = bug.importance.lower()
            else:
                threshold_template = "others"
            if is_customer_found:
                threshold_template += "_customer_found"
            threshold_template += "_threshold"
            try:
                threshold = getattr(self, threshold_template)
            except AttributeError:
                if is_customer_found:
                    threshold = getattr(
                        self,
                        threshold_template.replace("_customer_found", "")
                    )

        hint_data = {
            "importance": bug.importance,
            "with_customer_found": "with `customer-found` tag" if is_customer_found else "",
            "threshold": threshold,
        }
        return template.format(**hint_data)


class NonTriaged(BugCriteria):
    """Implementation for `sla-non-triaged` criteria"""

    def __init__(self, threshold):
        self.threshold = threshold

    def is_satisfied(self, bug):
        return (bug.date_created < business_days_ago(self.threshold)
                and (bug.milestone is None or bug.importance is None
                     or bug.assignee is None)
                )


class SLAFullLifecycle(BugCriteria):
    """Implementation for `sla-full-lifecycle` criteria"""

    def __init__(self, critical_threshold, high_threshold):
        self.critical_threshold = critical_threshold
        self.high_threshold = high_threshold

    def is_satisfied(self, bug):
        if bug.importance == HIGH_IMPORTANCE:
            return bug.date_created < business_days_ago(self.high_threshold)
        if bug.importance == CRITICAL_IMPORTANCE:
            return (bug.date_created <
                    business_days_ago(self.critical_threshold))
        else:
            # False for all other bugs
            return False


class SLAConfirmedTriaged(BugCriteria):
    """Implementation for `sla-confirmed-triaged` criteria"""

    def __init__(self, threshold):
        self.threshold = threshold

    def is_satisfied(self, bug):
        if bug.status in [CONFIRMED_STATUS, TRIAGED_STATUS]:
            return bug.date_last_updated < business_days_ago(self.threshold)
        return False


class SLAInProgress(BugCriteria):
    """Implementation for `sla-in-progress` criteria"""

    def __init__(self, critical_customer_found_threshold, critical_threshold,
                 high_customer_found_threshold, high_threshold,
                 others_threshold):
        self.critical_customer_found_threshold = critical_customer_found_threshold
        self.critical_threshold = critical_threshold
        self.high_customer_found_threshold = high_customer_found_threshold
        self.high_threshold = high_threshold
        self.others_threshold = others_threshold

    def is_satisfied(self, bug):
        if bug.status != IN_PROGRESS_STATUS:
            return False

        if bug.importance == CRITICAL_IMPORTANCE and CUSTOMER_FOUND_TAG in bug.tags:
            return bug.date_in_progress < business_days_ago(self.critical_customer_found_threshold)
        if bug.importance == CRITICAL_IMPORTANCE:
            return bug.date_in_progress < business_days_ago(self.critical_threshold)
        if bug.importance == HIGH_IMPORTANCE and CUSTOMER_FOUND_TAG in bug.tags:
            return bug.date_in_progress < business_days_ago(self.high_customer_found_threshold)
        if bug.importance == HIGH_IMPORTANCE:
            return bug.date_in_progress < business_days_ago(self.high_threshold)
        return bug.date_in_progress < business_days_ago(self.others_threshold)
