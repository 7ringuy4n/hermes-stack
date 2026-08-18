---
name: vi-people-terms
description: "Interpret Vietnamese words for people, gender, age, children, animals, and human classifiers from context. Use for every Vietnamese request/response and when translating those terms. Never map a word to gender or insult from the dictionary alone."
---

# Vietnamese people and gender terms

Default for Vietnamese chat and translation. Full tables and examples: [reference.md](reference.md).

## Agent instruction

**Never translate Vietnamese people/gender terms using a fixed word mapping alone. First determine gender, age, plurality, relationship, and tone from the surrounding context. When context does not establish gender, keep the interpretation gender-neutral.**

## Critical anti-confusion

The agent MUST NOT make these assumptions:

```text
con = female                ❌
con = animal                ❌
thằng = insult              ❌
đàn bà = bitch              ❌
cô gái = always child       ❌
con trai = always adult man ❌
người = male                ❌
đứa = female                ❌
```

Correct interpretation:

```text
con      → context-dependent
thằng    → usually male person; tone depends on context
đàn bà   → adult female; tone depends on context
cô gái   → girl / young woman
con trai → boy / son, sometimes male child/young male depending context
người    → person / people
đứa      → person/child classifier; gender-neutral
```

## Must follow

1. Use **context** when a Vietnamese word has multiple meanings.
2. `con` alone does not imply gender or animal — read the next noun (`con chó` vs `con gái` vs `Con ăn cơm chưa?`).
3. `thằng` is usually a male person; do not treat it as an insult unless the sentence is aggressive.
4. `đàn bà` is adult female; tone can be coarse — do not auto-translate as an insult.
5. `đàn ông` = adult male; `con trai` = boy/son (not automatically man).
6. `phụ nữ` is neutral adult female; `cô gái` is girl/young woman.
7. `người`, `đứa`, `em`, `bạn`, `họ` stay gender-neutral unless context names gender.
8. Plurality often comes from `các` / `những` / `nhiều` / numbers — a bare noun may still be plural.
9. If gender/age changes the answer and context is ambiguous, ask one short clarification.

## Sources

Product dictionary: Vietnamese Semantic Dictionary — People, Gender, and Human References (hermes plan).
