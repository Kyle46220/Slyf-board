#!/bin/bash
# Signal CLI Registration Monitor
# Keeps trying to register +61485676958 until successful

set -euo pipefail

PHONE_NUMBER="+61485676958"
SIGNAL_CONFIG="/var/signal-cli"
MAX_RETRIES=100
RETRY_DELAY=300  # 5 minutes between retries

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

check_registration() {
    sudo -u signal signal-cli --config "$SIGNAL_CONFIG" -a "$PHONE_NUMBER" receive --timeout 10 2>&1
}

attempt_registration() {
    log "Attempting registration for $PHONE_NUMBER..."

    # Try standard registration
    result=$(sudo -u signal signal-cli --config "$SIGNAL_CONFIG" -a "$PHONE_NUMBER" register 2>&1)

    if echo "$result" | grep -q "Captcha required"; then
        log "Captcha required - need manual intervention or wait for eSIM activation"
        return 1
    elif echo "$result" | grep -q "Verification code"; then
        log "SMS verification code sent - number may be active!"
        return 0
    else
        log "Registration attempt result: $result"
        return 1
    fi
}

main() {
    log "Starting Signal registration monitor for $PHONE_NUMBER"
    log "Infrastructure ready: DNS configured, hosts file mapped, Signal CLI running"

    for ((i=1; i<=MAX_RETRIES; i++)); do
        log "Attempt $i/$MAX_RETRIES"

        # First check if already registered
        if check_registration; then
            log "SUCCESS: Number is already registered and working!"
            exit 0
        fi

        # Try to register
        if attempt_registration; then
            log "Registration initiated successfully - waiting for SMS verification"
            exit 0
        fi

        if [ $i -lt $MAX_RETRIES ]; then
            log "Waiting ${RETRY_DELAY}s before next attempt..."
            sleep $RETRY_DELAY
        fi
    done

    log "Max retries reached. Please check eSIM activation status."
    exit 1
}

main "$@"
