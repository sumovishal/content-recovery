import util

def getUserMap(host, user, password, orgId):
    users = dict()

    with util.SqlClient(host, user, password, dbName='orgstore') as dbCursor:
        query = ("select id, email "
                 "from users "
                 "where customer_id={0} and email_verified=1")
        dbCursor.execute(query.format(orgId))
        for row in dbCursor.fetchall():
            users[row[0]] = row[1]

    return users

def getOrgName(host, user, password, orgId):
    orgName = ''
    with util.SqlClient(host, user, password, dbName='orgstore') as dbCursor:
        query = ("select display_name "
                 "from organization "
                 "where id = {0}")
        dbCursor.execute(query.format(orgId))
        orgName = dbCursor.fetchall()[0]

    return orgName


if __name__ == '__main__':
    db = config['orgDb']
    users = getUserMap(db['host'], db['user'], db['password'], config['orgId'])
    print(list(users.items())[:5])
