# Content Recovery With Some Hacks
*****This is a poor man's solution to recover deleted folder, searches, and dashboards**
This is hacky solution with some assumptions. It SHOULD be used with caution. Recovery is a two step process:
1. Restore a RDS snapshot that still has deleted content.
2. Read data from snapshot and use Content Import API to recreate it.


## Restoring DB Snapshot to a new RDS instance
Related SCR: https://jira.kumoroku.com/jira/browse/SUMO-118177

Snapshot Steps:
1. Restore from snapshot copy (https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_RestoreFromSnapshot.html)
   - Pick a DB instance name
   - Choose DB instance class (same as original org-store instance type)
   - Choose right subnet group (same as original org-store db)
   - Choose an availability zone

2. In AWS console, modify security groups for the newly restored db instance to include access from org-service node.

3. Go to dsh and get details for the newly restored db instance.


## Content Recovery from a snapshot
Related SCR: https://jira.kumoroku.com/jira/browse/SUMO-118260

For content recovery, we will use hop node to run recovery steps. We need to install some dependencies before we can
use recovery scripts. Below are the list of steps to install all the required dependencies:

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

4. Copy `src` folder to the new hop node.

5. Read the `README.md` under `src` folder to run the recovery script.

