#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse

from launchpad_reporting.launchpad import LaunchpadAnonymousClient
from launchpad_reporting.db import db

PROJECTS_LIST = [
    "fuel",
    "mos",
    "murano",
    "mistral",
    "sahara",
    "ceilometer"
]


def cleanup(project):
    """ Remove nonactual tasks from db

    The main reason of the task is get stuck in db in wrong state is changing
    information type of the task to non-public. In this case it isn't possible
    to update this task during common db synchronization as such task can't be
    downloaded via anonymous launchpad client. So we manually remove such
    tasks from db.

    """

    tasks_cache = {}

    def add_task_to_cache(task):
        task_id = task.self_link.split('/')[-1]
        if task_id in tasks_cache:
            tasks_cache[task_id].append(task.web_link)
        else:
            tasks_cache[task_id] = [task.web_link]

    # Adding tasks that are targeted to series
    for s in project.series:
        for t in s.searchTasks(
                omit_targeted=False,
                status=launchpad.lpdata.BUG_STATUSES['All']):
            add_task_to_cache(t)

    # Adding tasks that aren't targeted to series
    for t in project.searchTasks(
            status=launchpad.lpdata.BUG_STATUSES['All']):
        add_task_to_cache(t)

    # Moving through all bugs in db and delete those are not
    # presented in the cache
    for task in launchpad.bugs_db[project_name].find():
        ids = task['web_link'].split('/')[-1]
        if ids not in tasks_cache:
            launchpad.bugs_db[project_name].remove(task)
            continue
        if task['web_link'] not in tasks_cache[ids]:
            launchpad.bugs_db[project_name].remove(task)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Synchronize DB.")
    parser.add_argument("--db-name", default="bugs",
                        help='A DB name to synchronize')
    args = parser.parse_args()

    bugs_db = db.connection[args.db_name]

    launchpad = LaunchpadAnonymousClient(bugs_db)

    for project_name in PROJECTS_LIST:
        project = launchpad._get_project(project_name)
        cleanup(project)
