
import requests, flask
import pymongo
from launchpad.release_chart import ReleaseChart
from launchpad.lpdata import LaunchpadData



app = flask.Flask(__name__)
lpdata = LaunchpadData()

connection = pymongo.Connection()
db = connection["bugs"]
main_tab = db.main_page
project_tab = db.project_page

prs = db.projects.find_one()["Project"]
subprs = db.subprojects.find_one()["Subproject"]

fuel_milestone_id = {"4.1.2": "66156",
                    "5.1.1": "67221",
                    "5.0.2": "66454",
                    "5.1": "63962",
                    "6.0": "66011"}

mos_milestone_id = {"4.1.2": "66304",
                    "5.1.1": "67222",
                    "5.0.2": "66616",
                    "5.1": "66306",
                    "6.0": "66307"}

key_milestone = "5.1"

@app.route('/project/<project_name>/bug_table_for_status/<bug_type>/<milestone_name>/bug_list')
def bug_list(project_name, bug_type, milestone_name):
    project = lpdata.get_project(project_name)
    tags = None
    if 'tags' in flask.request.args:
        tags = flask.request.args['tags'].split(',')
    bugs = lpdata.get_bugs(project_name, LaunchpadData.BUG_STATUSES[bug_type], milestone_name, tags)
    return flask.render_template("bug_list.html", project=project, bugs=bugs, bug_type=bug_type, milestone_name=milestone_name, selected_bug_table=True, prs=list(prs))

@app.route('/project/<project_name>/api/release_chart_trends/<milestone_name>/get_data')
def bug_report_trends_data(project_name, milestone_name):
    data = ReleaseChart(lpdata, project_name, milestone_name).get_trends_data()
    return flask.json.dumps(data)

@app.route('/project/<project_name>/api/release_chart_incoming_outgoing/<milestone_name>/get_data')
def bug_report_get_incoming_outgoing_data(project_name, milestone_name):
    data = ReleaseChart(lpdata, project_name, milestone_name).get_incoming_outgoing_data()
    return flask.json.dumps(data)

@app.route('/project/<project_name>/bug_table_for_status/<bug_type>/<milestone_name>')
def bug_table_for_status(project_name, bug_type, milestone_name):
    project = lpdata.get_project(project_name)
    return flask.render_template("bug_table.html", project=project, prs=list(prs))

@app.route('/project/<project_name>/bug_trends/<milestone_name>')
def bug_trends(project_name, milestone_name):
    project = lpdata.get_project(project_name)
    return flask.render_template("bug_trends.html", project=project, milestone_name=milestone_name, selected_bug_trends=True, prs=list(prs))


@app.route('/project/<project_name>')
def project_overview(project_name):

    if project_name == "fuelplusmos":
        milestones = db.milestones.find_one()["Milestone"]

        subprojects = list(subprs)
        page_statistic = dict.fromkeys(subprojects)

        for sbpr in subprojects:
            page_statistic["{0}".format(sbpr)] = dict.fromkeys(["FUEL", "MOS"])
            for pr in ("FUEL", "MOS"):
                page_statistic["{0}".format(sbpr)]["{0}".format(pr)] = \
                    dict.fromkeys(["done", "total", "high"])

                page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["done"] = \
                    db['{0}'.format(pr)].find(
                        {"$and": [
                            {"milestone": "{0}".format(key_milestone)},
                            {"tags": "{0}".format(sbpr)},
                            {"status": {"$in": lpdata.BUG_STATUSES["Closed"]}}
                        ]}).count()

                page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["total"] = \
                    db['{0}'.format(pr)].find(
                        {"$and": [
                            {"milestone": "{0}".format(key_milestone)},
                            {"tags": "{0}".format(sbpr)},
                            {"status": {"$in": lpdata.BUG_STATUSES["All"]}}
                        ]}).count()

                page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["high"] = \
                    db['{0}'.format(pr)].find(
                        {"$and": [
                            {"milestone": "{0}".format(key_milestone)},
                            {"tags": "{0}".format(sbpr)},
                            {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}},
                            {"importance": {"$in": ["High", "Critical"]}}
                        ]}).count()

        summary_statistic = dict.fromkeys("summary")
        summary_statistic["summary"] = dict.fromkeys(["FUEL", "MOS"])
        for pr in ("FUEL", "MOS"):
            summary_statistic["summary"]["{0}".format(pr)] = \
                dict.fromkeys(["done", "total", "high"])

            summary_statistic["summary"]["{0}".format(pr)]["done"] = \
                db['{0}'.format(pr)].find(
                    {"$and": [
                        {"milestone": "{0}".format(key_milestone)},
                        {"tags": {"$in": subprojects}},
                        {"status": {"$in": lpdata.BUG_STATUSES["Closed"]}}
                    ]}).count()

            summary_statistic["summary"]["{0}".format(pr)]["total"] = \
                db['{0}'.format(pr)].find(
                    {"$and": [
                        {"milestone": "{0}".format(key_milestone)},
                        {"tags": {"$in": subprojects}},
                        {"status": {"$in": lpdata.BUG_STATUSES["All"]}}
                    ]}).count()

            summary_statistic["summary"]["{0}".format(pr)]["high"] = \
                db['{0}'.format(pr)].find(
                    {"$and": [
                        {"milestone": "{0}".format(key_milestone)},
                        {"tags": {"$in": subprojects}},
                        {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}},
                        {"importance": {"$in": ["High", "Critical"]}}
                    ]}).count()

        fuel_plus_mos = dict.fromkeys(subprojects)
        for subpr in subprojects:
            fuel_plus_mos["{0}".format(subpr)] = dict.fromkeys(["done",
                                                                "total",
                                                                "high"])

        for subpr in subprojects:
            tag = ["{0}".format(subpr)]
            summary = lpdata.bugs_ids(tag,key_milestone)
            fuel_plus_mos["{0}".format(subpr)]["done"] = summary["done"]
            fuel_plus_mos["{0}".format(subpr)]["total"] = summary["total"]
            fuel_plus_mos["{0}".format(subpr)]["high"] = summary["high"]


        return flask.render_template("project_fuelmos.html",
                                     milestones=milestones,
                                     current_milestone=key_milestone,
                                     prs=list(prs),
                                     subprs=subprojects,
                                     page_statistic=page_statistic,
                                     summary_statistic=summary_statistic,
                                     fuel_milestone_id=
                                     fuel_milestone_id[key_milestone],
                                     mos_milestone_id=
                                     mos_milestone_id[key_milestone],
                                     fuel_plus_mos=fuel_plus_mos)

    display = False
    project = lpdata.get_project(project_name)
    if project_name in ("mos", "fuel"):
        display = True
    project.display_name = project.display_name.capitalize()

    page_statistic = dict.fromkeys(["total",
                                   "critical",
                                   "new_for_week",
                                   "fixed_for_week",
                                   "new_for_month"
                                   "fixed_for_month",
                                   "unresolved"])

    page_statistic["total"] = db['{0}'.format(project_name)].count()
    page_statistic["critical"] = db['{0}'.format(project_name)].find(
        {"$and": [{"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}},
        {"importance": "Critical"}]}).count()
    page_statistic["unresolved"] = db['{0}'.format(project_name)].find(
        {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}}).count()
    page_statistic["new_for_week"] = db['{0}'.format(project_name)].find(
        {"created less than week": {"$ne": False}}).count()
    page_statistic["fixed_for_week"] = db['{0}'.format(project_name)].find(
        {"fixed less than week": {"$ne": False}}).count()
    page_statistic["new_for_month"] = db['{0}'.format(project_name)].find(
        {"created less than month": {"$ne": False}}).count()
    page_statistic["fixed_for_month"] = db['{0}'.format(project_name)].find(
        {"fixed less than month": {"$ne": False}}).count()

    return flask.render_template("project.html",
                                 project=project,
                                 selected_overview=True,
                                 display_subprojects=display,
                                 prs=list(prs),
                                 subprs=list(subprs),
                                 page_statistic=page_statistic)

@app.route('/project/<global_project_name>/<param>')
def mos_project_overview(global_project_name, param):
    if global_project_name == "fuelplusmos":
        milestones = db.milestones.find_one()["Milestone"]

        subprojects = list(subprs)
        page_statistic = dict.fromkeys(subprojects)

        for sbpr in subprojects:
            page_statistic["{0}".format(sbpr)] = dict.fromkeys(["FUEL", "MOS"])
            for pr in ("FUEL", "MOS"):
                page_statistic["{0}".format(sbpr)]["{0}".format(pr)] = \
                    dict.fromkeys(["done", "total", "high"])

                page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["done"] = \
                    db['{0}'.format(pr)].find(
                        {"$and": [
                            {"milestone": "{0}".format(param)},
                            {"tags": "{0}".format(sbpr)},
                            {"status": {"$in": lpdata.BUG_STATUSES["Closed"]}}
                        ]}).count()

                page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["total"] = \
                    db['{0}'.format(pr)].find(
                        {"$and": [
                            {"milestone": "{0}".format(param)},
                            {"tags": "{0}".format(sbpr)},
                            {"status": {"$in": lpdata.BUG_STATUSES["All"]}}
                        ]}).count()

                page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["high"] = \
                    db['{0}'.format(pr)].find(
                        {"$and": [
                            {"milestone": "{0}".format(param)},
                            {"tags": "{0}".format(sbpr)},
                            {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}},
                            {"importance": {"$in": ["High", "Critical"]}}
                        ]}).count()

        summary_statistic = dict.fromkeys("summary")
        summary_statistic["summary"] = dict.fromkeys(["FUEL", "MOS"])
        for pr in ("FUEL", "MOS"):
            summary_statistic["summary"]["{0}".format(pr)] = \
                dict.fromkeys(["done", "total", "high"])

            summary_statistic["summary"]["{0}".format(pr)]["done"] = \
                db['{0}'.format(pr)].find(
                    {"$and": [
                        {"milestone": "{0}".format(param)},
                        {"tags": {"$in": subprojects}},
                        {"status": {"$in": lpdata.BUG_STATUSES["Closed"]}}
                    ]}).count()

            summary_statistic["summary"]["{0}".format(pr)]["total"] = \
                db['{0}'.format(pr)].find(
                    {"$and": [
                        {"milestone": "{0}".format(param)},
                        {"tags": {"$in": subprojects}},
                        {"status": {"$in": lpdata.BUG_STATUSES["All"]}}
                    ]}).count()

            summary_statistic["summary"]["{0}".format(pr)]["high"] = \
                db['{0}'.format(pr)].find(
                    {"$and": [
                        {"milestone": "{0}".format(param)},
                        {"tags": {"$in": subprojects}},
                        {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}},
                        {"importance": {"$in": ["High", "Critical"]}}
                    ]}).count()

        fuel_plus_mos = dict.fromkeys(subprojects)
        for subpr in subprojects:
            fuel_plus_mos["{0}".format(subpr)] = dict.fromkeys(["done",
                                                                "total",
                                                                "high"])

        for subpr in subprojects:
            tag = ["{0}".format(subpr)]
            summary = lpdata.bugs_ids(tag, param)
            fuel_plus_mos["{0}".format(subpr)]["done"] = summary["done"]
            fuel_plus_mos["{0}".format(subpr)]["total"] = summary["total"]
            fuel_plus_mos["{0}".format(subpr)]["high"] = summary["high"]

        return flask.render_template("project_fuelmos.html",
                                     milestones=milestones,
                                     current_milestone=param,
                                     prs=list(prs),
                                     subprs=list(subprs),
                                     fuel_milestone_id=fuel_milestone_id[param],
                                     mos_milestone_id=mos_milestone_id[param],
                                     page_statistic=page_statistic,
                                     summary_statistic=summary_statistic,
                                     fuel_plus_mos=fuel_plus_mos)

    global_project_name = global_project_name.upper()
    project = lpdata.get_project(global_project_name)
    page_statistic = dict.fromkeys(["total",
                                   "critical",
                                   "new_for_week",
                                   "fixed_for_week",
                                   "new_for_month"
                                   "fixed_for_month",
                                   "unresolved"])

    page_statistic["total"] = db['{0}'.format(global_project_name)].\
        find({"tags": "{0}".format(param)}).count()
    page_statistic["critical"] = db['{0}'.format(global_project_name)].find(
        {"$and": [{"tags": "{0}".format(param)},
                  {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}},
                  {"importance": "Critical"}]}).count()
    page_statistic["unresolved"] = db['{0}'.format(global_project_name)].find(
        {"$and": [{"tags": "{0}".format(param)},
                  {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}}]}).count()
    page_statistic["new_for_week"] = db['{0}'.format(global_project_name)].find(
        {"$and": [{"tags": "{0}".format(param)},
                  {"created less than week": {"$ne": False}}]}).count()
    page_statistic["fixed_for_week"] = db['{0}'.format(global_project_name)].find(
        {"$and": [{"tags": "{0}".format(param)},
                  {"fixed less than week": {"$ne": False}}]}).count()
    page_statistic["new_for_month"] = db['{0}'.format(global_project_name)].find(
        {"$and": [{"tags": "{0}".format(param)},
                  {"created less than month": {"$ne": False}}]}).count()
    page_statistic["fixed_for_month"] = db['{0}'.format(global_project_name)].find(
        {"$and": [{"tags": "{0}".format(param)},
                  {"fixed less than month": {"$ne": False}}]}).count()

    return flask.render_template("project.html",
                                 project=project,
                                 tag=param,
                                 page_statistic=page_statistic,
                                 selected_overview=True,
                                 display_subprojects=True,
                                 prs=list(prs),
                                 subprs=list(subprs))

@app.route('/add_project')
def add_page():
    return flask.render_template("add_project.html")

@app.route('/')
def main_page():
    global_statistic = dict.fromkeys(prs)
    for pr in global_statistic.keys()[:]:
        types = dict.fromkeys(["total", "critical", "unresolved"])
        types["total"] = db['{0}'.format(pr)].count()
        types["critical"] = db['{0}'.format(pr)].find(
            {"$and": [{"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}},
                      {"importance": "Critical"}]}).count()
        types["unresolved"] = db['{0}'.format(pr)].find(
            {"status": {"$in": lpdata.BUG_STATUSES["NotDone"]}}).count()
        global_statistic['{0}'.format(pr)] = types

    return flask.render_template("main.html",
                                 statistic=global_statistic,
                                 prs=list(prs))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4444, threaded=True, debug=True)
