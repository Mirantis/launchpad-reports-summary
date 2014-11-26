# -*- coding: utf-8 -*-

import logging

from launchpad_reporting.launchpad.lpdata import LaunchpadData
from launchpad_reporting.launchpad.release_chart import ReleaseChart

from launchpad_reporting.db import db


LOG = logging.getLogger(__name__)


class LaunchpadClient(object):

    def __init__(self):
        self.lpdata = LaunchpadData(db=db)

    def __getattr__(self, item):
        return getattr(self.lpdata, item)

    def release_chart(self, project_name, milestone_name):
        return ReleaseChart(self, project_name, milestone_name)


launchpad = LaunchpadClient()
