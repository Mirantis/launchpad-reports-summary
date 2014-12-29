# -*- coding: utf-8 -*-

import logging

from launchpad_reporting.launchpad.lpdata import (LaunchpadAnonymousData,
                                                  LaunchpadData)
from launchpad_reporting.launchpad.release_chart import ReleaseChart

from launchpad_reporting.db import db


LOG = logging.getLogger(__name__)


class LaunchpadAnonymousClient(object):

    def __init__(self):
        self.lpdata = LaunchpadAnonymousData(db=db)

    def __getattr__(self, item):
        return getattr(self.lpdata, item)

    def release_chart(self, project_name, milestone_name):
        return ReleaseChart(self, project_name, milestone_name)


class LaunchpadClient(LaunchpadAnonymousClient):

    def __init__(self, credentials):
        self.lpdata = LaunchpadData(db=db, credentials=credentials)
