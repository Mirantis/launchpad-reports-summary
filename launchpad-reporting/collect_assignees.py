import pymongo
import json

from launchpad.lpdata import LaunchpadData

lpdata = LaunchpadData()
connection = pymongo.Connection()
db = connection["assignees"]

assignees = db.assignees

with open('launchpad/fuel_teams.json') as data_file:
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
    assignees.insert({"Team": "{0}".format(team),
                      "Members": people})
