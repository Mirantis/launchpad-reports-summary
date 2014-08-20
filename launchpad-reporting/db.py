from dateutil import relativedelta, parser
from datetime import date
import pymongo
from launchpad.lpdata import LaunchpadData

lpdata = LaunchpadData()
connection = pymongo.Connection()
db = connection["bugs_temp_db"]

# Objects storage
milestones = db.milestones
projects = db.projects
subprojects = db.subprojects


# Milestones
db.drop_collection('milestones')
mos = lpdata.get_project("mos")
fuel = lpdata.get_project("fuel")

milestones_list = lpdata.common_milestone(mos.active_milestones,
                                          fuel.active_milestones)
db.milestones.insert({"Milestone": milestones_list})

# Projects and subprojects
db.drop_collection('projects')
db.drop_collection('subprojects')

projects_list = ["fuel", "mos", "murano", "mistral", "sahara", "ceilometer"]
subprojects_list = ["murano", "sahara", "nova", "neutron", "keystone", "heat",
                    "glance", "horizon", "ceilometer", "oslo", "cinder"]

db.projects.insert({"Project": projects_list})
db.subprojects.insert({"Subproject": subprojects_list})

for pr in db.projects.find_one()["Project"]:
    db.drop_collection(pr)

for pr in db.projects.find_one()["Project"]:
    db.create_collection("{0}".format(pr))
    proj = lpdata._get_project("{0}".format(pr))
    bugs = lpdata.get_all_bugs(proj)

    for bug in bugs:
        db['{0}'.format(pr)].insert({
        'id': bug.bug.id,
        'web_link': bug.web_link,
        'milestone': bug.milestone.name if bug.milestone else bug.milestone,
        'milestone_link': bug.milestone.web_link if bug.milestone else bug.milestone,
        'status': bug.status,
        'tags': bug.bug.tags,
        'title': bug.bug.title,
        'importance': bug.importance,
        'owner': bug.owner.name,
        'owner_link': bug.owner.web_link,
        'assignee': bug.assignee.name if bug.assignee else bug.assignee,
        'assignee_link': bug.assignee.web_link if bug.assignee else bug.assignee,
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
            (date.today() - relativedelta.relativedelta(weeks=1)).ctime()),
        'created less than month': parser.parse(
            bug.date_created.ctime()) > parser.parse(
            (date.today() - relativedelta.relativedelta(months=1)).ctime()),
        'fixed less than week': parser.parse(
            bug.date_fix_committed.ctime()) > parser.parse(
            (date.today() - relativedelta.relativedelta(weeks=1)).ctime())
        if bug.date_fix_committed is not None else None,
        'fixed less than month': parser.parse(
            bug.date_fix_committed.ctime()) > parser.parse(
            (date.today() - relativedelta.relativedelta(months=1)).ctime())
        if bug.date_fix_committed is not None else None})

db = connection["bugs"]
for pr in db.projects.find_one()["Project"]:
    db.drop_collection(pr)
db.drop_collection('milestones')
db.drop_collection('projects')
db.drop_collection('subprojects')

db = connection["bugs_temp_db"]
connection.copy_database("bugs_temp_db", "bugs")
