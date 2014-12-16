# -*- coding: utf-8 -*-

import os
import json
import pymongo


class DB(object):

    def __init__(self, host="0.0.0.0", port=27017):
        self.connection = pymongo.Connection(host=host, port=port)
        self.bugs = self.connection["bugs"]
        self.assignees = self.connection["assignees"]
        self.mos = self.connection["mos"]
        self.main_tab = self.bugs.main_page
        self.project_tab = self.bugs.project_page

        project = self.bugs.projects.find_one()
        if project:
            self.prs = project["Project"]

        subproject = self.bugs.subprojects.find_one()
        if subproject:
            self.subprs = self.bugs.subprojects.find_one()["Subproject"]

credentials = None
path_to_data = "/".join(os.path.abspath(__file__).split('/')[:-3])
with open('{0}/db.json'.format(path_to_data)) as data_file:
    credentials = json.load(data_file)

db = DB(host=credentials['mongodb']['host'])
