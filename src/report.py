import json
import logging

import util
import timerange
from sumologic import client
from sumologic.api import content


logger = util.getLogger()


class Report:
    def __init__(self, row):
        self.type = "DashboardSyncDefinition"
        self.name = row[0]
        self.description = row[1]
        self.detailLevel = row[2]
        self.properties = row[3]
        self.panels = []
        self.filters = []

    def asdict(self):
        return {
            'type': self.type,
            'name': self.name,
            'description': self.description,
            'detailLevel': self.detailLevel,
            'properties': self.properties,
            'panels': [panel.asdict() for panel in self.panels],
            'filters': [reportFilter.asdict() for reportFilter in self.filters]
        }


class Panel:
    def __init__(self, row):
        self.id = row[0]
        self.name = row[1]
        self.viewerType = row[2]
        self.detailLevel = row[3]
        self.queryString = row[4]
        self.metricsQueries = []
        self.timeRange = timerange.convertDbToApiTimeRange(row[5])
        self.x = row[6]
        self.y = row[7]
        self.width = row[8]
        self.heigth = row[9]
        self.properties = row[10]
        self.desiredQuantizationInSecs = row[11]
        self.queryParams = []

    def asdict(self):
        return {
            'name': self.name,
            'viewerType': self.viewerType,
            'detailLevel': self.detailLevel,
            'queryString': self.queryString,
            'metricsQueries': self.metricsQueries,
            'timeRange': self.timeRange,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.heigth,
            'properties': self.properties,
            'id': self.id,
            'desiredQuantizationInSecs': self.desiredQuantizationInSecs,
            'queryParameters': self.queryParams,
        }


class Filters:
    def __init__(self, row):
        self.fieldName = row[0]
        self.label = row[1]
        self.defaultValue = row[2]
        self.filterType = row[3]
        self.properties = row[4]
        self.panelIds = []

    def asdict(self):
        return {
           'fieldName': self.fieldName,
           'label': self.label,
           'defaultValue': self.defaultValue,
           'filterType': self.filterType,
           'properties': self.properties,
           'panelIds': self.panelIds,
        }


def getPanelIds(dbCursor, filterId):
    query = ("select panel_id "
             "from panel_query_param "
             "where filter_id={0}")
    dbCursor.execute(query.format(filterId))
    results = dbCursor.fetchall()

    panelIds = []
    for row in results:
        panelIds.append(row[0])

    return panelIds


def getFilters(dbCursor, reportId, indent):
    query = ("select field_name, label, default_value, filter_type, properties, id "
              "from filters "
              "where report_id={0}")
    dbCursor.execute(query.format(reportId))
    results = dbCursor.fetchall()
    #logger.debug("Total filters fetched for report(=%s): %s", reportId, len(results))

    filters = []
    for row in results:
        filterId = row[-1]
        newFilter = Filters(row)
        newFilter.panelIds = getPanelIds(dbCursor, filterId)

        filters.append(newFilter)

    return filters


def getQueryParams(dbCursor, panelId, indent):
    query = ("select name, label, description, data_type_id, value, filter_id "
             "from panel_query_param "
             "where panel_id={0}")
    dbCursor.execute(query.format(panelId))
    results = dbCursor.fetchall()

    params = []
    for row in results:
        # find out dataType
        query = "select data_type from param_type_table where id={0}"
        dbCursor.execute(query.format(row[3]))
        retval = dbCursor.fetchall()
        if not retval:
            logger.error("no mapping for dataType(id: {0})".format(row[3]))
            dataType = 'NUMBER'
        else:
            dataType = retval[0][0]

        param = {
            'name': row[0],
            'label': row[1],
            'description': row[2],
            'dataType': dataType,
            'value': row[4],
            'autoComplete': getAutoComplete()
        }
        params.append(param)

    return params


def getAutoComplete():
    # Remedy only has auto complete set to 'SKIP_AUTOCOMPLETE'.
    autoComplete = {
        'autoCompleteType': 'SKIP_AUTOCOMPLETE',
        # skipping other optional fields (they are not set for Remedy)
    }
    return autoComplete


def getMetricsQueries(dbCursor, reportId, panelId):
    query = ("select query, row_id "
             "from metrics_panels "
             "where report_id={0} and panel_id={1}")
    dbCursor.execute(query.format(reportId, panelId))
    results = dbCursor.fetchall()

    queries = []
    for row in results:
        query = {
            'query': row[0],
            'rowId': row[1]
        }
        queries.append(query)

    return queries


def getPanels(dbCursor, reportId, indent):
    query = ("select id, title, viewer_type, detail_level, query, timerange, x, y, width, height, properties, desired_quantization "
             "from panels "
             "where report_id={0}")
    dbCursor.execute(query.format(reportId))
    results = dbCursor.fetchall()

    panels = []
    for row in results:
        panel = Panel(row)
        logger.info("Creating panel: {0}, id in snapshot: {1}".format(panel.name, panel.id))
        panel.queryParams = getQueryParams(dbCursor, panel.id, indent)
        panel.metricsQueries = getMetricsQueries(dbCursor, reportId, panel.id)
        panels.append(panel)

    return panels


def createReport(dbCursor, name, description, reportId, newParentId, indent):
    query = ("select detail_level, properties "
             "from reports "
             "where content_id = {0}")
    dbCursor.execute(query.format(reportId))
    results = dbCursor.fetchall()
    if not results:
        logger.error("no report with id: {0}".format(reportId))
        return

    logger.info("Creating report: %s", name)
    newReport = Report((name, description) + results[0])
    newReport.panels = getPanels(dbCursor, reportId, indent)
    newReport.filters = getFilters(dbCursor, reportId, indent)

    logger.info("report json: %s", json.dumps(newReport.asdict(), indent=4))
    if util.config['dryRun']:
        return

    try:
        contentApi = content.ContentManagementApi(util.getApiClient())
        contentApi.sync(newParentId, newReport.asdict(), overwrite=True)
    except Exception as e:
        logger.error("Got error while syncing report: %s", name)
        print("{0}ERROR: {1} - FAILED".format(' '*indent, name))

