import json

import util
from sumologic import client
from sumologic.api import content


logger = util.getLogger()


class Search:
    def __init__(self, row):
        self.type = "SavedSearchWithScheduleSyncDefinition"
        self.name = row[0]
        self.description = row[1]
        self.queryText = row[2]
        self.defaultTimeRange = row[3]
        self.viewName = row[4]
        self.viewStartTime = row[5]
        self.byReceiptTime = row[6]
        self.queryParams = []

    def asdict(self):
        return {
            'type': self.type,
            'name': self.name,
            'description': self.description,
            'search': {
                'queryText': self.queryText,
                'defaultTimeRange': self.defaultTimeRange,
                'byReceiptTime': self.byReceiptTime,
                'viewName': self.viewName,
                'viewStartTime': self.viewStartTime,
                'queryParameters': self.queryParams,
            },
        }


def getQueryParams(dbCursor, searchId, indent):
    query = ("select name, label, description, param_type_id, default_value "
             "from saved_query_param "
             "where search_definition_id={0}")
    dbCursor.execute(query.format(searchId))
    results = dbCursor.fetchall()

    params = []
    for row in results:
        # find out dataType
        query = "select data_type from param_type_table where id={0}"
        dbCursor.execute(query.format(row[3]))
        retval = dbCursor.fetchall()
        if not retval:
            print("{0}ERROR: no mapping for paramType(id: {1})".format(' '*indent, row[3]))
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


def createSearch(dbCursor, name, description, searchId, newParentId, indent):
    query = ("select search_query, time_range_expression, view_name, view_start_time, by_receipt_time "
             "from search_definition "
             "where content_id = {0}")
    dbCursor.execute(query.format(searchId))
    results = dbCursor.fetchall()
    if not results:
        print("{0}ERROR: no search with id: {1}".format(' '*indent, searchId))
        return

    logger.info("Creating search: %s", name)
    newSearch = Search((name, description) + results[0])
    newSearch.queryParams = getQueryParams(dbCursor, searchId, indent)

    logger.info("search json: %s", json.dumps(newSearch.asdict(), indent=4))
    if util.config['dryRun']:
        return

    try:
        contentApi = content.ContentManagementApi(util.getApiClient())
        contentApi.sync(newParentId, newSearch.asdict(), overwrite=True)
    except Exception as e:
        logger.error("Got error while syncing search: %s", name)
        print("{0}ERROR: {1} - FAILED".format(' '*indent, name))


