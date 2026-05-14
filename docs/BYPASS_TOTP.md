# Bypassing TOTP Authentication

If you need to temporarily disable TOTP authentication (for example, during testing, debugging, or if the token generator is unavailable), the backend now has a built-in feature to allow this.

## How it works
The backend checks for the `BYPASS_TOTP` environment variable. If set to `true`, the `signal_listener` will:
1. Not require a 6-digit code at the beginning of the message.
2. Accept any message and post the entire content directly to the board.
3. If a user *does* include a 6-digit TOTP code anyway, it will be parsed out automatically so it doesn't display on the public board, but validation is skipped.

## How to Enable the Bypass on the Production Server

1. SSH into the GCP board server:
   ```bash
   gcloud compute ssh board-server --zone=australia-southeast1-a
   ```

2. Edit the backend `.env` file:
   ```bash
   sudo nano /opt/backend/.env
   ```

3. Add the following line to the end of the file:
   ```env
   BYPASS_TOTP=true
   ```

4. Restart the backend service to apply the new configuration:
   ```bash
   sudo systemctl restart board
   ```

## How to Revert and Re-enable TOTP Security

To turn TOTP validation back on:

1. SSH into the server as shown above.
2. Edit `/opt/backend/.env` again.
3. Either change the line to:
   ```env
   BYPASS_TOTP=false
   ```
   Or delete the line entirely.
4. Restart the service:
   ```bash
   sudo systemctl restart board
   ```

**WARNING:** Leaving TOTP bypassed allows ANYONE with the Signal phone number to post anonymously without authentication. Only use this temporarily.
