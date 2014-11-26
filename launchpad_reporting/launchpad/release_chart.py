# -*- coding: utf-8 -*-

import datetime

from collections import OrderedDict
from collections import defaultdict
from bisect import bisect_left

import pytz

from launchpad_reporting.launchpad.lpdata import LaunchpadData


class ReleaseChart(object):

    def __init__(self, lpdata, project_name, milestone_name):
        self.bugs = []
        for status in LaunchpadData.BUG_STATUSES:
            self.bugs += lpdata.get_bugs(project_name,
                                         LaunchpadData.BUG_STATUSES[status],
                                         milestone_name)

    def get_trends_data(self):

        # the chart will span until tomorrow
        window_end = datetime.datetime.now(pytz.utc) + datetime.timedelta(
            days=1)

        # add chart series in order from bottom to top
        data = OrderedDict()
        data["Verified"] = []
        data["Resolved"] = []
        data["In Progress"] = []
        data["Open"] = []
        data["Incomplete"] = []

        # all dates
        all_dates = set()

        # process each bug and its events
        for b in self.bugs:
            events = b.get_status_changes()
            events.append({"date": window_end, "type": "N/A"})
            for i in range(0, len(events) - 1):
                e1 = events[i]
                e2 = events[i + 1]

                t = e1["type"]
                d1 = e1["date"].replace(tzinfo=None)
                d2 = e2["date"].replace(tzinfo=None)

                if d1 <= d2:
                    d1 = d1.replace(hour=0, minute=0, second=0, microsecond=0)
                    d2 = d2.replace(hour=0, minute=0, second=0, microsecond=0)

                    data[t].append({"date": d1, "num": 1})
                    data[t].append({"date": d2, "num": -1})
                    all_dates.add(d1)
                    all_dates.add(d2)

        # create the list of all sorted dates
        all_dates_sorted = sorted(all_dates)
        n = len(all_dates_sorted)

        # process each data item and construct chart
        d3_start = datetime.datetime(1970, 1, 1, 0, 0, 0, 0, pytz.utc)

        chart = []
        for t in data:
            events = sorted(data[t], key=lambda d: (d['date'], -d['num']))

            # for each date, mark result in global list with dates
            all_dates_values = [None] * n
            bug_count = 0
            for e in events:
                bug_count += e["num"]
                idx = bisect_left(all_dates_sorted, e["date"])
                if not all_dates_sorted[idx] == e["date"]:
                    raise ValueError(
                        "Date not found in array using binary search")
                all_dates_values[idx] = bug_count

            # process all global dates
            prev = 0
            for idx in range(0, n):
                if all_dates_values[idx] is not None:
                    prev = all_dates_values[idx]
                    break

            for idx in range(0, n):
                if all_dates_values[idx] is None:
                    all_dates_values[idx] = prev
                else:
                    prev = all_dates_values[idx]

            # create series for the chart
            # (except for the last point, which has all zeroes)
            values = []
            for idx in range(0, n - 1):
                chart_seconds = (all_dates_sorted[idx].replace(
                    tzinfo=None) - d3_start.replace(
                    tzinfo=None)).total_seconds() * 1000.0
                values.append([int(chart_seconds), all_dates_values[idx]])
            chart.append({'key': t, 'values': values})

        return chart

    def get_incoming_outgoing_data(self):

        # the chart will span until tomorrow
        window_end = datetime.datetime.now(pytz.utc) + datetime.timedelta(
            days=1)

        # add chart series in order from bottom to top
        data = OrderedDict()
        data["Incoming"] = defaultdict(int)
        data["Outgoing"] = defaultdict(int)

        # all dates
        all_dates = set()

        # process each bug and its events
        for b in self.bugs:
            for e in b.get_status_changes():
                # get the date for monday
                date = e["date"] - datetime.timedelta(days=e["date"].weekday())
                date = date.replace(hour=0, minute=0, second=0, microsecond=0)

                # process incoming and outgoing bugs
                if e["type"] == "Open":
                    data["Incoming"][date] += 1
                    all_dates.add(date)
                elif e["type"] == "Resolved":
                    data["Outgoing"][date] += 1
                    all_dates.add(date)

        # create the list of all sorted dates
        all_dates_sorted = sorted(all_dates)
        n = len(all_dates_sorted)

        # process each data item and construct chart
        d3_start = datetime.datetime(1970, 1, 1, 0, 0, 0, 0, pytz.utc)

        chart = []
        for t in data:
            # for each date, mark result in global list with dates
            all_dates_values = [None] * n
            for idx in range(0, n):
                date = all_dates_sorted[idx]
                all_dates_values[idx] = data[t][date]

            # create series for the chart
            values = []
            for idx in range(0, n):
                chart_seconds = (all_dates_sorted[idx].replace(
                    tzinfo=None) - d3_start.replace(
                    tzinfo=None)).total_seconds() * 1000.0
                values.append([int(chart_seconds), all_dates_values[idx]])
            chart.append({'key': t, 'values': values})

        return chart
