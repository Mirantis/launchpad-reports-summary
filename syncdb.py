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

from launchpad_reporting.launchpad import LaunchpadAnonymousClient
from launchpad_reporting.db import db
from launchpad_reporting.db.util import load_project_bugs, process_bugs

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

if __name__ == "__main__":
    launchpad = LaunchpadAnonymousClient()

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
            args=(pname, db, PROJECTS_LIST, queue, stop_events[i])
        ) for i, pname in enumerate(project_names)
    ]
    processors = map(
        lambda num: Process(
            target=process_bugs,
            args=(queue, db, stop_events)
        ),
        xrange(NUM_PROCESSES)
    )

    print("Spawning loaders...")
    map(lambda p: p.start(), loaders)
    print("Spawning processors...")
    map(lambda p: p.start(), processors)

    map(lambda p: p.join(), loaders)
    map(lambda p: p.join(), processors)

    db.bugs.drop_collection("update_date")
    db.bugs.create_collection("update_date")
    db.bugs.update_date.insert({"Update_date": time.time()})
