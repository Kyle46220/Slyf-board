# Signal CLI VPS Deployment Design

**Date:** 2026-04-23
**Project:** Secure Anonymous Board
**Status:** Design Approved

## Overview

Deploy Signal CLI entirely on the remote VPS (47.84.234.54) using existing Signal Desktop credentials from user's Windows machine. This enables the board backend to send and receive Signal messages without any local dependencies.

## Architecture

### Remote Components (VPS 47.84.234.54)

- **Signal CLI v0.14.3** (native build) - Command-line interface for Signal
- **Signal CLI Daemon** - systemd service running continuously with JSON-RPC interface
- **Board Backend** (FastAPI) - Handles TOTP validation and post management
- **PostgreSQL Database** - Stores posts and metadata
- **Frontend** (React/Vite) - Static files served by Nginx
- **Nginx** - Reverse proxy for frontend and API

### Data Flow

1. **Incoming Messages:** Signal CLI receives messages from Signal network
2. **Backend Monitoring:** FastAPI backend polls Signal CLI via JSON-RPC socket
3. **TOTP Validation:** Backend extracts and validates 6-digit TOTP codes
4. **Post Storage:** Validated posts stored in PostgreSQL with UUID-based hashes
5. **Real-time Updates:** SSE streaming pushes new posts to frontend
6. **Confirmation:** Backend sends confirmation messages via Signal CLI

## Implementation Details

### Signal CLI Configuration

**Installation Location:** `/opt/signal-cli` (native build, no Java required)

**Configuration Directory:** `/var/signal-cli/`
- `data/` - Signal client data and credentials
- `accounts.json` - Account configuration

**JSON-RPC Socket:** `/var/run/signal-cli/socket`

**Systemd Service:** `/etc/systemd/system/signal-cli.service`
- Runs as `signal` user
- Auto-restart on failure
- Socket-based JSON-RPC interface

### Credential Transfer Process

1. **Extract from Windows Signal Desktop:**
   - Source: `C:\Users\{username}\AppData\Roaming\Signal\`
   - Files: `config.json`, database files, encryption keys

2. **Transfer to VPS:**
   - Copy to `/var/signal-cli/data/` on VPS
   - Set proper ownership (`signal:signal`)
   - Verify permissions

3. **Configuration:**
   - Update Signal CLI to use transferred credentials
   - Test connectivity and message sending/receiving

### Board Backend Integration

**Signal CLI Communication:**
- JSON-RPC calls to `/var/run/signal-cli/socket`
- Methods: `send()`, `receive()`, `listContacts()`
- Background polling for incoming messages

**TOTP Validation:**
- Extract 6-digit code from Signal message body
- Validate against board's TOTP secret
- Accept current or previous 5-minute window (15-minute total window)

**Message Processing:**
- Strip sender metadata for anonymity
- Process media attachments (images/video)
- Generate post hashes with UUID
- Apply security fixes (rate limiting, input validation, CORS)

### Deployment Structure

```
/opt/signal-cli/                    # Signal CLI binary
/var/signal-cli/                    # Signal CLI configuration
  ├── data/                        # Credentials and data
  │   ├── config.json             # Signal configuration
  │   ├── accounts.json           # Account info
  │   └── database files          # Signal message database
  └── ...

/var/run/signal-cli/                # Runtime directory
  └── socket                       # JSON-RPC socket

/etc/systemd/system/signal-cli.service  # Service definition

/home/kyle46220/board/              # Board application
  ├── backend/                     # FastAPI backend
  ├── frontend/                    # React frontend
  └── nginx/                       # Nginx configuration
```

## Security Considerations

- **Signal CLI runs as non-root user** (`signal` user)
- **Socket permissions** restricted to board backend user
- **TOTP validation** prevents unauthorized posts
- **Rate limiting** prevents abuse
- **Input validation** prevents DoS attacks
- **CORS configuration** allows only GET requests from any origin
- **Security headers** (CSP, X-Frame-Options, etc.)

## Benefits

1. **Fully Remote:** No local dependencies, everything on VPS
2. **Reliable:** Systemd service ensures continuous operation
3. **Existing Credentials:** Uses working Signal Desktop setup
4. **Native Build:** No Java dependencies, faster performance
5. **JSON-RPC:** Standard interface for backend integration
6. **Isolated:** Signal CLI separate from board application

## Success Criteria

- [ ] Signal CLI runs successfully on VPS with transferred credentials
- [ ] Can send test message from VPS Signal CLI
- [ ] Can receive messages in VPS Signal CLI
- [ ] Board backend successfully polls Signal CLI via JSON-RPC
- [ ] TOTP validation works correctly
- [ ] Complete end-to-end test: send message → validate → store → display
- [ ] Signal CLI systemd service runs reliably
- [ ] No local dependencies required

## Next Steps

1. Extract Signal Desktop credentials from Windows machine
2. Transfer credentials to VPS
3. Configure Signal CLI with transferred credentials
4. Test Signal CLI functionality on VPS
5. Integrate Signal CLI with board backend
6. Deploy and test complete system
