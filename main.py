#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import collections
import json
import os
import time

import flask
from flask import request

from launchpad_reporting.launchpad import launchpad
from launchpad_reporting.db import db


path_to_data = "/".join(os.path.abspath(__file__).split('/')[:-1])

with open('{0}/data.json'.format(path_to_data)) as data_file:
    data = json.load(data_file)
with open('{0}/file.json'.format(path_to_data)) as teams_file:
    teams_data = json.load(teams_file, object_pairs_hook=collections.OrderedDict)

app = flask.Flask(__name__)


def print_select(dct, param, val):

    if param not in dct or val not in dct[param]:
        return ""

    return "selected=\"selected\""


app.jinja_env.globals.update(print_select=print_select)

key_milestone = "6.0"

flag = False


@app.route('/project/<project_name>/bug_table_for_status/<bug_type>/'
           '<milestone_name>/bug_list/')
def bug_list(project_name, bug_type, milestone_name):
    project = launchpad.get_project(project_name)
    tags = None

    if 'tags' in flask.request.args:
        tags = flask.request.args['tags'].split(',')
    if bug_type == "New":
        milestone_name = None

    bugs = launchpad.get_bugs(
        project_name=project_name,
        statuses=launchpad.BUG_STATUSES[bug_type],
        milestone_name=milestone_name, tags=tags)

    return flask.render_template("bug_list.html",
                                 project=project,
                                 bugs=bugs,
                                 bug_type=bug_type,
                                 milestone_name=milestone_name,
                                 selected_bug_table=True,
                                 prs=list(db.prs),
                                 key_milestone=key_milestone,
                                 update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/bug_list_for_sbpr/<milestone_name>/'
           '<bug_type>/<sbpr>')
def bug_list_for_sbpr(project_name, bug_type, milestone_name, sbpr):
    subprojects = [sbpr]

    if sbpr == 'all':
        subprojects = list(db.subprs)

    milestones = db.bugs.milestones.find_one()["Milestone"]

    bug_importance = []
    bug_statuses = ""
    bugs_type_to_print = ""

    if bug_type == "done":
        bugs_type_to_print = "Closed"
        bug_statuses = "Closed"

    if bug_type == "total":
        bugs_type_to_print = "Total"
        bug_statuses = "All"

    if bug_type == "high":
        bugs_type_to_print = "High and Critical"
        bug_statuses = "NotDone"
        bug_importance = ["High", "Critical"]

    if bug_type == "incomplete":
        bugs_type_to_print = "Incomplete"
        bug_statuses = "Incomplete"

    bugs = list(set(launchpad.get_bugs(project_name=project_name,
                                       statuses=launchpad.
                                       BUG_STATUSES[bug_statuses],
                                       milestone_name=milestone_name,
                                       tags=subprojects,
                                       importance=bug_importance)))

    return flask.render_template("bug_table_sbpr.html",
                                 project=project_name,
                                 prs=list(db.prs),
                                 bugs=bugs,
                                 sbpr=sbpr,
                                 key_milestone=key_milestone,
                                 milestone_name=milestone_name,
                                 milestones=milestones,
                                 update_time=launchpad.get_update_time(),
                                 bugs_type_to_print=bugs_type_to_print)


@app.route("/iso_build/<version>/<iso_number>/<result>")
def iso_build_result(version, iso_number, result):
    data = {"version": version, "iso_number": iso_number,
            "build_date": time.strftime("%d %b %Y %H:%M:%S", time.gmtime()),
            "build_status": result, "tests_results": {}}
    db.mos.images.insert(data)

    need_add = True
    for v in db.mos.images_versions.find():
        if v["version"] == version:
            need_add = False
    if need_add:
        db.mos.images_versions.insert({"version": version})

    return flask.json.dumps({"result": "OK"})


@app.route("/iso_tests/<version>/<iso_number>/<tests_name>/<result>")
def iso_tests_result(version, iso_number, tests_name, result):
    status = "FAIL"

    need_add = True
    for t in db.mos.tests_types.find():
        if t["name"] == tests_name:
            need_add = False
    if need_add:
        db.mos.tests_types.insert({"name": tests_name})

    for image in db.mos.images.find():
        if (image["version"] == version and
                image["iso_number"] == iso_number):
            image["tests_results"][tests_name] = result

            db.mos.images.update(
                {"version": version, "iso_number": iso_number},
                {"$set": {"tests_results": image["tests_results"]}}
            )

            status = "OK"

    return flask.json.dumps({"result": status})


@app.route('/mos_images/<version>/')
def mos_images_status(version):
    images = list(db.mos.images.find())
    tests_types = list(db.mos.tests_types.find())
    images_versions = list(db.mos.images_versions.find())

    return flask.render_template("iso_status.html", version=version,
                                 project="mos_images", images=images,
                                 images_versions=images_versions,
                                 prs=list(db.prs), tests_types=tests_types)


@app.route('/mos_images_auto/<version>/')
def mos_images_status_auto(version):
    images = list(db.mos.images.find())
    tests_types = list(db.mos.tests_types.find())
    images_versions = list(db.mos.images_versions.find())

    return flask.render_template("iso_status_auto.html", version=version,
                                 project="mos_images", images=images,
                                 images_versions=images_versions,
                                 tests_types=tests_types)


@app.route('/project/<project_name>/api/release_chart_trends/'
           '<milestone_name>/get_data')
def bug_report_trends_data(project_name, milestone_name):
    data = launchpad.release_chart(
        project_name,
        milestone_name
    ).get_trends_data()

    return flask.json.dumps(data)


@app.route('/project/<project_name>/api/release_chart_incoming_outgoing/'
           '<milestone_name>/get_data')
def bug_report_get_incotab_nameming_outgoing_data(project_name, milestone_name):
    data = launchpad.release_chart(
        project_name,
        milestone_name
    ).get_incoming_outgoing_data()
    return flask.json.dumps(data)


@app.route('/project/<project_name>/bug_table_for_status/'
           '<bug_type>/<milestone_name>')
def bug_table_for_status(project_name, bug_type, milestone_name):
    project = launchpad.get_project(project_name)

    if bug_type == "New":
        milestone_name = None

    return flask.render_template("bug_table.html",
                                 project=project,
                                 prs=list(db.prs),
                                 key_milestone=key_milestone,
                                 milestone_name=milestone_name,
                                 update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/bug_trends/<milestone_name>/')
def bug_trends(project_name, milestone_name):
    project = launchpatab_named.get_project(project_name)
    return flask.render_template("bug_trends.html",
                                 project=project,
                                 milestone_name=milestone_name,
                                 selected_bug_trends=True,
                                 prs=list(db.prs),
                                 key_milestone=key_milestone,
                                 update_time=launchpad.get_update_time())


@app.route('/project/code_freeze_report/<milestone_name>/')
def code_freeze_report(milestone_name):

    milestones = db.bugs.milestones.find_one()["Milestone"]
    teams = ["Fuel", "Partners", "mos-linux", "mos-openstack", "Unknown"]
    exclude_tags = ["devops", "docs", "fuel-devops", "experimental", "system-tests"]

    filters = {
        'status': request.args.getlist('status'),
        'importance': request.args.getlist('importance'),
        'assignee': request.args.getlist('assignee')
    }

    teams_data['Unknown'] = {'unknown': []}

    if 'tab_name' in request.args and request.args['tab_name'] in teams_data:
        filters['assignee'] = teams_data[request.args['tab_name']]

    bugs = launchpad.code_freeze_statistic(
            milestone=[milestone_name],
            teams=teams,
            exclude_tags=exclude_tags,
            filters=filters,
            teams_data=teams_data)


    return flask.render_template("code_freeze_report.html",
                                 milestones=milestones,
                                 current_milestone=milestone_name,
                                 prs=list(db.prs),
                                 list_teams=teams,
                                 bugs=bugs,
                                 key_milestone=key_milestone,
                                 update_time=launchpad.get_update_time(),
                                 teams=teams_data,
                                 filters=filters)

@app.route('/project/code_freeze_report_csv/<milestone_name>/')
def code_freeze_report_csv(milestone_name):

    milestones = db.bugs.milestones.find_one()["Milestone"]
    teams = ["Fuel", "Partners", "mos-linux", "mos-openstack", "Unknown"]
    exclude_tags = ["devops", "docs", "fuel-devops", "experimental", "system-tests"]

    filters = {
        'status': request.args.getlist('status'),
        'importance': request.args.getlist('importance'),
        'assignee': request.args.getlist('assignee')
    }

    teams_data['Unknown'] = {'unknown': []}

    if 'tab_name' in request.args and request.args['tab_name'] in teams_data:
        filters['assignee'] = teams_data[request.args['tab_name']]

    bugs = launchpad.code_freeze_statistic(
            milestone=[milestone_name],
            teams=teams,
            exclude_tags=exclude_tags,
            filters=filters,
            teams_data=teams_data)


    resp = flask.render_template("code_freeze_report.csv",
                                 milestones=milestones,
                                 current_milestone=milestone_name,
                                 prs=list(db.prs),
                                 list_teams=teams,
                                 bugs=bugs,
                                 key_milestone=key_milestone,
                                 update_time=launchpad.get_update_time(),
                                 teams=teams_data,
                                 filters=filters)

    resp = flask.make_response(resp)

    resp.headers["Content-Type"] = "text/plain"

    return resp





@app.route('/project/<project_name>/<milestone_name>/project_statistic/<tag>/')
def statistic_for_project_by_milestone_by_tag(project_name, milestone_name,
                                              tag):

    display = True
    project = launchpad.get_project(project_name)

    project.display_name = project.display_name.capitalize()

    page_statistic = launchpad.common_statistic_for_project(
        project_name=project_name,
        tag=tag,
        milestone_name=[milestone_name])

    milestone = dict.fromkeys(["name", "id"])
    milestone["name"] = milestone_name
    milestone["id"] = data[project_name][milestone_name]
    if project_name == "fuel":
        milestone["id"] = data[project_name][milestone_name]

    return flask.render_template("project.html",
                                 project=project,
                                 key_milestone=key_milestone,
                                 selected_overview=True,
                                 display_subprojects=display,
                                 prs=list(db.prs),
                                 subprs=list(db.subprs),
                                 page_statistic=page_statistic,
                                 milestone=milestone,
                                 flag=True,
                                 tag=tag,
                                 update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/<milestone_name>/project_statistic/')
def statistic_for_project_by_milestone(project_name, milestone_name):
    display = False
    project = launchpad.get_project(project_name)
    if project_name in ("mos", "fuel"):
        display = True
    project.display_name = project.display_name.capitalize()

    page_statistic = launchpad.common_statistic_for_project(
        project_name=project_name,
        tag=None,
        milestone_name=[milestone_name])

    milestone = dict.fromkeys(["name", "id"])
    milestone["name"] = milestone_name
    milestone["id"] = data[project_name][milestone_name]
    if project_name == "fuel":
        milestone["id"] = data[project_name][milestone_name]

    return flask.render_template("project.html",
                                 key_milestone=key_milestone,
                                 project=project,
                                 selected_overview=True,
                                 display_subprojects=display,
                                 prs=list(db.prs),
                                 subprs=list(db.subprs),
                                 page_statistic=page_statistic,
                                 milestone=milestone,
                                 flag=True,
                                 update_time=launchpad.get_update_time())


@app.route('/project/fuelplusmos/<milestone_name>/')
def fuel_plus_mos_overview(milestone_name):
    milestones = db.bugs.milestones.find_one()["Milestone"]

    subprojects = list(db.subprs)
    page_statistic = dict.fromkeys(subprojects)

    for sbpr in subprojects:
        page_statistic["{0}".format(sbpr)] = dict.fromkeys(["fuel", "mos"])
        for pr in ("fuel", "mos"):
            page_statistic["{0}".format(sbpr)]["{0}".format(pr)] = \
                dict.fromkeys(["done", "total", "high"])

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["done"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["Closed"],
                    milestone_name=milestone_name,
                    tags=[sbpr]))

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["total"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["All"],
                    milestone_name=milestone_name,
                    tags=[sbpr]))

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["high"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["NotDone"],
                    milestone_name=milestone_name,
                    tags=[sbpr],
                    importance=["High", "Critical"]))

    fuel_plus_mos = dict.fromkeys(subprojects)
    for subpr in subprojects:
        fuel_plus_mos["{0}".format(subpr)] = dict.fromkeys(["done",
                                                            "total",
                                                            "high"])
    for subpr in subprojects:
        tag = ["{0}".format(subpr)]
        summary = launchpad.bugs_ids(tag, milestone_name)
        fuel_plus_mos["{0}".format(subpr)]["done"] = summary["done"]
        fuel_plus_mos["{0}".format(subpr)]["total"] = summary["total"]
        fuel_plus_mos["{0}".format(subpr)]["high"] = summary["high"]

    summary_statistic = dict.fromkeys("summary")
    summary_statistic["summary"] = dict.fromkeys(["tags", "others"])
    for criterion in ["tags", "others"]:
        summary_statistic["summary"][criterion] = dict.fromkeys(
            ["fuel", "mos", "fuel_mos"])

    for criterion in ["tags", "others"]:

        if criterion == "others":
            condition = True
        else:
            condition = False

        for pr in ("fuel", "mos"):
            summary_statistic["summary"][criterion]["{0}".format(pr)] = \
                dict.fromkeys(["done", "total", "high"])

            summary_statistic[
                "summary"][criterion]["{0}".format(pr)]["done"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["Closed"],
                    milestone_name=milestone_name,
                    tags=subprojects,
                    condition=condition))

            summary_statistic[
                "summary"][criterion]["{0}".format(pr)]["total"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["All"],
                    milestone_name=milestone_name,
                    tags=subprojects,
                    condition=condition))

            summary_statistic[
                "summary"][criterion]["{0}".format(pr)]["high"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["NotDone"],
                    milestone_name=milestone_name,
                    tags=subprojects,
                    importance=["High", "Critical"],
                    condition=condition))

    for criterion in ["tags", "others"]:
        summary_statistic["summary"][criterion]["fuel_mos"] = \
            dict.fromkeys(["done", "total", "high"])
        for state in ["done", "total", "high"]:
            summary_statistic[
                "summary"][criterion]["fuel_mos"]["{0}".format(state)] = 0

    for state in ["done", "total", "high"]:
        for subpr in subprojects:
            summary_statistic[
                "summary"]["tags"]["fuel_mos"]["{0}".format(state)] +=\
                fuel_plus_mos["{0}".format(subpr)]["{0}".format(state)]

        summary_statistic[
            "summary"]["others"]["fuel_mos"]["{0}".format(state)] = \
            summary_statistic[
                "summary"]["others"]["fuel"]["{0}".format(state)] + \
            summary_statistic["summary"]["others"]["mos"]["{0}".format(state)]

    incomplete = dict.fromkeys("fuel", "mos")
    for pr in ("fuel", "mos"):
        incomplete['{0}'.format(pr)] = \
            len(launchpad.get_bugs(
                project_name=pr,
                statuses=["Incomplete"],
                milestone_name=milestone_name,
                tags=subprojects))

    return flask.render_template("project_fuelmos.html",
                                 milestones=milestones,
                                 key_milestone=key_milestone,
                                 current_milestone=milestone_name,
                                 prs=list(db.prs),
                                 subprs=list(db.subprs),
                                 fuel_milestone_id=data["fuel"][
                                     milestone_name],
                                 mos_milestone_id=data["mos"][milestone_name],
                                 page_statistic=page_statistic,
                                 summary_statistic=summary_statistic,
                                 fuel_plus_mos=fuel_plus_mos,
                                 all_tags="+".join(db.subprs),
                                 incomplete=incomplete,
                                 update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/')
def project_overview(project_name):

    project_name = project_name.lower()

    if project_name == "fuelplusmos":
        return flask.redirect(
            "/project/fuelplusmos/{0}/".format(key_milestone), code=302)

    if project_name == "code_freeze_report":
        return flask.redirect(
            "/project/code_freeze_report/{0}/".format(key_milestone),
            code=302)

    project = launchpad.get_project(project_name)
    project.display_name = project.display_name.capitalize()
    page_statistic = launchpad.common_statistic_for_project(
        project_name=project_name,
        milestone_name=project.active_milestones,
        tag=None)

    return flask.render_template("project.html",
                                 project=project,
                                 key_milestone=key_milestone,
                                 selected_overview=True,
                                 prs=list(db.prs),
                                 subprs=list(db.subprs),
                                 page_statistic=page_statistic,
                                 milestone=[],
                                 update_time=launchpad.get_update_time())


@app.route('/project/<global_project_name>/<tag>/')
def mos_project_overview(global_project_name, tag):

    global_project_name = global_project_name.lower()
    tag = tag.lower()

    project = launchpad.get_project(global_project_name)
    page_statistic = launchpad.common_statistic_for_project(
        project_name=global_project_name,
        milestone_name=project.active_milestones,
        tag=tag)

    return flask.render_template("project.html",
                                 project=project,
                                 key_milestone=key_milestone,
                                 tag=tag,
                                 page_statistic=page_statistic,
                                 selected_overview=True,
                                 display_subprojects=True,
                                 prs=list(db.prs),
                                 subprs=list(db.subprs),
                                 milestone=[],
                                 update_time=launchpad.get_update_time())


@app.route('/')
def main_page():
    global_statistic = dict.fromkeys(db.prs)
    for pr in global_statistic.keys()[:]:
        types = dict.fromkeys(["total", "critical", "unresolved"])
        types["total"] = len(launchpad.get_bugs(
            project_name=pr, statuses=launchpad.BUG_STATUSES["All"]))
        types["critical"] = len(launchpad.get_bugs(
            project_name=pr,
            statuses=launchpad.BUG_STATUSES["NotDone"],
            importance=["Critical"]))
        types["unresolved"] = len(launchpad.get_bugs(
            project_name=pr,
            statuses=launchpad.BUG_STATUSES["NotDone"]))
        global_statistic['{0}'.format(pr)] = types

    return flask.render_template("main.html",
                                 key_milestone=key_milestone,
                                 statistic=global_statistic,
                                 prs=list(db.prs),
                                 update_time=launchpad.get_update_time())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="action", help='actions'
    )
    run_parser = subparsers.add_parser(
        'run', help='run application locally'
    )
    run_parser.add_argument(
        '-p', '--port', dest='port', action='store', type=str,
        help='application port', default='80'
    )
    run_parser.add_argument(
        '-H', '--host', dest='host', action='store', type=str,
        help='application host', default='0.0.0.0'
    )

    params, args = parser.parse_known_args()
    app.run(
        debug=True,
        host=params.host,
        port=int(params.port),
        use_reloader=True,
        threaded=True
    )

