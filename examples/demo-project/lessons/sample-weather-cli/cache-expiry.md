---
graph_version: 1
id: lesson:sample-weather-cli/cache-expiry
type: lesson
project_id: sample-weather-cli
status: active
authority: verified
confidence: high
source_type: demo-fixture
created: 2026-01-01
aliases:
  - "Reject stale cache records"
domain_ids:
  - "caching"
project:
  - "[[projects/sample-weather-cli/sample-weather-cli|Sample Weather CLI]]"
domains:
  - "[[concepts/cache-expiry|Cache Expiry]]"
related: []
caused_by: []
---

# Validate cached record age

## What happened

The fictional CLI reused a cached record whenever the cache file existed, even
when the record was older than its configured lifetime.

## Root cause

The cached record did not include a capture time, so the reader could not make
an age decision.

## Correct approach

Store `captured_at` with each synthetic record and compare it with a configured
maximum age before reuse.

## Prevention

Keep cache-lifetime policy separate from file-existence checks and inject a
clock into tests.

## Verification

Tests with a fixed clock cover a fresh record, a record exactly at the expiry
boundary, and an expired record.
