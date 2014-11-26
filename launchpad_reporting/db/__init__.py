# -*- coding: utf-8 -*-

import pymongo


class DB(object):

    def __init__(self):
        self.connection = pymongo.Connection()
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


db = DB()
