# SurgeSense — Real-Time Dynamic Pricing & ETA Platform

> A ride-hailing / delivery-style backend that computes live price and ETA predictions using an XGBoost model, streams demand/supply signals in real time via Kafka, and serves everything through a horizontally scaled, containerized, Kubernetes-deployed architecture.

This README is written the way a senior SDE would hand off a system to a new team member: what we're building, why each piece was chosen, exactly how it's implemented, and — critically — what we do when the "clean" plan doesn't survive contact with reality. Every major component has a documented **Plan B**.

---

## Table of contents

1. [Problem statement](#1-problem-statement)
2. [System architecture](#2-system-architecture)
3. [Tech stack](#3-tech-stack)
4. [Component deep-dive](#4-component-deep-dive)
   - [4.1 Client layer](#41-client-layer)
   - [4.2 Nginx — load balancer / reverse proxy / gateway](#42-nginx--load-balancer--reverse-proxy--gateway)
   - [4.3 Spring Boot API service](#43-spring-boot-api-service)
   - [4.4 Python ML + MCP service](#44-python-ml--mcp-service)
   - [4.5 XGBoost model — training and serving](#45-xgboost-model--training-and-serving)
   - [4.6 Data layer — PostgreSQL, Redis](#46-data-layer--postgresql-redis)
   - [4.7 Real-time pipeline — Kafka + WebSocket](#47-real-time-pipeline--kafka--websocket)
   - [4.8 Containerization — Docker](#48-containerization--docker)
   - [4.9 Orchestration — Kubernetes](#49-orchestration--kubernetes)
   - [4.10 CI/CD — GitHub Actions](#410-cicd--github-actions)
   - [4.11 Security — auth, authz, secrets](#411-security--auth-authz-secrets)
   - [4.12 Observability — logging, metrics, tracing](#412-observability--logging-metrics-tracing)
5. [End-to-end data flow (walkthrough)](#5-end-to-end-data-flow-walkthrough)
6. [Database schema](#6-database-schema)
7. [REST API reference](#7-rest-api-reference)
8. [MCP tool reference](#8-mcp-tool-reference)
9. [Failure modes & fallback matrix](#9-failure-modes--fallback-matrix)
10. [Repository structure](#10-repository-structure)
11. [Git workflow](#11-git-workflow)
12. [Local development setup](#12-local-development-setup)
13. [Testing strategy](#13-testing-strategy)
14. [Deployment runbook](#14-deployment-runbook)
15. [Roadmap / future work](#15-roadmap--future-work)

---

## 1. Problem statement

Static pricing (a flat per-km rate) doesn't reflect real conditions: a driver shortage at 6 PM on a rainy Friday should cost more than the same trip at 11 AM on a Tuesday. We want a system that:

- Predicts a fair price and ETA **per request**, using live signals (demand, supply, traffic, weather, time-of-day).
- Updates that price **while the user is looking at the screen**, without a page refresh, if conditions change before they confirm.
- Stays available and fast under bursty load (everyone requesting rides at 6 PM).
- Is built so that no single component's failure takes down the whole system.

That last point is why this README spends as much time on fallbacks as it does on the happy path.

---

## 2. System architecture

```
Client apps (web/mobile)
        │
        ▼
   Nginx (LB / reverse proxy / TLS termination)
        │
   ┌────┴─────────────────┐
   ▼                       ▼
Spring Boot API      Python ML + MCP service
(auth, bookings,      (XGBoost inference,
 REST, WebSocket       MCP tools, feature
 gateway)              enrichment)
   │                       │
   └──────────┬────────────┘
              ▼
   PostgreSQL │ Redis │ Kafka
   (system of  (live   (event
    record)    cache)   stream)
```

Two independently deployable services sit behind Nginx. They don't call each other synchronously for the hot path — they communicate through Kafka (events) and Redis (shared fast-read state), which is what makes this a genuinely distributed system rather than two monoliths with a shared database.

---

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Reverse proxy / LB | Nginx | Battle-tested, cheap to run, doubles as TLS termination and static rate limiting |
| Core API | Java 17, Spring Boot 3.x | Strong typing, mature ecosystem, Spring Security for auth, what most fintech/ride-hailing backends actually use in production |
| ML/inference service | Python 3.11, FastAPI | Best ecosystem for ML serving; async-friendly; plays well with MCP SDKs |
| ML model | XGBoost | CPU-friendly (no GPU needed to train or serve), interpretable via SHAP, industry-standard for tabular pricing/ETA problems |
| Transactional DB | PostgreSQL 15 | ACID guarantees for bookings/payments-adjacent data |
| Fast-read cache | Redis 7 | Sub-millisecond reads for "current surge multiplier per zone" |
| Event streaming | Apache Kafka | Durable, replayable, decouples producers (location pings) from consumers (pricing engine) |
| Real-time push | WebSocket (STOMP over Spring) | Native two-way channel; Nginx proxies it with minor config |
| Containers | Docker (multi-stage builds) | Small, reproducible images |
| Orchestration | Kubernetes (EKS/GKE) | Auto-healing, HPA, rolling deploys |
| CI/CD | GitHub Actions | Free tier is generous, native to GitHub, easy to read |
| Auth | Spring Security + JWT, OAuth2 (Google login) | Stateless auth scales horizontally without session affinity |

---

## 4. Component deep-dive

### 4.1 Client layer

A thin web or mobile client. It does three things: calls REST endpoints for booking/user actions, opens a WebSocket connection for live price updates, and renders whatever the server sends — no pricing logic on the client, ever (that's a security and consistency requirement, not a style choice — a client-computed price is a client-forgeable price).

### 4.2 Nginx — load balancer / reverse proxy / gateway

**Role:** single entry point for all traffic. Terminates TLS, load-balances across N replicas of each backend service, applies coarse rate limiting, and proxies WebSocket upgrades.

**Implementation details:**
- `upstream` blocks for `spring-api` (round-robin across pod IPs, or the Kubernetes Service ClusterIP if Nginx sits as an Ingress controller) and `ml-service`.
- Path-based routing: `/api/v1/*` → Spring Boot, `/ml/*` and `/mcp/*` → Python service, `/ws/*` → WebSocket upgrade block with `proxy_set_header Upgrade $http_upgrade` and `Connection "upgrade"`.
- `limit_req_zone` for basic IP-based rate limiting (e.g. 20 req/s per IP with a burst of 40) as a first line of defense before requests even reach app-level rate limiters.
- Health check integration: Nginx `upstream` entries get `max_fails=3 fail_timeout=30s` so a crashing pod is automatically pulled out of rotation.
- TLS via Let's Encrypt (cert-manager if running inside Kubernetes) with auto-renewal.

**Why Nginx over alternatives:** it's free, well documented, and doubles as both LB and static asset server if we ever add a marketing page. In Kubernetes we actually run it as the backing engine for an **Ingress resource**, so app teams don't hand-edit `nginx.conf` — they edit Ingress YAML and the Nginx Ingress Controller regenerates config underneath.

**⚠️ Fallback — if Nginx integration gets stuck:**
- If path-based WebSocket proxying misbehaves (a known source of pain — sticky timeouts, dropped upgrades under certain Nginx versions), fall back to running the WebSocket endpoint on its **own subdomain** (`ws.surgesense.io`) with a dedicated, simpler `server` block, rather than fighting a single shared config.
- If we outgrow single-node Nginx's config-reload model (frequent redeploys causing brief connection drops), migrate to a cloud-native load balancer (AWS ALB / GCP Load Balancer) for L7 routing and keep Nginx only as the Ingress controller inside the cluster, or drop it in favor of **Traefik**, which handles dynamic backend registration more gracefully in Kubernetes.
- If rate limiting at the Nginx layer proves too coarse (can't distinguish authenticated users), move rate limiting into the Spring Boot gateway filter chain (bucket4j) and leave Nginx doing only IP-level abuse protection.

### 4.3 Spring Boot API service

**Role:** system of record for users, drivers, trips, and bookings. Owns authentication and exposes the REST API and WebSocket endpoint the client actually talks to.

**Package structure (layered, OOP-first):**
```
com.surgesense.api
├── controller     (REST controllers — thin, no business logic)
├── service        (business logic, interfaces + impls)
├── repository      (Spring Data JPA repositories)
├── domain          (entities: User, Driver, Trip, Booking)
├── dto             (request/response objects — never expose entities directly)
├── security        (JWT filter, OAuth2 config, role-based guards)
├── pricing         (Strategy pattern: PricingStrategy interface, SurgePricingStrategy, FlatRatePricingStrategy)
├── notification    (Factory pattern: NotificationFactory → EmailNotifier, PushNotifier, SmsNotifier)
├── websocket       (STOMP config, price-update broadcaster)
└── config          (beans, CORS, OpenAPI/Swagger config)
```

**OOP design choices, spelled out:**
- **Strategy pattern** for pricing: `PricingStrategy` is an interface with `calculate(TripContext)`. `SurgePricingStrategy` calls out to the ML service; `FlatRatePricingStrategy` is the fallback (see below) that uses a static per-km rate. Swapping between them is a one-line config change, not a redeploy of business logic.
- **Factory pattern** for notifications: adding a new channel (e.g. WhatsApp) means implementing `Notifier` and registering it in the factory — zero changes to calling code.
- **Repository pattern** via Spring Data JPA keeps persistence concerns out of services entirely.
- **DTOs everywhere** at the controller boundary — entities never leave the service layer, which avoids Jackson-serialization surprises and accidental over-exposure of internal fields.

**Key endpoints:** booking creation, trip status, user/driver registration, login/refresh — full list in [§7](#7-rest-api-reference).

**⚠️ Fallback — if the ML call from Spring Boot times out or the ML service is down:**
- Every price request has a **hard timeout budget** (e.g. 300 ms) for the call to the Python ML service. If it's exceeded or the call errors, `PricingContext` falls back to `FlatRatePricingStrategy` — a simple, deterministic distance × time-of-day multiplier stored in Postgres/config. The user still gets a price; it's just not the ML-optimized one. This is a **circuit breaker** (Resilience4j) around the ML call, not a try/catch — after N consecutive failures it stops calling the ML service entirely for a cooldown window, rather than hammering a service that's already struggling.

### 4.4 Python ML + MCP service

**Role:** two responsibilities living in one FastAPI app: (1) serve the XGBoost model as a REST endpoint, and (2) expose the same capabilities as MCP tools so an LLM-based ops/support assistant (or another agent) can query pricing/demand data conversationally.

**Structure:**
```
ml_service/
├── main.py              (FastAPI app, mounts REST + MCP routes)
├── inference/
│   ├── model.py          (loads the trained XGBoost model, feature pipeline)
│   └── features.py        (feature engineering: haversine distance, time buckets, demand ratio)
├── mcp/
│   └── server.py          (MCP server: tools = get_price_prediction, get_live_demand, get_driver_eta)
├── streaming/
│   └── kafka_consumer.py   (consumes location/demand events, updates Redis)
└── training/
    └── train.py            (offline training script, not part of the runtime image)
```

**MCP tools exposed** (see [§8](#8-mcp-tool-reference) for the full contract):
- `get_price_prediction(pickup, dropoff, rider_id)` → price, ETA, surge multiplier, confidence
- `get_live_demand(zone_id)` → current demand/supply ratio for a geo-zone
- `get_driver_eta(driver_id, destination)` → predicted arrival time

**Why bundle MCP into the same service rather than a separate one:** the MCP tools and the REST endpoint call the *exact same* inference function — splitting them into two services would mean either duplicating the model-loading code or adding a network hop between them for no benefit. One process, two transports.

**⚠️ Fallback — if MCP SDK integration causes friction:**
- If the MCP Python SDK's transport (stdio/SSE) conflicts with running inside the same ASGI app as FastAPI's own routes, split MCP into a **separate lightweight process** in the same pod (sidecar container) rather than forcing both into one event loop. They still share the same model artifact via a shared volume or by calling the same internal `/predict` endpoint over localhost.
- If exposing MCP tools externally raises security concerns before proper auth is in place, keep MCP internal-only (accessible only inside the cluster network) and only expose the REST API externally through Nginx, until an MCP-specific auth story (API keys per tool caller) is built.

### 4.5 XGBoost model — training and serving

**Features:** trip distance (haversine), pickup/dropoff zone, hour-of-day and day-of-week (cyclically encoded), current demand/supply ratio pulled from Redis, weather condition (categorical), historical average price for that route.

**Target:** fare amount (regression) and trip duration (a second regression head, or a separate model — we start with two independent XGBoost regressors rather than one multi-output model, since they have different error tolerances and it's easier to retrain/tune them independently).

**Training pipeline (offline, not in the request path):**
1. Pull historical trip data (public NYC TLC trip dataset works as a stand-in for real production data).
2. Feature engineering script (`features.py`) — shared between training and serving so there's no train/serve skew.
3. Train/validation split by time (not random shuffle — pricing models must be validated on *future* data relative to training data, or you leak information).
4. Hyperparameter search (a modest grid: `max_depth`, `n_estimators`, `learning_rate`) via `xgboost.cv`.
5. Export with `model.save_model('model.json')` — the plain JSON/UBJ format, not pickle, so the serving container isn't tied to a specific Python/XGBoost version for deserialization.
6. Log metrics (MAE, RMSE) to a simple experiment tracker (even a CSV file for v1 is fine — MLflow if this grows).

**Serving:** the model file is baked into the Docker image at build time (or pulled from an S3/GCS bucket on container startup — see fallback). A `/predict` endpoint takes raw trip context, runs it through the same `features.py` pipeline, and returns price + ETA + a confidence interval (from XGBoost's quantile regression objective, or a simple bootstrap over trees).

**⚠️ Fallback — if cloud GPU/managed ML infra isn't available or is too expensive:**
- We don't need a GPU at all for XGBoost — that's part of why it was chosen over a neural net. If even CPU cloud costs are a concern, the model is small enough (a few MB) to serve from a **single small VM or even a serverless function** (AWS Lambda container image, GCP Cloud Run) rather than a dedicated Kubernetes deployment — Cloud Run scales to zero, which matters for a side project with no constant traffic.
- If baking the model into the Docker image makes CI/CD slow (rebuilding the image every time the model retrains), switch to **loading the model from object storage (S3/GCS) at container startup** instead — the image stays generic infra, only the model artifact changes, and retraining doesn't require a new image build.
- If live feature lookups (e.g. current demand ratio from Redis) add too much latency to the hot path, **precompute and cache the surge multiplier per zone** on a short TTL (e.g. every 10 seconds via the Kafka consumer) instead of querying Redis synchronously per request — the `/predict` endpoint reads a cached multiplier, not a live query.

### 4.6 Data layer — PostgreSQL, Redis

**PostgreSQL** is the system of record: users, drivers, trips, bookings, payment status. Schema in [§6](#6-database-schema). Standard normalized design with foreign keys; Flyway (or Liquibase) manages migrations so schema changes are versioned alongside code, never applied by hand.

**Redis** holds ephemeral, fast-changing state that would be wasteful to hit Postgres for on every request:
- `zone:{id}:demand_ratio` — current demand/supply, TTL 15s, refreshed by the Kafka consumer.
- `driver:{id}:location` — last known lat/lng, TTL 60s (if a driver's location goes stale, we know to stop trusting it).
- `trip:{id}:live_price` — the most recently pushed price for an in-progress booking, so a reconnecting WebSocket client can immediately get the latest value instead of waiting for the next tick.

**⚠️ Fallback — if Redis becomes a bottleneck or a new integration risk:**
- If Redis Cluster mode adds operational complexity we don't want to own yet, run single-node Redis with persistence (AOF) enabled and accept it as a (documented, monitored) single point of failure for the cache layer only — losing it costs us the *fast* answer, not the *correct* one, since Postgres still has the durable data. That fallback tier matters: **cache misses degrade gracefully to a Postgres read**, they never cause a hard failure.
- If we don't want to run Redis at all for the first version, an **in-memory Caffeine cache inside the Spring Boot service** covers the same need for a single-instance deployment — the tradeoff is it's not shared across replicas, which is fine until we actually scale past one pod.

### 4.7 Real-time pipeline — Kafka + WebSocket

**Kafka topics:**
- `driver-location-events` — high-volume, produced by driver apps (simulated with a small producer script for a demo), consumed by the pricing engine to compute local supply.
- `demand-events` — produced whenever a rider opens the app / requests a quote in a zone, consumed to compute local demand.
- `price-updates` — produced by the ML service after recomputing a zone's surge multiplier, consumed by the Spring Boot WebSocket broadcaster to push updates to connected clients.

**Flow:** location/demand events → Python consumer aggregates per zone on a sliding window → writes updated demand ratio to Redis → if the ratio crossed a meaningful threshold, publishes to `price-updates` → Spring Boot consumer picks it up → broadcasts over WebSocket to any client subscribed to that zone/trip.

**Why Kafka and not just a direct DB write:** it decouples producers from consumers completely — the driver-location producer doesn't need to know or care who's consuming it, and we can add new consumers later (e.g. an analytics pipeline) without touching the producer at all. It's also replayable, which matters for debugging ("what did demand look like right before that price spike").

**⚠️ Fallback — if running/operating Kafka is too heavy for the project's scale:**
- Kafka has real operational weight (ZooKeeper or KRaft, partition management, consumer group rebalancing). If that's more infrastructure than the project needs to prove the concept, **RabbitMQ** is a lighter-weight message broker that covers the same producer/consumer decoupling for a project at this scale, at the cost of weaker replay/durability guarantees.
- If even running a message broker is overkill for a first pass, fall back to **Redis Pub/Sub** for the price-update fan-out (it's already in the stack) and a **scheduled polling job** (every few seconds) instead of a true event stream for demand aggregation. This is explicitly a "good enough for v1" simplification, not the target architecture — it's called out here so a future contributor doesn't mistake it for the intended design.

**⚠️ Fallback — if WebSocket scaling behind the load balancer is problematic:**
- WebSockets need sticky sessions or a shared pub/sub backplane across Spring Boot replicas, or a client connected to pod A never hears about a price update triggered via pod B. If that broker wiring (Spring's `RedisMessageBrokerConfig`) proves fiddly, fall back to **Server-Sent Events (SSE)** for the price stream — simpler to load-balance since it's plain HTTP, at the cost of being one-directional (which is fine here — the client never needs to send data over this channel, only receive).
- If neither is worth the complexity yet, the client can **poll a `/price` REST endpoint every few seconds** as a strictly-worse-but-simpler stand-in, with a clear TODO to upgrade to push-based updates.

### 4.8 Containerization — Docker

Each service gets its own multi-stage Dockerfile:
- **Spring Boot:** stage 1 builds the fat JAR with Maven (`mvn package`), stage 2 copies just the JAR into a slim `eclipse-temurin:17-jre-alpine` base — keeps the final image small and avoids shipping the build toolchain.
- **Python ML service:** stage 1 installs dependencies into a virtualenv, stage 2 copies the venv and app code into a `python:3.11-slim` base.
- **Nginx:** a thin custom image built `FROM nginx:alpine` with our config baked in, so config changes are versioned and deployed like any other artifact.

All images run as a non-root user, expose only the port they need, and have a `HEALTHCHECK` instruction so Docker/Kubernetes can tell a hung process from a healthy one.

**⚠️ Fallback — if multi-stage build times get painful in CI:**
- Enable Docker layer caching in CI (GitHub Actions' `docker/build-push-action` with `cache-from`/`cache-to` against the registry) rather than rebuilding dependency layers from scratch every run.

### 4.9 Orchestration — Kubernetes

**Resources per service:** a `Deployment` (replica count, rolling update strategy), a `Service` (ClusterIP, internal routing), a `HorizontalPodAutoscaler` (scale on CPU/memory, e.g. 2–10 replicas), and `ConfigMap`/`Secret` for environment config and credentials. Nginx runs as an `Ingress` (via the Nginx Ingress Controller) rather than a hand-managed Deployment where possible, so routing rules live in versioned YAML.

**Namespaces:** `surgesense-dev`, `surgesense-staging`, `surgesense-prod` — same manifests, different values via Kustomize overlays or Helm value files, so "it worked in staging" actually means something.

**⚠️ Fallback — if managing a full Kubernetes cluster is more than the project needs:**
- For local development or a portfolio demo, **Docker Compose** stands in for the whole stack (all services + Postgres + Redis + Kafka + Nginx) with one command. Kubernetes manifests are kept for the "production-shaped" deployment story, but nobody should need a cluster just to run the project locally.
- If a managed cluster (EKS/GKE) is too costly for a personal project, a **single VM running Docker Compose or K3s** (a lightweight Kubernetes distribution) gets you the same manifests working on a $5–10/month box, which is a reasonable middle ground between "just Compose" and "full managed Kubernetes."

### 4.10 CI/CD — GitHub Actions

**Pipeline stages (on every PR):** checkout → lint → unit tests (both Java and Python) → build Docker images (not pushed yet, just verified they build) → integration tests against ephemeral containers (Testcontainers for Postgres/Kafka in the Java test suite).

**Pipeline stages (on merge to `main`):** all of the above, plus: build and tag images with the commit SHA → push to the container registry (GHCR or ECR) → deploy to staging automatically → **manual approval gate** → deploy to production (`kubectl apply` or `helm upgrade`).

**⚠️ Fallback — if GitHub Actions minutes/cost become a constraint:**
- Switch heavier jobs (integration tests, image builds) to run on a **self-hosted runner** (even a spare machine) rather than GitHub-hosted minutes, or move CI entirely to **GitLab CI** if the repo migrates — the pipeline logic (lint → test → build → deploy) transfers directly, only the YAML dialect changes.
- If Testcontainers-based integration tests are too slow for every PR, run them only on merge to `main` and rely on mocked unit tests for fast PR feedback.

### 4.11 Security — auth, authz, secrets

- **Authentication:** JWT issued by Spring Security on login, short-lived access token + longer-lived refresh token. OAuth2 (Google) as an alternative login path using Spring's OAuth2 client support.
- **Authorization:** role-based (`RIDER`, `DRIVER`, `ADMIN`) enforced via `@PreAuthorize` annotations at the service layer, not just at the controller — defense in depth.
- **Secrets:** never in source control. Local dev uses a `.env` file (git-ignored); Kubernetes uses `Secret` resources, ideally sourced from a proper secrets manager (AWS Secrets Manager / HashiCorp Vault) rather than raw base64 YAML in production.
- **Transport security:** TLS terminated at Nginx; internal cluster traffic can optionally use mTLS if a service mesh (Istio/Linkerd) is introduced later.

**⚠️ Fallback — if OAuth2 provider integration stalls:**
- Ship JWT-based email/password auth first as the only login method; OAuth2 is additive and can land in a later iteration without blocking the rest of the system.

### 4.12 Observability — logging, metrics, tracing

- **Logging:** structured JSON logs from both services, shipped to a central place (even just `kubectl logs` plus a lightweight aggregator like Loki for a personal project; ELK if it needs to look more enterprise-grade).
- **Metrics:** Spring Boot Actuator + Micrometer exposing Prometheus-format metrics (`/actuator/prometheus`); the Python service exposes its own `/metrics` via `prometheus-fastapi-instrumentator`. Grafana dashboards on top.
- **Tracing:** optional — OpenTelemetry across both services if request tracing across the Spring Boot → Kafka → Python hop becomes necessary to debug latency.

**⚠️ Fallback — if a full Prometheus/Grafana stack is overkill for the project's current scale:**
- Start with just structured logs and Kubernetes' built-in liveness/readiness probes. Add metrics scraping only once there's an actual question ("why did p99 latency spike") that logs alone can't answer.

---

## 5. End-to-end data flow (walkthrough)

1. Rider opens the app, enters pickup/dropoff → client calls `POST /api/v1/quotes`.
2. Nginx routes the request to a Spring Boot pod.
3. Spring Boot's `PricingService` calls the ML service's `/predict` endpoint with trip context (with a circuit breaker guarding the call).
4. ML service enriches the request with the current demand ratio (read from Redis, itself kept fresh by the Kafka consumer) and runs it through the XGBoost model.
5. Price + ETA + confidence returned to Spring Boot, which persists a `Quote` record and returns it to the client.
6. Client opens a WebSocket subscription to that quote's zone.
7. Meanwhile, driver apps continuously publish location pings to `driver-location-events`; rider apps publish demand signals to `demand-events`.
8. The Python Kafka consumer aggregates these per zone every few seconds, updates Redis, and — if the surge multiplier moved meaningfully — publishes to `price-updates`.
9. Spring Boot's Kafka consumer picks up the update and broadcasts it over WebSocket to any client subscribed to that zone.
10. The rider sees their quote update live, without refreshing, before they confirm the booking.
11. On confirm, `POST /api/v1/bookings` locks in the last-seen price, writes to Postgres, and the trip lifecycle begins.

---

## 6. Database schema

```
users            (id, email, password_hash, role, created_at)
drivers          (id, user_id FK, license_no, vehicle_type, status)
trips            (id, rider_id FK, driver_id FK, pickup_geo, dropoff_geo, status, created_at)
bookings         (id, trip_id FK, quoted_price, final_price, surge_multiplier, status)
quotes           (id, rider_id FK, pickup_geo, dropoff_geo, predicted_price, predicted_eta, confidence, created_at)
```

Migrations are managed with Flyway (`V1__init_schema.sql`, `V2__add_surge_multiplier.sql`, etc.) — every schema change is a new versioned file, never an ad hoc `ALTER TABLE` run by hand against production.

---

## 7. REST API reference

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Create a rider or driver account | none |
| POST | `/api/v1/auth/login` | Returns JWT access + refresh token | none |
| POST | `/api/v1/auth/refresh` | Exchange refresh token for new access token | refresh token |
| POST | `/api/v1/quotes` | Get a price/ETA quote for a trip | rider |
| POST | `/api/v1/bookings` | Confirm a booking from a quote | rider |
| GET | `/api/v1/bookings/{id}` | Get booking/trip status | rider/driver/admin |
| PATCH | `/api/v1/drivers/{id}/status` | Driver goes online/offline | driver |
| GET | `/actuator/health` | Liveness/readiness probe | none |

Full request/response schemas are documented via OpenAPI/Swagger at `/swagger-ui.html` once the service is running.

---

## 8. MCP tool reference

| Tool | Input | Output |
|---|---|---|
| `get_price_prediction` | `pickup`, `dropoff`, `rider_id` | `price`, `eta_minutes`, `surge_multiplier`, `confidence` |
| `get_live_demand` | `zone_id` | `demand_ratio`, `active_drivers`, `pending_riders` |
| `get_driver_eta` | `driver_id`, `destination` | `eta_minutes`, `distance_km` |

These are the same tools an internal ops assistant or a future partner integration would call — the contract is intentionally identical to the REST layer's underlying logic so there's exactly one source of truth for "how do we compute a price."

---

## 9. Failure modes & fallback matrix

A consolidated view of every "what if this doesn't work" decision made above:

| Component | Primary choice | Risk | Fallback |
|---|---|---|---|
| Load balancing | Nginx | WebSocket proxying issues | Dedicated ws subdomain, or Traefik/cloud ALB |
| Rate limiting | Nginx `limit_req` | Too coarse (no per-user awareness) | Move to Spring Boot filter chain (bucket4j) |
| ML call from API | Synchronous REST call | Latency spike / service down | Circuit breaker → static `FlatRatePricingStrategy` |
| MCP hosting | In-process with FastAPI | Transport/event-loop conflicts | Sidecar process in same pod |
| Model artifact | Baked into Docker image | Slows CI on retrain | Load from S3/GCS at container startup |
| Model compute | XGBoost on CPU | N/A (chosen specifically to avoid this) | Serverless (Lambda/Cloud Run) if idle-cost matters |
| Feature freshness | Live Redis lookup | Adds latency to hot path | Precompute/cache surge multiplier on short TTL |
| Cache layer | Redis (shared) | Ops overhead of clustering | Single-node Redis with AOF, or Caffeine (in-memory, single-instance) |
| Event streaming | Kafka | Heavy to operate at small scale | RabbitMQ, or Redis Pub/Sub + polling for v1 |
| Real-time push | WebSocket + Redis backplane | Sticky-session/backplane wiring issues | Server-Sent Events, then plain polling as last resort |
| Orchestration | Kubernetes (EKS/GKE) | Cost/complexity for a small project | Docker Compose locally, K3s on a single VM |
| CI/CD compute | GitHub Actions hosted runners | Minutes/cost limits | Self-hosted runner, or migrate to GitLab CI |
| Auth | JWT + OAuth2 | OAuth2 provider setup friction | Ship JWT-only first, OAuth2 additive later |
| Observability | Prometheus + Grafana | Overkill pre-scale | Structured logs + k8s probes only, until a real need arises |

The pattern across all of these: **every fallback degrades gracefully rather than failing hard.** A user should never see an error screen because Redis hiccupped or the ML service was briefly slow — they should see a slightly-less-optimal-but-correct price.

---

## 10. Repository structure

```
surgesense/
├── api-service/            (Spring Boot)
│   ├── src/main/java/...
│   ├── src/test/java/...
│   ├── Dockerfile
│   └── pom.xml
├── ml-service/              (Python)
│   ├── inference/
│   ├── mcp/
│   ├── streaming/
│   ├── training/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── infra/
│   ├── k8s/                 (base manifests + Kustomize overlays: dev/staging/prod)
│   ├── nginx/                (nginx.conf, Dockerfile)
│   └── docker-compose.yml    (full local stack)
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
└── README.md
```

---

## 11. Git workflow

- `main` is always deployable; protected, requires PR review + passing CI.
- Feature branches: `feature/<short-description>`, `fix/<short-description>`.
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`) so changelogs can be generated automatically later.
- PRs must include: what changed, why, and how it was tested. No direct pushes to `main`.
- Squash-merge to keep `main`'s history readable; the feature branch's messy WIP commits don't need to survive.

---

## 12. Local development setup

```bash
# clone
git clone https://github.com/<you>/surgesense.git
cd surgesense

# spin up the full stack (Postgres, Redis, Kafka, both services, Nginx)
docker compose -f infra/docker-compose.yml up --build

# api-service: http://localhost:8080
# ml-service:  http://localhost:8000
# via nginx:   http://localhost
```

Run tests independently while developing:
```bash
# Java
cd api-service && mvn test

# Python
cd ml-service && pytest
```

---

## 13. Testing strategy

- **Unit tests:** service-layer logic in isolation (mocked repositories/HTTP clients) — Spring Boot side uses JUnit 5 + Mockito; Python side uses pytest + `unittest.mock`.
- **Integration tests:** Testcontainers spins up real Postgres/Kafka instances for the Java suite so repository/consumer logic is tested against the real thing, not a mock.
- **Contract tests:** a small suite that hits the ML service's `/predict` endpoint with fixed inputs and asserts the output shape (not exact values, since the model can be retrained) — catches breaking API changes between the two services early.
- **Load testing:** a basic k6 or Locust script simulating a burst of quote requests, to sanity-check the HPA actually kicks in and the circuit breaker actually trips when the ML service is throttled.

---

## 14. Deployment runbook

1. Merge to `main` triggers the CI/CD pipeline (build, test, image push).
2. Pipeline deploys to `surgesense-staging` automatically.
3. Smoke-test staging (a scripted health check + one end-to-end quote request).
4. Manual approval gate in GitHub Actions.
5. Pipeline deploys to `surgesense-prod` via rolling update (zero downtime — old pods stay up until new ones pass readiness probes).
6. Post-deploy: watch Grafana dashboards (or logs, in the lightweight setup) for error-rate/latency anomalies for the first 15 minutes.
7. Rollback path: `kubectl rollout undo deployment/<name>` or re-deploy the previous image tag — always keep the last 3 known-good tags available in the registry.

---

## 15. Roadmap / future work

- Replace the static NYC TLC training data with a proper feature store once there's real production traffic to learn from.
- Add a service mesh (Istio/Linkerd) if internal service-to-service traffic grows enough to need mTLS and finer-grained traffic policies.
- Multi-region deployment for latency-sensitive markets.
- A/B testing framework for comparing pricing strategies (Strategy pattern already makes this straightforward to wire up).
- Driver-side ETA model improvements using real GPS trace data instead of haversine-distance approximations.
#   D y n a F a r e  
 