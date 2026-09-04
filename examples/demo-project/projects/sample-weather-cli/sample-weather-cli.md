---
graph_version: 1
id: project:sample-weather-cli
type: project-knowledge
node_role: project
project_id: sample-weather-cli
status: active
authority: canonical
confidence: high
source_type: demo-fixture
created: 2026-01-01
aliases:
  - "Weather CLI Demo"
domain_ids:
  - "command-line-tools"
  - "synthetic-data"
project: []
domains:
  - "[[concepts/cache-expiry|Cache Expiry]]"
related:
  - "[[lessons/sample-weather-cli/cache-expiry|Validate cached record age]]"
uses: []
depends_on: []
---

# Sample Weather CLI

Sample Weather CLI is a fictional command-line application that formats
synthetic weather records. It does not contact a real weather service.

## Purpose

Demonstrate Portable Agent Brain retrieval and graph behavior without using
personal or production data.

## Current source

The imaginary application reads deterministic records from a local fixture,
caches the formatted output, and prints it to standard output.

## Constraints

- Tests use a fixed clock.
- Cache lifetime is configuration, not a hard-coded constant.
- Expired records must be recomputed before display.

## Verification

Unit tests cover fresh, boundary-age, and expired cache records.
