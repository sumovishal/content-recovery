#!/usr/bin/python3
import argparse
import logging

import util
import folder

#logger = logging.getLogger('sumologic')
#logger.setLevel(logging.ERROR)
#logger = logging.getLogger('urllib3')
#logger.setLevel(logging.INFO)


parser = argparse.ArgumentParser(description='Bring back dead content')
parser.add_argument('-o', dest='org', type=str, required=True, help='org id (in decimal)')
parser.add_argument('--dry-run', dest='dry', action='store_true', help='list down content to recover')
args = parser.parse_args()

util.config['dryRun'] = args.dry
util.config['orgId'] = args.org

logger = util.getLogger()
logger.setLevel(logging.INFO)
folder.recover()

