# Secrets Management Guide

## Current Secrets (ROTATE THESE IMMEDIATELY)

The following secrets are currently exposed in the repository and MUST be rotated:

### 1. TOTP_SECRET
**Current Value:** `JBSWY3DPEHPK3PXP` (weak, decodes to "HELLO WORLD")
**Purpose:** Validates TOTP codes for post submissions
**Rotation Steps:**
```bash
# Generate new secret
python -c "import pyotp; print(pyotp.random_base32())"

# Update .env file on all servers
TOTP_SECRET=<new_secret>

# Restart backend service
systemctl restart board-backend
```

### 2. ADMIN_TOKEN
**Current Value:** `localdevtoken`
**Purpose:** Admin API authentication
**Rotation Steps:**
```bash
# Generate new token (use strong random string)
openssl rand -base64 32

# Update .env file on all servers
ADMIN_TOKEN=<new_token>

# Restart backend service
systemctl restart board-backend
```

### 3. DATABASE_URL
**Current Value:** `postgresql+asyncpg://board@/board?host=/tmp`
**Purpose:** Database connection
**Rotation Steps:**
```bash
# Change database user password
sudo -u postgres psql -c "ALTER USER board PASSWORD 'new_password';"

# Update .env file on all servers
DATABASE_URL=postgresql+asyncpg://board:new_password@/board?host=/tmp

# Restart backend service
systemctl restart board-backend
```

## Secret Storage Best Practices

1. **Never commit secrets to git**
   - All secrets are now excluded by .gitignore
   - If secrets were committed, use BFG Repo-Cleaner to remove from history:
     ```bash
     java -jar bfg.jar --delete-files .env
     git reflog expire --expire=now --all
     git gc --prune=now --aggressive
     git push --force
     ```

2. **Use environment variables in production**
   - Store secrets in environment variables, not .env files
   - Use secret management tools (HashiCorp Vault, AWS Secrets Manager, etc.)

3. **Rotate secrets regularly**
   - TOTP_SECRET: Every 6 months
   - ADMIN_TOKEN: Every 3 months
   - Database passwords: Every 6 months

4. **Use different secrets per environment**
   - Development: `dev_` prefix
   - Staging: `staging_` prefix
   - Production: No prefix, strong secrets

5. **Audit secret access**
   - Monitor who accesses secret management systems
   - Log all secret usage

## Cleanup Steps

1. **Remove committed .env from git history:**
   ```bash
   # Backup current branch
   git checkout -b backup-before-cleanup

   # Remove .env from history
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch backend/.env' \
     --prune-empty --tag-name-filter cat -- --all

   # Clean up
   git for-each-ref --format='delete %(refname)' refs/original | git update-ref --stdin
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive

   # Force push (WARNING: This rewrites history)
   git push origin --force --all
   ```

2. **Generate new secrets:**
   ```bash
   # TOTP secret
   python -c "import pyotp; print(pyotp.random_base32())"

   # Admin token
   openssl rand -base64 32

   # Database password
   openssl rand -base64 24
   ```

3. **Update all servers:**
   - Update .env files with new secrets
   - Restart services
   - Verify functionality

## Verification

After rotation, verify:
- [ ] New TOTP codes work
- [ ] Admin API functions with new token
- [ ] Database connects successfully
- [ ] No errors in application logs
- [ ] All services are running
