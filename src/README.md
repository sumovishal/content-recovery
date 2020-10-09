## Content Recovery with some hacks
**This is a poor man's solution to recover folder, searches, and dashboards for an org from a RDS snapshot.**

We only attempt to recover saved searches and dashboards. Not all information is recovered. See next section for
more details.

### Limitations
1. "autocomplete" data in searches is not recovered.
2. Timeranges for panels in dashboards are recovered via a hacky solution (see report.py#toTimeRange).
3. Search schedules are not recovered.
4. Permissions are not recovered.

### Dashboard Drilldown Feature
Drilldown feature doesn't work in dashboards after recovery. Drilldown feature needs `properties_blob` column in
`panels` table to set. Content import api doesn't set the `properties_blob` column. To fix that, we copy over
`properties_blob` from snapshot to the newly created dashboards. See `drilldown.py` for details.


## Requirements
  - Python 3.7+
  - [Requests](http://docs.python-requests.org/en/master/) package
  - python3-mysqldb package

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
