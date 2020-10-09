import logging

LOGGER_NAME = 'recovery'
LOG_FORMAT = '%(asctime)-15s %(levelname)-5s [module=%(module)s] %(message)s'
logging.basicConfig(filename='recovery.log',
                    format=LOG_FORMAT,
                    datefmt='%H:%M:%S'
                    level=logging.DEBUG)
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)


