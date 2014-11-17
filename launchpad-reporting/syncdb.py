#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time

from Queue import Empty

from datetime import date
from itertools import ifilter
from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Event

from dateutil import relativedelta, parser

from launchpad import LaunchpadClient
from db import db


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


def serialize_bug(bug):
    print("Loading bug: {0}".format(bug.web_link))
    bug_dates = {
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
    }
    bug_assignee = bug.assignee
    bug_milestone = bug.milestone
    bug_owner = bug.owner
    bug_item = bug.bug

    return {
        'id': bug_item.id,
        'target_name': bug.bug_target_name,
        'web_link': bug.web_link,
        'milestone': (
            bug_milestone.name if bug_milestone else None
        ),
        'milestone_link': (
            bug_milestone.web_link if bug_milestone else None,
        ),
        'status': bug.status,
        'tags': bug_item.tags,
        'title': bug_item.title,
        'importance': bug.importance,
        'owner': bug_owner.name,
        'owner_link': bug_owner.web_link,
        'assignee': (
            bug_assignee.name if bug_assignee else None
        ),
        'assignee_link': (
            bug_assignee.web_link if bug_assignee else bug_assignee
        ),
        'created less than week': parser.parse(
            bug_dates["date_created"].ctime()
        ) > parser.parse(
            (date.today() -
             relativedelta.relativedelta(weeks=1)).ctime()
        ),
        'created less than month': parser.parse(
            bug_dates["date_created"].ctime()
        ) > parser.parse(
            (date.today() -
             relativedelta.relativedelta(months=1)).ctime()),
        'fixed less than week': parser.parse(
            bug_dates["date_fix_committed"].ctime()
        ) > parser.parse(
            (date.today() -
             relativedelta.relativedelta(weeks=1)).ctime())
        if bug_dates["date_fix_committed"] is not None else None,
        'fixed less than month': parser.parse(
            bug_dates["date_fix_committed"].ctime()
        ) > parser.parse(
            (date.today() -
             relativedelta.relativedelta(months=1)).ctime())
        if bug_dates["date_fix_committed"] is not None else None
    }


def load_project_bugs(project_name, queue, stop_event):
    launchpad = LaunchpadClient()
    project = launchpad._get_project(project_name)
    counter = 0
    for bug in launchpad.get_all_bugs(project):
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
                bug['target_name']
            ].update({'id': bug['id']}, bug, upsert=True)
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
