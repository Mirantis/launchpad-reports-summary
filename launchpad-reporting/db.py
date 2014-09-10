from dateutil import relativedelta, parser
from datetime import date
from multiprocessing import Process
import pymongo
import time

from launchpad.lpdata import LaunchpadData

lpdata = LaunchpadData()
connection = pymongo.Connection()
db = connection["bugs"]

milestones = db.milestones
projects = db.projects
subprojects = db.subprojects

mos = lpdata.get_project("mos")
fuel = lpdata.get_project("fuel")

milestones_list = lpdata.common_milestone(mos.active_milestones,
                                          fuel.active_milestones)
milestones.update({"Milestone": milestones.find_one()["Milestone"] if "Milestone" in db.collection_names() else ""},
                  {"Milestone": milestones_list}, upsert=True)

projects_list = ["fuel", "mos", "murano", "mistral", "sahara", "ceilometer"]
subprojects_list = ["murano", "sahara", "nova", "neutron", "keystone", "heat",
                    "glance", "horizon", "ceilometer", "oslo", "cinder"]

projects.update({"Project": projects.find_one()["Project"] if "Project" in db.collection_names() else ""},
                {"Project": projects_list}, upsert=True)
subprojects.update({"Subproject": subprojects.find_one()["Subproject"] if "Subproject" in db.collection_names() else ""},
                   {"Subproject": subprojects_list}, upsert=True)

bugs_list = []

for pr in projects.find_one()["Project"]:
    if pr not in db.collection_names():
        db.create_collection("{0}".format(pr))
    proj = lpdata._get_project("{0}".format(pr))
    bugs_list.extend([bug for bug in lpdata.get_all_bugs(proj)])

processes = []

for pr in projects.find_one()["Project"]:
    db['{0}'.format(pr)].update({}, {"$set": {'flag': False}}, upsert=True, multi=True)

def create_collections(bugs):
    for bug in bugs:
        while True:
            try:
                db['{0}'.format(bug.bug_target_name)].update(
                    {'id': bug.bug.id},
                    {
                        'id': bug.bug.id,
                        'web_link': bug.web_link,
                        'milestone': bug.milestone.name if bug.milestone
                        else bug.milestone,
                        'milestone_link': bug.milestone.web_link
                        if bug.milestone else bug.milestone,
                        'status': bug.status,
                        'tags': bug.bug.tags,
                        'title': bug.bug.title,
                        'importance': bug.importance,
                        'owner': bug.owner.name,
                        'owner_link': bug.owner.web_link,
                        'assignee': bug.assignee.name if bug.assignee
                        else bug.assignee,
                        'assignee_link': bug.assignee.web_link
                        if bug.assignee else bug.assignee,
                        'date_assigned': bug.date_assigned,
                        'date_closed': bug.date_closed,
                        'date_confirmed': bug.date_confirmed,
                        'date_created': bug.date_created,
                        'date_fix_committed': bug.date_fix_committed,
                        'date_fix_released': bug.date_fix_released,
                        'date_in_progress': bug.date_in_progress,
                        'date_incomplete': bug.date_incomplete,
                        'date_left_closed': bug.date_left_closed,
                        'date_left_new': bug.date_left_new,
                        'date_triaged': bug.date_triaged,
                        'created less than week': parser.parse(
                            bug.date_created.ctime()) > parser.parse(
                            (date.today() -
                             relativedelta.relativedelta(weeks=1)).ctime()),
                        'created less than month': parser.parse(
                            bug.date_created.ctime()) > parser.parse(
                            (date.today() -
                             relativedelta.relativedelta(months=1)).ctime()),
                        'fixed less than week': parser.parse(
                            bug.date_fix_committed.ctime()) > parser.parse(
                            (date.today() -
                             relativedelta.relativedelta(weeks=1)).ctime())
                        if bug.date_fix_committed is not None else None,
                        'fixed less than month': parser.parse(
                            bug.date_fix_committed.ctime()) > parser.parse(
                            (date.today() -
                             relativedelta.relativedelta(months=1)).ctime())
                        if bug.date_fix_committed is not None else None,
                        'flag': True},
                    upsert=True)
                break
            except Exception:
                pass


for i in xrange(1,11):
    proc = Process(
        target=create_collections,
        args=(bugs_list[(i-1)*len(bugs_list)/10:i*len(bugs_list)/10],))
    processes.append(proc)
    time.sleep(5)
    proc.start()

for i in processes:
    i.join()

# Removing all 'non-actual' bugs (duplicates, with inactive milestone)
for pr in projects.find_one()["Project"]:
    db['{0}'.format(pr)].remove({'flag': False}, multi=True)




