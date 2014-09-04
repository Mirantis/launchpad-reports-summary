import json
import pymongo
import os

from launchpad.lpdata import LaunchpadData

lpdata = LaunchpadData()
connection = pymongo.Connection()
db = connection["assignees"]

assignees = db.assignees

path_to_data = "/".join(os.path.abspath(__file__).split('/')[:-1])
with open('{0}/fuel_teams.json'.format(path_to_data)) as data_file:
    data = json.load(data_file)

teams = ["Fuel", "Partners", "mos-linux", "mos-openstack"]

db.drop_collection(assignees)

for team in teams:
    people = []
    people.extend(data[team]["teams"])
    people.extend(data[team]["people"])

    for t in data[team]["teams"]:
        tt = lpdata.launchpad.people[t]
        members = tt.members_details
        for member in members:
            people.append(member.member.name)

    for member in data["excludes"]["people"]:
        if member in people:
            people.remove(member)

    assignees.insert({"Team": "{0}".format(team),
                      "Members": people})
