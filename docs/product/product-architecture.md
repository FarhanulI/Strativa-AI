# AI Content Studio — Product Architecture

## Product Definition

AI Content Studio is an AI-powered Content Operating System that tells businesses and creators what to create, helps them create it, and learns what works.

The product is fundamentally a **personalized content strategy and intelligence system**, not simply an AI content generator, trend feed, analytics dashboard, scheduler, or collection of disconnected AI tools.

Core loop:

```text
Understand
→ Decide
→ Brief
→ Create
→ Publish
→ Measure
→ Learn
→ Understand
```

The central product question is:

> **What should this specific profile create next, and why?**

Answering that question requires more than storing facts about a profile. It requires **reasoning** over those facts — which is why the LLM is a core reasoning capability of the Understand and Decide stages, not only the Create stage. See **LLM Role in Content Intelligence and Strategy** for the architectural rule that governs this.

This document describes both the product architecture (intelligence, strategy, creation, learning) and the platform architecture (tenancy, security, AI job control, data and operations) that a multi-tenant deployment of it requires. See **Production Readiness Model** for the stages in which those platform requirements must be met.

---

# Universal Content Profile

`ContentProfile` is the universal strategic root entity.

Supported profile types include:

* creator
* business
* personal_brand
* expert
* coach
* startup
* local_business
* ecommerce_brand

Business and creator users share the same Content Intelligence and Strategy architecture.

The system does not fundamentally ask:

> "What business do you have?"

It asks:

> "Who are you, what do you want to be known for, who do you want to reach, what are you trying to achieve, what is happening in your market, and what should you create next?"

---

# Business Context

`BusinessContext` is an optional extension of `ContentProfile`.

It may contain:

* products
* services
* offers
* commercial objectives

BusinessContext influences strategy when relevant but does not replace the universal intelligence architecture.

Creators do not need BusinessContext.

A creator can use the full strategy system for:

* growth
* authority
* engagement
* audience development
* personal brand building

If a creator later launches a product or service, BusinessContext can be added without changing the underlying ContentProfile or Strategy Engine.

---

# Content Intelligence

Content Intelligence is the **central brain** of the Content Operating System.

It answers:

> **What is happening around this profile, its audience, its market, and its content performance—and what does that mean for what should be created next?**

## Core Principle

> **Content Intelligence = Data + Deterministic Analysis + LLM Reasoning**

Content Intelligence is not a data store, and it is not an LLM improvising freely on a prompt. It is the combination of three layers, and all three are required:

1. **Structured data** — the facts a profile, its audience, its market, and its performance actually consist of.
2. **Deterministic analysis** — calculations, thresholds, comparisons, and scores computed by application code against that data.
3. **LLM reasoning** — interpretation and synthesis of what the data and the deterministic analysis mean, for this specific profile, audience, and goal.

The LLM's job inside Content Intelligence is to answer questions such as:

> "What does this information mean for this specific profile, audience, and goal?"

The LLM must **not** simply generate content from raw signals. Reasoning about meaning and generating execution output are different tasks with different grounding requirements — see **Deterministic vs LLM Responsibilities**.

Content Intelligence contains four major domains. Each domain now has both a data layer and an LLM reasoning layer.

---

## Brand Intelligence

Brand Intelligence represents what the profile is and how it should communicate.

**Data layer** includes:

* identity
* positioning
* topics
* expertise
* goals
* content pillars
* voice
* tone
* visual identity
* USP
* communication rules

**LLM reasoning layer:** the LLM analyzes the profile's positioning, expertise, voice, tone, topics, and goals to derive strategic brand insights — for example, identifying an underused content pillar relative to stated goals, or a tension between stated positioning and actual topic coverage. This reasoning is grounded in the stored Brand Intelligence data; it does not invent brand facts the profile has not provided.

Brand Intelligence applies equally to businesses and creators.

Example business:

> Affordable premium sportswear for young athletes.

Example creator:

> An energetic football commentator who explains complex tactical concepts simply.

---

## Audience Intelligence

Audience Intelligence represents who the profile wants to reach and what that audience cares about.

**Data layer** may contain:

* personas
* pain points
* desires
* questions
* objections
* motivations
* language
* preferences
* behavioral patterns
* engagement patterns
* audience signals

**LLM reasoning layer:** the LLM synthesizes audience questions, pain points, desires, comments, and engagement patterns to identify meaningful audience needs — connecting scattered signals (a recurring question, a cluster of similar objections, an engagement pattern on a format) into a coherent statement of what the audience actually needs next, rather than treating each signal in isolation.

Audience Intelligence evolves as the platform learns from new audience behavior and content performance.

**Grounding basis:** reasoning may be grounded on accumulated signal/record data (personas, pain points, questions — `observed`), on onboarding-stated profile data (a stated target-audience description, stated goals — `stated`), or both (`mixed`). A brand-new profile with no engagement history yet is not "insufficient data" — its onboarding-stated audience description is valid grounding in its own right, independent of whether any signal has been observed yet. See **Cold Start / Activation Mode** for how this applies to cross-domain synthesis.

---

## Market Intelligence

Market Intelligence represents the external environment surrounding the profile.

**Data layer** may contain:

* topics
* trends
* market signals
* competitors
* creator benchmarks
* market conversations
* emerging topics
* ecosystem changes

**LLM reasoning layer:** the LLM interprets trends, competitors, formats, and market signals **in the context of the specific profile and audience** — a trend is only meaningful once the LLM has reasoned about whether and how it connects to this profile's positioning and this audience's needs. A trend the LLM cannot connect to profile or audience context is not elevated into strategy.

Market signals remain **inputs into strategy**, never automatic content-generation commands, regardless of how the LLM characterizes them.

**Grounding basis:** as with Audience Intelligence, Market reasoning may be grounded on accumulated signal data (topics, market signals, competitors — `observed`), on onboarding-stated profile data (stated topics, expertise, positioning — `stated`), or both (`mixed`). A profile with no observed market signals yet can still reason about its market from what it stated about itself at onboarding.

---

## Performance Intelligence

Performance Intelligence represents what the profile has learned from its published content.

**Data layer** may contain:

* content performance
* historical baselines
* winning patterns
* underperforming patterns
* hooks
* formats
* retention
* engagement
* shares
* saves
* comments
* clicks
* conversions
* CTA performance
* audience response
* creative patterns

**LLM reasoning layer:** the LLM analyzes structured performance data and deterministic performance analysis to explain **why** content succeeded or failed, rather than only reporting metrics.

Example:

> "POV tactical videos consistently generate more shares because they simplify complex football concepts while creating a strong opinion-driven perspective."

Performance Intelligence must answer:

> **Why did this content perform the way it did?**

rather than merely displaying raw analytics. The deterministic analysis (baseline comparison, statistical deltas) is the evidence; the LLM's explanation must be grounded in that evidence, not offered as an unsupported narrative.

Performance learnings become future strategic inputs.

---

## Cold Start / Activation Mode

A brand-new profile has no Performance Intelligence — it hasn't published anything yet. That absence is **expected and normal**, not a data gap, and the system must not treat it as one.

Cross-domain synthesis (see **Content Intelligence is the Central Brain** and the four-domain architecture above) distinguishes two different reasons Performance Intelligence can be missing from the full picture:

1. **Genuine insufficient data** — one or more of Brand, Audience, or Market Intelligence is *also* thin or missing. The system falls back to a deterministic, unenriched result rather than reasoning over gaps, per **Deterministic First, AI Enriched**.
2. **Cold start** — Brand, Audience, and Market Intelligence are all present and adequately grounded (stated, observed, or both), and only Performance is absent, specifically because the profile has not published any content yet. This must be verified directly against the absence of published content and performance records — never merely inferred from Performance Intelligence being empty, since a profile can also lack Performance Intelligence for reasons that *are* a genuine gap (content published, but not yet analyzed).

Cold start is not a reason to degrade the reasoning: synthesis still runs as a full, AI-reasoned output, not a templated fallback. The reasoning is reframed rather than suppressed — it explains what a strong **first** piece of content should be, grounded in the profile's positioning, audience, and market context, and must never fabricate or imply performance history that doesn't exist. The result should read as an inspiring activation recommendation for a new profile, not an apologetic or degraded one.

Once the profile publishes its first content and performance data begins accumulating, cold start resolves automatically through the same staleness/regeneration mechanism that keeps every other domain current — it is a transitional state a profile passes through, not a permanent product mode.

---

# LLM Role in Content Intelligence and Strategy

The LLM is a core reasoning capability of AI Content Studio, but it must **not** become the entire Intelligence or Strategy system.

The system combines:

* Structured data
* Deterministic analysis and calculations
* LLM-based reasoning, interpretation, and synthesis

## Strategy Must Combine All Five Inputs

Strategy must combine:

```text
Profile + Brand + Audience + Market + Performance + Goals
```

with LLM reasoning to determine strategic implications. No single input — including a trend or signal on its own — is sufficient to justify a strategic decision.

## The Forbidden Path

The system must **not** implement:

```text
Trend → LLM → Generate Content
```

Routing a trend directly through an LLM into generated content is exactly what turns AI Content Studio into a generic AI writer. The LLM's presence in the pipeline does not make this path acceptable — the forbidden path is about what's missing (profile, audience, performance, goals), not about which component the trend passes through.

## The Required Flow

```text
Trend / Signal
      +
Profile
      +
Audience
      +
Performance
      +
Goals
      ↓
Content Intelligence
      +
LLM Reasoning
      ↓
Strategy
      ↓
Opportunity
      ↓
Content Brief
      ↓
Creation
```

LLM Reasoning sits inside the Content Intelligence → Strategy transition, grounded in the full profile context — never upstream of it, and never as a substitute for it.

## Deterministic vs LLM Responsibilities

**Deterministic system** — use application code and database logic for:

* data storage
* metrics
* calculations
* trend velocity
* engagement rates
* filtering
* thresholds
* opportunity scoring components
* validation
* permissions
* profile/workspace isolation
* data lineage

**LLM** — use the LLM for:

* interpretation
* synthesis
* pattern recognition
* strategic reasoning
* explaining why
* generating strategic hypotheses
* connecting multiple intelligence signals
* contextual recommendations
* natural-language strategic rationale

The dividing line is not "simple vs. complex" — it is **reproducible computation vs. contextual interpretation**. Anything that must be reproducible, auditable, or gate a workflow decision (a score, a permission check, a lifecycle transition) stays deterministic. Anything that requires understanding what data *means* in context is the LLM's responsibility.

## Architectural Rule

> **The LLM is the reasoning layer, not the source of truth.**

The system's strategic decisions must be grounded in available profile, audience, market, performance, and goal context. An LLM reasoning output that cannot be traced back to stored data or a deterministic calculation is not a valid strategic input — it must be treated as unvalidated narrative, subject to the same discipline described in **Evaluation Validity**.

AI Content Studio's differentiation is not "AI generates content." Its core value is:

> **AI understands the profile, audience, market, and performance, reasons over those signals, decides what content should be created next, and then helps execute that decision.**

---

# Strategy

The Strategy Engine converts Content Intelligence — data, deterministic analysis, and LLM reasoning together — into decisions.

The required strategic flow is:

```text
Content Intelligence
        ↓
Opportunity
        ↓
Content Brief
        ↓
Creation
```

The system must never use:

```text
Trend
   ↓
AI Generation
```

Instead:

```text
Trend
+
Audience
+
Profile
+
Goals
+
Performance
        ↓
Opportunity
        ↓
Brief
        ↓
Creation
```

Strategy determines **what should be created and why**. The "why" is expected to be an LLM-reasoned, context-grounded explanation, not a templated string — see `opportunity_reasoning` under **AI Tasks and AI Capabilities**.

Creation determines **how that strategic decision is executed**.

---

# Content Opportunity

A `ContentOpportunity` is a strategically evaluated reason for a profile to create content.

Possible sources include:

* trend
* performance_gap
* audience_question
* pillar_rotation
* market_conversation

An opportunity may include:

* strategic rationale
* relevance
* opportunity score
* target objective
* recommended format
* priority
* timing

The **opportunity score, relevance, and priority remain deterministic** — computed from signal strength, goal alignment, timing, and accumulated learning, per **Deterministic vs LLM Responsibilities**. The **strategic rationale is an LLM reasoning output** (`opportunity_reasoning`), grounded in the deterministic score components and the Content Intelligence synthesis for that profile — it explains the "why" behind a number the formula already produced, rather than producing the number itself.

The Opportunity Engine prevents blind trend-chasing by evaluating external signals against the profile's:

* positioning
* audience
* goals
* market context
* performance history

---

# Content Brief

A `ContentBrief` is the strategic contract between the Strategy Engine and the Creation Engine.

The brief ensures that content generation remains aligned with strategic intent.

A brief may contain:

* objective
* platform
* target audience
* content pillar
* topic
* hook
* angle
* format
* emotion
* story structure
* key message
* product/offer
* CTA
* visual direction
* audio direction
* duration
* success metrics

The brief's structural fields (objective, platform, pillar, format, success metrics) are composed deterministically from the opportunity and profile context. LLM enrichment (`brief_enrichment`) may improve the language of the angle, hook direction, or key message, but per **Deterministic First, AI Enriched**, a complete deterministic brief must exist independent of whether enrichment succeeds.

The Content Brief is required before major content creation workflows.

---

# AI Infrastructure

AI is an infrastructure and execution layer inside the Content Operating System.

The product does not depend on a single AI provider or model.

The architecture is provider-agnostic:

```text
Application Feature
        ↓
AI Task
        ↓
AI Orchestrator
        ↓
AI Router
        ↓
AI Provider
        ↓
AI Model
        ↓
AI / Media Result
```

The system can select different models based on:

* task
* required capability
* quality requirement
* cost requirement
* latency requirement
* provider availability
* fallback policy

The Content OS owns the intelligence, strategy, opportunities, briefs, and learning.

AI providers are interchangeable reasoning and execution infrastructure.

---

# AI Tasks and AI Capabilities

The architecture distinguishes between an **AI Task** and an **AI Capability**.

### AI Task

An AI Task describes **what the product wants the AI to do**.

AI tasks support both **strategic reasoning** and **execution** use cases. They are AI tasks, not separate strategy engines — there remains **one universal Content Intelligence + Strategy Engine** for all ContentProfile types.

**Strategic reasoning tasks:**

* `brand_analysis`
* `audience_analysis`
* `market_analysis`
* `performance_analysis`
* `strategic_synthesis`
* `opportunity_reasoning`

**Execution tasks:**

* `brief_enrichment`
* `content_drafting`
* `hook_generation`
* `caption_generation`
* `content_evaluation`
* research
* content concept generation
* script generation
* image generation
* video generation
* UGC generation
* voice generation
* remix
* content transformation

### AI Capability

An AI Capability describes **what a model or provider is capable of doing**.

Examples include:

* text generation
* reasoning
* structured output
* web research
* image understanding
* image generation
* video understanding
* video generation
* audio generation
* long context

Tasks and capabilities are separate architectural concepts. This allows the system to determine which model is appropriate for a particular task — a `strategic_synthesis` task requires a reasoning-capable model with structured output and long context (it may need to reason over an entire profile's accumulated intelligence); a `hook_generation` task requires fast, cheap text generation.

---

# Multi-Model AI

The platform is designed to use different AI models for different jobs.

For example:

```text
Brand / Audience / Market Analysis
→ Reasoning-capable LLM

Strategic Synthesis
→ Reasoning-capable LLM (long context)

Opportunity Reasoning
→ Reasoning-capable LLM

Performance Reasoning
→ Reasoning-capable LLM

Research
→ Research-capable model

Content Concepts / Drafting
→ Generative LLM

Image Creation
→ Image Generation Model

Video Creation
→ Video Generation Model

UGC
→ LLM + Video + Voice Models

Voice
→ Audio / Voice Model
```

The specific model can change over time according to:

* capability
* quality
* cost
* latency
* availability
* historical effectiveness

The core product architecture must not depend on any single model vendor.

---

# AI Orchestration and Routing

The AI Orchestrator coordinates AI-powered workflows.

The AI Router selects the appropriate provider/model for an individual AI task.

Conceptually:

```text
AI Task
    ↓
AI Orchestrator
    ↓
AI Router
    ↓
Task Policy
+
Required Capability
+
Quality
+
Cost
+
Latency
    ↓
Selected Provider / Model
```

The Router is infrastructure.

It does not make product strategy decisions.

The Strategy Engine — Content Intelligence's data, deterministic analysis, and LLM reasoning together — decides what content should be created.

The AI infrastructure determines which model is best suited to execute a particular task, whether that task is strategic reasoning or creative execution.

---

# Creation

Creation is an execution layer.

Creation follows the Content Brief.

Creation capabilities may include:

* copy
* hooks
* captions
* scripts
* images
* video
* UGC
* voice
* Blitz
* Remix
* content transformation
* asset assembly

Creation may use multiple AI model types rather than a single LLM.

For example:

```text
Content Brief
      ↓
AI Orchestrator
      ↓
 ┌────┼────────┬────────┐
 ↓    ↓        ↓        ↓
 LLM Image    Video    Voice
 ↓    ↓        ↓        ↓
Text Visual   UGC    Narration
      ↓
Asset Assembly
      ↓
Final Content
```

The Creation Engine is therefore an orchestration and execution system, not simply an AI text generator.

---

# AI Content Creation

Future content-generation workflows may combine multiple specialized models.

### Text Content

LLMs may generate:

* hooks
* angles
* captions
* scripts
* CTAs
* content concepts
* variations

### Image Content

Image generation models may create:

* social creatives
* campaign visuals
* supporting graphics
* product/context visuals
* creative variations

### Video Content

Video models and supporting AI systems may create:

* short videos
* scenes
* animations
* visual sequences
* video variations

### UGC

UGC can combine:

```text
UGC Strategy
→ UGC Script
→ Persona / Character
→ Video Generation
→ Voice
→ Editing
→ Final UGC
```

### Remix

The Remix Engine can transform existing successful content into new variants.

Examples:

* Reel → carousel
* video → text post
* post → UGC
* long video → short video
* existing hook → new hooks
* existing angle → new angles
* existing content → localized version

These are execution capabilities built on top of the strategic system.

---

# Creation Does Not Replace Strategy

The platform must never become:

```text
Prompt
→ AI
→ Random Content
```

It must remain:

```text
Profile
+
Audience
+
Market
+
Goals
+
Performance
        ↓
Content Intelligence
    (Data + Deterministic Analysis + LLM Reasoning)
        ↓
Strategy
        ↓
Opportunity
        ↓
Content Brief
        ↓
AI Creation
        ↓
Content
```

This separation is a core architectural principle. Adding LLM reasoning to Content Intelligence does not weaken this separation — it strengthens the Strategy stage's output without collapsing Strategy and Creation into a single AI call.

---

# Performance and Learning

Published content produces performance data.

The system measures:

* views
* reach
* impressions
* likes
* comments
* shares
* saves
* clicks
* conversions
* retention
* watch time
* completion
* other platform-specific metrics

Performance Intelligence then compares results against appropriate historical baselines (deterministic).

It identifies patterns such as:

* winning hooks
* winning formats
* strong topics
* retention patterns
* audience behavior
* CTA effectiveness
* creative patterns
* underperforming formats
* performance gaps

The system must explain **why** performance changed, using evidence from the available data — the explanation is an LLM reasoning output grounded in the deterministic pattern detection, per **Performance Intelligence** above.

---

# Learning Loop

The Content OS continuously learns from published content.

```text
Content Intelligence
   (Data + Deterministic Analysis + LLM Reasoning)
        ↓
Strategy
        ↓
Opportunity
        ↓
Brief
        ↓
Creation
        ↓
Publish
        ↓
Measure
        ↓
Performance Intelligence
        ↓
Learning
        ↓
Content Intelligence
```

Every meaningful performance result should strengthen future strategic decisions.

Performance is therefore not merely an analytics feature.

It is part of the intelligence system.

---

# Social Platform Architecture

The platform is designed to eventually integrate with external social platforms.

The architectural principle is:

```text
External Platform
        ↓
Platform Adapter
        ↓
Normalization
        ↓
Internal Content / Performance Models
        ↓
Performance Intelligence
```

Potential platforms include:

* Facebook
* Instagram
* TikTok
* YouTube
* LinkedIn
* X

External platform integrations should not leak platform-specific models into the core Content Intelligence architecture.

The internal system should operate on normalized content and performance data.

**Implementation status (Day 23):** the first real `Platform Adapter`
implementations now exist for YouTube, Facebook, and Instagram
(`app/platform_connections/adapters.py`), implementing this section's
connection/authorization surface — OAuth connect, token refresh, and
disconnect — behind the same `SocialPlatformAdapter` contract Day 9
defined. `publish`/`fetch_posts`/`fetch_post`/`fetch_metrics` remain typed
stubs that raise; wiring a real publish call through these adapters is Day
24. TikTok, LinkedIn, and X have no OAuth implementation yet.

A `PlatformConnection` model (one row per `ContentProfile` per platform,
never per `Workspace`) records the credential a profile actually
publishes with. This makes explicit a distinction the architecture had
not previously needed to state: **one OAuth login is not one publishable
destination.** A person has one Facebook login but may administer several
Pages; one Google login but may manage several YouTube channels
(including Brand Account channels); Instagram publishing runs through a
Business Account reachable only via a linked Facebook Page. Because
`ContentProfile` is the universal strategic root and a `Workspace` may
hold several of them, two profiles under the same workspace — and the
same underlying social login — may legitimately need to publish to two
different Pages/Channels. The connect flow therefore has an explicit
destination-selection step between token exchange and persistence, and
never assumes the first (or only) destination an API returns is the
intended one.

Stored credentials are envelope-encrypted at rest (application-level, not
a bare database column), for both the final connection and the short-TTL
pending state held between token exchange and destination selection. A
scheduled job proactively refreshes a token before it expires and marks
a connection `expired` on failure — the "durable, visible failure state,"
never a silent one, that **AI Execution and Job Control** already
requires of AI work applies equally here to platform credentials.

---

# Creator Example

A creator can have:

```text
ContentProfile
    ↓
Brand Intelligence
    ↓
Audience Intelligence
    ↓
Market Intelligence
    ↓
Performance Intelligence
    ↓
Strategy (LLM-reasoned, data-grounded)
    ↓
Content Creation
```

without:

```text
BusinessContext
```

A creator may focus on:

* sports
* comedy
* photography
* fitness
* gaming
* education
* lifestyle

The same Strategy Engine supports all of these profile types.

---

# Business Example

A business can have:

```text
ContentProfile
    ↓
BusinessContext
    ↓
Brand Intelligence
    ↓
Audience Intelligence
    ↓
Market Intelligence
    ↓
Performance Intelligence
    ↓
Strategy (LLM-reasoned, data-grounded)
    ↓
Content Creation
```

BusinessContext adds:

* products
* services
* offers
* commercial objectives

but does not replace universal intelligence.

---

# Identity, Tenancy, and Authorization

The Content OS is a multi-tenant system. Tenancy is therefore an architectural layer, not an endpoint detail.

The required chain is:

```text
Authenticated User
        ↓
Workspace Membership
        ↓
Role / Permissions
        ↓
Workspace
        ↓
ContentProfile
        ↓
Resource
```

Rules:

* The caller's identity is established by the server from an authenticated credential (session, JWT, or OAuth token).
* Workspace context is **derived from membership**, never trusted from a client-supplied identifier.
* Every resource lookup validates the full ownership chain, and a mismatch at any level returns **404** so cross-tenant existence is never leaked.
* Roles determine which workspace actions a member may perform (read, author, approve, administer, billing).
* Identifier-based isolation is not authorization; it is only the last check after identity and membership have been established.

Until identity and membership exist, the system is an internal or controlled-beta workspace, not a public multi-tenant product.

**Implementation status (Day 20):** the "Authenticated User" step of this
chain now exists — `app/auth/` issues and verifies JWT access tokens
(login, refresh with mandatory rotation, logout via Redis-based `jti`
revocation, password reset), and `app/auth/dependencies.get_current_user`
is the one reusable dependency that establishes caller identity from a
verified credential, per the rule above. This API is consumed exclusively
by a trusted Next.js server (BFF pattern) over a server-to-server
connection, never directly by the browser, so both the access and
refresh tokens are returned in the JSON response body rather than a
cookie — browser-facing cookie protections (httpOnly, Secure, SameSite)
are the BFF's responsibility on its own domain, not this API's. The
chain stops there, however:
**every step below "Authenticated User" — Workspace Membership, Role/
Permissions, and the full ownership-chain validation on resource
lookups — remains unimplemented.** `WorkspaceMember.user_id` is a bare,
unenforced `String(255)` with no foreign key to `User.id`, and every
Day 15-19 router still trusts a client-supplied `workspace_id`/
`profile_id` directly rather than deriving it from membership. This is a
live cross-tenant access gap, tracked as Day 21 - Ownership-Chain
Enforcement Retrofit (see `docs/development/progress.md`, Day 20 entry).
Days 15-19 must not be treated as satisfying this section until Day 21
lands.

---

# Platform Security Boundary

Security is part of the product architecture because the Content OS holds a profile's strategy, audience knowledge, and performance history — proprietary information to its owner. It also holds LLM-reasoned strategic conclusions about that profile, which are as sensitive as the raw data they're derived from.

The platform boundary must define:

* authentication on every non-public route
* rate limiting and request-size limits
* abuse protection on AI-backed endpoints
* explicit, environment-specific CORS policy
* security headers
* structured exception handling with safe (non-leaking) error responses
* validated secrets and configuration per environment
* environment-gated API documentation
* audit logs for significant workspace actions

Development-friendly defaults (open docs, permissive CORS, unvalidated config) are acceptable only in development environments and must differ in staging and production.

---

# AI Execution and Job Control

AI is infrastructure, and infrastructure needs operational controls. This applies equally to strategic reasoning tasks (`brand_analysis`, `strategic_synthesis`, `opportunity_reasoning`) and execution tasks (`content_drafting`, image/video generation) — a reasoning call that hangs is as disruptive to the product as a generation call that hangs.

Long-running or provider-dependent AI work belongs in background jobs rather than inside request handling:

```text
Request
   ↓
Job Record (queued)
   ↓
Worker
   ↓
AI Orchestrator → AI Router → Provider
   ↓
Job Record (succeeded | failed | timed out)
   ↓
Client polls / is notified
```

Required controls:

* per-task timeouts, retries, and backoff
* circuit breaking and provider fallback on repeated failure
* durable job status, failure state, and retry visibility
* idempotency protection for generation requests
* token and cost accounting per task
* per-workspace quotas and usage tracking

Deterministic paths remain the safety net: when all providers fail, the system produces the deterministic result and records the degraded source rather than failing the workflow. For strategic reasoning tasks specifically, the deterministic fallback is the un-enriched deterministic analysis (e.g., the scored opportunity without a synthesized rationale, or a templated rationale) — the workflow must never block on LLM reasoning succeeding.

Synchronous AI calls are acceptable only for short, bounded enrichment where a deterministic fallback already guarantees a complete result.

---

# Data and Transaction Architecture

Persistence behavior is part of the architecture, not an implementation detail.

Principles:

* **Transaction ownership sits at the request / unit-of-work boundary.** Services flush during orchestration; the boundary commits or rolls back once, so a multi-step workflow cannot leave partial state.
* **Integrity errors are normalized consistently** into domain-level conflicts rather than surfacing raw database errors.
* **Counts are computed in the database**, not by loading rows into memory and measuring them.
* **Loading is explicit and response-shaped** — eager loading only where a response needs it, and never automatic loading of large child collections.
* **Every potentially large collection is paginated.**
* **Indexes are designed for actual access paths** (foreign keys used in filters, profile + created_at, workspace-scoped lookups, status and lifecycle filtering, performance by profile and publication date) and validated against query plans.
* **Connection pooling, statement timeouts, SSL, and health checks are configured per environment.**

The production database is PostgreSQL. Fast in-memory SQLite tests are a development convenience and do not validate PostgreSQL enum behavior, JSONB semantics, partial unique indexes, concurrency, or migrations — so a PostgreSQL integration pipeline runs migrations and tests against a real instance before release.

---

# Operational Readiness

The Content OS must be observable and recoverable:

* metrics, tracing, and structured logging across request, job, and AI layers
* alerting on provider failure rates, job backlogs, latency, and error budgets
* database backups with tested restores
* CI running tests, migrations, linting, and security checks
* staged environments (development, staging, production) with environment-specific configuration
* API versioning with backward-compatibility tests
* data retention and archival policies
* load and concurrency testing before scale

---

# Evaluation Validity

Quality evaluation (of briefs, drafts, and variations) is a product claim, not only a computation. The same discipline applies to **strategic reasoning outputs** — brand/audience/market synthesis, opportunity rationale, and performance explanations are also claims about reality, not just generated text, and are held to the same standard.

Deterministic heuristics provide a reliable technical fallback, but a score — or a reasoned explanation — is only trustworthy once it is shown to track human judgment. Before evaluation scores or LLM-reasoned strategic conclusions drive significant product decisions (ranking, auto-selection, gating, being presented to the user as "why"), they must be validated against a labeled benchmark comparing:

* human reviewer scores / judgments
* deterministic scores
* AI-enriched scores or reasoning
* user acceptance and revision behavior
* downstream content performance

Unvalidated scores and unvalidated reasoning may inform and rank, but must not silently decide.

---

# Architectural Principles

## 1. Content Intelligence is the Central Brain

All major strategic decisions should be grounded in Content Intelligence — data, deterministic analysis, and LLM reasoning together.

---

## 2. ContentProfile is the Universal Strategic Root

Businesses and creators are profile types, not separate strategy systems.

---

## 3. Business Context is Optional

Commercial information enriches strategy but is not required for creators.

---

## 4. Strategy Comes Before Creation

The platform decides what should be created before AI generates the content.

---

## 5. Trends Are Inputs, Not Commands

A trend alone must never automatically trigger content generation — including when an LLM is the component that would otherwise turn it into content. Presence of LLM reasoning in the pipeline does not exempt a signal from evaluation against profile, audience, goals, and performance.

---

## 6. Content Opportunities Are Required

Signals must be evaluated for profile relevance, audience relevance, goals, timing, and performance before becoming content decisions.

---

## 7. Content Briefs Connect Strategy and Creation

The brief is the contract that keeps generated content aligned with strategic intent.

---

## 8. AI Providers Are Interchangeable

The product must not be architecturally coupled to Gemini, OpenAI, Claude, Perplexity, or any other provider.

---

## 9. AI Tasks and AI Capabilities Are Separate

A task represents what the product wants done.

A capability represents what a model can do.

---

## 10. Multimodal AI is Part of the Long-Term Architecture

The system must support the future use of:

* LLMs
* reasoning models
* image models
* video models
* audio/voice models
* multimodal models

without changing the core Content Intelligence and Strategy architecture.

---

## 11. Performance Intelligence Must Explain WHY

Analytics show what happened.

Performance Intelligence explains what the results suggest and what should be tested next — an LLM reasoning output grounded in deterministic pattern detection.

---

## 12. Learning Must Feed Strategy

Performance learnings must become future intelligence and strategic inputs.

---

## 13. Strategy Optimizes for Both Creators and Businesses

For creators, optimization may focus on:

* growth
* authority
* engagement
* audience development

For businesses, it may additionally focus on:

* leads
* sales
* conversions
* commercial objectives

The underlying Strategy Engine remains the same.

---

## 14. Authorization Is Derived, Never Supplied

The server establishes who the caller is and which workspaces they belong to. A client-supplied workspace or ownership identifier is an input to validate, never a grant of access.

---

## 15. AI Work Is Controlled Work

Every AI task — strategic reasoning or creative execution — has a timeout, a retry policy, a cost accounting, a failure state, and a deterministic fallback. Long-running generation runs as a durable background job, not inside a request.

---

## 16. Deterministic First, AI Enriched

Every AI-assisted output has a complete deterministic form. Enrichment may improve a result but must never be able to destroy it or block the workflow. This applies to strategic rationale exactly as it applies to a generated caption.

---

## 17. Transactions Are Owned at the Boundary

A workflow commits once, at its unit-of-work boundary, so that a multi-step operation never leaves partially applied state.

---

## 18. Tenancy, Security, and Operability Are Architecture

Authentication, quotas, observability, backups, and environment-specific configuration are part of the product architecture, on the same footing as intelligence and strategy — not later additions to a finished system.

---

## 19. The LLM Is a Reasoning Layer, Not the Source of Truth

Content Intelligence and Strategy decisions must be grounded in stored profile, audience, market, performance, and goal data plus deterministic analysis of that data. The LLM interprets and synthesizes; it does not originate facts, does not compute scores that gate workflow decisions, and any LLM-reasoned conclusion presented as strategic insight must be traceable back to the data or calculation that grounds it.

---

# Final Product Architecture

```text
                    AUTHENTICATED USER
                             │
                             ▼
                   WORKSPACE MEMBERSHIP
                    (role / permissions)
                             │
                             ▼
                         WORKSPACE
                             │
                             ▼
                      CONTENT PROFILE
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
      BRAND              AUDIENCE              MARKET
  INTELLIGENCE         INTELLIGENCE         INTELLIGENCE
   (data +               (data +               (data +
    LLM reasoning)        LLM reasoning)        LLM reasoning)
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
                    PERFORMANCE INTELLIGENCE
                     (deterministic analysis +
                      LLM reasoning: explains WHY)
                             │
                             ▼
                   CONTENT INTELLIGENCE
              (Data + Deterministic Analysis +
                      LLM Reasoning)
                             │
                             ▼
                     STRATEGY ENGINE
                             │
                             ▼
                  OPPORTUNITY ENGINE
              (deterministic score + ranking;
               LLM-reasoned strategic rationale)
                             │
                             ▼
                     CONTENT BRIEF
              (deterministic structure;
               LLM-enriched language)
                             │
                             ▼
                    AI ORCHESTRATOR
                  (job queue + retries,
                   timeouts, quotas, cost)
                             │
                             ▼
                       AI ROUTER
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
       TEXT                IMAGE                VIDEO
        │                    │                    │
       LLMs             Image Models         Video Models
        │                                         │
        └────────────────────┬────────────────────┘
                             ▼
                       VOICE / AUDIO
                             │
                             ▼
                      CONTENT ASSETS
                             │
                             ▼
                      ASSET ASSEMBLY
                             │
                             ▼
                          PUBLISH
                             │
                             ▼
                         MEASURE
                             │
                             ▼
                   PERFORMANCE INTELLIGENCE
                             │
                             └──────────→ LEARNING
                                          │
                                          └──→ CONTENT INTELLIGENCE
```

---

# Production Readiness Model

The architecture progresses through readiness stages. A feature is not "done" for a stage until it meets that stage's platform requirements.

### Stage 1 — Controlled Beta (internal / invited workspaces)

Requires:

* authentication and workspace membership authorization
* server-derived workspace context
* validated production secrets and configuration
* rate limiting and request-size limits
* structured exception handling and safe error responses
* PostgreSQL integration tests run against a real instance
* database backups with tested restore
* CI running tests, migrations, linting, and security checks
* AI timeouts, retries, cost limits, and provider failure handling — for both reasoning and execution tasks
* environment-gated API documentation

### Stage 2 — Paid Beta

Adds:

* AI-heavy operations moved to background jobs with status and retry visibility
* workspace quotas and usage tracking
* database-side counts and reviewed query plans and indexes
* standardized transaction ownership
* metrics, tracing, and alerting
* a PostgreSQL staging deployment
* audit logs for significant workspace actions
* API versioning and backward-compatibility tests
* initial validation of LLM-reasoned strategic outputs against human judgment, per **Evaluation Validity**

### Stage 3 — Scale

Adds:

* social platform adapters and ingestion jobs — **connection/authorization
  surface implemented for YouTube, Facebook, and Instagram (Day 23)**;
  publish/ingestion calls through these adapters, and adapters for
  TikTok/LinkedIn/X, remain outstanding
* publishing and scheduling
* durable performance synchronization and content→performance attribution
* model/provider fallback policies
* caching for stable intelligence reads
* data retention and archival policies
* load and concurrency testing
* tenant-level usage isolation and billing enforcement

Until the full loop — connected accounts, publishing, measurement, and automated learning — is operational, the system is a strategy and intelligence workspace rather than a complete Content Operating System. **Connected accounts** now has a first real implementation (Day 23: OAuth connect/disconnect and destination selection for YouTube, Facebook, and Instagram); publishing through those connections, measurement, and automated learning from real platform data remain outstanding.

The ordering principle: **security and platform reliability precede additional creative-generation capability.**

---

# Core Architectural Statement

> **AI Content Studio is an AI-powered Content Operating System that understands a profile, reasons over its brand, audience, market, and performance signals using both deterministic analysis and LLM reasoning, decides what content opportunity matters, creates a strategic brief, uses the best available AI models to execute it, measures the result, and continuously learns what to create next.**

Short positioning:

> **AI that figures out what content you should create next.**

The architectural priority order is: prove the intelligence → strategy → brief → creation → learning loop, then make it safe, controlled, and operable for many tenants, and only then broaden creative generation.