# AI Content Studio — Product Architecture

## Product Definition

AI Content Studio is an AI-powered Content Operating System that tells businesses and creators what to create, helps them create it, and learns what works.

Core loop:

Understand
→ Decide
→ Brief
→ Create
→ Publish
→ Measure
→ Learn
→ Understand

## Universal Content Profile

ContentProfile is the universal strategic root entity.

Supported types include:

* creator
* business
* personal_brand
* expert
* coach
* startup
* local_business
* ecommerce_brand

Business and creator users share the same intelligence and strategy architecture.

## Business Context

BusinessContext is optional.

It may contain:

* products
* services
* offers
* commercial objectives

Creators do not need BusinessContext.

## Content Intelligence

Content Intelligence is the central brain.

It contains:

### Brand Intelligence

Identity, positioning, topics, expertise, voice, tone, visual identity, USP, pillars and goals.

### Audience Intelligence

Personas, pain points, desires, questions, objections, motivations, language, preferences and engagement behavior.

### Market Intelligence

Topics, trends, signals, competitors, creator benchmarks, market conversations and emerging opportunities.

### Performance Intelligence

Content performance, winning patterns, failure patterns, hooks, formats, retention, engagement, CTAs and explanations of why content worked or failed.

## Strategy

Strategy converts intelligence into decisions.

The required flow is:

Intelligence
→ Opportunity
→ Brief
→ Creation

Never:

Trend
→ Content Generation

## Content Opportunity

A ContentOpportunity is a strategically evaluated reason for a profile to create content.

Possible sources:

* trend
* performance_gap
* audience_question
* pillar_rotation
* market_conversation

## Content Brief

A ContentBrief is the contract between strategy and creation.

It can contain:

* objective
* platform
* audience
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

## Creation

Creation is an execution layer.

Capabilities may include:

* copy
* image
* video
* UGC
* Blitz
* Remix
* asset assembly

Creation follows the ContentBrief.

## Performance and Learning

Published content produces performance data.

Performance Intelligence explains WHY content worked or failed.

Learnings feed back into Content Intelligence.

## Creator Example

A creator can have:

ContentProfile
→ Brand Intelligence
→ Audience Intelligence
→ Market Intelligence
→ Performance Intelligence

without:

BusinessContext

A creator may focus entirely on:

* sports
* comedy
* photography
* fitness
* gaming
* education
* lifestyle

The same strategy engine must support them.

## Business Example

A business can have:

ContentProfile
→ BusinessContext
→ Brand Intelligence
→ Audience Intelligence
→ Market Intelligence
→ Performance Intelligence

BusinessContext adds commercial information but does not replace universal intelligence.

## Architectural Principle

The product should answer:

"What should this specific profile create next, and why?"

not merely:

"What is trending?"

and not merely:

"Can AI generate a post?"
