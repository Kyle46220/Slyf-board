# Ralph Loop Agent Patterns - Signal CLI Registration

## Known Signal CLI Issues and Patterns

### Registration Methods to Try (in order)
1. **Standard SMS registration with captcha**
   - Command: `signal-cli --config /var/signal-cli register +61485676958 --captcha <token>`
   - Requires captcha token from Signal CLI

2. **Voice call registration**
   - Command: `signal-cli --config /var/signal-cli register +61485676958 --voice --captcha <token>`
   - Alternative if SMS fails

3. **Reregistration attempt**
   - Command: `signal-cli --config /var/signal-cli register +61485676958 --captcha <token> --force-sms`
   - Try if previous registration attempts failed

4. **Without captcha (if available)**
   - Command: `signal-cli --config /var/signal-cli register +61485676958`
   - May work if captcha servers are down

### Daemon Management
- **Check daemon status:** `systemctl status signal-cli`
- **Stop daemon:** `systemctl stop signal-cli`
- **Start daemon:** `systemctl start signal-cli`
- **Restart daemon:** `systemctl restart signal-cli`
- **View logs:** `journalctl -u signal-cli -f`

### Network Troubleshooting
- **Test Signal connectivity:** `curl -I https://textsecure-service.whispersystems.org`
- **Test captcha server:** `curl -I https://signalcaptchas.org`
- **Check DNS:** `nslookup textsecure-service.whispersystems.org`
- **Test from VPS:** Run curl commands from the VPS, not local

### Common Error Patterns
1. **Captcha 404 errors:** Signal captcha servers may be temporarily down
2. **"Connection closed!" errors:** Network issues to Signal linking servers
3. **"Rate limited" errors:** Wait 30 minutes before retrying
4. **"Already registered" errors:** Number may be registered elsewhere, need to deregister

### Verification Command
Always verify with: `sudo -u signal signal-cli --config /var/signal-cli receive --timeout 30`

Success indicators:
- Command runs without errors
- Output shows connection to Signal servers
- Can receive messages (even if empty is fine)
