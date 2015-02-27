    #!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
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

    sync_start_time = time.time()

    parser = argparse.ArgumentParser(description="Synchronize DB.")
    parser.add_argument("--db-name", default="bugs",
                        help='A DB name to synchronize')
    args = parser.parse_args()


    bugs_db = db.connection[args.db_name]

    launchpad = LaunchpadAnonymousClient(bugs_db)

    milestones = bugs_db.milestones
    bugs_db.drop_collection(milestones)

    projects = bugs_db.projects
    subprojects = bugs_db.subprojects

    mos = launchpad.get_project("mos")
    fuel = launchpad.get_project("fuel")

    milestones_list = launchpad.common_milestone(
        mos.active_milestones,
        fuel.active_milestones
    )

    print("Creating milestones...")
    milestones.insert({"Milestone": milestones_list})

    print("Creating projects...")
    collection_names = bugs_db.collection_names()
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
        lambda pr: bugs_db.create_collection(pr),
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
            args=(pname, bugs_db, PROJECTS_LIST, queue, stop_events[i])
        ) for i, pname in enumerate(project_names)
    ]
    processors = map(
        lambda num: Process(
            target=process_bugs,
            args=(queue, bugs_db, stop_events)
        ),
        xrange(NUM_PROCESSES)
    )

    print("Spawning loaders...")
    map(lambda p: p.start(), loaders)
    print("Spawning processors...")
    map(lambda p: p.start(), processors)

    map(lambda p: p.join(), loaders)
    map(lambda p: p.join(), processors)

    bugs_db.drop_collection("update_date")
    bugs_db.create_collection("update_date")
    bugs_db.update_date.insert({"Update_date": sync_start_time})
