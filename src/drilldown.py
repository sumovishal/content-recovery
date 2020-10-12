#!/usr/bin/python3
import argparse
import json
import logging
import time
from sumologic.api import folder
import util
import org

config = {
    'srcOrgDb': {
        'host': "",
        'user': "",
        'password': ""
    },
    'srcAppDb': {
        'host': "",
        'user': "",
        'password': ""
    },
    'destAppDb': {
        'host': "",
        'user': "",
        'password': ""
    },
}

logger = util.getLogger()
logger.setLevel(logging.INFO)
dryRun = False
users = {}


def fixPropertiesBlob(name, propertiesBlob, indent):
    fixedPropertiesBlob = None
    try:
        propertiesJson = json.loads(propertiesBlob)
        target = propertiesJson['settings']['common']['configuration']['drilldown']['fallback']['target']
        # don't fix linked dashboards. Override properties_blob to remove dashboard linking.
        if target.get('key'):
            print("{0}[P]AccessKey: {1}, id: {2}, name: {3}".format(
                ' '*indent, target['key'], target['id'], target['name']))
            targetJson = json.loads('{"id":null,"name":null,"enabled":null}')
            propertiesJson['settings']['common']['configuration']['drilldown']['fallback']['target'] = targetJson
            fixedPropertiesBlob = json.dumps(propertiesJson)
    except KeyError as ke:
        logger.exception("Failed to fix blob: %s", ke)

    fixedPropertiesBlob = fixedPropertiesBlob.encode('UTF-8') if fixedPropertiesBlob else propertiesBlob
    #logger.debug("Fixed blob: %s", fixedPropertiesBlob)
    return fixedPropertiesBlob


def updatePropertiesBlob(srcDb, oldReportId, destDb, newReportId, indent):
    query = ("select title, id, properties_blob "
             "from panels "
             "where report_id = {0}")
    srcDb.execute(query.format(oldReportId))
    oldResults = srcDb.fetchall()
    assert(len(oldResults[0]) >= 1)

    destDb.execute(query.format(newReportId))
    newResults = destDb.fetchall()

    oldPanelMap = {r[0]: r[1:] for r in oldResults}
    newPanelMap = {r[0]: r[1:] for r in newResults}
    for panel in oldResults:
        name, propertiesBlob = panel[0], panel[2]
        newPanelId = newPanelMap[name][0]
        logger.debug("Fixing blob for panel: {0}({1})".format(name, panel[1]))
        try:
            print("{0}[P]{1} -> snapshotId: {2}, newId: {3}".format(
                ' '*indent, name, oldPanelMap[name][0], newPanelId))
            propertiesBlob = fixPropertiesBlob(name, propertiesBlob, indent).decode('UTF-8')

            query = ("update panels "
                     "set properties_blob=%s "
                     "where report_id=%s and id=%s")
            global dryRun
            if not dryRun:
                logger.info("Updating panel: {0}({1}), query: {2}".format(
                    name, newPanelId, query % (propertiesBlob, newReportId, newPanelId)))
                retval = destDb.execute(query, (propertiesBlob, newReportId, newPanelId))
                logger.info("Panel: %s(%s), rows affected: %s", name, newPanelId, retval)
            else:
                logger.info("[DryRun] Will update panel: {0}({1}), query: {2}".format(
                    name, newPanelId, query % (propertiesBlob, newReportId, newPanelId)))
        except KeyError as ke:
            print("{0}[P]ERROR: {1}".format(' '*indent, name))
            logger.exception("Missing panel: {0}, reportId: {1}".format(name, newReportId))


def findFolder(dbClient, orgId, name, parentId):
    query = ("select system_id "
             "from content_tree "
             "where organization_id = {0} and target_type = 'folder' and "
             "name like '%{1}%' and parent_id = {2}")
    dbClient.execute(query.format(orgId, name, parentId))
    queryResults = dbClient.fetchall()
    logger.debug("looking for folder: %s, result: %s", name, queryResults)
    if len(queryResults) == 0 or len(queryResults[0]) == 0:
        logger.error("No folder with name: {0} and parent: {1}".format(name, parentId))
        return None
    return queryResults[0][0]


def iterateFolders(srcDb, oldParentId, destDb, newParentId, indent):
    query = ("select name, target_type, system_id "
             "from content_tree "
             "where parent_id = {0} and target_type in ('folder', 'report')")

    srcDb.execute(query.format(oldParentId))
    oldResults = srcDb.fetchall()
    oldChildrenMap = {r[0]: r[1:] for r in oldResults}

    destDb.execute(query.format(newParentId))
    newResults = destDb.fetchall()
    newChildrenMap = {r[0]: r[1:] for r in newResults}

    for child in oldResults:
        name, targetType = child[0], child[1]
        typeStr = 'F' if targetType == 'folder' else 'R'

        try:
            assert(newChildrenMap[name][0] == targetType)
            oldContentId, newContentId = oldChildrenMap[name][1], newChildrenMap[name][1]
            print("{0}[{1}]{2} -> snapshotId: {3}, newId: {4}".format(
                ' '*indent, typeStr, name, oldChildrenMap[name][1], newChildrenMap[name][1]))
            if targetType == 'folder':
                iterateFolders(srcDb, oldContentId, destDb, newChildrenMap[name][1], indent + 2)
            elif targetType == 'report':
                logger.info("Updating report: {0}, oldId: {1}, newId: {2}".format(name, oldContentId, newContentId))
                updatePropertiesBlob(srcDb, oldContentId, destDb, newContentId, indent + 2)
        except KeyError as ke:
            print("{0}[{1}]ERROR: {2}".format(' '*indent, typeStr, name))
            logger.error("Item missing in new db: {0}, parentId: {1}".format(child, newParentId))


def iteratePersonalFolders(srcDb, destDb, recoveryFolderId, userId=None):
    # find all personal folders
    query = ("select user_id, description, system_id "
             "from content_tree "
             "where organization_id = {0} and target_type = 'folder' and "
             "name = 'Personal' and parent_id is null")
    #query += " and user_id not in (2791963)" # security+sumosupport+remedy+bpci+partners+llc@sumologic.com
    if userId is not None:
        query += " and user_id={0}".format(userId)
    srcDb.execute(query.format(srcOrgId))

    # iterate over all personal folders
    queryResults = srcDb.fetchall()
    for row in queryResults:
        userId, description, oldFolderId = row[0], row[1], row[2]
        # if user does not exist, use userId as folder name
        name = users.get(userId, "user-{}".format(userId))

        # if user has some reports
        query = ("select count(id) "
                 "from content_tree "
                 "where parent_id={0} and target_type in ('report', 'folder')")
        srcDb.execute(query.format(oldFolderId))
        count = srcDb.fetchall()[0][0]
        if count > 0:
            newFolderId = findFolder(destDb, destOrgId, name, recoveryFolderId)
            if newFolderId:
                print("\n== Personal Folder: {0} (userId={1}) ==".format(name, userId))
                indent = 2
                print("{0}[F]Personal -> snapshotId: {1}, newId: {2}".format(' '*indent, oldFolderId, newFolderId))
                iterateFolders(srcDb, oldFolderId, destDb, newFolderId, indent)


def recoverPropertiesBlob(srcOrgId, destOrgId, recoveryFolderId, userId=None):
    srcAppDbConfig = config['srcAppDb']
    srcHost, srcUser, srcPass = srcAppDbConfig['host'], srcAppDbConfig['user'], srcAppDbConfig['password']

    destAppDbConfig = config['destAppDb']
    destHost, destUser, destPass = destAppDbConfig['host'], destAppDbConfig['user'], destAppDbConfig['password']

    srcOrgDbConfig = config['srcOrgDb']
    global users
    users = org.getUserMap(srcOrgDbConfig['host'], srcOrgDbConfig['user'], srcOrgDbConfig['password'], srcOrgId,
                            userId)

    with util.SqlClient(srcHost, srcUser, srcPass) as srcDb, util.SqlClient(destHost, destUser, destPass) as destDb:
        startTime = time.time()
        iteratePersonalFolders(srcDb, destDb, recoveryFolderId, userId)
        print("\nDone..time taken={0}m".format((time.time() - startTime) // 60))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Copy properties_blob column from source db to destination db')
    parser.add_argument('-s', dest='srcOrgId', type=str, required=True, help='Source org id (in decimal)')
    parser.add_argument('-d', dest='destOrgId', type=str, required=True, help='Destination org id (in decimal)')
    parser.add_argument('-f', dest='folderId', type=str, required=True, help='Recovery folder id (in decimal)')
    parser.add_argument('-u', dest='user', type=str, required=False,
                        help='user id (in decimal) if recovery needs to run for a user only')
    parser.add_argument('--dry-run', dest='dry', action='store_true', help='List down panels that will be updated')
    args = parser.parse_args()

    dryRun = args.dry

    srcOrgId = args.srcOrgId
    destOrgId = args.destOrgId
    recoveryFolderId = args.folderId
    userId = args.user
    recoverPropertiesBlob(srcOrgId, destOrgId, recoveryFolderId, userId)
