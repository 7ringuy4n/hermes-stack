# 2026-08-27

3 incident(s). Times are UTC+7.

## 07:10 — Quote file reply, folder-zip empty text, English refuse, auto-learn risk docs

### Symptom

Reply-quoting a prior file did not process the attachment. Folder zip packs with images looked empty. Secret refuse stayed English. Blank/risk documents still opened Knowledge pending; PDF paths reached Hermes terminal tools.

### Root cause

Quote media lacked `fileUrl`/bridge `media`. Archive extract dropped text when OCR was empty despite media members. Host used a fixed English refuse string. File pipeline auto-staged learn for every extract; OCR/PDF binaries were not stripped after worker extract.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Bridge quote media map; wider quote URL keys; archive returns media member list when OCR empty; classify refuse in user language; learn only when classify allows knowledge; strip office/text/archive/ocr paths before Hermes.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never auto-learn blank/risk/archives. Never hand worker-extracted packages to Hermes tools. Prefer classify instructions for refuse copy.

## 07:45 — Zip with caption silent; answering lock 45s

### Symptom

Sending zip files produced no Zalo reply when a caption was present. Long turns were cut off while the user was still waiting.

### Root cause

Archive extract with meaningful text skipped host ack and waited on Hermes (Omni queue rate-limit). Queue turn timeout defaulted to 5 minutes; answering lock TTL was hardcoded to 45 seconds.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Always host-ack archives from ingest extract. Raise Zalo queue turn wait floor to 15 minutes; align answering TTL and drain max; increase archive worker timeout.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never route zip/7z/rar/tar chat reads through Hermes after the worker extract. Keep turn wait ≥ archive/OCR budget.

## 08:25 — Mixed risk+safe zip silent or refused entirely

### Symptom

Zip packs with one short risk text member and one blank/safe office produced no useful extract reply (silence or whole-pack refuse).

### Root cause

Archive host-ack still ran classify on the combined extract body. A short risk member looked like a user secret ask; under Omni queue saturation the sync classify hop blocked the turn.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Skip attachment-body secret classify for archives; host-ack media extract always. Classify treats archive member text as data. Standalone short risk files still refuse.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never map archive member bodies to secret probes. Prefer caption/user ask only for refuse on compressed attachments.
