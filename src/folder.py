import time
import logging
import requests
from sumologic.api import folder
import util
import org
import search
import report


orgId = None
folderApi = None
users = {}
logger = util.getLogger()


class Folder():
    def __init__(self, row):
        self.name = row[0]
        self.description = row[1]
        self.parentId = row[2]

    def asdict(self):
        return {
            'name': self.name,
            'description': self.description,
            'parentId': self.parentId
        }


def createNewFolder(name, description, parentId):
    if util.config['dryRun']:
        return '00000000'

    # name and description less than 128 and 255 chars respectively
    name = name[:128]
    description = description[:255]
    folderReq = Folder([name, description, parentId])

    try:
        newFolder = folderApi.create_folder(folderReq.asdict())
    except requests.exceptions.HTTPError as he:
        rsp = he.response
        if rsp.status_code == 400:
            # if request fails with 'duplicate_content' don't fail the recovery.
            err = rsp.json()
            if err['errors'][0]['code'] == 'content:duplicate_content':
                # find out id of folder with same name
                children = folderApi.get_folder(parentId)['children']
                for child in children:
                    if child['name'] == name:
                        return child['id']
                print("ERROR: Unexpected error. Expecting {0} inside folder:{1}, not found".format(name, parentId))
        raise he

    logger.info("Created folder '%s', id:%s, parentId:%s", name, newFolder['id'], parentId)
    return newFolder['id']


def createTopFolder(name, description, parentId):
    if util.config['dryRun']:
        return '00000000'

    topFolderId = createNewFolder(name, description, parentId)
    print("Content will be recovered in folder: {}".format(topFolderId))
    return topFolderId


def createPersonalFolders(appDbCursor, conciergeDbCursor, topFolderId):
    # find all personal folders
    query = ("select user_id, description, system_id "
             "from content_tree "
             "where organization_id = {0} and target_type = 'folder' and "
             "name = 'Personal' and parent_id is null")
    if util.config['userId']:
        query += f" and user_id = {util.config['userId']}"
    appDbCursor.execute(query.format(orgId))

    # iterate over all personal folders and create all content underneath
    queryResults = appDbCursor.fetchall()
    for row in queryResults:
        userId, description, oldPersonalFolderId = row[0], row[1], row[2]
        # if user does not exist, use userId as folder name
        name = users.get(userId, "user-{}".format(userId))

        # Create personal folder only if user has some content
        query = ("select count(id) "
                 "from content_tree "
                 "where parent_id={0} and target_type in ('folder', 'search')")
        appDbCursor.execute(query.format(oldPersonalFolderId))
        count = appDbCursor.fetchall()[0][0]
        if count > 0:
            print("\n== Personal Folder: {0}, children: {1} ==".format(name, count))
            personalFolderId = createNewFolder(name, description, topFolderId)
            createFolderStructure(appDbCursor, conciergeDbCursor, oldPersonalFolderId, personalFolderId, 2)


def createFolderStructure(appDbCursor, conciergeDbCursor, oldParentId, newParentId, indent):
    query = ("select name, description, target_type, system_id, target_external_id "
             "from content_tree "
             "where parent_id = {0} and target_type in ('search', 'folder', 'report')")
    appDbCursor.execute(query.format(oldParentId))

    children = appDbCursor.fetchall()
    reqCount = 0
    for child in children:
        name, description, targetType, oldContentId, targetExternalId = child[0], child[1], child[2], child[3], child[4]

        if targetType == 'folder':
            print("{0}[F]{1} - START".format(' '*indent, name))
            folderId = createNewFolder(name, description, newParentId)
            createFolderStructure(appDbCursor, conciergeDbCursor, oldContentId, folderId, indent + 2)
            print("{0}[F]{1} - DONE (id: {2}, parent: {3})".format(' '*indent, name, folderId, newParentId))
        elif targetType == 'search':
            print("{0}[S]{1} - START".format(' '*indent, name))
            search.createSearch(appDbCursor, conciergeDbCursor, name, description, oldContentId, newParentId, targetExternalId, indent)
            print("{0}[S]{1} - DONE (parent: {2})".format(' '*indent, name, newParentId))
        elif targetType == 'report':
            print("{0}[R]{1}".format(' '*indent, name))
            report.createReport(appDbCursor, name, description, oldContentId, newParentId, indent)
            print("{0}[R]{1} - DONE (parent: {2})".format(' '*indent, name, newParentId))

        if not util.config['dryRun']:
            reqCount += 1
            if reqCount == 7:
                reqCount = 0
                time.sleep(0.5)


# This method recovers content from a specific folder only, as opposed to all content from Personal folder
def recoverSingleFolder(appDbCursor, conciergeDbCursor, folderId, topFolderId):
    # find the folder to be recovered
    query = ("select name, description "
             "from content_tree "
             "where organization_id = {0} and system_id = {1}")
    appDbCursor.execute(query.format(orgId, folderId))

    queryResults = appDbCursor.fetchall()
    if len(queryResults) != 1:
        print("ERROR: Expecting 1 folder with the provided folderId. Found: {0}.".format(folderId))
        exit(1)

    for row in queryResults:
        name, description = row[0], row[1]

        query = ("select count(id) "
                 "from content_tree "
                 "where parent_id={0} and target_type in ('folder', 'search', 'report')")
        appDbCursor.execute(query.format(folderId))
        count = appDbCursor.fetchall()[0][0]
        if count > 0:
            print("\n== Folder: {0}, children: {1} ==".format(name, count))
            newFolderId = createNewFolder(name, description, topFolderId)
            createFolderStructure(appDbCursor, conciergeDbCursor, folderId, newFolderId, 2)


def recover():
    global orgId, users, folderApi

    orgId = util.config['orgId']
    orgName = util.config['orgName']
    orgDb = util.config['orgDb']
    userId = util.config['userId']
    folderId = util.config['folderId']
    # There is no need to get users map if we recover a specific folder only
    if folderId is None:
        users = org.getUserMap(orgDb['host'], orgDb['user'], orgDb['password'], orgId, userId)

    appDb = util.config['appDb']
    conciergeDb = util.config['appDb']
    with util.SqlClient(appDb['host'], appDb['user'], appDb['password'], "org") as appDbCursor,\
            util.SqlClient(conciergeDb['host'], conciergeDb['user'], conciergeDb['password'], "org") as conciergeDbCursor:
        startTime = time.time()

        print(f"Start recovery for {orgName}(id={orgId})..")
        topFolderId = '00000000'
        if not util.config['dryRun']:
            folderApi = folder.FolderManagementApi(util.getApiClient())
            myPersonalFolder = folderApi.get_personal_folder()
            # parent folder for recovery
            topFolderId = createTopFolder(f"{orgName} - Recovered Content", "All recovered content", myPersonalFolder['id'])
        if folderId is not None:
            recoverSingleFolder(appDbCursor, conciergeDbCursor, folderId, topFolderId)
        else:
            createPersonalFolders(appDbCursor, conciergeDbCursor, topFolderId)
        print("\nDone..time taken={0}s".format(int(time.time() - startTime)))

