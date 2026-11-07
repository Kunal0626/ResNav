#!/bin/sh
# Applied once, by the mysql image's own entrypoint, the first time the data
# volume is empty. Files in /docker-entrypoint-initdb.d run in lexical order,
# which is why this is a single script rather than the SQL files directly:
# the order across db/schema, db/procedures, db/triggers, db/views and
# db/seed matters, and a flat alphabetical sort would not respect it.
#
# The DELIMITER lines in the trigger and procedure files are client
# instructions, not SQL, so they are fed to the mysql CLIENT rather than to
# the server over a socket library.
set -eu

DB="${MYSQL_DATABASE:-resnav}"
run() {
    echo "  applying $1"
    mysql --protocol=socket -uroot -p"${MYSQL_ROOT_PASSWORD}" "$DB" < "$1"
}

echo "==> building the ResNav schema"
for dir in schema procedures triggers views seed; do
    for file in /sql/"$dir"/*.sql; do
        [ -e "$file" ] || continue
        run "$file"
    done
done

echo "==> done"
mysql --protocol=socket -uroot -p"${MYSQL_ROOT_PASSWORD}" "$DB" -e "
  SELECT 'tables'   AS object, COUNT(*) AS n FROM information_schema.TABLES   WHERE TABLE_SCHEMA='$DB' AND TABLE_TYPE='BASE TABLE'
  UNION ALL SELECT 'views',    COUNT(*) FROM information_schema.VIEWS         WHERE TABLE_SCHEMA='$DB'
  UNION ALL SELECT 'triggers', COUNT(*) FROM information_schema.TRIGGERS      WHERE TRIGGER_SCHEMA='$DB'
  UNION ALL SELECT 'routines', COUNT(*) FROM information_schema.ROUTINES      WHERE ROUTINE_SCHEMA='$DB'
  UNION ALL SELECT 'providers', COUNT(*) FROM Providers
  UNION ALL SELECT 'requests',  COUNT(*) FROM Requests;"
