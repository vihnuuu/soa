set -euo pipefail

KCADM="/opt/keycloak/bin/kcadm.sh"
SERVER="${KC_SERVER:-http://keycloak:8080}"
REALM="${KC_REALM:-library}"
CLIENT="account-console"

SCOPES=("basic" "profile" "roles")

echo "keycloak-init: waiting for Keycloak..."

READY=false

for i in {1..60}; do
    if "$KCADM" config credentials \
        --server "$SERVER" \
        --realm master \
        --user "$KEYCLOAK_ADMIN" \
        --password "$KEYCLOAK_ADMIN_PASSWORD" \
        >/dev/null 2>&1; then
        READY=true
        break
    fi

    echo "keycloak-init: waiting ($i/60)..."
    sleep 3
done

if [ "$READY" != "true" ]; then
    echo "ERROR: Keycloak is not ready"
    exit 1
fi

echo "keycloak-init: Keycloak is ready"

CID=$("$KCADM" get clients \
    -r "$REALM" \
    -q "clientId=$CLIENT" \
    --fields id \
    --format csv \
    --noquotes | tr -d '\r\n')

if [[ ! "$CID" =~ ^[0-9a-fA-F-]{36}$ ]]; then
    echo "ERROR: invalid client ID: $CID"
    exit 1
fi

echo "keycloak-init: found client $CLIENT"

ALL_SCOPES=$("$KCADM" get client-scopes \
    -r "$REALM" \
    --fields id,name \
    --format csv \
    --noquotes)

for S in "${SCOPES[@]}"; do

    SID=""

    while IFS=',' read -r ID NAME; do
        ID="${ID//$'\r'/}"
        NAME="${NAME//$'\r'/}"

        if [ "$NAME" = "$S" ]; then
            SID="$ID"
            break
        fi
    done <<< "$ALL_SCOPES"

    if [[ ! "$SID" =~ ^[0-9a-fA-F-]{36}$ ]]; then
        echo "ERROR: scope $S not found or invalid ID"
        exit 1
    fi

    "$KCADM" update \
        "clients/$CID/default-client-scopes/$SID" \
        -r "$REALM" \
        -n

    echo "keycloak-init: $CLIENT <- $S (default)"
done

echo "keycloak-init: done"
