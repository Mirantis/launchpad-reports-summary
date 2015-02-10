import itertools
import yaml

import pymongo

from launchpad.bug import Bug
from db import db
import criterias as criterias_realization

TEAMS = ["Fuel", "Partners", "mos-linux", "mos-openstack", "Unknown"]

BUG_IMPORTANCE = ["Essential", "Critical", "High", "Medium",
                  "Low", "Wishlist", "Unknown", "Undecided"]

BUG_STATUSES = ["New", "Incomplete", "Invalid", "Won't Fix", "Confirmed",
                "Triaged", "In Progress", "Opinion", "Expired"]

CUSTOMER_FOUND_TAG = "customer-found"


def read_config_file(config_path='launchpad_reporting/config/sample.yaml'):
    with open(config_path, 'r') as stream:
        return yaml.load(stream)


def get_team_members(team):
    """Get all members of the team from DB."""
    connection = pymongo.Connection()
    db_assignees = connection["assignees"]

    # Originally this was something like:
    #
    # result = []
    # for b in db_assignees.assignees.find({"Team": team}):
    #     result.extend(b["Members"])
    # return result

    return db_assignees.assignees.find({"Team": team})[0]['Members']


def get_criteria_by_name(criteria_name):
    conf_criterias = read_config_file()['criterias']
    if criteria_name not in [_['name'] for _ in conf_criterias]:
        raise ValueError("There is no %r section in 'criterias' config "
                         "section" % criteria_name)

    return [cr for cr in conf_criterias if cr['name'] == criteria_name][0]


def get_criteria_implementation(config_criteria, milestone_name):
    """Get implementation of the criteria, based on config.

    This function checks for config criteria_name in config['criterias'],
    gets class - realization of this criteria - and returns an instance
    of this class.
    """

    criteria = get_criteria_by_name(config_criteria['name'])
    class_name = criteria['implementation'].split('.')[-1]
    try:
        ImplClass = getattr(criterias_realization, class_name)
    except AttributeError:
        raise ValueError("There is no implementation for %r class in "
                         "'criterias' file " % class_name)

    if 'config-override' not in config_criteria:
        # there is no config values to override, so we use defaut valuse
        kwargs = {conf['name']: conf['default']
                  for conf in criteria.get('config', [])}
    else:
        kwargs = {}
        for conf in criteria.get('config', []):
            override_name = "{0}_{1}".format(milestone_name, conf['name'])
            if override_name in config_criteria['config-override']:
                kwargs[conf['name']] = config_criteria['config-override'][override_name]
            else:
                kwargs[conf['name']] = conf['default']

    return ImplClass(**kwargs)


def get_criteria_description(criterias, milestone_name):
    """Get implementation of the criteria, based on config.

    This function checks for config criteria_name in config['criterias'],
    gets class - realization of this criteria - and returns an instance
    of this class.
    """

    description = ""
    for config_criteria in criterias:
        criteria = get_criteria_by_name(config_criteria['name'])

        if 'config-override' not in config_criteria:
            kwargs = {conf.get("text", conf['name']): conf['default']
                      for conf in criteria.get('config', [])}
        else:
            kwargs = {}
            for conf in criteria.get('config', []):
                override_name = "{0}_{1}".format(milestone_name, conf['name'])
                detailed_name = conf.get("text", conf['name'])
                if override_name in config_criteria['config-override']:
                    kwargs[detailed_name] = config_criteria['config-override'][override_name]
                else:
                    kwargs[detailed_name] = conf['default']

        criteria_name = criteria.get('text', criteria['name'])
        description += "%s (%s):\n" % (criteria_name, criteria['name'])
        description += "\n".join("\t%s: %s" % (k, v) for (k, v) in kwargs.items())
        description += "\n"

    return description.strip()


def filter_bugs_by_report_parameters():
    pass


def get_bugs_by_criteria(criterias, projects, milestone_name, team=None, options={}, user_agent=None):

    # Create filters, based on incoming data, to get bugs from db

    filters = []

    if not options:
        options["status"] = BUG_STATUSES
        options["importance"] = BUG_IMPORTANCE

    private_bugs = []
    if user_agent is not None:
        for pr in projects:
            private_bugs.extend(user_agent.get_bugs(
                pr,
                statuses=options['status'],
                milestone_name=[milestone_name],
                importance=options["importance"]))

    # NOTE(ochuprykov): at this moment it is impossible to know information
    #                   type of the bug without making call to l-api. Manually
    #                   setting type to private for visual distinction from
    #                   other bugs.
    for bug in private_bugs:
        bug.information_type = "Private"

    filters.append({"status": {"$in": options["status"]}})
    filters.append({"importance": {"$in": options["importance"]}})

    if milestone_name is not None:
        filters.append({'milestone': milestone_name})
    if team is not None and team != "Unknown":
        filters.append({"assignee": {"$in": get_team_members(team)}})
        private_bugs = [bug for bug in private_bugs
                        if bug.assignee in get_team_members(team)]
    if team is not None and team == "Unknown":
        all_assigners = [get_team_members(t) for t in TEAMS if t != "Unknown"]
        all_assigners = list(itertools.chain(*all_assigners))
        filters.append({"assignee": {"$nin": all_assigners}})
        private_bugs = [bug for bug in private_bugs if bug.assignee not in all_assigners]

    all_bugs = []
    all_bugs.extend(private_bugs)
    for pr in projects:
        all_bugs.extend([Bug(b) for b in db.bugs[pr].find({"$and": filters})])

    result = []

    for crit in criterias:

        impl = get_criteria_implementation(crit, milestone_name)
        criteria = get_criteria_by_name(crit['name'])

        # TODO (viktors): refactor this loop
        for bug in all_bugs:

            if impl.is_satisfied(bug):
                try:
                    hint_text = impl.get_hint_text(
                        bug, criteria.get('hint-text', ''))
                except:
                    # something wrong with hint text
                    hint_text = ""

                if hint_text:
                    hint_text += " (%s)" % criteria['name']

                if bug in result:
                    bug_idx = result.index(bug)
                    result[bug_idx].criteria += "\n" + criteria['name']
                    result[bug_idx].criteria_hint_text += "\n" + hint_text
                else:
                    bug.criteria = criteria['name']
                    bug.criteria_hint_text = hint_text
                    result.append(bug)

    # NOTE(viktors): Bugs should be sorted by priority and "customer-found" tag
    #                in bug tags
    result = sorted(result,
                    key=lambda bug: (BUG_IMPORTANCE.index(bug.importance),
                                     CUSTOMER_FOUND_TAG not in bug.tags))
    return result


def get_reports_data(report_name, projects, milestone_name=None, user_agent=None):
    config = read_config_file()
    try:
        report = [r for r in config['reports'] if r['name'] == report_name][0]
    except IndexError:
        raise ValueError("These is no report %r in config" % report_name)

    all_res = []

    criterias = [cr['name'] for cr in report['criterias']]

    if not 'options' in report.keys():
        report['options'] = {}

    if report.get('group-by') == "team":
        # returns a list of dictionaries
        for team in TEAMS:
            result = {
                'name': "%s for %s team" % (report['name'], team),
                'display_name': team,
                'parameter': report['parameter'],
                'display_criterias': report.get('display-trigger-criterias', False),
                'bugs': get_bugs_by_criteria(criterias=report['criterias'],
                                             projects=projects,
                                             milestone_name=milestone_name,
                                             team=team,
                                             options=report['options'],
                                             user_agent=user_agent),
                'report_legend': get_criteria_description(report['criterias'],
                                                          milestone_name),
            }
            all_res.append(result)
    else:
        # return a list with a single element to use same template :)
        result = {
            'name': report['name'],
            'display_name': report['text'],
            'parameter': report['parameter'],
            'display_criterias': report.get('display-trigger-criterias', False),
            'bugs': get_bugs_by_criteria(criterias=report['criterias'],
                                         projects=projects,
                                         milestone_name=milestone_name,
                                         options=report['options']),
            'report_legend': get_criteria_description(report['criterias'],
                                                      milestone_name),
        }
        all_res.append(result)

    result = {}
    result["DATA"] = all_res
    report["options"]["criterias"] = criterias
    result["PROPERTIES"] = report["options"]


    return result
