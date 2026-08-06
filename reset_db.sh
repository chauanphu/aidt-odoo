#!/bin/bash
# Script reset va khoi tao lai Database 'aidt' mac dinh tu dau

set -e

DB_NAME="aidt"
CONTAINER_DB="aidt-odoo-dev-db-1"
CONTAINER_ODOO="aidt-odoo-dev-odoo-1"

echo "==> Dang ngat ket noi toi CSDL..."
docker exec $CONTAINER_DB psql -U odoo -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('aidt_demo', '$DB_NAME') AND pid <> pg_backend_pid();" || true

echo "==> Dang xoa CSDL cu..."
docker exec $CONTAINER_DB dropdb -U odoo --if-exists aidt_demo || true
docker exec $CONTAINER_DB dropdb -U odoo --if-exists $DB_NAME || true

echo "==> Dang tao CSDL sach '$DB_NAME'..."
docker exec $CONTAINER_DB createdb -U odoo -O odoo $DB_NAME

echo "==> Dang nap he thong va du lieu mac dinh (aidt_vanban_demo)..."
docker exec $CONTAINER_ODOO /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d $DB_NAME -i aidt_vanban_demo --stop-after-init

echo "==> Khoi tao CSDL '$DB_NAME' va du lieu mac dinh thanh cong!"
