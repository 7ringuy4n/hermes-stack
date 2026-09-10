# Case 52: OCR False-Positive / Blind Vision Regression

**Gap matrix id:** Case 48 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Prevent another regression where a vision-incapable model returns a normal HTTP 200 response that is mistaken for OCR text.

The current implementation specifically added refusal detection and a vision cooldown after this exact failure.

## Procedure

Feed OCR:

- valid image;
- blank image;
- image with known text;
- image with no text;
- corrupt image.

Mock the model with:

- "I don't see an image";
- "Please upload the image";
- "I cannot view images";
- curly-apostrophe variants;
- unrelated hallucinated description;
- valid OCR text.

## Pass criteria

Blind-model replies never become OCR output.

Known image text must come from:

- vision when valid;
- deterministic OCR fallback otherwise.

---
