#!/usr/bin/python3
import argparse
import logging
import sys

import util
import org
import folder

#logger = logging.getLogger('sumologic')
#logger.setLevel(logging.ERROR)
#logger = logging.getLogger('urllib3')
#logger.setLevel(logging.INFO)


parser = argparse.ArgumentParser(description='Bring back dead content')
parser.add_argument('-o', dest='org', type=str, required=True, help='org id (in decimal)')
parser.add_argument('-u', dest='user', type=str, required=False,
                    help='user id (in decimal) if recovery needs to run for a user only')
parser.add_argument('--dry-run', dest='dry', action='store_true', help='list down content to recover')
args = parser.parse_args()

# validate all required config parms are set
if util.config['orgDb']['host'] is None:
    sys.exit("Set the org db endpoint")

if util.config['orgDb']['user'] is None:
    sys.exit("Set the org db user")

if util.config['orgDb']['password'] is None:
    sys.exit("Set the org db password")

if util.config['appDb']['host'] is None:
    sys.exit("Set the app db endpoint")

if util.config['appDb']['user'] is None:
    sys.exit("Set the app db user")

if util.config['appDb']['password'] is None:
    sys.exit("Set the app db password")

if not args.dry and util.config['api']['endpoint'] is "":
    sys.exit("Set the API endpoint for deployment where you want to recover content")


util.config['dryRun'] = args.dry
util.config['orgId'] = args.org
util.config['userId'] = args.user

orgDb = util.config['orgDb']
util.config['orgName'] = org.getOrgName(orgDb['host'], orgDb['user'], orgDb['password'], util.config['orgId'])

logger = util.getLogger()
logger.setLevel(logging.INFO)
# disable logs on dry run
if args.dry:
    logging.disable(logging.CRITICAL)

# start recovery
folder.recover()

