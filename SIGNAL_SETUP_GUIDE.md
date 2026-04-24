# Signal Integration Setup Guide
## Get the Secure Anonymous Board System Working

---

## Current System Status

### ✅ Already Deployed
- **Backend API:** Running on http://47.84.234.54:8000
- **Frontend:** Running on http://47.84.234.54/
- **Database:** PostgreSQL 15 initialized and configured
- **Token Generator:** Deployed to https://qwe-rty.netlify.app
- **System Services:** All systemd services configured and running

### ⏳ Pending Setup
- **Signal CLI:** Not installed or configured
- **Signal Phone:** Not registered
- **Message Processing:** Not receiving Signal messages

---

## Phase 1: Local TOTP Validation (Testing Without Signal)

Before setting up Signal, verify the TOTP system works correctly.

### Step 1: Test Token Generator Locally

```bash
# Navigate to token-generator
cd /home/kyle46220/board/token-generator

# Install dependencies
npm install

# Update TOTP secret to match backend
# Open token-generator/src/main.ts and update:
const TOTP_SECRET = "3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ"; // From .env.example

# Start dev server
npm run dev

# Visit http://localhost:5173
# You should see a 6-digit code that updates every 5 minutes
```

### Step 2: Test Backend TOTP Validation

```bash
# Navigate to backend
cd /home/kyle46220/board/backend

# Create a test virtual environment
python -m venv test_venv
source test_venv/bin/activate

# Install dependencies
pip install -e .

# Create test script
cat > test_totp.py << 'EOF'
from app.totp import verify_totp

# Test with current time code (get from token generator)
print("Testing TOTP validation...")
print("Enter a 6-digit code from the token generator:")
code = input().strip()

result = verify_totp(code, "3MEW54GCJ5ATGUYEOYCGZ27AN6NQMSIZ")
print(f"Valid: {result}")
EOF

# Run test
python test_totp.py
```

### Expected Results
- Token generator shows 6-digit code updating every 5 minutes
- Backend validates codes correctly (both current and previous 5-minute window)
- If both work, TOTP system is functioning ✅

---

## Phase 2: Signal CLI Setup (VPS)

Signal CLI needs to be installed on the VPS to receive and process messages.

### Prerequisites
- Signal phone number (virtual SIM recommended for privacy)
- SSH access to VPS: `ssh -i /tmp/board-keypair.pem root@47.84.234.54`
- Root or sudo access on VPS

### Step 1: Install Signal CLI on VPS

```bash
# SSH into VPS
ssh -i /tmp/board-keypair.pem root@47.84.234.54

# Update system
yum update -y

# Install Java (required for Signal CLI)
yum install -y java-17-openjdk-headless

# Download and install Signal CLI
cd /opt
wget https://github.com/AsamK/signal-cli/releases/download/v0.12.1/signal-cli-0.12.1.tar.gz
tar -xzf signal-cli-0.12.1.tar.gz
mv signal-cli-0.12.1 signal-cli
ln -s /opt/signal-cli/bin/signal-cli /usr/local/bin/signal-cli

# Verify installation
signal-cli --version
```

### Step 2: Register Signal Phone Number

```bash
# IMPORTANT: Use a phone number you have access to for verification
signal-cli -u +15551234567 register
# You'll receive a verification code via SMS

# Verify the number
signal-cli -u +15551234567 verify VERIFICATION_CODE

# Enable JSON-RPC mode (required for the application)
signal-cli -u +15551234567 jsonRpc start --socket /var/run/signal-cli/socket

# Create socket directory
mkdir -p /var/run/signal-cli
chown nginx:nginx /var/run/signal-cli
chmod 755 /var/run/signal-cli
```

### Step 3: Configure systemd Service

```bash
# Create signal-cli service file
cat > /etc/systemd/system/signal-cli.service << 'EOF'
[Unit]
Description=Signal CLI JSON-RPC Service
After=network.target

[Service]
Type=simple
User=nginx
ExecStart=/usr/local/bin/signal-cli -u +15551234567 jsonRpc start --socket /var/run/signal-cli/socket
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable signal-cli
systemctl start signal-cli
systemctl status signal-cli
```

---

## Phase 3: Connect Backend to Signal CLI

### Step 1: Update Backend Configuration

```bash
# On VPS, edit the backend configuration
vim /opt/board/backend/.env

# Add/update these lines:
SIGNAL_SOCKET=/var/run/signal-cli/socket
SIGNAL_PHONE_NUMBER=+15551234567

# Save and exit
```

### Step 2: Restart Backend Service

```bash
# Restart the board service to pick up new configuration
systemctl restart board

# Check logs for Signal connection status
journalctl -u board -f
# Look for: "Connected to signal-cli socket"
```

---

## Phase 4: Full Integration Testing

### Step 1: Test Message Reception

```bash
# From your personal phone with Signal app:
# Send a test message to the registered Signal number

# Format: "<TOTP_CODE> <MESSAGE>"
# Example: "123456 Hello World"

# Check backend logs
journalctl -u board -f
# Should see message processing logs
```

### Step 2: Test Post Creation

1. **Generate TOTP code** from token generator (https://qwe-rty.netlify.app)
2. **Send Signal message** to the registered number:
   ```
   123456 This is a test post
   ```
3. **Check the board** at http://47.84.234.54/
4. **Verify** the post appears in the grid

### Step 3: Test Different Content Types

#### Text Post
```
123456 Just some text content
```

#### Image Post
- Generate TOTP code
- Attach image to Signal message
- Send: "123456 " (with image attachment)

#### Link Post
```
123456 https://example.com/article
```
(Should scrape OG tags and create preview)

#### Video Post
- Generate TOTP code
- Attach video to Signal message
- Send: "123456 " (with video attachment)

---

## Phase 5: Troubleshooting

### Issue 1: Signal CLI Not Starting

```bash
# Check service status
systemctl status signal-cli

# View logs
journalctl -u signal-cli -f

# Common fixes:
# - Verify Java is installed
# - Check socket permissions
# - Ensure phone number is properly registered
```

### Issue 2: Backend Can't Connect to Signal

```bash
# Check socket exists
ls -la /var/run/signal-cli/socket

# Test manual connection
signal-cli -u +15551234567 jsonRpc start --socket /var/run/signal-cli/socket

# Check backend logs for connection errors
journalctl -u board -f
```

### Issue 3: TOTP Validation Failing

```bash
# Verify secrets match on both sides
# Backend: Check /opt/board/backend/.env
# Token Generator: Check embedded secret in code

# Test TOTP generation manually
python -c "import pyotp; print(pyotp.TOTP('YOUR_SECRET').now())"

# Compare with token generator output
```

### Issue 4: Messages Not Appearing on Board

```bash
# Check Signal CLI received message
signal-cli -u +15551234567 receive --timeout 10

# Check backend logs for processing
journalctl -u board -f

# Verify database connection
psql -U board -d board -c "SELECT * FROM posts;"
```

---

## Security Considerations

### Signal Privacy
- Use a virtual phone number (not your personal number)
- Enable "Sealed Sender" in Signal settings
- Don't share the registered phone number publicly

### TOTP Secret
- Keep secret secure and never expose in logs
- Generate a new random secret (not the one in .env.example)
- Store in secure environment variables

### Signal Phone Number
- This number can be spammed/messaged
- Consider using a dedicated number for the board
- Monitor for abuse and block if necessary

---

## Testing Checklist

### Basic Functionality
- [ ] Token generator produces valid TOTP codes
- [ ] Backend validates TOTP codes correctly
- [ ] Signal CLI is running and connected
- [ ] Backend connects to Signal CLI socket
- [ ] Text messages create posts
- [ ] Image attachments work
- [ ] Video attachments work
- [ ] Link scraping works
- [ ] Posts appear on the board
- [ ] Admin token allows deletion

### Edge Cases
- [ ] Expired TOTP codes are rejected
- [ ] Previous window codes work (within limits)
- [ ] Invalid formats are rejected
- [ ] Large files are rejected
- [ ] Malformed URLs are handled
- [ ] Connection drops are recovered
- [ ] Multiple concurrent messages work

---

## Production Deployment Steps

### 1. Use Real Secrets
```bash
# Generate new TOTP secret (not from .env.example)
python -c "import pyotp; print(pyotp.random_base32())"

# Update backend .env
TOTP_SECRET=<new_secret>

# Update token generator and rebuild
# Deploy to Netlify
```

### 2. Configure Production Signal Number
- Register dedicated Signal phone number
- Enable all features (groups, attachments, etc.)
- Test thoroughly before going live

### 3. Add SSL/TLS
```bash
# Install certbot
yum install -y certbot python3-certbot-nginx

# Generate certificate
certbot --nginx -d 47.84.234.54

# Auto-renewal is configured automatically
```

### 4. Setup Monitoring
- Configure log rotation
- Set up uptime monitoring
- Monitor disk usage (media files)
- Track error rates

### 5. Document Procedures
- Recovery procedures
- Backup schedules
- Contact information
- Escalation paths

---

## Next Steps After Signal Setup

1. **Performance Testing**
   - Load test the board with multiple posts
   - Test concurrent Signal messages
   - Monitor system resources

2. **Security Hardening**
   - Implement SSL/TLS
   - Add rate limiting adjustments
   - Configure fail2ban for SSH

3. **User Guide**
   - Document how to post to the board
   - Explain TOTP code generation
   - Provide troubleshooting help

4. **Monitoring Setup**
   - Application monitoring
   - Error tracking
   - Performance metrics

---

## Summary

To get the system working, you need to:
1. ✅ Test TOTP locally (Phase 1)
2. 🔲 Install Signal CLI on VPS (Phase 2)
3. 🔲 Connect backend to Signal (Phase 3)
4. 🔲 Test full integration (Phase 4)

Start with Phase 1 to verify the authentication system works, then proceed to Signal CLI setup on the VPS.
