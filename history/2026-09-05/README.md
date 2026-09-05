# 2026-09-05

## 20:15 — Direct fallbacks were chat-shaped regardless of endpoint

### Symptom

Model Router could use one explicit chat fallback after OmniRoute became
unavailable, but embeddings and image endpoints inherited a chat model, image
editing lost multipart metadata, and web search had no independent fallback.
Host media shortcuts also bypassed Model Router and therefore never reached its
fallback pool.

### Root cause

Fallback selection was provider-wide instead of capability-specific. The proxy
assumed JSON request bodies, while image edits are multipart. Search routing was
correctly combo-owned but had no local continuity path.

### Fix (core)

Direct providers are now opt-in priority profiles with separate chat, vision,
embedding, image, and image-edit model declarations. Their credentials are
loaded from OpenBao. Multipart image edits retain the original file bytes while
only the model field is replaced for a compatible fallback. Host and Dispatcher
still generation call Model Router, and web search uses internal SearXNG after
OmniRoute failure. Missing capability declarations skip a provider instead of
guessing support.

### Prevent recurrence

Fallback tests must disable OmniRoute and exercise the real endpoint shape.
Never infer media capability from a provider or model name, and never route a
non-chat endpoint through a generic chat-model setting.

## 19:20 — Clean startup depended on an already-running secret service

### Symptom

After a verified `destroy`, `run.sh up` attempted to load OpenBao KV values
before recreating OpenBao. Required Compose variables were therefore absent and
the clean deployment could not start.

### Root cause

The normal update path assumed the secret service was already running. A full
container removal exposed the circular dependency between Compose interpolation
and loading the values held in OpenBao.

The backup path also discovered the Compose container correctly but executed
the export against a literal service name that did not exist. It replaced that
failure with a note file, so structural verification reported a false success.

### Fix (core)

Cold startup creates only OpenBao with non-functional parsing sentinels for
application-only required variables, waits until KV loading succeeds, imports
the real values into the current process, and only then creates the full stack.
The sentinels are neither persisted as secrets nor consumed by an application
container.

OpenBao backup now uses the discovered container name, validates that the KV
payload is non-empty, and fails the backup gate otherwise. Cold startup restores
that verified KV export before importing Compose values.

Credential-bearing environment names are centralized in the OpenBao seed and
scrub registry. The root bootstrap exception is generated in a mode-600 file
outside `.env`, backed up with the OpenBao component, and loaded only into the
deployment process.

Environment cleanup now runs before the deployment shell imports `.env`. This
ensures an exact legacy internal route is both rewritten on disk and absent from
the Compose process that creates new containers.

### Prevent recurrence

The clean-deploy gate must begin from zero project containers and verify the
secret bootstrap before testing higher-level capabilities.

## 18:10 — Filesystem Zalo owner election required replica restarts

### Symptom

Scaled Hermes could process ordinary HTTP traffic, but only the replica chosen
at container startup loaded Zalo. A dead owner left a shared filesystem marker,
and recovery restarted every Hermes replica, interrupting unrelated turns.

### Root cause

Zalo ownership was coupled to entrypoint-time filesystem state and local DNS
checks. Standby adapters were disabled, the bridge bypassed the edge load
balancer, and the watcher treated a missing SSE client as a reason to bounce the
whole agent set.

The first shared-lease implementation returned a failed connection from a
standby replica. The gateway did not retry that startup connection, leaving the
standby process healthy but unable to acquire an expired owner lease.

### Fix (core)

All replicas now load the adapter against an internal-only Traefik bridge route.
A renewable Valkey lease uses atomic acquire and owner-checked renew/release;
only the lease holder opens SSE. Message IDs remain deduplicated and queued in
Valkey per conversation. Watcher recovery clears the scoped lease and restarts
the proxy without restarting healthy Hermes replicas. Exact legacy bridge URLs
are migrated while operator-custom URLs are preserved.

A standby now remains inside the adapter lifecycle and periodically contends
for the lease. Promotion proceeds directly into bridge health validation and
SSE startup; it does not require the gateway or container supervisor to retry
the platform connection.

### Verification

- Static topology and lease protocol units cover routing, lease ownership,
  removal of the filesystem election, and legacy URL migration.
- Live release verification must stop the current owner, observe bounded
  standby acquisition, and prove no duplicate or cross-thread delivery.
- One-versus-two-replica results must separate local queue/agent time from
  provider time; a small run is not a general capacity claim.

### Prevent recurrence

Singleton channel ownership must use a renewable shared lease, never replica
startup order or a persistent marker. Health recovery is scoped to the failed
hop and cannot restart the full agent pool for provider latency or queue
saturation.

## 16:30 — Quoted images were analyzed instead of edited

### Symptom

An explicit image transformation sent by replying to a Zalo photo was routed as
image analysis, and a direct edit could fail after 30 seconds even though the
provider was still producing a valid artifact.

### Root cause

The quote path correctly extracted, downloaded, and staged the original image,
but the host shortcut rejected every turn containing media. The remaining path
therefore treated the photo as an analysis attachment. Independently, the image
provider waits until its artifact is ready before sending response headers,
exceeding OmniRoute's direct-response default.

### Technical detail

- **Ownership:** an explicit `skill=image-edit`, `skill_action=edit_media`, and
  `output_type=image` contract consumes the staged quote source on both inline
  and queued Zalo paths; other image requests still use vision analysis.
- **Transport:** `OMNIROUTE_DIRECT_HEADERS_TIMEOUT_MS=300000` is separate from
  `resilienceSettings.requestQueue.maxWaitMs` and covers slow direct image calls.
- **Lifecycle:** setup removes retired capability aliases and stale combo rows
  instead of leaving callable legacy shells.

### AI decision

Make the structured classifier result the only intent gate, preserve the quote
source as data, and let the host own the one edit request and one attachment
delivery. Keep credentials in OmniRoute and provider details out of prompts.

### Fix (core)

Raised the direct image response-header budget, added the multipart image-edit
executor to the core Zalo media path, and removed retired capability code and
configuration across setup, routing, skills, attribution, tests, and docs.

### Todo list

- [x] Verify quoted-media extraction and staged local-path ownership.
- [x] Verify the multipart edit request and result-only delivery contract.
- [x] Reproduce and verify a real image artifact through the combo.
- [x] Remove retired skills, aliases, endpoints, setup state, and tests.
- [x] Audit the deployed Zalo quote-reply flow and service logs.

### Prevent recurrence

Routing-only responses cannot pass the image-edit lab. A quote test must prove
source extraction, endpoint completion, artifact validity, and Zalo delivery;
the release remains blocked if any layer merely asserts success.

The release probe used a deterministic scene with independently recognizable
objects. The edited artifact remained structurally coherent, contained no
unwanted text, passed image decoding, and received an independent visual score
of 8/10 before the outbound Zalo photo event was accepted.

## 13:47 — Media capability shells were still routed to refusal

### Symptom

The image-edit combo existed in setup, but supplied-image transformation requests
could not reach it because mounted guidance and the host gate treated all image
attachments as analysis inputs.

### Root cause

The combo layer was added before the classifier schema and mounted skill layer
were migrated. The host attachment gate did not distinguish analysis from edit
actions using the classifier contract.

### Technical detail

- **Function:** `hermes/main/plugins/zalo/classify_client.py::plan_allows_image_edit()` owns the structured edit gate.
- **Fields:** `skill=image-edit`, `skill_action=edit_media`, and `output_type=image` remain executable only with an image source.
- **Combos:** `hermes` and `image-edit` use `strategy=priority`; member order remains operator-owned.

### AI decision

Complete the image-edit architecture through classifier and reusable skills,
without adding topic matching or provider-specific prompts.

### Fix (core)

Added the endpoint-owned image-edit skill, expanded the shared classify contract,
and added a strategy-only migration that keeps exact combo membership and order.

### Todo list

- [x] Inspect the existing image-edit shell and attachment route.
- [x] Preserve operator members while changing strategy.
- [x] Add the reusable image-edit contract and classifier enum.
- [x] Add local regression coverage.
- [x] Verify the real endpoint and artifact on the authorized lab host.

### Prevent recurrence

Unit coverage distinguishes image editing from image analysis and verifies
strategy migration does not reorder combo members.

## 13:47 — Visual document wording created an extra media deliverable

### Symptom

A request for one styled office document could also emit a standalone generated
image, and model-authored HTML could repeat a short subject line immediately
above a title band containing the same subject.

### Root cause

The file-generation skill required a scenic asset for every visual presentation
document and lacked a single-visible-title constraint. Classification guidance
did not state that visual styling verbs remain inside the requested office type.

### Technical detail

- **Function:** `classify.py::assemble_classify_system()` — consumes the corrected external media prompt; no host NLU was added.
- **Lines:** `hermes/main/skills/classify/parts/media.txt:L7–L16`; `hermes/main/skills/file-gen/SKILL.md:L58–L82`.
- **Fields:** `output_type=pdf` remains authoritative; `media_generation` is added only for an independently requested or explicitly embedded image.

### AI decision

Correct the owning prompt and skill contracts so every topic and language gets
the same behavior; do not special-case a place name or weather request.

### Fix (core)

Made embedded visuals opt-in, prohibited separate delivery of document assets,
required one visible document title, and bound overlay copy to the dominant
language of the current request with general-audience wording.

### Todo list

- [x] Inspect the supplied PDF and chat screenshots as evidence.
- [x] Trace office and image routing ownership.
- [x] Update generic prompt/skill sources.
- [x] Add request-language and document-title contract tests.
- [ ] Inspect a regenerated lab PDF and its actual Zalo delivery.

### Prevent recurrence

Regression checks cover office-output precedence, single-title guidance,
request-language overlays, and the absence of implicit image delivery.

## Scheduled media plan was lost or weakened between storage and fire

### Symptom

A one-time schedule was stored, but at its due time the adapter classified the
inner request again or split search and image generation into generic workflow
jobs. Provider variance also labeled explicit image work with a coarse artifact
hint or flattened child task types.

### Cause

The scheduler accepted only one concrete in-memory map type when copying the
stored plan. Media detection treated a broad hint as file processing even when
the plan contained explicit search, image output, and render-contract fields.

### Decision and fix

The schedule worker forwards the plan as an opaque JSON value. Due events carry
a stable schedule/execution message identity, bypass unrelated per-thread work,
and execute the persisted plan without classification. Explicit task/output and
classifier-owned render fields outrank coarse hints.

### Verification and prevention

A real two-minute Zalo run stored one structured plan, issued exactly one
creation classification, fired with the plan present, performed one search, did
not create a workflow, and delivered one image. Unit coverage includes flattened
child types and coarse artifact hints.

## Grounded overlay and background needed one design owner

### Symptom

Generated backgrounds could invent a second temperature, misspell a place name,
or collapse into an empty gradient while the authoritative overlay remained
factually correct.

### Cause

The overlay planner owned factual copy and styling, but diffusion still received
a classifier-authored scene that could mention screens, displays, or overlay
content. Negative-only instructions could also erase the requested scene.

### Decision and fix

The grounded composition model now authors both the adaptive overlay plan and a
compact English background-scene brief based on retrieved facts. External prompt
assets require a rich requested subject, reserve negative space, prohibit
competing readable facts/UI, and require timestamps for current material. The
renderer remains deterministic and validates design fields.

### Verification and prevention

The final Zalo artifact used an English weather card over a misty Da Lat-style
lake, pine, and flower scene. Vision OCR found no accidental background text,
confirmed the complete overlay and timestamp, and rated fulfillment strong.

## Half-open Zalo SSE looked healthy while losing inbound events

### Symptom

Bridge health reported one SSE client and both Hermes containers were running,
yet accepted synthetic inbound events never appeared in the gateway log.

### Cause

The bridge emits heartbeats every 15 seconds, but the Hermes SSE client used an
unbounded socket-read timeout. A half-open stream could therefore remain counted
without delivering bytes or reconnecting.

### Decision and fix

The SSE client now uses a 45-second read deadline, equal to three missed bridge
heartbeats. Timeout enters the existing cursor/session reset and reconnect loop.

### Verification and prevention

After deployment the next bridge event reached the elected owner and completed
classification, search, image generation, and one Zalo attachment delivery.

## Update recreation raced self-healing

### Symptom

Enabled optional containers disappeared during update, then the watchdog tried
to recreate or restart services while Compose still owned the transition.

### Cause

Some branches compared feature flags only with `1` even though `active` is a
supported canonical value. Update and watchdog also lacked mutual exclusion.

### Decision and fix

All update decisions use the shared active/inactive parser. Update holds a
data-directory maintenance lock for its full mutation window; stack-watch uses
a nonblocking acquisition and performs no healing while maintenance owns it.
Only the service whose independent health probe failed is restarted.
The updater also creates the shared watch directory and repairs its ownership
before opening the lock, because existing root-owned timer state must not block
an operator-run update.

### Prevention

Exercise update with canonical word-valued flags and inspect restart counts and
logs before and after an in-flight long request.

## OpenBao rotation was coupled to plaintext env persistence

### Symptom

Scrubbing API keys could break the next Compose recreation, while reloading the
keys restored them to repository `.env` and defeated disk cleanup.

### Cause

Compose interpolation and secret persistence were treated as the same concern.

### Decision and fix

The OpenBao loader writes a mode-0600 transient export only. The shell imports
it without evaluation, recreates declared consumers, then removes the export
and scrubs repository/data env files. A rotation lab compares values in memory
without logging secret material and restores the original vault value.

### Prevention

Future consumers must be added to the controlled sync set and the rotation lab;
they must never require secrets to remain in repository `.env`.

## Non-chat call logs lost the requested combo identity

### Symptom

Image, embedding, and search requests succeeded, but OmniRoute displayed the
resolved backend or an empty value in the Requested Model column.

### Decision and fix

A key-scoped reconciliation worker restores the configured combo alias for
stack-owned non-chat endpoints and leaves the resolved provider in the model
field. The worker never writes provider or combo configuration.

### Prevention

Endpoint attribution tests verify both identities independently, and rollout
checks query live call logs after the reconciliation worker starts.

## A fresh replica recovered only after one restart

### Symptom

The upstream UID remap treated the shared data root as the account home and
encountered read-only bind mounts. A new replica failed its first bootstrap,
then succeeded on restart after the UID change had partially persisted.

### Decision and fix

The replica entrypoint changes the account home to its writable per-replica
directory before chaining into the upstream s6 bootstrap. The classifier bake
is also regenerated from its prompt-part source so update does not dirty git.

### Prevention

A bootstrap regression test enforces ordering of the account-home handoff, and
release verification checks restart counts plus repository cleanliness after a
fresh rolling update.

## Retired routing and audio paths accumulated operational ambiguity

### Symptom

Two router planes, stale exporter panels, old environment aliases, and an
optional local transcription backend produced conflicting setup and monitoring
behavior.

### Decision and fix

OmniRoute is the model provider plane and `model-router` is the internal
task-aware proxy. The retired router profile, volume, setup scripts, health
probes, fallbacks, and exporter are removed. Local Whisper transcription is
removed from dispatcher and compose. Obsolete secret names remain only as
one-release scrub tombstones.

### Prevention

Current code/docs/tests may reference only OmniRoute and Model Router. Migration
tombstones must never be read as runtime configuration.

## Discontinued JavaScript crypto dependency

### Symptom

The Zalo bridge install emitted a deprecation warning for an unmaintained crypto
package and depended on mutable registry resolution during setup.

### Decision and fix

Pin the upstream bridge and API sources in `vendor/`, retain their MIT licenses,
replace MD5 and AES-CBC calls with Node.js `node:crypto`, and validate against
fixed compatibility vectors. Runtime setup installs the vendored dependency
graph and verifies the deprecated package is absent.

### Prevention

Vendor refreshes must regenerate npm lockfiles, rebuild distributions, run the
crypto vector test, and verify the dependency tree before rollout.

## Model-authored office artifacts require rendered-output gates

### Symptom

A fresh-data office request could be split into retrieval and authoring jobs,
turn an operational instruction into document body text, add an unrequested
sibling image, or produce a polished-looking file whose language, locality,
timestamp, scope, units, or pagination was wrong.

### Decision and fix

Keep fresh-data document work in one evidence-owning file job and bypass the
literal office shortcut when the model must process the original message.
The classifier instruction and file skill now require dominant-language copy,
one title, one verified current source, correct timezone semantics,
locale-appropriate units, exact requested scope, and a pre-delivery layout
review. The Zalo lab fixture verifies the actual delivered file and rejects a
separate image artifact.

### Verification result and prevention

Structural routing, single-file delivery, current timestamp handling, and
language/unit checks passed progressively. The final rendered page still used
an unreliable card layout and unsupported descriptive interpretations, so the
release gate remained closed. Future releases must inspect rendered pages and
their extracted text; a successful API call or file assertion alone is not a
pass. A bridge injection must also wait for an active SSE subscriber after a
replica restart.
