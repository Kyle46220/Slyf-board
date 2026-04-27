# Board Documentation

## Directory Structure
```
docs/
├── architecture/     # System architecture and design
│   └── PRD.md        # Product Requirements Document
├── adrs/           # Architecture Decision Records
│   ├── SECURITY_AUDIT_REPORT.md
│   ├── SECURITY_FIXES_IMPLEMENTED.md
│   └── TOTP_VALIDATION_COMPLETE.md
└── runbooks/       # Operational procedures
    ├── DEPLOY.md
    ├── SIGNAL_SETUP_GUIDE.md
    ├── DEPLOYMENT_IMPLEMENTATION.md
    ├── FIXES_IMPLEMENTATION.md
    └── SIGNAL_INTEGRATION_SUCCESS.md
```

## Quick Links
- **Architecture:** See `architecture/PRD.md` for system design
- **Decisions:** See `adrs/` for security and TOTP decisions
- **Operations:** See `runbooks/` for deployment and troubleshooting
- **Agent Docs:** See `../AGENTS.md` for AI agent documentation
- **Success Report:** See `runbooks/SIGNAL_INTEGRATION_SUCCESS.md` for recent integration work

## Documentation Philosophy
- **CLAUDE.md** (root) = Working context, commands, rules
- **AGENTS.md** (root) = Complete reference for AI agents
- **docs/** = Progressive disclosure, detailed explanations
- **.claude/skills/** = Reusable workflows and expert modes
- **.claude/hooks/** = Guardrails and automation
