# -*- coding: utf-8 -*-

import copy
import datetime
import logging
import pymongo
import time

import launchpadlib.launchpad
from launchpadlib.uris import LPNET_SERVICE_ROOT

from bug import Bug
from project import Project
from ttl_cache import ttl_cache


LOG = logging.getLogger(__name__)


class LaunchpadAnonymousData(object):

    BUG_STATUSES = {"New":        ["New"],
                    "Incomplete": ["Incomplete"],
                    "Open":       ["Triaged", "In Progress", "Confirmed"],
                    "Closed":     ["Fix Committed", "Fix Released",
                                   "Won't Fix", "Invalid", "Expired",
                                   "Opinion", "Incomplete"],
                    "All":        ["New", "Incomplete", "Invalid",
                                   "Won't Fix", "Confirmed", "Triaged",
                                   "In Progress", "Fix Committed",
                                   "Opinion", "Expired"],
                    "NotDone":    ["New", "Confirmed", "Triaged", "In Progress"],
                    "Fixed": ["Fix Committed", "Fix Released"]}
    BUG_STATUSES_ALL = []
    for k in BUG_STATUSES:
        BUG_STATUSES_ALL.append(BUG_STATUSES[k])

    def __init__(
        self,
        db,
        cachedir="~/.launchpadlib/cache/",
    ):
        self.db = db
        self.launchpad = launchpadlib.launchpad.Launchpad.login_anonymously(
            'launchpad-reporting-www', service_root=LPNET_SERVICE_ROOT,
            launchpadlib_dir=cachedir)

    def _get_project(self, project_name):
        return self.launchpad.projects[project_name]

    @ttl_cache(minutes=5)
    def get_project(self, project_name):
        return Project(self._get_project(project_name))

    def get_bugs(self, project_name, statuses, milestone_name=None,
                 tags=[], importance=[], **kwargs):
        project = self.db.bugs[project_name]

        search = [{"status": {"$in": statuses}}]

        if milestone_name:
            search.append({'milestone': milestone_name})

        if importance:
            search.append({"importance": {"$in": importance}})

        if tags:
            if kwargs.get("condition"):
                search.append({"tags": {"$nin": tags}})
            else:
                search.append({"tags": {"$in": tags}})

        return [Bug(r) for r in project.find({"$and": search})]

    @ttl_cache(minutes=5)
    def get_all_bugs(self, project, milestone=None):

        def timestamp_to_utc_date(timestamp):
            return (datetime.datetime.fromtimestamp(timestamp).
                    strftime('%Y-%m-%d'))

        update_time = None
        try:
            update_time = self.db.bugs.update_date.find_one()["Update_date"]
            update_time = timestamp_to_utc_date(update_time)
        except:
            pass

        return project.searchTasks(status=self.BUG_STATUSES["All"],
                                   milestone=milestone,
                                   modified_since=update_time,
                                   omit_duplicates=False)

    @ttl_cache(minutes=5)
    def get_bug_targets(self, bug):
        targets = set()
        targets.add(bug.bug_target_name.split('/')[0])
        for task in bug.related_tasks:
            targets.add(task.bug_target_name.split('/')[0])
        return targets

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
            bugs_fuel = self.get_bugs("fuel", self.BUG_STATUSES[bug_type],
                                      milestone, tag, importance)
            bugs_mos = self.get_bugs("mos", self.BUG_STATUSES[bug_type],
                                     milestone, tag, importance)
            ids = []
            for bug in bugs_fuel:
                ids.append(bug.id)
            for bug in bugs_mos:
                ids.append(bug.id)

            return len(list(set(ids)))

        sum_without_duplicity["done"] = count(milestone, tag, "Closed", None)
        sum_without_duplicity["total"] = count(milestone, tag, "All", None)
        sum_without_duplicity["high"] = count(milestone, tag, "NotDone",
                                              ["Critical", "High"])

        return sum_without_duplicity

    def common_statistic_for_project(self, project_name, milestone_name, tag):

        page_statistic = dict.fromkeys(["total",
                                        "critical",
                                        "new_for_week",
                                        "fixed_for_week",
                                        "new_for_month",
                                        "fixed_for_month",
                                        "unresolved"])

        def criterion(dict_, tag):
            if tag:
                internal = copy.deepcopy(dict_)
                internal["$and"].append({"tags": {"$in": ["{0}".format(tag)]}})
                return internal
            return dict_

        page_statistic["total"] = self.db.bugs['{0}'.format(project_name)].find(
            criterion(
                {"$and": [{"milestone": {"$in": milestone_name}}]},
                tag)).count()
        page_statistic["critical"] = self.db.bugs[
            '{0}'.format(project_name)
        ].find(
            criterion(
                {"$and": [{"status": {"$in": self.BUG_STATUSES["NotDone"]}},
                          {"importance": "Critical"},
                          {"milestone": {"$in": milestone_name}}]},
                tag)).count()
        page_statistic["unresolved"] = self.db.bugs[
            '{0}'.format(project_name)
        ].find(
            criterion(
                {"$and": [{"status": {"$in": self.BUG_STATUSES["NotDone"]}},
                          {"milestone": {"$in": milestone_name}}]},
                tag)).count()

        page_statistic["new_for_week"] = self.db.bugs[
            '{0}'.format(project_name)
        ].find(
            criterion({"$and": [
                      {"status": {"$in": self.BUG_STATUSES["New"]}},
                      {"created less than week": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["fixed_for_week"] = self.db.bugs[
            '{0}'.format(project_name)
        ].find(
            criterion({"$and": [
                      {"status": {"$in": self.BUG_STATUSES["Fixed"]}},
                      {"fixed less than week": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["new_for_month"] = self.db.bugs[
            '{0}'.format(project_name)
        ].find(
            criterion({"$and": [
                      {"status": {"$in": self.BUG_STATUSES["New"]}},
                      {"created less than month": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["fixed_for_month"] = self.db.bugs[
            '{0}'.format(project_name)
        ].find(
            criterion({"$and": [{"status": {"$in": self.BUG_STATUSES["Fixed"]}},
                                {"fixed less than month": {"$ne": False}},
                                {"milestone": {"$in": milestone_name}}]},
                      tag)).count()

        return page_statistic

    def get_update_time(self):

        update_time = time.time()
        try:
            update_time = self.db.bugs.update_date.find_one()["Update_date"]
        except:
            pass

        return update_time

    def filter_bugs(self, bugs, filters, teams_data):

        def _filter(bugs, parameter):
            filtered_bugs = []
            for b in bugs:
                if getattr(b, parameter) in filters[parameter]:
                    filtered_bugs.append(b)

            return filtered_bugs

        for team in bugs["DATA"]:
            if filters['status']:
                team["bugs"] = _filter(team["bugs"], 'status')

            if filters['importance']:
                team["bugs"] = _filter(team["bugs"], 'importance')

            if filters['criteria']:
                team["bugs"] = _filter(team["bugs"], 'criteria')

            if filters['assignee']:
                new_teams_data = {}

                for x in teams_data.values():
                    new_teams_data.update(x)

                all_people = new_teams_data.keys()
                for vals in new_teams_data.values():
                    all_people.extend(vals)

                newbugs = []
                for b in team["bugs"]:

                    if ('unknown' in filters['assignee'] and b.assignee
                            not in all_people):
                        newbugs.append(b)

                    for name, lst in new_teams_data.items():
                        if (name in filters['assignee'] and
                            (b.assignee == name or b.assignee in lst)):
                                if b not in newbugs:
                                    newbugs.append(b)

                team["bugs"] = newbugs

        return bugs


class LaunchpadData(LaunchpadAnonymousData):

    def __init__(
        self,
        cachedir="~/.launchpadlib/cache/",
        credentials_filename="/etc/lp-reports/credentials.txt"
    ):
        self.launchpad = launchpadlib.launchpad.Launchpad.login_with(
            'launchpad-reporting-www', service_root=LPNET_SERVICE_ROOT,
            credentials_file=credentials_filename, launchpadlib_dir=cachedir)
