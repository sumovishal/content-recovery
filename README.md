# Content Recovery With Some Hacks
*****This is a poor man's solution to recover deleted folder, searches, and dashboards**
This is hacky solution with some assumptions. It SHOULD be used with caution. Recovery is a two step process:
1. Restore a RDS snapshot that still has deleted content.
2. Read data from snapshot and use Content Import API to recreate it.

See [Limitations](https://github.com/sumovishal/content-recovery/blob/master/src/README.md#limitations) section for
details about what is not recovered as part of recovery.

## Restoring DB Snapshot to a new RDS instance
Related SCR: https://jira.kumoroku.com/jira/browse/SUMO-118177

Snapshot Steps for org db (app RDS):
1. Restore from snapshot copy (https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_RestoreFromSnapshot.html)
   - Pick a DB instance name
   - Choose DB instance class (same as original org instance type)
   - Choose right subnet group (same as original org db)
   - Choose an availability zone

2. In AWS console, modify security groups for the newly restored db instance to include access from hop node (by adding
   appropriate security group).

3. Go to dsh and get details for the app RDS instance. Use login credentials for app rds instance to login to
   newly restored instance.

Perform same steps to recover org-store db(org RDS instance).

## Content Recovery from a snapshot
Related SCR: https://jira.kumoroku.com/jira/browse/SUMO-118260

For content recovery, we will use hop node to run recovery steps. We need to install some dependencies before we can
use recovery scripts.

**Make sure python3.7+ is installed on the hop node as scripts work with python3.7+.**

Below are the list of steps to install all the required dependencies:

1. Create a new instance of hop node
```
cluster resize -i 1 hop
dep start -i hop --instances-only
```

2. Install MySQL db package
```
sudo apt-get install python3-mysqldb
```

3. Install pip and python packages
```
sudo apt install python3-pip
pip3 install requests
```

4. Clone the content-recovery repo on the hop node `git clone https://github.com/sumovishal/content-recovery.git`

5. Read the `README.md` under `src` folder to run the recovery script.

