# Case 72: Unknown Input Fuzzing

**Gap matrix id:** Case 68 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Find cases that humans did not explicitly anticipate.

Generate malformed/random inputs for:

- natural-language requests;
- schedules;
- numbered lists;
- compound requests;
- file names;
- captions;
- group names;
- tool arguments;
- model-router JSON;
- workflow payloads.

Include:

- empty string;
- whitespace;
- Unicode;
- Vietnamese diacritics;
- emoji;
- extremely long text;
- repeated text;
- nested numbering;
- mixed languages;
- malformed JSON;
- control characters.

## Pass criteria

No crash.

No stack trace to user.

No unsafe execution.

No infinite loop.

No invalid database state.

---
