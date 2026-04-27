# Board Documentation

## Directory Structure
```
docs/
└── runbooks/       # Current operational procedures
    ├── FIXES_IMPLEMENTATION.md           # Recent connection and token fixes
    └── SIGNAL_INTEGRATION_SUCCESS.md    # Signal integration success report
```

## Quick Links
- **Operations:** See `runbooks/` for current deployment and troubleshooting
- **Agent Docs:** See `../AGENTS.md` for AI agent documentation
- **Success Report:** See `runbooks/SIGNAL_INTEGRATION_SUCCESS.md` for Signal integration work

## Documentation Philosophy
- **CLAUDE.md** (root) = Working context, commands, rules
- **AGENTS.md** (root) = Complete reference for AI agents
- **docs/** = Progressive disclosure, detailed explanations
- **.claude/skills/** = Reusable workflows and expert modes
- **.claude/hooks/** = Guardrails and automation
