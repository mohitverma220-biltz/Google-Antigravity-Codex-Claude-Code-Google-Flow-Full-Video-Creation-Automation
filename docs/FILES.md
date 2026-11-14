# File inventory

The repository inventory below lists the core workflow files, templates, documentation, and zero-generation acceptance test suite. Workflow updates and production lessons are documented in [LESSONS_LEARNED.md](LESSONS_LEARNED.md) and the [acceptance report](ACCEPTANCE.md). All paths below are relative to the workspace root.

```text
AGENTS.md                         Agent chat entry points and operating rules
README.md                         Overview, architecture diagrams, and usage guide
.gitignore                        Excludes local projects, media outputs, and secrets
flow.py                           Standard-library production journal and local media runner

0. General_Best Practices for Workflows/
  CLAUDE.md                       Agent workflow best-practice instructions
  CODEXBESTPRACTICES.md.txt       Codex operating best practices
  EXAMPLES.md                     Reference workflow examples
  README.md                       Overview of general workflow practices

templates/
  manifest.json                   Reusable structured project/shot schema
  brief.md                        Brief and production limits
  continuity.md                   Supplied/generated references and cut-critical details
  edit-list.md                    Selected clips and trim points
  review.json                     Concrete visual/playback review record
  dialogue-shot.json              Sole-speaker dialogue, silent lead-in and ending-hold contract
  recovery-provenance.json        Source evidence for an existing Flow download
  video-intake.md                 Intake, delivery authorization and storage decisions

docs/
  PRODUCTION.md                   Planning, MCP execution, fallback, recovery and delivery
  CAPABILITIES.md                 Installed operation map and model/schema limitations
  VIDEO_RECIPE.md                 Step-by-step recipe for dialogue and frame-chained videos
  ACCEPTANCE.md                   Executed tests and zero-generation verification report
  LESSONS_LEARNED.md              Production findings and mitigation contracts
  FILES.md                        This inventory
  discovery/
    cli-help.txt                  Captured installed CLI modes and command help
    mcp-tools.json                Exact registered MCP tool declarations
    final-status.json             Read-only connector/Edge/usage snapshot
    final-jobs.json               Read-only empty recent-job result
    acceptance-tests.txt          Final passing test output
    acceptance-result.json        Machine-readable acceptance result and interruption trace
    workflow-update-tests.txt     48-test regression output
    workflow-update-result.json   Machine-readable 48-test result

tests/
  test_workflow.py                Original zero-Flow-generation acceptance tests
  test_lessons.py                 Dialogue, payload, recovery, timing and expiry regressions
  fixtures/ceramicist-plan.json   Frozen plan fixture used by unit tests
```

Python bytecode caches and active `projects/<slug>/` directories are git-ignored so local media outputs and user characters are never committed.
