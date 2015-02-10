#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import collections
import json
import os
import time
from functools import wraps

import flask

from flask import (Flask, request, render_template, json as flask_json,
                   redirect, session, url_for)
from launchpadlib.credentials import Credentials, AccessToken
from launchpadlib.uris import LPNET_WEB_ROOT


from launchpad_reporting import sla_reports
from launchpad_reporting.db import db
from launchpad_reporting.launchpad import (LaunchpadClient,
                                           LaunchpadAnonymousClient)
from launchpad_reporting.launchpad.lpdata import (authorization_url,
                                                  SimpleLaunchpad)


path_to_data = "/".join(os.path.abspath(__file__).split('/')[:-1])

with open('{0}/data.json'.format(path_to_data)) as data_file:
    data = json.load(data_file)

with open('{0}/file.json'.format(path_to_data)) as teams_file:
    teams_data = json.load(teams_file, object_pairs_hook=collections.OrderedDict)


launchpad = LaunchpadAnonymousClient()

app = Flask(__name__)
app_config = sla_reports.read_config_file()
app.secret_key = "lei3raighuequic3Pephee8duwohk8"


def print_select(dct, param, val):
    if param not in dct or val not in dct[param]:
        return ""
    return "selected=\"selected\""


def get_report_by_name(name):
    for report in app_config['reports']:
        if report['name'] == name:
            return report

    raise RuntimeError('Can not find report %s!' % name)

def filter(request, bugs):

    filters = {
        'status': request.args.getlist('status'),
        'importance': request.args.getlist('importance'),
        'assignee': request.args.getlist('assignee'),
        'criteria': request.args.getlist('criteria')
    }

    teams_data['Unknown'] = {'unknown': []}

    if 'tab_name' in request.args and request.args['tab_name'] in teams_data:
        filters['assignee'] = teams_data[request.args['tab_name']]


    bugs = launchpad.lpdata.filter_bugs(bugs, filters, teams_data)

    return bugs, filters

KEY_MILESTONE = "6.1"
MILESTONES = db.bugs.milestones.find_one()["Milestone"]
flag = False
user_agents = {}


app.jinja_env.globals.update(print_select=print_select,
                             get_report_by_name=get_report_by_name,
                             app_config=app_config,
                             key_milestone=KEY_MILESTONE)


def get_access_token(credentials):
    global user_agents
    credentials._request_token = AccessToken.from_params(
        session['request_token_parts'])
    request_token_key = credentials._request_token.key
    try:
        credentials.exchange_request_token_for_access_token(LPNET_WEB_ROOT)
    except:
        auth_url = authorization_url(LPNET_WEB_ROOT,
                                     request_token=request_token_key)
        return (True, auth_url, False)
    user_agents[credentials.access_token.key] = LaunchpadClient(credentials)
    session['access_token_parts'] = {
        'oauth_token': credentials.access_token.key,
        'oauth_token_secret': credentials.access_token.secret,
        'lp.context': credentials.access_token.context
    }
    is_authorized = True
    session['is_authorized'] = is_authorized
    del session['request_token_parts']
    return (False, None, is_authorized)


def use_access_token(credentials):
    global user_agents
    if not session['access_token_parts']['oauth_token'] in user_agents:
        credentials.access_token = AccessToken.from_params(
            session['access_token_parts'])
        user_agents[credentials.access_token.key] = LaunchpadClient(credentials)
    is_authorized = True
    session['is_authorized'] = is_authorized
    return (False, None, is_authorized)


def get_and_authorize_request_token(credentials):
    credentials.get_request_token(
        web_root=LPNET_WEB_ROOT)
    request_token_key = credentials._request_token.key
    request_token_secret = credentials._request_token.secret
    request_token_context = credentials._request_token.context
    session['request_token_parts'] = {
        'oauth_token': request_token_key,
        'oauth_token_secret': request_token_secret,
        'lp.context': request_token_context
    }
    auth_url = authorization_url(LPNET_WEB_ROOT,
                                 request_token=request_token_key)
    is_authorized = False
    session['is_authorized'] = is_authorized
    return (True, auth_url, is_authorized)


def process_launchpad_authorization():
    global user_agents
    credentials = Credentials()
    SimpleLaunchpad.set_credentials_consumer(credentials,
                                             "launchpad-reporting-www")
    if 'should_authorize' in session and session['should_authorize']:
        if 'request_token_parts' in session:
            return get_access_token(credentials)
        elif 'access_token_parts' in session:
            return use_access_token(credentials)
        else:
            return get_and_authorize_request_token(credentials)
    else:
        return (False, None, False)



def handle_launchpad_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        should_redirect, lp_url, is_authorized = process_launchpad_authorization()
        if should_redirect:
            return redirect(lp_url)
        try:
            kwargs.update({'is_authorized': is_authorized})
            return f(*args, **kwargs)
        except Exception as e:
            if hasattr(e, "content") and "Expired token" in e.content:
                if 'access_token_parts' in session:
                    del session['access_token_parts']
                should_redirect, lp_url, is_authorized = process_launchpad_authorization()
                print should_redirect, lp_url, is_authorized
                if should_redirect:
                    return redirect(lp_url)
            else:
                raise e

    return decorated


@app.route('/project/<project_name>/bug_table_for_status/<bug_type>/'
           '<milestone_name>/bug_list/')
@handle_launchpad_auth
def bug_list(project_name, bug_type, milestone_name, is_authorized=False):
    project = launchpad.get_project(project_name)
    tags = None

    if 'tags' in request.args:
        tags = request.args['tags'].split(',')
    if bug_type == "New":
        milestone_name = None

    bugs = launchpad.get_bugs(
        project_name=project_name,
        statuses=launchpad.BUG_STATUSES[bug_type],
        milestone_name=milestone_name, tags=tags)

    return render_template("bug_list.html",
                           is_authorized=is_authorized,
                           project=project,
                           bugs=bugs,
                           bug_type=bug_type,
                           milestone_name=milestone_name,
                           selected_bug_table=True,
                           prs=list(db.prs),
                           update_time=launchpad.get_update_time())




@app.route('/project/<project_name>/bug_list_for_sbpr/<milestone_name>/'
           '<bug_type>/<sbpr>')
@handle_launchpad_auth
def bug_list_for_sbpr(project_name, bug_type, milestone_name, sbpr, is_authorized=False):
    subprojects = [sbpr]

    if sbpr == 'all':
        subprojects = list(db.subprs)

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

    return render_template("bug_table_sbpr.html",
                           is_authorized=is_authorized,
                           project=project_name,
                           prs=list(db.prs),
                           bugs=bugs,
                           sbpr=sbpr,
                           milestone_name=milestone_name,
                           milestones=MILESTONES,
                           update_time=launchpad.get_update_time(),
                           bugs_type_to_print=bugs_type_to_print)


@app.route('/project/<project_name>/api/release_chart_trends/'
           '<milestone_name>/get_data')
@handle_launchpad_auth
def bug_report_trends_data(project_name, milestone_name, is_authorized=False):
    data = launchpad.release_chart(
        project_name,
        milestone_name
    ).get_trends_data()

    return flask_json.dumps(data)


@app.route('/project/<project_name>/api/release_chart_incoming_outgoing/'
           '<milestone_name>/get_data')
@handle_launchpad_auth
def bug_report_get_incoming_outgoing_data(project_name, milestone_name, is_authorized=False):
    data = launchpad.release_chart(
        project_name,
        milestone_name
    ).get_incoming_outgoing_data()
    return flask_json.dumps(data)


@app.route('/project/<project_name>/bug_table_for_status/'
           '<bug_type>/<milestone_name>')
@handle_launchpad_auth
def bug_table_for_status(project_name, bug_type, milestone_name, is_authorized=False):
    project = launchpad.get_project(project_name)

    if bug_type == "New":
        milestone_name = None

    return render_template("bug_table.html",
                           is_authorized=is_authorized,
                           project=project,
                           prs=list(db.prs),
                           milestone_name=milestone_name,
                           update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/bug_trends/<milestone_name>/')
@handle_launchpad_auth
def bug_trends(project_name, milestone_name, is_authorized=False):
    project = launchpad.get_project(project_name)

    return render_template("bug_trends.html",
                           is_authorized=is_authorized,
                           project=project,
                           milestone_name=milestone_name,
                           selected_bug_trends=True,
                           prs=list(db.prs),
                           update_time=launchpad.get_update_time())


def milestone_based_report(report):
    @handle_launchpad_auth
    def handle_report(milestone_name, is_authorized):
        user_agent = None
        if is_authorized:
            oauth_token = session['access_token_parts']['oauth_token']
            user_agent = user_agents[oauth_token]
        bugs = sla_reports.get_reports_data(report['name'], ['mos', 'fuel'],
                                            milestone_name, user_agent)

        bugs, filters = filter(request, bugs)

        return flask.render_template(
            "bugs_lifecycle_report.html",
            is_authorized=is_authorized,
            report=report,
            milestone_name=milestone_name,
            milestones=MILESTONES,
            all_bugs=bugs,
            teams=teams_data,
            filters=filters,
        )
    return handle_report


def project_based_report(report):
    @handle_launchpad_auth
    def handle_report(project, is_authorized):
        user_agent = None
        if is_authorized:
            oauth_token = session['access_token_parts']['oauth_token']
            user_agent = user_agents[oauth_token]
        bugs = sla_reports.get_reports_data(report['name'], [project], None, user_agent)

        bugs, filters = filter(request, bugs)

        return flask.render_template(
            "bugs_lifecycle_report.html",
            is_authorized=is_authorized,
            report=report,
            all_bugs=bugs,
            teams=teams_data,
            filters=filters,
        )
    return handle_report


for report in app_config['reports']:
    if report['parameter'] == 'milestone':
        handler = milestone_based_report(report)
        url = '/%s/<milestone_name>' % report['name']
    elif report['parameter'] == 'project':
        handler = project_based_report(report)
        url = '/%s/<project>' % report['name']
    else:
        raise RuntimeError('Invalid report parameter: %s' % report['parameter'])

    app.add_url_rule(url, report['name'], handler)


@app.route('/project/<project_name>/<milestone_name>/project_statistic/<tag>/')
@handle_launchpad_auth
def statistic_for_project_by_milestone_by_tag(project_name, milestone_name,
                                              tag, is_authorized=False):
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

    return render_template("project.html",
                           is_authorized=is_authorized,
                           project=project,
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
@handle_launchpad_auth
def statistic_for_project_by_milestone(project_name, milestone_name, is_authorized=False):
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

    return render_template("project.html",
                           is_authorized=is_authorized,
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
@handle_launchpad_auth
def fuel_plus_mos_overview(milestone_name, is_authorized=False):
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

    return render_template("project_fuelmos.html",
                           is_authorized=is_authorized,
                           milestones=milestones,
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
@handle_launchpad_auth
def project_overview(project_name, is_authorized=False):
    should_redirect, lp_url, is_authorized = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    project_name = project_name.lower()

    if project_name == "fuelplusmos":
        return redirect(
            "/project/fuelplusmos/{0}/".format(KEY_MILESTONE), code=302)

    project = launchpad.get_project(project_name)
    project.display_name = project.display_name.capitalize()
    page_statistic = launchpad.common_statistic_for_project(
        project_name=project_name,
        milestone_name=project.active_milestones,
        tag=None)

    return render_template("project.html",
                           is_authorized=is_authorized,
                           project=project,
                           selected_overview=True,
                           prs=list(db.prs),
                           subprs=list(db.subprs),
                           page_statistic=page_statistic,
                           milestone=[],
                           update_time=launchpad.get_update_time())


@app.route('/project/<global_project_name>/<tag>/')
@handle_launchpad_auth
def mos_project_overview(global_project_name, tag, is_authorized=False):
    global_project_name = global_project_name.lower()
    tag = tag.lower()

    project = launchpad.get_project(global_project_name)
    page_statistic = launchpad.common_statistic_for_project(
        project_name=global_project_name,
        milestone_name=project.active_milestones,
        tag=tag)

    return render_template("project.html",
                           is_authorized=is_authorized,
                           project=project,
                           tag=tag,
                           page_statistic=page_statistic,
                           selected_overview=True,
                           display_subprojects=True,
                           prs=list(db.prs),
                           subprs=list(db.subprs),
                           milestone=[],
                           update_time=launchpad.get_update_time())


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if 'request_token_parts' in session:
        del session['request_token_parts']
    if 'access_token_parts' in session:
        del session['access_token_parts']
    session['should_authorize'] = False
    return redirect(url_for('main_page'))


@app.route('/login', methods=["GET", "POST"])
def login(is_authorized=False):
    session['should_authorize'] = True
    return redirect(url_for('main_page'))


@app.route('/', methods=["GET", "POST"])
@handle_launchpad_auth
def main_page(is_authorized=False):
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

    return render_template("main.html",
                           key_milestone=KEY_MILESTONE,
                           is_authorized=is_authorized,
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

