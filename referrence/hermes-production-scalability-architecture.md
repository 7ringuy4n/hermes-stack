# Hermes Stack — Production Scalability Architecture

## 1. Purpose

This document defines the production architecture for running multiple Hermes instances safely and horizontally.

The core principles are:

- API Gateway is the entry point for HA, authentication, routing, and rate limiting.
- Traefik provides TLS termination and load balancing.
- OpenVPN provides private administrative/internal access.
- Hermes containers are stateless and disposable.
- Session state is externalized.
- Memory is externalized through the Memory Manager.
- Heavy workloads are executed by dedicated workers, not inside Hermes.
- Skills are versioned and backed up outside the Hermes container.
- Uploaded files and generated artifacts are stored outside Hermes.
- PostgreSQL is the canonical durable data store.
- Qdrant is a rebuildable retrieval/index layer.
- Valkey is used for rate limiting and ephemeral distributed state.
- Multiple Hermes instances can process concurrent requests without depending on a specific instance.

---

# 2. Target Production Architecture

```text
                              INTERNET
                                  |
                                  v
                         +----------------+
                         |   OpenVPN      |
                         | Private Admin  |
                         +----------------+
                                  |
                                  | Admin / Internal
                                  |
                    +-------------+-------------+
                    |                           |
                    | Public API                | Private API
                    v                           v
             +----------------------------------------+
             |              API GATEWAY                |
             |                                        |
             | Authentication / Authorization         |
             | Global Rate Limit                      |
             | Request Validation                     |
             | Request ID / Correlation ID            |
             | Routing                                |
             +-------------------+--------------------+
                                 |
                                 v
                         +---------------+
                         |    Traefik    |
                         | TLS / LB      |
                         | Health checks |
                         +-------+-------+
                                 |
                +----------------+----------------+
                |                |                |
                v                v                v
           +---------+      +---------+      +---------+
           | Hermes 1|      | Hermes 2|      | Hermes N|
           +----+----+      +----+----+      +----+----+
                |                |                |
                +----------------+----------------+
                                 |
             +-------------------+-------------------+
             |                   |                   |
             v                   v                   v
      +-------------+     +-------------+     +-------------+
      | Memory      |     | Session     |     | Tool/Task   |
      | Manager     |     | Services    |     | Dispatcher  |
      +------+------+     +------+------+     +------+------+
             |                   |                   |
       +-----+------+            |           +-------+--------+
       |            |            |           |       |        |
       v            v            v           v       v        v
 PostgreSQL      Qdrant       Valkey       OCR   Image   Coding
 canonical      retrieval     rate-limit   Worker Worker Worker
 durable data   index         /ephemeral
       |
       v
 Backup / Recovery

External Storage
       |
       +---- Skills Git Repository
       +---- Uploaded Files
       +---- Generated Files
       +---- Knowledge Source Files
       +---- Backup/Object Storage
```

---

# 3. API Gateway — HA and Global Rate Limiting

The API Gateway is the controlled entry point before traffic reaches Hermes.

Responsibilities:

1. Authentication
2. Authorization
3. Global rate limiting
4. Request validation
5. Correlation/request ID
6. Routing
7. Protection against abusive traffic
8. API versioning
9. Failure handling

The Gateway must not depend on one Hermes instance.

```text
Client
  |
  v
API Gateway
  |
  +---- authenticate
  |
  +---- authorize
  |
  +---- rate limit
  |
  +---- request validation
  |
  v
Traefik
  |
  +---- Hermes 1
  +---- Hermes 2
  +---- Hermes N
```

## 3.1 Global Rate Limit

Valkey is the shared rate-limit store.

Do not maintain independent rate-limit counters inside Hermes.

Bad:

```text
Hermes 1 -> local counter
Hermes 2 -> local counter
Hermes 3 -> local counter
```

This allows the effective limit to multiply with the number of replicas.

Correct:

```text
                    API Gateway
                         |
                         v
                      Valkey
                 shared counters
                         |
             +-----------+-----------+
             |                       |
          allowed                  rejected
             |                       |
             v                       v
          Traefik                   HTTP 429
             |
             v
        Hermes x N
```

Recommended logical rate-limit keys:

```text
rate:user:{identity_id}
rate:workspace:{workspace_id}
rate:channel:{channel}
rate:ip:{ip}
```

Expensive operations may have independent limits:

```text
rate:image:{identity_id}
rate:ocr:{identity_id}
rate:coding:{identity_id}
rate:upload:{identity_id}
```

The limit must be based on resource cost, not only request count.

---

# 4. Traefik

Traefik is responsible for traffic distribution between healthy Hermes instances.

```text
                    Traefik
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
    Hermes-1       Hermes-2       Hermes-3
```

## 4.1 Hermes must expose health endpoints

At minimum:

```text
GET /health/live
GET /health/ready
```

### Liveness

Indicates that the Hermes process is alive.

### Readiness

Indicates that the instance is capable of accepting new work.

For example:

```text
/live  -> 200
/ready -> 503
```

when Hermes is running but required dependencies are unavailable.

Traefik must stop routing traffic to a non-ready instance.

---

# 5. OpenVPN

OpenVPN is for private administration and internal access.

Public traffic should not require access to private infrastructure.

```text
Internet
   |
   v
Public API Gateway
   |
   v
Traefik
   |
   v
Hermes
```

Administrative access:

```text
Administrator
      |
      v
   OpenVPN
      |
      +---- Docker management
      +---- Monitoring
      +---- Admin API
      +---- Database administration
      +---- Internal services
```

Do not expose PostgreSQL, Qdrant, Valkey, Docker management interfaces, or administrative endpoints directly to the public Internet.

---

# 6. Hermes Must Be Stateless

A Hermes container must be disposable.

Do not make a specific Hermes instance the owner of durable state.

Bad:

```text
Hermes-1
  |
  +-- conversation state
  +-- user session
  +-- memory
  +-- uploaded files
  +-- generated files
  +-- mutable skills
```

Correct:

```text
Hermes-1 ---+
Hermes-2 ---+---- External Services
Hermes-N ---+
```

Hermes replicas must be interchangeable.

If:

```text
Request 1 -> Hermes-1
Request 2 -> Hermes-3
Request 3 -> Hermes-2
```

the user must still see the same durable session, memory, permissions, skills, and files.

---

# 7. Session and Concurrent Request Handling

## 7.1 Session State

Session state must not live only in Hermes process memory.

Recommended separation:

```text
PostgreSQL
    |
    +-- durable conversation/session metadata
    +-- identity
    +-- workspace
    +-- permissions
    +-- job metadata

Valkey
    |
    +-- active/short-lived session state
    +-- rate limiting
    +-- distributed ephemeral state

Hermes
    |
    +-- current request context only
```

Valkey must not become the canonical database for durable conversation or memory.

## 7.2 No Sticky Session Requirement

The architecture should support:

```text
User
 |
 +-- Request 1 -> Hermes-1
 +-- Request 2 -> Hermes-3
 +-- Request 3 -> Hermes-2
```

without requiring sticky sessions.

This is possible only when state is externalized.

## 7.3 Concurrent Requests

A Hermes instance should be able to keep multiple interactive requests in flight.

Example:

```text
Hermes-1
 |
 +-- Request 1 -> waiting for LLM
 +-- Request 2 -> waiting for LLM
 +-- Request 3 -> RAG
 +-- Request 4 -> tool call
 +-- Request 5 -> waiting for LLM
```

However, concurrency must not be unlimited.

Use separate concurrency limits by workload:

```text
Hermes instance

Interactive chat     -> configurable concurrency
RAG                  -> configurable concurrency
OCR                  -> low concurrency
Image generation     -> very low concurrency
Embedding            -> controlled concurrency
Coding               -> controlled concurrency
```

Do not use a single global limit such as:

```text
MAX_REQUESTS = 5
```

for every workload.

The correct model is:

```text
                    Hermes
                       |
             +---------+---------+
             |         |         |
           Chat       RAG      Heavy
             |         |         |
          limit N    limit N    queue
```

---

# 8. Separate Heavy Workers from Hermes

Hermes should orchestrate heavy work, not execute every heavy workload inside the Hermes container.

Bad:

```text
Hermes
 |
 +-- Chat
 +-- OCR
 +-- Embedding
 +-- Image generation
 +-- Coding
```

This causes one workload to consume resources needed by another.

Correct:

```text
                         Hermes x N
                              |
                         Dispatcher
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
      Chat/LLM           OCR Worker          Image Worker
                            |                   |
                            v                   v
                          OCR                ComfyUI

                         +-------------------+
                         | Embedding Worker  |
                         +-------------------+

                         +-------------------+
                         | Coding Worker     |
                         +-------------------+
```

Each worker type has independent concurrency and resource limits.

Example:

```text
Hermes replicas       = 3
OCR workers            = 2
Embedding workers     = 2
Image workers          = 1
Coding workers         = 1
```

Scaling one workload must not require scaling all Hermes instances.

---

# 9. Memory Manager Architecture

The Memory Manager is a logical component used by every Hermes replica.

```text
                 Hermes Instance
                        |
                        v
                +---------------+
                | MemoryManager |
                |               |
                | search        |
                | remember      |
                | update        |
                | forget        |
                | prefetch      |
                +-------+-------+
                        |
              +---------+---------+
              |                   |
              v                   v
       Memory Repository    Vector Repository
              |                   |
              v                   v
        PostgreSQL             Qdrant
```

## 9.1 PostgreSQL

PostgreSQL is the canonical durable memory/data store.

Use it for durable state such as:

```text
identity
workspace
memory metadata
conversation metadata
ACL
job metadata
audit information
timestamps
status
```

## 9.2 Qdrant

Qdrant is the retrieval/index layer.

```text
Canonical data
      |
      v
PostgreSQL / source documents
      |
      v
Embedding
      |
      v
Qdrant
```

Qdrant must be rebuildable from the canonical source.

## 9.3 Valkey

Valkey remains responsible for:

```text
rate limiting
ephemeral session state
short-lived cache
distributed ephemeral coordination
```

Do not make Valkey the canonical memory database.

---

# 10. Memory Manager and Horizontal Hermes Scaling

The Memory Manager must not depend on the identity of the Hermes container.

```text
Hermes-1 ---+
Hermes-2 ---+---- Memory Manager
Hermes-3 ---+
Hermes-N ---+
```

All instances must access the same logical memory namespace.

Memory boundaries should include the architecture's identity/workspace context.

Conceptually:

```text
tenant
  |
  +-- workspace
        |
        +-- identity
              |
              +-- memory
```

A request routed to another Hermes instance must not change the memory scope.

---

# 11. Concurrent Memory Operations

Multiple Hermes instances can access the same memory simultaneously.

Therefore:

```text
Hermes-1 ----+
Hermes-2 ----+---- Memory Manager ---- PostgreSQL
Hermes-3 ----+
```

must safely support concurrent:

```text
read
write
update
delete
```

Do not rely on process-local locks inside Hermes.

Concurrency control must be enforced at the shared persistence layer through:

- database transactions
- unique constraints
- deterministic keys
- optimistic concurrency where appropriate
- retry handling for conflicts

---

# 12. Skills Must Be External and Backed Up

Skills must not exist only inside the writable Hermes container.

Bad:

```text
Hermes container
  |
  +-- /skills
```

If the container is destroyed, the skill changes disappear.

Correct:

```text
                 Skills Repository
                        |
                        v
                 Version-controlled
                        |
             +----------+----------+
             |                     |
             v                     v
         Hermes-1              Hermes-N
```

Recommended source:

```text
Git repository
```

Skills should be:

- versioned
- reviewable
- reproducible
- backed up
- deployable to new Hermes instances

A Hermes container should be able to start from a clean image and retrieve the required skill version.

---

# 13. Uploaded Files Must Be Outside Hermes

Uploaded files must not be stored only in the Hermes container filesystem.

Bad:

```text
Hermes-1
  |
  +-- /uploads
```

because:

```text
Upload -> Hermes-1
Next request -> Hermes-2
```

may not find the file.

Correct:

```text
Client
  |
  v
API Gateway
  |
  v
External File/Object Storage
  |
  +---- Hermes-1
  +---- Hermes-2
  +---- Hermes-N
```

Store metadata in PostgreSQL:

```text
file_id
workspace_id
identity_id
storage_location
filename
content_type
size
checksum
created_at
status
```

The actual file remains in external storage.

---

# 14. Generated Files Must Also Be External

Generated images, documents, reports, exports, and other artifacts must not be treated as Hermes container state.

```text
Hermes
  |
  v
Worker
  |
  v
External Artifact Storage
```

Metadata:

```text
artifact_id
workspace_id
identity_id
type
storage_location
checksum
created_at
status
```

This allows:

```text
Hermes-1 -> generates artifact
Hermes-1 dies
Hermes-3 -> can still return artifact
```

---

# 15. Knowledge Files Must Have a Canonical Source

Knowledge should follow:

```text
Source Documents
       |
       v
Ingestion
       |
       v
Embedding
       |
       v
Qdrant
```

Do not make Qdrant the only copy of the source knowledge.

The original documents must remain in external storage or their canonical source system.

This allows Qdrant to be rebuilt.

---

# 16. Failure Isolation

A failure in one component must not take down all Hermes replicas.

Examples:

```text
Image Worker fails
    |
    +-- Chat continues
    +-- RAG continues
    +-- File reading continues
```

```text
OCR Worker fails
    |
    +-- Chat continues
    +-- Image generation continues
```

```text
Hermes-2 fails
    |
    +-- Hermes-1 continues
    +-- Hermes-3 continues
```

```text
Qdrant unavailable
    |
    +-- Durable memory/data remains in PostgreSQL
    +-- RAG becomes unavailable/degraded
```

---

# 17. Scaling Model

## Single instance

```text
Traefik
   |
Hermes x1
   |
PG / Qdrant / Valkey
```

## Horizontal Hermes scaling

```text
Traefik
   |
   +-- Hermes-1
   +-- Hermes-2
   +-- Hermes-3
```

## Heavy workload scaling

```text
Traefik
   |
Hermes x3
   |
Dispatcher
   |
   +-- OCR x2
   +-- Image x1
   +-- Embedding x2
   +-- Coding x1
```

## Multi-node scaling

```text
                  Load Balancer
                       |
          +------------+------------+
          |                         |
        Node A                    Node B
          |                         |
      Hermes x3                 Hermes x3
      Workers                  Workers
          |                         |
          +------------+------------+
                       |
              Shared Data Services
```

The Hermes application architecture should not depend on whether it is deployed using Docker Compose or Kubernetes.

---

# 18. Production Rules

The following rules should be treated as architectural requirements.

### Hermes

- Must be stateless.
- Must support multiple concurrent requests.
- Must support graceful shutdown.
- Must expose liveness and readiness.
- Must not own durable files.
- Must not own canonical memory.
- Must not require sticky sessions.

### API Gateway

- Must enforce authentication and authorization.
- Must enforce global rate limits.
- Must use shared Valkey state.
- Must reject requests before expensive Hermes work when limits are exceeded.

### Traefik

- Must route only to healthy Hermes instances.
- Must provide TLS termination.
- Must load balance across Hermes replicas.

### Session

- Durable session state must be external.
- Short-lived state may use Valkey.
- Session routing must not depend on a specific Hermes instance.

### Memory

- Memory Manager must be stateless.
- PostgreSQL is canonical durable state.
- Qdrant is retrieval/index state.
- Valkey is not the canonical memory store.
- Concurrent memory updates must be safe.

### Skills

- Skills must be outside the container's mutable filesystem.
- Skills must be version-controlled.
- Skills must be backed up.
- A new Hermes container must be able to restore the same skill set.

### Files

- Uploaded files must be stored outside Hermes.
- Generated artifacts must be stored outside Hermes.
- File/artifact metadata belongs in PostgreSQL.
- External storage must be backed up.

### Heavy workloads

- OCR, image generation, embedding, and coding must run as separate workers.
- Each worker type must have independent concurrency/resource limits.
- Heavy workload failures must not take down Hermes.

### Networking

- Public traffic enters through the API Gateway.
- Traefik handles internal routing/load balancing.
- OpenVPN is used for private administrative access.
- PostgreSQL, Qdrant, Valkey, and administrative interfaces must not be publicly exposed.

---

# 19. Final Target

```text
                              CLIENTS
                                 |
                                 v
                       +-------------------+
                       |    API Gateway    |
                       |                   |
                       | Auth              |
                       | Authorization     |
                       | Global RateLimit  |
                       +---------+---------+
                                 |
                                 v
                           +-----------+
                           | Traefik   |
                           | TLS / LB  |
                           +-----+-----+
                                 |
                 +---------------+---------------+
                 |               |               |
                 v               v               v
             Hermes-1       Hermes-2        Hermes-N
                 |               |               |
                 +---------------+---------------+
                                 |
                         +-------+-------+
                         |               |
                         v               v
                  Memory Manager     Dispatcher
                         |               |
                +--------+-------+       |
                |                |       |
                v                v       +---------+---------+---------+
          PostgreSQL          Qdrant      |         |         |         |
          canonical          retrieval   OCR      Image    Embed     Coding
          durable             index      Worker    Worker   Worker    Worker

                 +-------------------------------+
                 | External Storage              |
                 |                               |
                 | Skills Git                    |
                 | Uploaded Files                |
                 | Generated Artifacts           |
                 | Knowledge Sources             |
                 | Backups                       |
                 +-------------------------------+

                         +---------------+
                         |    Valkey     |
                         |               |
                         | Rate Limit    |
                         | Session       |
                         | Ephemeral     |
                         +---------------+

                         +---------------+
                         |    OpenVPN    |
                         | Private Admin |
                         +---------------+
```

## Core Principle

> **Hermes is the stateless agent runtime. It should be safe to add, remove, restart, or replace any Hermes container without losing sessions, memory, skills, uploaded files, generated artifacts, or durable state.**

This makes horizontal scaling possible without coupling the architecture to a specific Hermes instance.
