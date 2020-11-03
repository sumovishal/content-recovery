import util
import json
import math

logger = util.getLogger()

timeRangeDefaultJson = {
    'type': 'BeginBoundedTimeRange',
    'from': {
        'type': 'RelativeTimeRangeBoundary',
        'relativeTime': '-15m'
    },
}


# Converts a DB time range object to an appropriate API time range object (ResolvableTimeRange)
def convertDbToApiTimeRange(timeRange):
    try:
        timeRangeApiJson = getTimeRangeApiJsonHelper(timeRange)
    except Exception as err:
        print("Error getting timeRange: {0}. Falling back on default.".format(err))
        timeRangeApiJson = timeRangeDefaultJson

    logger.info("Original DB timeRange JSON: {0}. Converted API timeRange JSON: {1}".format(timeRange,
                                                                                            timeRangeApiJson))
    return timeRangeApiJson


def getTimeRangeApiJsonHelper(timeRange):
    timeRangeJson = json.loads(timeRange)
    if len(timeRangeJson) == 1:
        timeRangeObject = timeRangeJson[0]
        if timeRangeObject['t'] == 'relative':
            return {
                'type': 'BeginBoundedTimeRange',
                'from': getTimeRangeBoundary(timeRangeObject)
            }
        elif timeRangeObject['t'] == 'literal':
            if timeRangeObject['d'] in ('yesterday', 'previous_week', 'previous_month'):
                return {
                    'type': 'CompleteLiteralTimeRange',
                    'rangeName': timeRangeObject['d']
                }
            else:
                return {
                    'type': 'BeginBoundedTimeRange',
                    'from': getLiteralTimeRangeApiJson(timeRangeObject)
                }
        else:
            raise Exception("Conversion for the following timeRange isn't supported: {0}. Falling back on default."
                            .format(timeRange))
    elif len(timeRangeJson) == 2:
        timeRangeFromObject = timeRangeJson[0]
        timeRangeToObject = timeRangeJson[1]
        return {
            'type': 'BeginBoundedTimeRange',
            'from': getTimeRangeBoundary(timeRangeFromObject),
            'to': getTimeRangeBoundary(timeRangeToObject)
        }
    else:
        raise Exception("Conversion for the following timeRange isn't supported: {0}. Falling back on default."
                        .format(timeRange))


def getTimeRangeBoundary(timeRangeObject):
    if timeRangeObject['t'] == 'relative':
        return {
            'type': 'RelativeTimeRangeBoundary',
            'relativeTime': getRelativeTime(timeRangeObject['d'])
        }
    elif timeRangeObject['t'] == 'literal':
        return getLiteralTimeRangeApiJson(timeRangeObject)
    elif timeRangeObject['t'] == 'absolute' and isinstance(timeRangeObject['d'], int):
        return {
            'type': 'EpochTimeRangeBoundary',
            'epochMillis': timeRangeObject['d']
        }
    else:
        Exception("Conversion for the following timeRangeBoundary isn't supported: {0}. Falling back on default."
                  .format(timeRangeObject))


def getRelativeTime(millisecs):
    if millisecs == 0:
        return '0'
    return getRelativeTimeHelper(abs(millisecs), '-' if millisecs < 0 else '')


millisecsPerUnit = [
    ('w', 604800000),
    ('d', 86400000),
    ('h', 3600000),
    ('m', 60000),
    ('s', 1000)
]


def getRelativeTimeHelper(remainingMillisecs, currRelativeTimeString):
    if remainingMillisecs <= 0:
        return currRelativeTimeString

    # Going from largest to smallest:
    for unit in millisecsPerUnit:
        millisecsInUnit = unit[1]
        if remainingMillisecs >= millisecsInUnit:
            numWholeUnits = math.floor(remainingMillisecs / millisecsInUnit)
            newRemainingMillisecs = remainingMillisecs - (millisecsInUnit * numWholeUnits)
            newRelativeTimeString = currRelativeTimeString + (str(numWholeUnits) + unit[0])
            return getRelativeTimeHelper(newRemainingMillisecs, newRelativeTimeString)

    return currRelativeTimeString


def getLiteralTimeRangeApiJson(timeRangeObject):
    if timeRangeObject['d'] in ('now', 'today', 'second', 'minute', 'hour', 'day', 'week', 'month', 'year',
                                'yesterday', 'previous_week', 'previous_month'):
        return {
            'type': 'LiteralTimeRangeBoundary',
            'rangeName': timeRangeObject['d']
        }
    else:
        raise Exception("Unrecognized literal value: {0}. Falling back on default.".format(timeRangeObject['d']))
