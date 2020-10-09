import util

def getUserMap(host, user, password, orgId, userId=None):
    users = dict()
    with util.SqlClient(host, user, password, dbName='orgstore') as dbCursor:
        query = getUsersQuery(orgId, userId)
        dbCursor.execute(query)
        for row in dbCursor.fetchall():
            users[row[0]] = row[1]

    return users

def getUsersQuery(orgId, userId):
    # If userId is not provided, query for all users in org.
    if userId is None:
        query = ("select id, email "
                 "from users "
                 "where customer_id={0} and email_verified=1").format(orgId)
    else:
        query = ("select id, email "
                 "from users "
                 "where customer_id={0} and id={1}").format(orgId, userId)

    return query

def getOrgName(host, user, password, orgId):
    orgName = ''
    with util.SqlClient(host, user, password, dbName='orgstore') as dbCursor:
        query = ("select display_name "
                 "from organization "
                 "where id = {0}")
        dbCursor.execute(query.format(orgId))
        orgName = dbCursor.fetchall()[0][0]

    return orgName


if __name__ == '__main__':
    db = config['orgDb']
    users = getUserMap(db['host'], db['user'], db['password'], config['orgId'])
    print(list(users.items())[:5])
