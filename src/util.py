import MySQLdb
import json
import logging
from sumologic import client


config = {
    'orgDb': {
        'host': "",
        'user': "",
        'password': ""
    },
    'appDb': {
        'host': "",
        'user': "",
        'password': ""
    },
    'api': {
        'accessId': "",
        'accessKey': "",
        'endpoint': ""
    },
}

logger = None


class SqlClient:
    def __init__(self, host, user, password, dbName='org'):
        self.conn = None
        self.host = host
        self.user = user
        self.password = password
        self.dbName = dbName

    def __enter__(self):
        self.conn = MySQLdb.connect(
            host=self.host,
            user=self.user,
            passwd=self.password,
            db=self.dbName)
        return self.conn.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()


def getApiClient():
    accessId = config['api']['accessId']
    accessKey = config['api']['accessKey']
    endpoint = config['api']['endpoint']
    return client.ApiClient(accessId, accessKey, endpoint)


def getLogger():
    global logger
    if not logger:
        logging.basicConfig(
            filename='recovery.log',
            format='%(asctime)-15s %(levelname)-5s [module=%(module)s] %(message)s',
            datefmt='%H:%M:%S',
            level=logging.INFO)

        logger = logging.getLogger('recovery')

    return logger

