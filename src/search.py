import json

import util
import timerange
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
        self.searchSchedule = None

    def asdict(self):
        search = {
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
        if self.searchSchedule is not None:
            search['searchSchedule'] = self.searchSchedule
        return search


def getQueryParams(dbCursor, targetExternalId, indent):
    # the saved_query_param table is using the search's target_external_id as the value for search_definition_id
    query = ("select name, label, description, param_type_id, default_value "
             "from saved_query_param "
             "where search_definition_id={0}")
    dbCursor.execute(query.format(targetExternalId))
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


# Gets the notification object for the corresponding scheduleId
def getSearchScheduleNotification(conciergeDbCursor, scheduleId, indent):
    query = ("SELECT notification_type, notification_data "
             "FROM schedule_notification "
             "WHERE schedule_id = {0}")
    conciergeDbCursor.execute(query.format(scheduleId))
    rows = conciergeDbCursor.fetchall()
    if not rows:
        print("{0}ERROR: No notification found for schedule with id {1}".format(' '*indent, scheduleId))
        return {}
    elif len(rows) != 1:
        print("{0}ERROR: Found more than 1 notifications for schedule with id {1}".format(' '*indent, scheduleId))
        return None

    dbSNotificationRow = rows[0]
    # Salesforce only has WebhookSearchNotificationSyncDefinition currently, so this logic only support that.
    if dbSNotificationRow[0] != 5:
        print("{0}ERROR: Only WebhookSearchNotificationSyncDefinition type is currently supported".format(' '*indent))
        return {}

    try:
        notificationDataJson = json.loads(dbSNotificationRow[1])
        notification = {
            'taskType': 'WebhookSearchNotificationSyncDefinition',
            'webhookId': notificationDataJson['webhookId']
        }
        if 'payload' in notificationDataJson:
            notification['payload'] = notificationDataJson['payload']
        if 'itemizeAlerts' in notificationDataJson:
            notification['itemizeAlerts'] = notificationDataJson['itemizeAlerts']
        if 'maxItemizedAlerts' in notificationDataJson:
            notification['maxItemizedAlerts'] = notificationDataJson['maxItemizedAlerts']
        return notification
    except Exception:
        print("{0}ERROR: Couldn't parse the following notification object from DB: {1}"
              .format(' '*indent, dbSNotificationRow[1]))
        return {}


# Gets the notification object for the corresponding scheduleId
def getSearchScheduleParameters(conciergeDbCursor, scheduleId):
    params = []
    query = ("SELECT param_name, param_value "
             "FROM schedule_query_param "
             "WHERE search_schedule_id = {0}")
    conciergeDbCursor.execute(query.format(scheduleId))
    rows = conciergeDbCursor.fetchall()
    if not rows:
        return params

    for row in rows:
        param = {
            'name': row[0],
            'value': row[1]
        }
        params.append(param)

    return params


# Converts the schedule search type from DB to API format
# Conversion logic can be found here: https://github.com/Sanyaku/sumologic/blob/3b342030d7f4a32a3b8b0e204a11450157e3a260/external/src/main/scala/com/sumologic/external/util/ScheduleTypeConversionHelper.scala#L29
def convertSearchScheduleType(scheduleType, indent):
    if scheduleType == 'Real time':
        return 'RealTime'
    elif scheduleType == 'Every 15 minutes':
        return '15Minutes'
    elif scheduleType == 'Hourly':
        return '1Hour'
    elif scheduleType == 'Every 2 hours':
        return '2Hours'
    elif scheduleType == 'Every 4 hours':
        return '4Hours'
    elif scheduleType == 'Every 6 hours':
        return '6Hours'
    elif scheduleType == 'Every 8 hours':
        return '8Hours'
    elif scheduleType == 'Every 12 hours':
        return '12Hours'
    elif scheduleType == 'Daily':
        return '1Day'
    elif scheduleType == 'Weekly':
        return '1Week'
    elif scheduleType == 'Custom':
        return 'Custom'
    else:
        print("{0}Error: Found an unrecognized scheduleType: {1}", ' '*indent, scheduleType)
        return ''


# Tries to get the corresponding search schedule from concierge DB. If not found, then it's not a scheduled search
def getSearchSchedule(conciergeDbCursor, targetExternalId, indent):
    query = ("SELECT id, cron_schedule, displayable_time_range, parseable_time_range, time_zone, threshold_type, "
             "operator, count, schedule_type, mute_error_emails "
             "FROM search_schedule "
             "WHERE saved_search_id = {0}")
    conciergeDbCursor.execute(query.format(targetExternalId))
    rows = conciergeDbCursor.fetchall()
    if not rows:
        # this search is not a schedule search
        return None

    print("{0}Search with target_external_id of {1} is a scheduled search".format(' '*indent, targetExternalId))
    if len(rows) != 1:
        print("{0}ERROR: Found more than 1 search schedule for target_external_id={1}"
              .format(' '*indent, targetExternalId))
        return None
    dbSearchRow = rows[0]
    scheduleId = dbSearchRow[0]

    searchSchedule = {}
    if dbSearchRow[1] is not None:
        searchSchedule['cronExpression'] = dbSearchRow[1]
    if dbSearchRow[2] is not None:
        searchSchedule['displayableTimeRange'] = dbSearchRow[2]
    searchSchedule['parseableTimeRange'] = timerange.convertDbToApiTimeRange(dbSearchRow[3])
    searchSchedule['timeZone'] = dbSearchRow[4]
    if dbSearchRow[5] is not None:
        searchSchedule['threshold'] = {
            'thresholdType': 'message' if (int(dbSearchRow[5]) == 1) else 'group',
            'operator': dbSearchRow[6],
            'count': dbSearchRow[7]
        }
    searchSchedule['notification'] = getSearchScheduleNotification(conciergeDbCursor, scheduleId, indent)
    searchSchedule['scheduleType'] = convertSearchScheduleType(dbSearchRow[8], indent)
    if dbSearchRow[9] is not None:
        searchSchedule['muteErrorEmails'] = False if (dbSearchRow[9] == 0) else True
    searchSchedule['parameters'] = getSearchScheduleParameters(conciergeDbCursor, scheduleId)

    return searchSchedule


def createSearch(appDbCursor, conciergeDbCursor, name, description, searchId, newParentId, targetExternalId, indent):
    query = ("select search_query, time_range_expression, view_name, view_start_time, by_receipt_time "
             "from search_definition "
             "where content_id = {0}")
    appDbCursor.execute(query.format(searchId))
    results = appDbCursor.fetchall()
    if not results:
        print("{0}ERROR: no search with id: {1}".format(' '*indent, searchId))
        return

    logger.info("Creating search: %s", name)
    newSearch = Search((name, description) + results[0])
    newSearch.queryParams = getQueryParams(appDbCursor, targetExternalId, indent)
    newSearch.searchSchedule = getSearchSchedule(conciergeDbCursor, targetExternalId, indent)

    logger.info("search json: %s", json.dumps(newSearch.asdict(), indent=4))
    if util.config['dryRun']:
        return

    try:
        contentApi = content.ContentManagementApi(util.getApiClient())
        contentApi.sync(newParentId, newSearch.asdict(), overwrite=True)
    except Exception as e:
        logger.error("Got error while syncing search: %s", name)
        print("{0}ERROR: {1} - FAILED".format(' '*indent, name))


