# Ralph Loop - Signal CLI Registration

## Objective
Register phone number +61485676958 to signal-cli on VPS 47.84.234.54 and keep trying until successful.

## Current Status
- Signal CLI: Installed (v0.14.2)
- VPS: 47.84.234.54 (Alibaba Cloud, Singapore)
- Target Number: +61485676958
- Config Directory: /var/signal-cli
- Daemon: signal-cli service is running

## Acceptance Criteria
Signal CLI is successfully registered with +61485676958 and can receive messages.

## Verification Method
Run this command and check for successful registration:
```bash
ssh -i /tmp/board-keypair.pem root@47.84.234.54 "sudo -u signal signal-cli --config /var/signal-cli receive --timeout 30"
```
If the command successfully connects to Signal and can receive messages without errors, the task is complete.

## Known Issues to Try
- Signal captcha servers returning 404 errors
- Try different registration methods (standard, voice, with/without captcha)
- Try with daemon stopped/started
- Try reregister flag
- Test network connectivity to Signal servers
- Check signal-cli daemon logs

## Progress Tracking
- Each iteration: Try one approach, document result
- Avoid repeating failed approaches
- Try new methods systematically
- Update strategies based on failures

## Success Indicators
- Command receives SMS verification code
- Command outputs "Account registered" or "successfully"
- signal-cli receive command connects without errors
- Daemon logs show successful connection to Signal servers

## Instructions
Each iteration:
1. Read .claude/ralph/prd.json — find first task where passes is false
2. Read .claude/ralph/progress.txt — avoid repeating mistakes
3. Read .claude/ralph/agents.md — apply persistent patterns
4. Do the work for that single task only
5. Verify: run a command with an exit code
6. If all criteria pass: set "passes": true in prd.json, append summary to progress.txt
7. If any fail: append failure details to progress.txt, then stop

When ALL tasks have "passes": true, output: <promise>COMPLETE</promise>