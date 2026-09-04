---
graph_version: 1
id: concept:cache-expiry
type: concept
concept_key: cache-expiry
status: active
authority: verified
confidence: high
source_type: demo-fixture
created: 2026-01-01
aliases:
  - "Cache lifetime"
domain_ids:
  - "caching"
domains: []
related:
  - "[[projects/sample-weather-cli/sample-weather-cli|Sample Weather CLI]]"
  - "[[lessons/sample-weather-cli/cache-expiry|Validate cached record age]]"
---

# Cache Expiry

Cache expiry is the rule that determines when a cached record is too old to be
reused. The decision requires both a capture time and a configured maximum age.
