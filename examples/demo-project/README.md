# Fictional demo library

This directory is a complete but fictional knowledge-library fixture. It does
not describe a real project, person, organization, system, or incident.

`sample-weather-cli` formats synthetic weather records for a command-line demo.
The example contains one project node, one concept, and one lesson so that
search, task-aware context, graph links, and duplicate capture can be tested
without personal data.

From the engine repository root:

```sh
./brain search --library examples/demo-project "cache expiry"

./brain context --library examples/demo-project \
  --project sample-weather-cli \
  --task-type debugging \
  "debug stale cached output"
```

To exercise capture safely, copy this fixture to a temporary directory first.
The checked-in fixture should remain unchanged:

```sh
demo_library="$(mktemp -d)/sample-library"
cp -R examples/demo-project "$demo_library"

./brain learn-extract --library "$demo_library" \
  --project sample-weather-cli \
  --task-type debugging \
  --stdin < examples/demo-project/task-summary.json
```

Because the reusable lesson already exists, a conforming implementation should
suppress a duplicate or reinforce it only when the summary represents an
independent observation. Replaying the exact same summary must not increase the
evidence count.

Do not install this fixture into a new personal library automatically. New
libraries must start with zero knowledge and zero candidates.
