#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time

from Queue import Empty

from datetime import date
from itertools import ifilter
from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Event
import pytz

from datetime import datetime
from dateutil import relativedelta, parser

from launchpad_reporting.launchpad import LaunchpadClient
from launchpad_reporting.db import db


NUM_PROCESSES = 5


PROJECTS_LIST = [
    "fuel",
    "mos",
    "murano",
    "mistral",
    "sahara",
    "ceilometer"
]
SUBPROJECTS_LIST = [
    "murano",
    "sahara",
    "nova",
    "neutron",
    "keystone",
    "heat",
    "glance",
    "horizon",
    "ceilometer",
    "oslo",
    "cinder"
]


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

    if task:
        bug_item = task.bug
        bug_assignee = str(bug.assignee_link).split("~")[1] \
            if bug.assignee_link else None
        bug_assignee_link = bug.assignee_link \
            if bug.assignee_link else None
        bug_milestone = str(bug.milestone_link).split("/")[-1]
        bug_milestone_link = bug.milestone_link
        bug_owner = str(bug.owner_link).split("~")[1]
        bug_owner_link = bug.owner_link
    else:
        bug_item = bug.bug
        bug_assignee = bug.assignee.name if bug.assignee else None
        bug_assignee_link = bug.assignee.web_link \
            if bug.assignee else None
        bug_milestone = bug.milestone.name
        bug_milestone_link = bug.milestone.web_link
        bug_owner = bug.owner.name
        bug_owner_link = bug.owner.web_link

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
        'created less than week': younger_than(bug_dates["date_created"], weeks=1),
        'created less than month': younger_than(bug_dates["date_created"], months=1),
        'fixed less than week': younger_than(bug_dates["date_fix_committed"], weeks=1),
        'fixed less than month': younger_than(bug_dates['date_fix_committed'], months=1),
    }


def load_project_bugs(project_name, queue, stop_event):
    launchpad = LaunchpadClient()
    project = launchpad._get_project(project_name)

    milestone_series = {}
    for m in project.active_milestones:
        milestone_series[str(m)] = str(m.series_target)

    counter = 0
    for bug in launchpad.get_all_bugs(project):
        bug_id = bug.bug.id
        db.bugs[
            str(bug.bug_target_name).split('/')[0]
        ].remove({'id': bug_id})

        if bug.bug.duplicate_of is not None:
            continue

        target_projects = launchpad.get_bug_targets(bug)

        for project in PROJECTS_LIST:
            if project not in target_projects:
                db.bugs[project].remove({'id': bug_id})

        bug_milestone = str(bug.milestone)
        rts = bug.related_tasks.entries

        if rts:
            rts_milestones = []
            for rt in rts:
                rts_milestones.append(rt["target_link"])
            if milestone_series[bug_milestone] not in rts_milestones:
                queue.put(serialize_bug(bug))

            for rt in rts:
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


def process_bugs(queue, stop_events):
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


if __name__ == "__main__":
    launchpad = LaunchpadClient()

    milestones = db.bugs.milestones
    db.bugs.drop_collection(milestones)

    projects = db.bugs.projects
    subprojects = db.bugs.subprojects

    mos = launchpad.get_project("mos")
    fuel = launchpad.get_project("fuel")

    milestones_list = launchpad.common_milestone(
        mos.active_milestones,
        fuel.active_milestones
    )

    print("Creating milestones...")
    milestones.insert({"Milestone": milestones_list})

    print("Creating projects...")
    collection_names = db.bugs.collection_names()
    projects.update(
        {
            "Project": projects.find_one()["Project"]
            if "Project" in collection_names else ""
        },
        {"Project": PROJECTS_LIST},
        upsert=True
    )

    print("Creating subprojects...")
    subprojects.update(
        {
            "Subproject": subprojects.find_one()["Subproject"]
            if "Subproject" in collection_names else ""
        },
        {"Subproject": SUBPROJECTS_LIST},
        upsert=True
    )

    project_names = projects.find_one()["Project"]

    print("Creating collections...")
    map(
        lambda pr: db.bugs.create_collection(pr),
        ifilter(
            lambda pr: pr not in collection_names,
            project_names
        )
    )

    queue = Queue()
    stop_events = [Event() for _ in project_names]
    loaders = [
        Process(
            target=load_project_bugs,
            args=(pname, queue, stop_events[i])
        ) for i, pname in enumerate(project_names)
    ]
    processes = map(
        lambda num: Process(
            target=process_bugs,
            args=(queue, stop_events)
        ),
        xrange(NUM_PROCESSES)
    )

    print("Spawning loader processes...")
    map(lambda p: p.start(), loaders)
    print("Spawning processes...")
    map(lambda p: p.start(), processes)

    map(lambda p: p.join(), loaders)
    map(lambda p: p.join(), processes)

    db.bugs.drop_collection("update_date")
    db.bugs.create_collection("update_date")
    db.bugs.update_date.insert({"Update_date": time.time()})
