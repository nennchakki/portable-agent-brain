# Fictional demo library

This directory is a complete but fictional knowledge-library fixture. It does
not describe a real project, person, organization, system, or incident.

`sample-weather-cli` formats synthetic weather records for a command-line demo.
The example has a project note, a topic note, and a lesson. It lets you test
search, note selection for a task, links between notes, and duplicate checks
without personal data.

From the engine repository root:

```sh
./brain search --library examples/demo-project "cache expiry"

./brain context --library examples/demo-project \
  --project sample-weather-cli \
  --task-type debugging \
  "debug stale cached output"
```

To try saving notes safely, copy this example to a temporary directory first.
The checked-in fixture should remain unchanged:

```sh
demo_library="$(mktemp -d)/sample-library"
cp -R examples/demo-project "$demo_library"

./brain learn-extract --library "$demo_library" \
  --project sample-weather-cli \
  --task-type debugging \
  --stdin < examples/demo-project/task-summary.json
```

Because the lesson already exists, the tool should avoid making a duplicate.
It may add supporting evidence to an existing unreviewed note only when the
summary describes an independent observation. Submitting the exact same
summary again must not increase the evidence count.

Do not install this fixture into a new personal library automatically. New
libraries must start with zero saved notes, including notes awaiting review.
