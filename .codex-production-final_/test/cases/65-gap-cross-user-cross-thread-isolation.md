# Case 65: Cross-User / Cross-Thread Isolation

**Gap matrix id:** Case 61 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Detect the most dangerous class of production bug: one user's context appearing in another user's response.

## Procedure

Create:

- User A;
- User B;
- Group A;
- Group B;
- two concurrent Hermes replicas.

Give each unique markers:

- `USER_A_SECRET_TEST`
- `USER_B_SECRET_TEST`
- `GROUP_A_TEST`
- `GROUP_B_TEST`

Send concurrent:

- chat;
- file;
- web search;
- schedule;
- memory query;
- generated file.

## Pass criteria

No marker crosses its security boundary.

Test both:

- same Hermes replica;
- different Hermes replicas.

---
