#!/bin/bash
# Signal CLI Captcha Helper
# Helps with manual captcha completion for Signal registration

set -euo pipefail

PHONE_NUMBER="+61485676958"
SIGNAL_CONFIG="/var/signal-cli"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

generate_captcha_url() {
    log "Opening captcha generation page..."
    log "Please solve the captcha and copy the 'signalcaptcha://' URL"
    log "URL: https://signalcaptchas.org/registration/generate.html"
    echo ""
    echo "After solving the captcha, you'll get a URL like:"
    echo "signalcaptcha://signal-hcaptcha-short.5fad97ac-7d06-4e44-b18a-b950b20148ff.registration.YOUR_TOKEN"
    echo ""
}

register_with_captcha() {
    local captcha_token="$1"
    log "Attempting registration with captcha token: ${captcha_token:0:50}..."

    result=$(sudo -u signal signal-cli --config "$SIGNAL_CONFIG" -a "$PHONE_NUMBER" register --captcha "$captcha_token" 2>&1)

    if echo "$result" | grep -q "Verification code"; then
        log "SUCCESS! SMS verification code sent to $PHONE_NUMBER"
        log "Please check your phone and enter the verification code when prompted"
        return 0
    elif echo "$result" | grep -q "Invalid captcha"; then
        log "ERROR: Invalid captcha token. Please try again."
        return 1
    else
        log "Registration result: $result"
        return 1
    fi
}

verify_code() {
    local verification_code="$1"
    log "Verifying code: $verification_code"

    result=$(sudo -u signal signal-cli --config "$SIGNAL_CONFIG" -a "$PHONE_NUMBER" verify "$verification_code" 2>&1)

    if echo "$result" | grep -q "Successfully"; then
        log "SUCCESS! Phone number $PHONE_NUMBER is now registered!"
        return 0
    else
        log "Verification result: $result"
        return 1
    fi
}

test_connection() {
    log "Testing Signal connection..."

    result=$(sudo -u signal signal-cli --config "$SIGNAL_CONFIG" -a "$PHONE_NUMBER" receive --timeout 10 2>&1)

    if echo "$result" | grep -q "User is not registered"; then
        log "Number not yet registered"
        return 1
    elif echo "$result" | grep -q "No new messages"; then
        log "SUCCESS! Number is registered and connected to Signal"
        return 0
    else
        log "Connection test result: $result"
        return 1
    fi
}

show_menu() {
    echo ""
    echo "Signal CLI Captcha Helper"
    echo "========================"
    echo "1. Generate captcha URL"
    echo "2. Register with captcha token"
    echo "3. Verify SMS code"
    echo "4. Test Signal connection"
    echo "5. Exit"
    echo ""
    read -p "Select option: " choice

    case $choice in
        1)
            generate_captcha_url
            ;;
        2)
            read -p "Enter captcha token: " token
            register_with_captcha "$token"
            ;;
        3)
            read -p "Enter SMS verification code: " code
            verify_code "$code"
            ;;
        4)
            test_connection
            ;;
        5)
            log "Exiting..."
            exit 0
            ;;
        *)
            log "Invalid option"
            ;;
    esac
}

main() {
    log "Signal CLI Captcha Helper initialized"
    log "Target number: $PHONE_NUMBER"

    while true; do
        show_menu
    done
}

main "$@"
