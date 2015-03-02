import sys
from pprint import pprint
from launchpad_reporting.db import db


old_db_name = sys.argv[1]
new_db_name = sys.argv[2]

found = False

lst = db.connection.database_names()
pprint(lst)
for entry in lst:
    if entry == new_db_name:
        found = True

if found:
    print "Dropping already existing database '%s'" % new_db_name
    db.connection.drop_database(new_db_name)

db.connection.admin.command('copydb',
                            fromdb=old_db_name,
                            todb=new_db_name)

db.connection.drop_database(old_db_name)
