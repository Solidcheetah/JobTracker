#!/bin/bash
# Runs once, on first initialisation of the postgres data volume.
#
# Creates the unprivileged role the API connects as. This role must NOT be a
# superuser and must not own the tables: Postgres lets superusers bypass RLS
# outright, and `FORCE ROW LEVEL SECURITY` is what makes a policy apply to a
# table's owner. Keeping the app role distinct from the migration role is what
# gives `application_owner_isolation` any teeth.
set -euo pipefail

: "${APP_USER:?APP_USER not set}"
: "${APP_PASSWORD:?APP_PASSWORD not set}"

psql_admin() {
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" "$@"
}

# psql does not interpolate its variables inside dollar-quoted blocks, so the
# existence check happens here rather than in a DO block.
if [ -z "$(psql_admin -tAc "SELECT 1 FROM pg_roles WHERE rolname = '${APP_USER}'")" ]; then
    psql_admin -c "CREATE ROLE \"${APP_USER}\" LOGIN PASSWORD '${APP_PASSWORD}'"
    echo "created role ${APP_USER}"
else
    echo "role ${APP_USER} already exists"
fi

psql_admin -v app_user="$APP_USER" -v db_name="$POSTGRES_DB" <<-'EOSQL'
	GRANT CONNECT ON DATABASE :"db_name" TO :"app_user";
	GRANT USAGE ON SCHEMA public TO :"app_user";

	-- Alembic has not run yet, so the interesting grants are the DEFAULT ones;
	-- the ALL TABLES pass is here for re-runs against a populated schema.
	GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
	GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_user";

	ALTER DEFAULT PRIVILEGES IN SCHEMA public
	    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
	ALTER DEFAULT PRIVILEGES IN SCHEMA public
	    GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";
EOSQL
