import flask
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

all_tags = ""
for s in subprs:
    all_tags = all_tags+s+"+"
all_tags = all_tags[:-1]

flag = False

@app.route('/project/<project_name>/bug_table_for_status/<bug_type>/<milestone_name>/bug_list')
def bug_list(project_name, bug_type, milestone_name):
    project = lpdata.get_project(project_name)
    tags = None
    if 'tags' in flask.request.args:
        tags = flask.request.args['tags'].split(',')
    bugs = lpdata.get_bugs(project_name, LaunchpadData.BUG_STATUSES[bug_type], milestone_name, tags)
    return flask.render_template("bug_list.html", project=project, bugs=bugs, bug_type=bug_type, milestone_name=milestone_name, selected_bug_table=True, prs=list(prs), key_milestone=key_milestone,)

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
    return flask.render_template("bug_table.html", project=project, prs=list(prs), key_milestone=key_milestone,)

@app.route('/project/<project_name>/bug_trends/<milestone_name>')
def bug_trends(project_name, milestone_name):
    project = lpdata.get_project(project_name)
    return flask.render_template("bug_trends.html", project=project, milestone_name=milestone_name, selected_bug_trends=True, prs=list(prs), key_milestone=key_milestone,)

@app.route('/project/<project_name>/<milestone_name>/project_statistic/<tag>')
def statistic_for_project_by_milestone_by_tag(project_name, milestone_name, tag):
    display = True
    project = lpdata.get_project(project_name)

    project.display_name = project.display_name.capitalize()

    page_statistic = lpdata.common_statistic_for_project(project_name=project_name,
                                                         tag=tag,
                                                         milestone_name=[milestone_name])
    return flask.render_template("project.html",
                                 project=project,
                                 key_milestone=key_milestone,
                                 selected_overview=True,
                                 display_subprojects=display,
                                 prs=list(prs),
                                 subprs=list(subprs),
                                 page_statistic=page_statistic,
                                 milestone=milestone_name,
                                 flag=True)

@app.route('/project/<project_name>/<milestone_name>/project_statistic/')
def statistic_for_project_by_milestone(project_name, milestone_name):
    display = False
    project = lpdata.get_project(project_name)
    if project_name in ("mos", "fuel"):
        display = True
    project.display_name = project.display_name.capitalize()

    page_statistic = lpdata.common_statistic_for_project(project_name=project_name,
                                                         tag=None,
                                                         milestone_name=[milestone_name])

    return flask.render_template("project.html",
                                 key_milestone=key_milestone,
                                 project=project,
                                 selected_overview=True,
                                 display_subprojects=display,
                                 prs=list(prs),
                                 subprs=list(subprs),
                                 page_statistic=page_statistic,
                                 milestone=milestone_name,
                                 flag=True)

@app.route('/project/fuelplusmos/<milestone_name>')
def fuel_plus_mos_overview(milestone_name):

    milestones = db.milestones.find_one()["Milestone"]

    subprojects = list(subprs)
    page_statistic = dict.fromkeys(subprojects)

    for sbpr in subprojects:
        page_statistic["{0}".format(sbpr)] = dict.fromkeys(["fuel", "mos"])
        for pr in ("fuel", "mos"):
            page_statistic["{0}".format(sbpr)]["{0}".format(pr)] = \
                dict.fromkeys(["done", "total", "high"])

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["done"] = \
            len(lpdata.get_bugs(project_name=pr,
                                statuses=lpdata.BUG_STATUSES["Closed"],
                                milestone_name=milestone_name,
                                tags=[sbpr]))

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["total"] = \
                len(lpdata.get_bugs(project_name=pr,
                                    statuses=lpdata.BUG_STATUSES["All"],
                                    milestone_name=milestone_name,
                                    tags=[sbpr]))

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["high"] = \
            len(lpdata.get_bugs(project_name=pr,
                                statuses=lpdata.BUG_STATUSES["NotDone"],
                                milestone_name=milestone_name,
                                tags=[sbpr],
                                importance=["High", "Critical"]))


    summary_statistic = dict.fromkeys("summary")
    summary_statistic["summary"] = dict.fromkeys(["fuel", "mos"])
    for pr in ("fuel", "mos"):
        summary_statistic["summary"]["{0}".format(pr)] = \
            dict.fromkeys(["done", "total", "high"])

        summary_statistic["summary"]["{0}".format(pr)]["done"] = \
        len(lpdata.get_bugs(project_name=pr,
                            statuses=lpdata.BUG_STATUSES["Closed"],
                            milestone_name=milestone_name,
                            tags=subprojects))

        summary_statistic["summary"]["{0}".format(pr)]["total"] = \
        len(lpdata.get_bugs(project_name=pr,
                            statuses=lpdata.BUG_STATUSES["All"],
                            milestone_name=milestone_name,
                            tags=subprojects))

        summary_statistic["summary"]["{0}".format(pr)]["high"] = \
        len(lpdata.get_bugs(project_name=pr,
                            statuses=lpdata.BUG_STATUSES["Closed"],
                            milestone_name=milestone_name,
                            tags=subprojects,
                            importance=["High", "Critical"]))

    fuel_plus_mos = dict.fromkeys(subprojects)
    for subpr in subprojects:
        fuel_plus_mos["{0}".format(subpr)] = dict.fromkeys(["done",
                                                            "total",
                                                            "high"])

    for subpr in subprojects:
        tag = ["{0}".format(subpr)]
        summary = lpdata.bugs_ids(tag, milestone_name)
        fuel_plus_mos["{0}".format(subpr)]["done"] = summary["done"]
        fuel_plus_mos["{0}".format(subpr)]["total"] = summary["total"]
        fuel_plus_mos["{0}".format(subpr)]["high"] = summary["high"]


    incomplete = dict.fromkeys("fuel", "mos")
    for pr in ("fuel", "mos"):
        incomplete['{0}'.format(pr)] = db['{0}'.format(pr)].find(
            {"$and": [
                {"milestone": "{0}".format(milestone_name)},
                {"tags": {"$in": subprojects}},
                {"status": "Incomplete"}
            ]}).count()

    return flask.render_template("project_fuelmos.html",
                                 milestones=milestones,
                                 key_milestone=key_milestone,
                                 current_milestone=milestone_name,
                                 prs=list(prs),
                                 subprs=list(subprs),
                                 fuel_milestone_id=fuel_milestone_id[milestone_name],
                                 mos_milestone_id=mos_milestone_id[milestone_name],
                                 page_statistic=page_statistic,
                                 summary_statistic=summary_statistic,
                                 fuel_plus_mos=fuel_plus_mos,
                                 all_tags=all_tags,
                                 incomplete=incomplete)

@app.route('/project/<project_name>')
def project_overview(project_name):

    project_name = project_name.lower()

    if project_name == "fuelplusmos":
        return flask.redirect("/project/fuelplusmos/{0}".format(key_milestone),
                              code=302)

    display = False
    project = lpdata.get_project(project_name)
    if project_name in ("mos", "fuel"):
        display = True
    project.display_name = project.display_name.capitalize()

    page_statistic = lpdata.common_statistic_for_project(project_name=project_name,
                                                         milestone_name=project.active_milestones,
                                                         tag=None)

    return flask.render_template("project.html",
                                 project=project,
                                 key_milestone=key_milestone,
                                 selected_overview=True,
                                 display_subprojects=display,
                                 prs=list(prs),
                                 subprs=list(subprs),
                                 page_statistic=page_statistic)

@app.route('/project/<global_project_name>/<param>')
def mos_project_overview(global_project_name, param):

    global_project_name = global_project_name.lower()

    project = lpdata.get_project(global_project_name)
    page_statistic = lpdata.common_statistic_for_project(project_name=global_project_name,
                                                         tag=param,
                                                         milestone_name=project.active_milestones)

    return flask.render_template("project.html",
                                 project=project,
                                 key_milestone=key_milestone,
                                 tag=param,
                                 page_statistic=page_statistic,
                                 selected_overview=True,
                                 display_subprojects=True,
                                 prs=list(prs),
                                 subprs=list(subprs),
                                 flag=True)

@app.route('/')
def main_page():
    global_statistic = dict.fromkeys(prs)
    for pr in global_statistic.keys()[:]:
        types = dict.fromkeys(["total", "critical", "unresolved"])
        types["total"] = db['{0}'.format(pr)].find().count()
        types["critical"] = len(lpdata.get_bugs(project_name=pr,
                                                statuses=["Triaged"],
                                                importance=["Critical"]))
        types["unresolved"] = len(lpdata.get_bugs(
            project_name=pr,
            statuses=lpdata.BUG_STATUSES["NotDone"]))
        global_statistic['{0}'.format(pr)] = types

    return flask.render_template("main.html",
                                 key_milestone=key_milestone,
                                 statistic=global_statistic,
                                 prs=list(prs))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4444, threaded=True, debug=True)