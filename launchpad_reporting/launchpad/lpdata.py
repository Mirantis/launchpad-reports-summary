# -*- coding: utf-8 -*-

import copy
import datetime
import logging
from pymongo import MongoClient
import time
import os

from urlparse import urlsplit, urljoin

import launchpadlib.launchpad
from launchpadlib.credentials import Consumer
from launchpadlib.credentials import authorize_token_page
from launchpadlib.uris import (LPNET_SERVICE_ROOT, STAGING_SERVICE_ROOT,
                               lookup_service_root)
from lazr.restfulclient.authorize.oauth import SystemWideConsumer
from lazr.restfulclient.resource import ServiceRoot

from bug import Bug
from launchpad_reporting.db.util import serialize_bug
from project import Project
from ttl_cache import ttl_cache


LOG = logging.getLogger(__name__)


def authorization_url(web_root, request_token,
                      allow_access_levels=["DESKTOP_INTEGRATION"]):
    """Return the authorization URL for a request token.

    This is the URL the end-user must visit to authorize the
    token. How exactly does this happen? That depends on the
    subclass implementation.
    """
    allow_access_levels = allow_access_levels or []
    page = "%s?oauth_token=%s" % (authorize_token_page, request_token)
    allow_permission = "&allow_permission="
    if len(allow_access_levels) > 0:
        page += (
            allow_permission
            + allow_permission.join(allow_access_levels))
    return urljoin(web_root, page)


class SimpleLaunchpad(ServiceRoot):
    """Custom Launchpad API class.

    Provides simplified launchpad authentication way,
    without using complex RequestTokenAuthorizationEngine machinery.
    """

    DEFAULT_VERSION = '1.0'

    RESOURCE_TYPE_CLASSES = {
            'bugs': launchpadlib.launchpad.BugSet,
            'distributions': launchpadlib.launchpad.DistributionSet,
            'people': launchpadlib.launchpad.PersonSet,
            'project_groups': launchpadlib.launchpad.ProjectGroupSet,
            'projects': launchpadlib.launchpad.ProjectSet,
            }
    RESOURCE_TYPE_CLASSES.update(ServiceRoot.RESOURCE_TYPE_CLASSES)

    def __init__(self, credentials, service_root=STAGING_SERVICE_ROOT,
                 cache=None, timeout=None, proxy_info=None,
                 version=DEFAULT_VERSION):
        service_root = lookup_service_root(service_root)
        if (service_root.endswith(version) or
           service_root.endswith(version + '/')):
            error = ("It looks like you're using a service root that "
                     "incorporates the name of the web service version "
                     '("%s"). Please use one of the constants from '
                     "launchpadlib.uris instead, or at least remove "
                     "the version name from the root URI." % version)
            raise ValueError(error)
        super(SimpleLaunchpad, self).__init__(
            credentials, service_root, cache, timeout, proxy_info, version)

    @classmethod
    def set_credentials_consumer(cls, credentials, consumer_name):
        if isinstance(consumer_name, Consumer):
            consumer = consumer_name
        else:
            # Create a system-wide consumer. lazr.restfulclient won't
            # do this automatically, but launchpadlib's default is to
            # do a desktop-wide integration.
            consumer = SystemWideConsumer(consumer_name)
        credentials.consumer = consumer

    @classmethod
    def login_with(cls, credentials, application_name=None,
                   service_root=STAGING_SERVICE_ROOT,
                   launchpadlib_dir=None, timeout=None, proxy_info=None,
                   allow_access_levels=None, max_failed_attempts=None,
                   version=DEFAULT_VERSION, consumer_name=None):
        (service_root, launchpadlib_dir, cache_path,
         service_root_dir) = cls._get_paths(service_root, launchpadlib_dir)
        if (application_name is None and consumer_name is None):
            raise ValueError("At least one of application_name or"
                             "consumer_name must be provided.")
        cls.set_credentials_consumer(credentials, consumer_name)
        return cls(credentials, service_root, cache_path, timeout, proxy_info,
                   version)

    @classmethod
    def _get_paths(cls, service_root, launchpadlib_dir=None):
        if launchpadlib_dir is None:
            launchpadlib_dir = os.path.join('~', '.launchpadlib')
        launchpadlib_dir = os.path.expanduser(launchpadlib_dir)
        if launchpadlib_dir[:1] == '~':
            raise ValueError("Must set $HOME or pass 'launchpadlib_dir' to "
                "indicate location to store cached data")
        if not os.path.exists(launchpadlib_dir):
            os.makedirs(launchpadlib_dir, 0700)
        os.chmod(launchpadlib_dir, 0700)
        # Determine the real service root.
        service_root = lookup_service_root(service_root)
        # Each service root has its own cache and credential dirs.
        scheme, host_name, path, query, fragment = urlsplit(
            service_root)
        service_root_dir = os.path.join(launchpadlib_dir, host_name)
        cache_path = os.path.join(service_root_dir, 'cache')
        if not os.path.exists(cache_path):
            os.makedirs(cache_path, 0700)
        return (service_root, launchpadlib_dir, cache_path, service_root_dir)


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
                                   "Fix Released",
                                   "Opinion", "Expired"],
                    "NotDone":    ["New", "Confirmed", "Triaged", "In Progress"],
                    "Fixed": ["Fix Committed", "Fix Released"]}
    BUG_STATUSES_ALL = []
    for k in BUG_STATUSES:
        BUG_STATUSES_ALL.append(BUG_STATUSES[k])

    def __init__(
        self,
        bugs_db,
        cachedir="~/.launchpadlib/cache/",
    ):
        self.bugs_db = bugs_db
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
        project = self.bugs_db[project_name]

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
            return (datetime.datetime.utcfromtimestamp(timestamp).
                    strftime('%Y-%m-%d'))

        update_time = None
        try:
            update_time = self.bugs_db.update_date.find_one()["Update_date"]
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

        page_statistic["total"] = self.bugs_db['{0}'.format(project_name)].find(
            criterion(
                {"$and": [{"milestone": {"$in": milestone_name}}]},
                tag)).count()
        page_statistic["critical"] = self.bugs_db[
            '{0}'.format(project_name)
        ].find(
            criterion(
                {"$and": [{"status": {"$in": self.BUG_STATUSES["NotDone"]}},
                          {"importance": "Critical"},
                          {"milestone": {"$in": milestone_name}}]},
                tag)).count()
        page_statistic["unresolved"] = self.bugs_db[
            '{0}'.format(project_name)
        ].find(
            criterion(
                {"$and": [{"status": {"$in": self.BUG_STATUSES["NotDone"]}},
                          {"milestone": {"$in": milestone_name}}]},
                tag)).count()

        page_statistic["new_for_week"] = self.bugs_db[
            '{0}'.format(project_name)
        ].find(
            criterion({"$and": [
                      {"status": {"$in": self.BUG_STATUSES["New"]}},
                      {"created less than week": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["fixed_for_week"] = self.bugs_db[
            '{0}'.format(project_name)
        ].find(
            criterion({"$and": [
                      {"status": {"$in": self.BUG_STATUSES["Fixed"]}},
                      {"fixed less than week": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["new_for_month"] = self.bugs_db[
            '{0}'.format(project_name)
        ].find(
            criterion({"$and": [
                      {"status": {"$in": self.BUG_STATUSES["New"]}},
                      {"created less than month": {"$ne": False}},
                      {"milestone": {"$in": milestone_name}}]}, tag)).count()
        page_statistic["fixed_for_month"] = self.bugs_db[
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
            update_time = self.bugs_db.update_date.find_one()["Update_date"]
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

        def transform_date(str):
            if str is not None:
                return datetime.datetime.strptime(str, "%Y-%m-%d")

        for team in bugs["DATA"]:
            if filters['status']:
                team["bugs"] = _filter(team["bugs"], 'status')

            if filters['importance']:
                team["bugs"] = _filter(team["bugs"], 'importance')

            if filters['criteria']:
                team["bugs"] = _filter(team["bugs"], 'criteria')

            if filters['tags']:
                filtered_bugs = []
                for b in team["bugs"]:
                    print(getattr(b, 'tags'), filters['tags'])
                    if set(getattr(b, 'tags')) & set(filters['tags']):
                        filtered_bugs.append(b)
                        print(True)
                team["bugs"] = filtered_bugs

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

            date_state = ["created", "triaged", "fix_committed", "fix_released"]

            filtered_bugs = []
            for bug in team["bugs"]:
                satisfies = True

                for state in date_state:
                    bug_date = getattr(bug, 'date_{0}'.format(state))

                    if bug_date is not None:
                        if (filters[state+"_from"] is not None and
                                bug_date < transform_date(filters[state+"_from"])):

                            satisfies = False
                            break

                        if (filters[state+"_to"] is not None and
                                bug_date > transform_date(filters[state+"_to"])):
                            satisfies = False
                            break
                    else:
                        if (filters[state+"_from"] is not None
                                or filters[state+"_to"] is not None):
                            satisfies = False
                            break

                if satisfies:
                    filtered_bugs.append(bug)

            team["bugs"] = filtered_bugs

        return bugs


class LaunchpadData(LaunchpadAnonymousData):

    PRIVATE_BUG_TYPES = ['Private', 'Private Security', 'Proprietary']

    def __init__(
        self,
        db,
        credentials,
    ):
        self.launchpad = SimpleLaunchpad.login_with(
            credentials, 'launchpad-reporting-www',
            service_root=LPNET_SERVICE_ROOT)

    @ttl_cache(minutes=5)
    def serialize_private(self, task):
        return serialize_bug(task)

    def get_bugs(self, project_name, statuses, milestone_name=None,
                 tags=[], importance=[], **kwargs):
        result_bugs = self.get_all_bugs_by(project_name, milestone_name)
        result_bugs = [task for task in result_bugs
                       if task.status in statuses]
        if milestone_name:
            result_bugs = [task for task in result_bugs
                           if task.milestone_link.split('/')[-1] in milestone_name]
        if importance:
            result_bugs = [task for task in result_bugs
                           if task.importance in importance]
        if tags:
            if kwargs.get("condition"):
                result_bugs = [task for task in result_bugs
                               if len(set(task.bug.tags).difference(set(tags))) > 0]
            else:
                result_bugs = [task for task in result_bugs
                               if len(set(task.bug.tags).intersection(set(tags))) > 0]
        return [Bug(self.serialize_private(bug)) for bug in result_bugs]

    @ttl_cache(minutes=5)
    def get_all_bugs(self, project):
        project_tasks = project.searchTasks(status=self.BUG_STATUSES["All"],
                                            milestone=[
                                                i.self_link
                                                for i in project.active_milestones])
        private_tasks = [task for task
                         in project_tasks
                         if "Private" in task.bug.information_type]
        return private_tasks

    @ttl_cache(minutes=5)
    def get_all_bugs_by(self, project_name, milestone):
        project = self.launchpad.projects[project_name]
        try:
            milestone = [unicode('https://api.launchpad.net/1.0/{0}/+milestone/{1!s}').format(
                project_name, ms) for ms in milestone]
            return project.searchTasks(status=self.BUG_STATUSES["All"],
                                       milestone=milestone,
                                       information_type=self.PRIVATE_BUG_TYPES)
        except Exception as e:
            print e
