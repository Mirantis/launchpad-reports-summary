import copy
import pymongo


from launchpadlib.launchpad import Launchpad
from bug import Bug
from project import Project
from ttl_cache import ttl_cache

connection = pymongo.Connection()
db = connection["bugs"]

class LaunchpadData():

    BUG_STATUSES = {"New":        ["New"],
                    "Incomplete": ["Incomplete"],
                    "Open":       ["Triaged", "In Progress", "Confirmed"],
                    "Closed":     ["Fix Committed", "Fix Released", "Won't Fix",
                                   "Invalid", "Expired", "Opinion", "Incomplete"],
                    "All":        ["New", "Incomplete", "Invalid", "Won't Fix",
                                   "Confirmed", "Triaged", "In Progress",
                                   "Fix Released", "Fix Committed", "Opinion",
                                   "Expired"],
                    "NotDone":    ["New", "Confirmed", "Triaged", "In Progress"]}
    BUG_STATUSES_ALL = []
    for k in BUG_STATUSES:
        BUG_STATUSES_ALL.append(BUG_STATUSES[k])

    def __init__(self):
        cachedir = "~/.launchpadlib/cache/"
        self.launchpad = Launchpad.login_anonymously(
            'launchpad-reporting-www', 'production', cachedir)

    def _get_project(self, project_name):
        return self.launchpad.projects[project_name]

    @ttl_cache(minutes=5)
    def get_project(self, project_name):
        return Project(self._get_project(project_name))

    def get_bugs(self, project_name, statuses, milestone_name=None,
                 tags=[], importance=[]):
        project = db[project_name]

        search = [{"status": {"$in": statuses}}]

        if milestone_name:
            search.append({'milestone': milestone_name})

        if importance:
            search.append({"importance": {"$in": importance}})

        if tags:
            search.append({"tags": {"$in": tags}})

        return [Bug(r) for r in project.find({"$and": search})]

    @ttl_cache(minutes=5)
    def get_all_bugs(self, project):
        return project.searchTasks(status=self.BUG_STATUSES["All"],
                                   milestone=[
                                       i.self_link
                                       for i in project.active_milestones])

    @staticmethod
    def dump_object(object):
        for name in dir(object):
            try:
                value = getattr(object, name)
            except AttributeError:
                value = "n/a"
            try:
                print name + " --- " + str(value)
            except ValueError:
                print name + " --- " + "n/a"

    def common_milestone(self, pr_a, pr_b):
        return list(set(pr_a) & set(pr_b))

    def bugs_ids(self, tag, milestone):
        sum_without_duplicity = {"done": "",
                                "total": "",
                                "high": ""}

        def count(milestone, tag, bug_type, importance):
            bugs_fuel = self.get_bugs("fuel", self.BUG_STATUSES[bug_type], milestone, tag, importance)
            bugs_mos = self.get_bugs("mos", self.BUG_STATUSES[bug_type], milestone, tag, importance)
            ids = []
            for bug in bugs_fuel:
                ids.append(bug.id)
            for bug in bugs_mos:
                ids.append(bug.id)

            return len(list(set(ids)))

        sum_without_duplicity["done"] = count(milestone, tag, "Closed", None)
        sum_without_duplicity["total"] = count(milestone, tag, "All", None)
        sum_without_duplicity["high"] = count(milestone, tag, "NotDone", ["Critical", "High"] )

        return sum_without_duplicity

    def common_statistic_for_project(self, project_name, tag, milestone_name):

        page_statistic = dict.fromkeys(["total",
                                   "critical",
                                   "new_for_week",
                                   "fixed_for_week",
                                   "new_for_month"
                                   "fixed_for_month",
                                   "unresolved"])


        def criterion(dict_, tag):
            if tag:
                internal = copy.deepcopy(dict_)
                internal["$and"].append({"tags": {"$in": ["{0}".format(tag)]}})
                return internal
            return dict_

        page_statistic["total"] = db['{0}'.format(project_name)].find(
            criterion({"$and": [{"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["critical"] = db['{0}'.format(project_name)].find(
            criterion({"$and": [{"status": {"$in": self.BUG_STATUSES["NotDone"]}},
                      {"importance": "Critical"},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["unresolved"] = db['{0}'.format(project_name)].find(
            criterion({"$and": [{"status": {"$in": self.BUG_STATUSES["NotDone"]}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["new_for_week"] = db['{0}'.format(project_name)].find(
            criterion({"$and": [{"created less than week": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["fixed_for_week"] = db['{0}'.format(project_name)].find(
            criterion({"$and": [{"fixed less than week": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["new_for_month"] = db['{0}'.format(project_name)].find(
            criterion({"$and": [{"created less than month": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["fixed_for_month"] = db['{0}'.format(project_name)].find(
            criterion({"$and": [{"fixed less than month": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()

        return page_statistic
