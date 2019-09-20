## Content Recovery with some hacks
*****This is a poor man's solution to recover folder, searches, and dashboards for an org from a RDS snapshot.**

This is highly customized for the use-case (Remedy) we had to recover. Some gotchas:
1. We did not recover "autocomplete" data in searches. Remedy was not using it.
2. We hacked timeranges in panels in dashboards. We didn't write a converter to convert timeranges (see report.py#toTimeRange).
3. Search schedules are not recovered.
4. Permissions are not recovered.

Drilldown features doesn't work in dashboards after recovery. Drilldown feature needs `properties_blob` column in `panels`
table to set. Content import api doesn't set the `properties_blob` column. To fix that, we copy over properties_blob
from snapshot to the newly created dashboards. See `drilldown.py` for details.


## Requirements
  - Python 3.5+
  - [Requests](http://docs.python-requests.org/en/master/) package
  - python-mysqldb package

## Usage
### To recover content
1. Fill in configuration details in `config` object in `util.py`.
2. Do a dry run
   ```
   ./recover.py -o {orgId} --dry-run >data 2>err
   ```
3. If everything looks good in dry run logs, do the actual recovery
   ```
   ./recover.py -o {orgId} >data 2>err
   ```

### To fix drilldown feature
1. Fill in configuration details in `config` object in `drilldown.py`
2. Do a dry run
   ```
   ./drilldown.py -s {orgIdInSnapshot} -d {newOrgIdInRDS} --dry-run >data 2>err
   ```
3. If everything looks good in dry run logs, run `drilldown.py`.
   ```
   ./drilldown.py -s {orgIdInSnapshot} -d {newOrgIdInRDS} >data 2>err
   ```
