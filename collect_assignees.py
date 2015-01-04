#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from pymongo import MongoClient
import os

from launchpad_reporting.db import db

from launchpad_reporting.launchpad.lpdata import LaunchpadAnonymousData

lpdata = LaunchpadAnonymousData(db=db)
connection = MongoClient()
db = connection["assignees"]

assignees = db.assignees

path_to_data = "/".join(os.path.abspath(__file__).split('/')[:-1])
with open('{0}/fuel_teams.json'.format(path_to_data)) as data_file:
    data = json.load(data_file)

teams = ["Fuel", "Partners", "mos-linux", "mos-openstack"]

db.drop_collection(assignees)

global_team_list = {}

for team in teams:
    people = []
    people.extend(data[team]["teams"])

    team_list = {}

    for t in data[team]["teams"]:
        team_list[t] = []
        tt = lpdata.launchpad.people[t]
        members = tt.members_details
        for member in members:
            people.append(member.member.name)
            team_list[t].append(member.member.name)

    global_team_list[team] = team_list
    assignees.insert({"Team": "{0}".format(team),
                      "Members": people})


with open("file.json", "w") as f:
    f.write(json.dumps(global_team_list))
