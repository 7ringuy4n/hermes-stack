# Case 50: Qdrant Failure / Knowledge Consistency

**Gap matrix id:** Case 46 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test knowledge ingestion when Qdrant becomes unavailable.

## Procedure

1. Ingest a known document.
2. Stop Qdrant during embedding.
3. Stop Qdrant after vector creation but before commit.
4. Restart Qdrant.
5. Retry ingestion.
6. Query knowledge.
7. Repeat with duplicate document.

## Pass criteria

- No false "knowledge indexed" claim.
- No corrupted vector records.
- Retry does not create uncontrolled duplicates.
- Knowledge becomes searchable after recovery.
- Source document remains available for rebuild.

---
