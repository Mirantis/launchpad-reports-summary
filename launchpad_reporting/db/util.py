import time
from datetime import date
from Queue import Empty
import pytz
from dateutil import relativedelta, parser
from datetime import datetime


class Bug(object):
    def __init__(self, dictionary):
        for key, value in dictionary.iteritems():
            if 'date' in key and value:
                dt = datetime.strptime(
                    value, '%Y-%m-%dT%H:%M:%S.%f+00:00').replace(tzinfo=pytz.UTC)
                self.__setattr__(key, dt)
            else:
                self.__setattr__(key, value)


def younger_than(bug_time, **kwargs):
    if (bug_time == None):
        return True

    bug_time = parser.parse(bug_time.ctime())

    threshold = date.today() - relativedelta.relativedelta(**kwargs)
    threshold = parser.parse(threshold.ctime())

    return bug_time > threshold


def process_date(bug_date):
    if bug_date == None:
        return None
    else:
        return bug_date.replace(tzinfo=pytz.UTC)


def serialize_bug(bug, task=None):

    print("Loading bug: {0}".format(bug.web_link))
    bug_dates = {
        'date_assigned': process_date(bug.date_assigned),
        'date_closed': process_date(bug.date_closed),
        'date_confirmed': process_date(bug.date_confirmed),
        'date_created': process_date(bug.date_created),
        'date_fix_committed': process_date(bug.date_fix_committed),
        'date_fix_released': process_date(bug.date_fix_released),
        'date_in_progress': process_date(bug.date_in_progress),
        'date_incomplete': process_date(bug.date_incomplete),
        'date_left_closed': process_date(bug.date_left_closed),
        'date_left_new': process_date(bug.date_left_new),
        'date_triaged': process_date(bug.date_triaged)
    }

    bug_assignee = str(bug.assignee_link).split("~")[1] \
        if bug.assignee_link else None
    bug_assignee_link = bug.assignee_link \
        if bug.assignee_link else None
    bug_milestone_link = bug.milestone_link if bug.milestone_link else None
    bug_milestone = str(bug_milestone_link).split("/")[-1] \
        if bug_milestone_link else None
    bug_owner = str(bug.owner_link).split("~")[1]
    bug_owner_link = bug.owner_link

    if task is not None:
        bug_item = task.bug
    else:
        bug_item = bug.bug

    return {
        'id': bug_item.id,
        'target_name': bug.bug_target_name,
        'web_link': bug.web_link,
        'milestone': (
            bug_milestone if bug_milestone else None
        ),
        'milestone_link': (
            bug_milestone_link if bug_milestone else None,
        ),
        'status': bug.status,
        'tags': bug_item.tags,
        'title': bug_item.title,
        'importance': bug.importance,
        'owner': bug_owner,
        'owner_link': bug_owner_link,
        'assignee': (
            bug_assignee if bug_assignee else None
        ),
        'assignee_link': (
            bug_assignee_link if bug_assignee else bug_assignee
        ),
        'date_assigned': bug_dates["date_assigned"],
        'date_closed': bug_dates["date_closed"],
        'date_confirmed': bug_dates["date_confirmed"],
        'date_created': bug_dates["date_created"],
        'date_fix_committed': bug_dates["date_fix_committed"],
        'date_fix_released': bug_dates["date_fix_released"],
        'date_in_progress': bug_dates["date_in_progress"],
        'date_incomplete': bug_dates["date_incomplete"],
        'date_left_closed': bug_dates["date_left_closed"],
        'date_left_new': bug_dates["date_left_new"],
        'date_triaged': bug_dates["date_triaged"],
        'date_last_updated': process_date(bug_item.date_last_updated),
        'created less than week': younger_than(bug_dates["date_created"], weeks=1),
        'created less than month': younger_than(bug_dates["date_created"], months=1),
        'fixed less than week': younger_than(bug_dates["date_fix_committed"], weeks=1),
        'fixed less than month': younger_than(bug_dates['date_fix_committed'], months=1),
    }


def load_project_bugs(project_name, db, project_list, queue, stop_event):
    from launchpad_reporting.launchpad import LaunchpadAnonymousClient
    launchpad = LaunchpadAnonymousClient()
    project = launchpad._get_project(project_name)

    milestone_series = {}
    for m in project.active_milestones:
        milestone_series[str(m)] = str(m.series_target)

    milestone_series[None] = None

    counter = 0
    for bug in launchpad.get_all_bugs(project):
        bug_id = bug.bug.id
        db.bugs[
            str(bug.bug_target_name).split('/')[0]
        ].remove({'id': bug_id})

        if bug.bug.duplicate_of is not None:
            continue

        target_projects = launchpad.get_bug_targets(bug)

        for project in project_list:
            if project not in target_projects:
                db.bugs[project].remove({'id': bug_id})

        bug_milestone = str(bug.milestone) if bug.milestone else None
        related_tasks = bug.related_tasks.entries
        related_tasks_milestones = [rt["target_link"] for rt in related_tasks]

        if related_tasks:
            if milestone_series.get(bug_milestone) not in related_tasks_milestones:
                queue.put(serialize_bug(bug))

            for rt in related_tasks:
                counter += 1
                rt = Bug(rt)
                queue.put(serialize_bug(rt, task=bug))
        else:
            counter += 1
            queue.put(serialize_bug(bug))
    print(
        "No more bugs for project '{0}' ({1} processed)".format(
            project_name,
            counter
        )
    )
    stop_event.set()


def process_bugs(queue, db, stop_events):
    while True:
        try:
            bug = queue.get_nowait()
            db.bugs[
                str(bug['target_name']).split('/')[0]
            ].update({"$and": [
                {'id': bug['id']},
                {'milestone': bug['milestone']}]}, bug, upsert=True)

        except Empty:
            if all([e.is_set() for e in stop_events]):
                break
            time.sleep(0.1)
