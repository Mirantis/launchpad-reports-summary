from datetime import date
from dateutil import relativedelta, parser
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
                                   "Fix Released", "Fix Committed"],
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

    def _get_milestone(self, project_name, milestone_name):
        project = self._get_project(project_name)
        return self.launchpad.load(
            "%s/+milestone/%s" % (project.self_link, milestone_name))

    @ttl_cache(minutes=5)
    def get_project(self, project_name):
        return Project(self._get_project(project_name))

    @ttl_cache(minutes=5)
    def get_bugs(self, project_name, statuses, milestone_name = None, tags = None, importance = None):
        project = self._get_project(project_name)
        if (milestone_name is None) or (milestone_name == 'None'):
            return [Bug(r) for r in project.searchTasks(status=statuses)]

        milestone = self._get_milestone(project_name, milestone_name)
        if (tags is None) or (tags == 'None'):
            return [Bug(r) for r in project.searchTasks(status=statuses, milestone=milestone)]

        if (importance is None) or (importance == 'None'):
            return [Bug(r) for r in project.searchTasks(status=statuses, milestone=milestone, tags=tags)]

        return [Bug(r) for r in project.searchTasks(importance=importance, status=statuses, milestone=milestone, tags=tags)]

    @ttl_cache(minutes=5)
    def get_all_bugs(self, project):
        return project.searchTasks()

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

    def total_number_bugs(self, project_name, tag):

        def get_date(parameter):
            return parser.parse(parameter.ctime())

        week_ago = date.today() - relativedelta.relativedelta(weeks=1)
        months_ago = date.today() - relativedelta.relativedelta(months=1)

        project = self._get_project(project_name)
        statistic = {"total": "",
                     "critical": "",
                     "new_for_week": "",
                     "fixed_for_week": "",
                     "new_for_month": "",
                     "fixed_for_month": ""}

        launchpad_bugs = project.searchTasks(importance=["Critical",],
                                             status=["New",
                                                     "Confirmed",
                                                     "Triaged",
                                                     "In Progress",
                                                     "Incomplete"],
                                             tags=tag)

        statistic["critical"] = str(len(launchpad_bugs))

        launchpad_bugs = project.searchTasks(status=["New",
                                                     "Confirmed",
                                                     "Triaged",
                                                     "In Progress",
                                                     "Incomplete"],
                                             tags=tag)

        statistic['total_unresolved'] = str(len(launchpad_bugs))
        launchpad_bugs = project.searchTasks(status=["New",
                                                     "Fix Committed",
                                                     "Confirmed",
                                                     "Triaged",
                                                     "In Progress",
                                                     "Incomplete"],
                                             tags=tag)

        statistic["total"] = str(len(launchpad_bugs))

        fixed_on_the_last_month = 0
        created_on_the_last_month = 0
        fixed_on_the_last_week = 0
        created_on_the_last_week = 0
        for bug in launchpad_bugs:
            if get_date(months_ago) < get_date(bug.date_created):
                created_on_the_last_month += 1
            if get_date(week_ago) < get_date(bug.date_created):
                created_on_the_last_week += 1
            if bug.date_fix_committed is not None:
                if get_date(months_ago) < get_date(bug.date_fix_committed):
                    fixed_on_the_last_month += 1
                if get_date(week_ago) < get_date(bug.date_fix_committed):
                    fixed_on_the_last_week += 1

        statistic['new_for_week'] = created_on_the_last_week
        statistic['fixed_for_week'] = fixed_on_the_last_week
        statistic['new_for_month'] = created_on_the_last_month
        statistic['fixed_for_month'] = fixed_on_the_last_month
        return statistic

    def common_milestone(self, pr_a, pr_b):
        return list(set(pr_a) & set(pr_b))

    def count_bugs_by_milestone(self, project_name, tag, milestone):

        statistic = {"done": "",
                     "total": "",
                     "high": ""}

        project = self._get_project(project_name)
        bugs = project.searchTasks(status=self.BUG_STATUSES["Closed"],
                                   tags=tag,
                                   milestone=milestone)
        statistic["done"] = str(len(bugs))

        bugs = project.searchTasks(status=self.BUG_STATUSES["NotDone"],
                                   importance=["Critical", "High"],
                                   tags=tag,
                                   milestone=milestone)

        statistic["high"] = str(len(bugs))

        bugs = project.searchTasks(status=self.BUG_STATUSES["All"],
                                   tags=tag,
                                   milestone=milestone)

        statistic["total"] = str(len(bugs))

        return statistic

    def statistic_by_milestone(self, milestone):
        fuel = []
        mos = []
        fuel_mos = []
        for pr in db.milestone_tab.find({},{ 'Subproject':1, 'high':1, 'total':1, 'done':1 }).\
            where('this.Milestone == "{0}" & this.Project == "fuel"'.format(milestone)):
            fuel.append(pr)
        for pr in db.milestone_tab.find({},{ 'Subproject':1, 'high':1, 'total':1, 'done':1 }).\
            where('this.Milestone == "{0}" & this.Project == "mos"'.format(milestone)):
            mos.append(pr)
        for  pr in db.fuel_plus_mos_statistic.find({},{ 'Subproject':1, 'high':1, 'total':1, 'done':1 }).\
            where('this.Milestone == "{0}"'.format(milestone)):
            fuel_mos.append(pr)

        k = {}
        for i in mos:
            k[i['Subproject']] = {}
            k[i['Subproject']]["mos"] = i

        for i in fuel:
            k[i['Subproject']]["fuel"] = i

        for i in fuel_mos:
            k[i['Subproject']]["fuel_mos"] = i

        return k

    def summary_by_milestone(self, k):
        sum = {"fuel_done": 0,
               "fuel_high": 0,
               "fuel_total": 0,
               "mos_done": 0,
               "mos_high": 0,
               "mos_total": 0,
               "fuel_mos_done": 0,
               "fuel_mos_total": 0,
               "fuel_mos_high": 0}

        for pr in k:
            sum["fuel_total"] += int(k[pr]["fuel"]["total"])
            sum["fuel_high"] += int(k[pr]["fuel"]["high"])
            sum["fuel_done"] += int(k[pr]["fuel"]["done"])
            sum["mos_total"] += int(k[pr]["mos"]["total"])
            sum["mos_high"] += int(k[pr]["mos"]["high"])
            sum["mos_done"] += int(k[pr]["mos"]["done"])
            sum["fuel_mos_done"] += int(k[pr]["fuel_mos"]["done"])
            sum["fuel_mos_total"] += int(k[pr]["fuel_mos"]["total"])
            sum["fuel_mos_high"] += int(k[pr]["fuel_mos"]["high"])

        return sum

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
