# Case 51: Attachment Pipeline Partial Failure

**Gap matrix id:** Case 47 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test the complete:

`Zalo → attachment → AV → OCR/extract/media → Hermes`

pipeline when one stage fails.

## Matrix

For each file type:

- TXT
- MD
- PDF
- image
- DOCX
- XLSX
- PPTX
- CSV
- MP3
- MP4

Fail each stage independently:

- download;
- file permission;
- AV;
- OCR;
- extraction;
- Whisper;
- ffmpeg;
- embedding;
- Hermes summarization;
- Zalo outbound.

## Pass criteria

The user receives exactly one honest result:

- successful extraction/summary;
- or short controlled failure.

Never:

- fake summary;
- "file processed" when it was not;
- stack trace;
- duplicate reply;
- request to re-upload when extracted content already exists.

---
