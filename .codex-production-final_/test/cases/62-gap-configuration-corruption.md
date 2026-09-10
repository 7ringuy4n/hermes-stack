# Case 62: Configuration Corruption

**Gap matrix id:** Case 58 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Verify invalid configuration cannot partially start the stack in a dangerous state.

## Corrupt one setting at a time:

- missing API key;
- malformed URL;
- invalid port;
- invalid boolean;
- invalid worker mode;
- unknown model;
- empty combo;
- invalid timeout;
- invalid profile;
- malformed JSON/YAML;
- invalid cron;
- conflicting worker flags.

## Pass criteria

Either:

- startup fails clearly and safely;

or:

- the component disables itself safely.

Never:

- partially starts with misleading health;
- silently falls back to an unsafe endpoint;
- exposes an internal service publicly.

---
