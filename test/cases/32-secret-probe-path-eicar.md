# Case: Secret path refuse + AV via Security Worker (no adapter EICAR cheat)

## Goal

Protected server paths must be refused by secret-probe. Malware / EICAR detection must go through **Security Worker / av-gateway**, not a local signature check in the Zalo adapter.

## Preconditions

- Zalo authenticated (preferred)
- `config/agent/secret-probe.json` mounted
- For AV: `WORKER_SECURITY=active` and `ENABLE_ANTIVIRUS=1`

## Steps

1. DM: `tìm /opt/data` → secret-probe refuse
2. Send EICAR `question.txt` with Security Worker + antivirus on → AV block / refuse learn (not adapter `_as_eicar_hit`)
3. Send a clean PDF → summary in chat + learn-approve notify
4. Send an image without caption → agent describes the image (does not ask user to describe it)
5. Ask to create a `.txt` with `1` and send → user receives content (attachment or text fallback)

## Pass criteria

- No `EICAR-STANDARD-ANTIVIRUS-TEST-FILE` string match in `hermes/main/plugins/zalo/adapter.py`
- OCR uses `/data/media/...` paths (not hermes-only `/opt/data/media/...` that 404)
- Per-thread inbound queue is FIFO; concurrent messages get a “queued” ack

## Lab

```bash
python test/scripts/secret_probe_path_unit.py
```
