# Vietnamese Semantic Dictionary — People, Gender, and Human References

## Purpose

Help the AI agent correctly interpret common Vietnamese words and phrases referring to **men, women, boys, girls, children, animals, and people**.

The agent MUST use **context** when a Vietnamese word has multiple meanings. Do not blindly translate a word based only on its dictionary entry.

---

## 1. Male — Man / Men / Boy

| Vietnamese | Semantic meaning | Typical English |
|---|---|---|
| đàn ông | adult male | man |
| nhiều đàn ông | multiple adult males | men |
| một người đàn ông | one adult male | a man |
| những người đàn ông | multiple adult males | men |
| người đàn ông | adult male person | man |
| nam giới | male gender / males | men / male |
| nam | male / male person | male / man |
| anh | adult male, usually younger/equal age depending context | man / guy / older brother |
| anh ấy | male person | he / him |
| anh ta | male person, often somewhat distant | he / him / that man |
| anh chàng | informal adult male | guy |
| chàng trai | young male | young man / guy |
| trai | male / boy / young man depending context | boy / guy / male |
| con trai | male child or son | boy / son |
| cậu bé | young male child | boy |
| bé trai | male child | boy |
| thằng bé | male child; informal | boy |
| thằng nhóc | young male child; informal | kid / boy |
| thằng | male person; informal and potentially rude depending context | guy / boy / man |

### Important rule: "thằng"

`thằng` normally refers to a **male person**, but its tone depends on context.

Examples:

- `thằng bé` → boy / little boy
- `thằng con trai` → boy / son
- `thằng đó` → that guy / that man
- `một thằng đàn ông` → a man / a guy

Do NOT automatically translate `thằng` as an insult.

However, when used aggressively or with insulting context, preserve the negative tone appropriately.

---

## 2. Female — Woman / Women / Girl

| Vietnamese | Semantic meaning | Typical English |
|---|---|---|
| phụ nữ | adult female / women as a group | woman / women |
| phụ nữ Việt Nam | Vietnamese women | Vietnamese women |
| một người phụ nữ | one adult female | a woman |
| những người phụ nữ | multiple adult females | women |
| đàn bà | adult female; context-dependent tone | woman / women |
| một người đàn bà | adult female | a woman |
| nhiều người đàn bà | multiple adult females | women |
| cô gái | young female | girl / young woman |
| các cô gái | multiple young females | girls / young women |
| một cô gái | young female | a girl / young woman |
| cô | adult female, often polite/social relationship | woman / lady / aunt depending context |
| cô ấy | female person | she / her |
| cô ta | female person, often distant | she / her / that woman |
| chị | adult female, usually older than speaker | woman / older sister |
| chị ấy | adult female | she / her |
| bà | adult/older female; meaning depends context | woman / lady / grandmother |
| bà ấy | older female | she / that woman |
| bé gái | female child | girl |
| con gái | female child / daughter | girl / daughter |
| cô bé | young female child | girl |
| em gái | younger female / younger sister | girl / younger sister |

---

## 3. "Đàn ông" vs "Con trai"

These are NOT interchangeable.

### `đàn ông`

Means an **adult male**.

Examples:

- `một người đàn ông` → a man
- `hai người đàn ông` → two men
- `người đàn ông đang đi bộ` → the man is walking

### `con trai`

Usually means:

1. **boy / male child**
2. **son**

Examples:

- `một cậu con trai` → a boy
- `con trai tôi` → my son
- `hai đứa con trai` → two boys

Do NOT automatically translate:

`con trai` → man

unless context clearly indicates an adult male.

---

## 4. "Phụ nữ" vs "Cô gái" vs "Đàn bà"

These terms have different semantic ranges.

### `phụ nữ`

Neutral and generally respectful.

Meaning:

- woman
- women
- female adult

Example:

`Có nhiều phụ nữ trong phòng.`

→ There are many women in the room.

### `cô gái`

Usually refers to a **young woman or girl**.

Depending on context:

- girl
- young woman

Example:

`Một cô gái đang đứng ngoài cửa.`

→ A girl / young woman is standing outside the door.

### `đàn bà`

Usually refers to an **adult female**.

It can be neutral in some contexts but can sound coarse, dismissive, or insulting in others.

The agent MUST inspect context and tone.

Do NOT automatically translate:

`đàn bà` → bitch

unless the Vietnamese context explicitly carries that insulting meaning.

---

## 5. "Con" — Context-Dependent Word

`con` is highly context-dependent.

It can refer to:

### A. Child / offspring

- `con tôi` → my child
- `con trai tôi` → my son
- `con gái tôi` → my daughter
- `đứa con` → child / offspring

### B. Animal

Vietnamese commonly uses `con` as a classifier for animals.

- `con chó` → dog
- `con mèo` → cat
- `con bò` → cow
- `con gà` → chicken
- `con cá` → fish

Therefore:

`con` ≠ automatically female.

### C. Person referred to as a child/dependent

- `con bé` → the girl / little girl
- `con bé ấy` → that girl
- `con trai` → boy / son
- `con gái` → girl / daughter

### D. Relational pronoun

A parent may refer to their child as `con`.

Example:

`Con ăn cơm chưa?`

→ Have you eaten yet?

Here `con` refers to the child/listener, not an animal and not specifically female.

### Rule

When `con` appears alone, DO NOT infer gender.

Use surrounding nouns, pronouns, and context.

---

## 6. "Đứa"

`đứa` is commonly used as a classifier/reference for a person, especially a child or young person.

Examples:

- `một đứa trẻ` → a child
- `một đứa con gái` → a girl
- `một đứa con trai` → a boy
- `hai đứa trẻ` → two children
- `đứa đó` → that person / that kid

`đứa` does NOT indicate gender by itself.

---

## 7. "Người"

`người` generally means **person / people / human**.

Examples:

- `một người` → one person
- `hai người` → two people
- `nhiều người` → many people
- `người đàn ông` → man
- `người phụ nữ` → woman
- `người lớn` → adult
- `người trẻ` → young person

Do not infer gender from `người`.

---

## 8. Gender-Neutral References

| Vietnamese | Meaning |
|---|---|
| người | person / people |
| một người | a person |
| mọi người | everyone / everybody |
| con người | human / humanity |
| người lớn | adult |
| người trẻ | young person |
| trẻ em | children |
| trẻ con | children / kids |
| đứa trẻ | child |
| em bé | baby |
| em | younger person / younger sibling / child depending context |
| bạn | friend / you / person depending context |
| họ | they / them |

These terms should NOT automatically be assigned male or female gender.

---

## 9. Common Gender Patterns

### Male

```text
đàn ông
người đàn ông
nam giới
nam
con trai
cậu bé
bé trai
chàng trai
anh
anh ấy
anh ta
anh chàng
thằng
thằng bé
```

### Female

```text
phụ nữ
người phụ nữ
đàn bà
cô gái
cô
cô ấy
cô ta
chị
chị ấy
bà
bà ấy
con gái
bé gái
cô bé
```

### Gender-neutral

```text
người
một người
mọi người
con
đứa
đứa trẻ
trẻ em
trẻ con
em
bạn
người lớn
người trẻ
họ
```

---

## 10. Plural Detection

Vietnamese does not always mark plural using grammatical inflection.

The following words commonly indicate plurality:

```text
các
những
nhiều
mọi
tất cả
hai
ba
nhiều người
```

Examples:

```text
đàn ông
→ man / men depending context

nhiều đàn ông
→ many men

các cô gái
→ girls

những người phụ nữ
→ women

nhiều người
→ many people

hai người đàn ông
→ two men

ba cô gái
→ three girls
```

Do NOT assume that every noun without a plural marker is singular.

---

## 11. Translation Priority Rules

When translating Vietnamese → English:

### Rule 1 — Identify the entity

Determine whether the phrase refers to:

```text
adult male
adult female
boy
girl
child
animal
person
group of people
```

### Rule 2 — Use surrounding words

Examples:

```text
con chó
→ dog

con gái
→ girl / daughter

con trai
→ boy / son

con bé
→ girl / little girl

con đó
→ that person / that one
```

### Rule 3 — Do not infer gender from classifiers

```text
con
đứa
người
em
```

are not inherently male or female.

### Rule 4 — Preserve age

Prefer:

```text
đàn ông → man
con trai → boy
cô gái → girl / young woman
trẻ em → children
```

Do not flatten all of them into `person`.

### Rule 5 — Preserve tone

Words such as:

```text
thằng
đàn bà
con bé
thằng nhóc
```

may carry informal or emotional tone.

Interpret the tone from the complete sentence instead of automatically treating the word as an insult.

### Rule 6 — Context overrides dictionary defaults

The dictionary provides semantic hints, not absolute translations.

If the context is ambiguous, prefer a neutral interpretation or ask for clarification when the distinction materially changes the answer.

---

## 12. Examples

```text
Một người đàn ông đang đi bộ.
→ A man is walking.

Có nhiều đàn ông ở đó.
→ There are many men there.

Một cô gái đang đứng ngoài đường.
→ A girl / young woman is standing outside.

Có nhiều phụ nữ trong phòng.
→ There are many women in the room.

Con trai tôi đang chơi.
→ My son is playing.

Một cậu bé đang chạy.
→ A boy is running.

Con gái tôi đang ngủ.
→ My daughter is sleeping.

Một bé gái đang chơi.
→ A little girl is playing.

Con chó đang chạy.
→ The dog is running.

Con bé đang chơi.
→ The girl is playing.

Thằng bé đang chạy.
→ The boy is running.

Thằng đó đang đứng ngoài cửa.
→ That guy / that man is standing outside.

Có nhiều người ở đây.
→ There are many people here.

Con đang làm gì vậy?
→ What are you doing?
```

## 13. Critical Anti-Confusion Rules

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

## Agent Instruction

**Never translate Vietnamese people/gender terms using a fixed word mapping alone. First determine gender, age, plurality, relationship, and tone from the surrounding context. When context does not establish gender, keep the interpretation gender-neutral.**