#!/bin/bash
set -euo pipefail

# --- defaults (overridable via environment) ---------------------------------
: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=odoo}"
: "${DB_PASSWORD:=}"
: "${ODOO_ADMIN_PASSWD:=}"
: "${ODOO_WORKERS:=5}"
: "${ODOO_LIST_DB:=False}"
: "${ODOO_LOG_LEVEL:=info}"
: "${ODOO_LIMIT_MEMORY_SOFT:=1073741824}"   # 1 GiB per worker
: "${ODOO_LIMIT_MEMORY_HARD:=1342177280}"   # 1.25 GiB per worker
: "${ODOO_UPDATE_MODULES:=}"                # dev stage only, see Dockerfile
: "${ODOO_UPDATE_DB:=aidt_demo}"

launch_odoo() {
    if [ -z "$DB_PASSWORD" ] || [ -z "$ODOO_ADMIN_PASSWD" ]; then
        echo "Error: DB_PASSWORD and ODOO_ADMIN_PASSWD must be set." >&2
        exit 1
    fi

    # --- wait for postgres --------------------------------------------------
    for i in $(seq 1 30); do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q; then
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "Error: PostgreSQL at $DB_HOST:$DB_PORT not ready after 60s, giving up." >&2
            exit 1
        fi
        echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT... ($i/30)"
        sleep 2
    done

    # --- render config from template (only substitute our own variables) ----
    TEMPLATE="/etc/odoo/odoo.conf.template"
    if [ -f "/opt/odoo/docker/odoo.conf" ]; then
        TEMPLATE="/opt/odoo/docker/odoo.conf"
    fi
    export DB_HOST DB_PORT DB_USER DB_PASSWORD \
        ODOO_ADMIN_PASSWD ODOO_WORKERS ODOO_LIST_DB ODOO_LOG_LEVEL \
        ODOO_LIMIT_MEMORY_SOFT ODOO_LIMIT_MEMORY_HARD
    envsubst '$DB_HOST $DB_PORT $DB_USER $DB_PASSWORD $ODOO_ADMIN_PASSWD $ODOO_WORKERS $ODOO_LIST_DB $ODOO_LOG_LEVEL $ODOO_LIMIT_MEMORY_SOFT $ODOO_LIMIT_MEMORY_HARD' \
        < "$TEMPLATE" > /etc/odoo/odoo.conf

    # --- dev-only: register code changes on the custom aidt_* apps ---------
    # ODOO_UPDATE_MODULES is only baked as a build ENV in the Dockerfile's
    # `dev` stage, so this is a no-op in production (`runtime` stage/image).
    if [ -n "$ODOO_UPDATE_MODULES" ]; then
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc \
                "SELECT 1 FROM pg_database WHERE datname = '$ODOO_UPDATE_DB'" | grep -q 1 \
            && PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$ODOO_UPDATE_DB" -tAc \
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'ir_module_module'" | grep -q 1; then
            module_flag=-u   # already initialized: upgrade to pick up code/view/data changes
        else
            module_flag=-i   # first run: fresh/uninitialized database
        fi
        echo "Registering changes on $ODOO_UPDATE_DB: odoo-bin $module_flag $ODOO_UPDATE_MODULES"
        /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d "$ODOO_UPDATE_DB" \
            "$module_flag" "$ODOO_UPDATE_MODULES" --stop-after-init --no-http
    fi

    exec /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf "$@"
}

case "${1:-odoo}" in
    odoo)
        shift || true
        launch_odoo "$@"
        ;;
    -*)
        launch_odoo "$@"
        ;;
    *)
        # arbitrary command (e.g. `docker run ... python`, shell) — run as-is
        exec "$@"
        ;;
esac
