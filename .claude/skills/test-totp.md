---
name: test-totp
description: Test TOTP authentication system - generate codes, validate timing, verify integration
triggers:
  - "test TOTP"
  - "verify TOTP code"
  - "check authentication"
  - "token generator not working"
---

# TOTP Testing

## Generate Current TOTP Code

### Local Testing
```bash
# Using backend venv
cd backend && source venv/bin/activate
python3 -c "import pyotp; print(pyotp.TOTP('3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ').now())"

# On GCP
gcloud compute ssh board-server --zone=australia-southeast1-a --command "cd /opt/backend && source venv/bin/activate && python3 -c \"import pyotp; print(pyotp.TOTP('3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ').now())\""
```

### Web Interface
Visit: https://qwe-rty.netlify.app/

Code updates every 5 minutes.

## TOTP Validation Rules
- **Code Length:** 6 digits
- **Algorithm:** SHA1
- **Period:** 300 seconds (5 minutes)
- **Validity:** 15 minutes (current + previous windows)
- **Secret:** `3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ`

## Test Message Format
```
<TOTP_CODE> <your_message>
```

Examples:
- Text: `123456 Hello world`
- Image: Attach image + `123456 ` (with space after code)
- Link: `123456 https://example.com`

## Testing Procedure

### 1. Generate Valid Code
```bash
# Get current code
cd backend && source venv/bin/activate
CODE=$(python3 -c "import pyotp; print(pyotp.TOTP('3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ').now())")
echo "Current TOTP: $CODE"
```

### 2. Send Test Message
- Open Signal
- Message: +61485676958
- Content: `$CODE test message from CLI`

### 3. Verify Processing
```bash
# Check Signal CLI logs
sudo journalctl -u signal-cli -f | grep "Body:"

# Check board processing
sudo journalctl -u board -f | grep -E "Found message body|processed|Invalid TOTP"
```

### 4. Verify Display
- Visit: http://35.213.252.2/
- Message should appear within 10 seconds
- Check for content display

## Common Issues

### Issue: "Invalid TOTP code from logs"
**Cause:** Code expired (>15 minutes old)
**Fix:** Generate fresh code, test again

### Issue: Token generator shows dashes
**Cause:** VITE_TOTP_SECRET not set at build time
**Fix:**
```bash
netlify env:set VITE_TOTP_SECRET 3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ --site=qwe-rty.netlify.app
netlify deploy --prod
```

### Issue: Local TOTP matches but fails validation
**Cause:** Time synchronization or secret mismatch
**Fix:**
```bash
# Verify secrets match
# Backend: .env file on GCP
# Token generator: Netlify env vars
# Local: backend/.env or venv activation
```

### Issue: Code works sometimes, fails others
**Cause:** Testing at window boundaries (5-min changes)
**Fix:** Generate code, wait 30 seconds, then test

## TOTP Window Verification
```python
import pyotp
from datetime import datetime, timedelta

secret = "3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ"
totp = pyotp.TOTP(secret)

# Current window
current = totp.now()

# Previous windows (up to 3 back = 15 minutes)
windows = [totp.at(int((datetime.now() - timedelta(minutes=i*5)).timestamp()))
           for i in range(3)]

print(f"Current: {current}")
print(f"Valid windows: {windows}")
```

## Security Notes
- Never commit TOTP_SECRET to git
- Secret must match between backend and token generator
- 15-minute window balances security vs usability
- Failed TOTP attempts logged but not stored
