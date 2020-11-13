import json
import logging

import util
import timerange


logger = util.getLogger()


class Dashboard:
    def __init__(self, row):
        self.type = "MewboardSyncDefinition"
        self.name = row[0]
        self.description = row[1]
        self.title = row[2]
        self.timeRange = row[3]
        self.refreshInterval = row[4]
        self.layout = {}
        self.panels = []
        self.variables = []

    def asdict(self):
        return {
            'type': self.type,
            'name': self.name,
            'description': self.description,
            'title': self.title,
            'timeRange': None if (self.timeRange is None) else timerange.convertDbToApiTimeRange(self.timeRange),
            'refreshInterval': self.refreshInterval,
            'layout': self.layout,
            'panels': [panel.asdict() for panel in self.panels],
            'variables': [variable.asdict() for variable in self.variables]
        }


class Panel:
    def __init__(self, row):
        self.key = row[0]
        self.title = row[1].decode("utf-8")
        self.panelType = row[2]
        self.visualSettings = row[3].decode("utf-8")
        self.timeRange = row[4]
        self.queries = []

    def asdict(self):
        return {
            'key': self.key,
            'title': self.title.replace(u"\u00A0", " "),
            'panelType': self.panelType,
            'visualSettings': self.visualSettings,
            'timeRange': None if (self.timeRange is None) else timerange.convertDbToApiTimeRange(self.timeRange),
            'queries': [query.asdict() for query in self.queries],
        }


class Variable:
    def __init__(self, name):
        self.name = name
        self.sourceDefinition = None

    def asdict(self):
        return {
            'name': self.name,
            'sourceDefinition': self.sourceDefinition,
        }


class Query:
    def __init__(self, row):
        self.queryType = row[0]
        self.queryString = row[1]
        self.queryKey = row[2]

    def asdict(self):
        return {
            'queryType': self.queryType,
            'queryString': self.queryString,
            'queryKey': self.queryKey,
        }


# Converts an integer to 16-digit hex (prepending 0's if needed)
def convertToHex(number):
    if number < 0:
        offset = 1 << 64
        mask = offset - 1
        number = number + offset & mask
    hexString = hex(number).lstrip("0x")
    hexLength = len(hexString)
    if hexLength < 16:
        hexString = ("0"*(16-hexLength)) + hexString
    return hexString


def getVariableSourceDefinition(cqDbCursor, variableHexId, indent):
    query = ("select variable_source_type, csv_values "
             "from variable_source_definition "
             "where variable_id='{0}'")
    cqDbCursor.execute(query.format(variableHexId))
    results = cqDbCursor.fetchall()
    if not results:
        print("{0}no variable source definition for variable with id: {1}".format(" "*indent, variableHexId))
        return None

    sourceDefinition = results[0]
    sourceType = sourceDefinition[0]
    if sourceType != "CsvSourceDef":
        print("{0}variable of source type: {1} is not supported".format(" "*indent, sourceType))
        return None
    csvValues = sourceDefinition[1]
    return {
        "variableSourceType": "CsvVariableSourceDefinition",
        "values": csvValues.decode("utf-8")
    }


def getVariables(cqDbCursor, dashboardHexId, indent):
    query = ("select hex_id, name "
             "from variable "
             "where dashboard_id='{0}'")
    cqDbCursor.execute(query.format(dashboardHexId))
    results = cqDbCursor.fetchall()
    if not results:
        print("{0}no variables for dashboard with id: {1}".format(" "*indent, dashboardHexId))
        return []

    variables = []
    for row in results:
        logger.info("{0}Creating query for panel with id: {1}".format(" "*indent, dashboardHexId))
        variable = Variable(row[1])
        variable.sourceDefinition = getVariableSourceDefinition(cqDbCursor, row[0], indent)
        variables.append(variable)
    return variables


def getQueries(cqDbCursor, panelHexId, indent):
    query = ("select query_type, query_string, query_key "
             "from query "
             "where panel_id='{0}'")
    cqDbCursor.execute(query.format(panelHexId))
    results = cqDbCursor.fetchall()
    if not results:
        print("{0}no queries for panel with id: {1}".format(" "*indent, panelHexId))
        return

    queries = []
    for row in results:
        logger.info("{0}Creating query for panel with id: {1}".format(" "*indent, panelHexId))
        query = Query(row)
        queries.append(query)
    return queries


def getPanels(cqDbCursor, dashboardHexId, indent):
    query = ("select panel_key, panel_title, panel_type, visual_settings, time_range, hex_id "
             "from panel "
             "where dashboard_id='{0}'")
    cqDbCursor.execute(query.format(dashboardHexId))
    results = cqDbCursor.fetchall()
    if not results:
        print("{0}no panels for dashboard with id: {1}".format(" "*indent, dashboardHexId))
        return

    panels = []
    for row in results:
        if row[2] != "SumoSearchPanel":
            print("{0}Panel type not supported: {1}", " "*indent, row[2])
            continue
        logger.info("{0}Creating panel for dashboard with id: {1}".format(" "*indent, dashboardHexId))
        panel = Panel(row)
        panel.queries = getQueries(cqDbCursor, row[5], indent)
        panels.append(panel)
    return panels


def formatLayoutObject(layout, indent):
    # For some reason the DB longblob for layout has some extra characters that the API can't handle.... Strip those
    layout = layout.replace("\x00", "").replace("\x05", "").replace("\x14", "").replace("\x02", "").replace("\x10", "")\
        .replace("\x06", "").replace("\x16", "").replace("|", "").replace("~", "").replace(u"\u0000", "")
    if not layout.startswith("GridLayout"):
        print("{0}ERROR: layout type not supported for layout: {1}".format(" "*indent, layout))
        return None

    layout = layout.lstrip("GridLayout").strip().lstrip("*")
    panels = layout.split("*")
    panelLayouts = []
    for panel in panels:
        key = panel[:panel.index("{")]
        panelLayout = {
            # For some reason in the DB *sometimes* an extra character gets appended which makes the panel layout
            # mismatch the panels.... Just strip it if so
            "key": key[:-1] if len(key) == 22 else key,
            "structure": panel.lstrip(key)
        }
        panelLayouts.append(panelLayout)

    return {
        "layoutType": "Grid",
        "layoutStructures": panelLayouts
    }


# This method simply logs the dashboard object and does NOT actually create it. This code would need to be extended for
# it to create it as well via the API
def createDashboard(cqDbCursor, name, description, targetExternalId, indent):
    dashboardHexId = convertToHex(targetExternalId)
    query = ("select title, time_range, refresh_interval, layout "
             "from dashboard "
             "where hex_id='{0}'")
    cqDbCursor.execute(query.format(dashboardHexId))
    results = cqDbCursor.fetchall()
    if not results:
        print("no dashboard with id: {0}".format(dashboardHexId))
        return

    logger.info("Creating dashboard: {0}".format(name))
    newDashboard = Dashboard((name, description) + results[0])
    newDashboard.layout = formatLayoutObject(results[0][3].decode("utf-8"), indent)
    newDashboard.panels = getPanels(cqDbCursor, dashboardHexId, indent)
    newDashboard.variables = getVariables(cqDbCursor, dashboardHexId, indent)

    print("Dashboard json: {0}".format(json.dumps(newDashboard.asdict())))
