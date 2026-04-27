---
name: debug-signal
description: Debug Signal CLI integration issues - message reception, connection problems, TOTP validation failures
triggers:
  - "Signal not receiving messages"
  - "Messages not showing on board"
  - "TOTP validation failing"
  - "Signal CLI connection error"
---

# Signal Integration Debugging

## 1. Check Signal CLI Status
```bash
sudo systemctl status signal-cli
sudo journalctl -u signal-cli -n 50
```
- Must show "active (running)"
- Should have "Started JSON-RPC server"
- Look for "Envelope from" lines (incoming messages)

## 2. Verify Socket Connection
```bash
ls -la /var/run/signal-cli/socket
# Must exist and be readable by kyle46220 user
```

## 3. Check Board Service Logs
```bash
sudo journalctl -u board -n 50 | grep -E "Signal|Body:|processed|Invalid TOTP"
```
- Look for "Found message body:" 
- Look for "Message from logs processed:"
- Check for "Invalid TOTP code" (expired codes are OK)

## 4. Test Signal CLI Directly
```bash
signal-cli --config /var/signal-cli listAccounts
# Should show +61485676958
```

## 5. Verify Message Reception
```bash
# Watch for new messages in real-time
sudo journalctl -u signal-cli -f | grep -E "Envelope|Body:"
```
Send test message, should see "Envelope from" and "Body: XXXXXX"

## 6. Check TOTP Validation
```bash
# Generate current TOTP
cd /opt/backend && source venv/bin/activate
python3 -c "import pyotp; print(pyotp.TOTP('3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ').now())"
```
Use this code in test message

## 7. Verify Database
```bash
sudo -u postgres psql board -c "SELECT id, content_type, created_at FROM posts ORDER BY created_at DESC LIMIT 5;"
```
Check if new posts appearing

## Common Issues & Fixes

### Issue: "Messages already being received" error
**Cause:** Signal CLI receiving via log parsing (working as designed)
**Action:** No fix needed, log parsing is fallback

### Issue: No "Envelope from" in logs
**Cause:** Signal CLI daemon not receiving messages
**Fix:** Restart Signal CLI service

### Issue: "Invalid TOTP code" but code is correct
**Cause:** TOTP expired (>15 minutes old)
**Fix:** Generate fresh code, test again

### Issue: Board service not processing messages
**Cause:** Log parsing not running or crashed
**Fix:** Check board logs, restart if needed

## Success Indicators
✅ Signal CLI shows "Envelope from" with messages
✅ Board logs show "Found message body:"  
✅ Board logs show "Message from logs processed:"
✅ New posts appear in database
✅ Posts display on board
