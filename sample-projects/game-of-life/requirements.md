# Game of Life Sample Project Requirements

## Purpose

This sample project is a deliberately small, reproducible software project that can be used to evaluate HiggsAgent-driven implementation quality across different models. It must be large enough to require coordination across multiple tickets, small enough to finish quickly, and concrete enough to demonstrate to users in a live walkthrough.

Conway's Game of Life is the reference example because it has clear rules, deterministic behavior, testable state transitions, and an easy demo surface.

## Primary Evaluation Goals

The project should let an evaluator compare models on:

- instruction adherence
- ability to execute independent tickets in parallel
- correctness under test-driven constraints
- quality of project structure and documentation
- consistency of implementation choices across agents
- ability to produce a demonstrable working result

## Project Outcome

The finished sample project must provide a small Python application that simulates Conway's Game of Life and exposes both a library API and a CLI demo interface.

The project must be structured so that a coordinator can hand individual tickets to multiple agents with minimal overlap and with clear validation boundaries.

## Required Deliverables

The project must include all of the following:

- a Python package under `src/game_of_life`
- a command-line entrypoint that can load or generate a board and run the simulation
- deterministic core simulation logic for one-step and multi-step evolution
- support for at least a fixed board mode and one optional seeded/random initialization mode
- board parsing and serialization helpers for plain-text patterns
- unit tests for rule correctness and edge cases
- integration tests for the CLI demo flow
- a concise README explaining installation, usage, and demo commands
- a small pattern fixture set with at least `block`, `blinker`, and `glider`
- a demonstration path that a user can run locally in under a minute

## Functional Requirements

### Core Domain

The simulation must implement standard Conway's Game of Life rules:

- any live cell with fewer than two live neighbors dies
- any live cell with two or three live neighbors lives on
- any live cell with more than three live neighbors dies
- any dead cell with exactly three live neighbors becomes a live cell

The implementation must use deterministic state transitions.

The domain layer must support:

- constructing a board from dimensions plus live-cell coordinates
- constructing a board from a plain-text pattern format
- advancing the board by one generation
- advancing the board by `n` generations
- counting live cells
- rendering the board as stable plain text

### CLI Surface

The CLI must support a command flow such as:

- run a named built-in pattern
- run a pattern loaded from a file
- choose board width and height when appropriate
- choose number of generations to simulate
- optionally animate output in terminal mode, or print final board only

The CLI must produce output that is readable in logs and suitable for screenshot-based demo use.

### Patterns and Fixtures

The project must ship with at least these patterns:

- `block`
- `blinker`
- `glider`

Pattern definitions must be reusable in both tests and the CLI.

## Non-Functional Requirements

### Reproducibility

The project must be reproducible from a clean checkout with a short documented setup path.

Preferred workflow:

- `uv sync`
- `uv run pytest`
- `uv run python -m game_of_life.cli ...`

If randomness is used for seeded board generation, the CLI and library must allow an explicit seed so tests and comparisons remain deterministic.

### Parallel Workability

The work must be intentionally separable into at least 10 tickets, with several tickets available in parallel after the project scaffold is in place.

The backlog should allow concurrent work across at least these streams:

- project scaffolding
- core simulation logic
- parsing and fixtures
- CLI implementation
- testing
- documentation and demo polish

### Demonstrability

A user should be able to run one or two commands and see:

- a stable pattern stay stable
- an oscillator alternate as expected
- a glider move across the board over several generations

The demo must be suitable for comparing output quality and instruction adherence across models.

## Suggested Technical Scope

This sample should stay intentionally small.

Target scope:

- single-package Python project
- standard library first
- optional third-party dependencies only if they clearly simplify packaging or testing
- no web UI
- no database
- no network access
- no persistent service process

## Repository Layout

The intended project layout is:

```text
sample-projects/game-of-life/
  README.md
  pyproject.toml
  requirements.md
  src/
    game_of_life/
      __init__.py
      board.py
      patterns.py
      simulation.py
      cli.py
  tests/
    test_board.py
    test_simulation.py
    test_patterns.py
    test_cli.py
  fixtures/
    patterns/
      block.txt
      blinker.txt
      glider.txt
  tickets/
    ...
```

Exact filenames may vary, but the project must keep a clear separation between domain logic, CLI surface, fixtures, and tests.

## Validation Requirements

The final project must provide automated checks proving it works.

Minimum validation surface:

- unit tests for board representation and rule transitions
- unit tests for known canonical patterns
- integration tests for at least one CLI invocation
- one command in the README that runs the full test suite

Recommended validation cases:

- empty board remains empty
- block remains unchanged
- blinker alternates every generation
- glider position after multiple generations matches expectation
- invalid pattern input returns a clear error
- CLI can load a built-in pattern and print expected output

## Demo Requirements

The README must include a short demo script with commands that show:

- setup
- running tests
- running `block`
- running `blinker`
- running `glider`

The demo commands should be chosen so an evaluator can compare different model outputs and implementation quality without needing extra explanation.

## Ticketing Requirements

The local ticket board for this sample project must contain at least 10 meaningful tickets.

The tickets should be split so they support parallel execution and review. At minimum, the ticket set should cover:

- project scaffold and packaging
- board model
- simulation rules
- named pattern fixtures
- text parsing and serialization
- CLI surface
- unit test coverage for core rules
- integration test coverage for CLI
- README and demo walkthrough
- final validation and polish

Dependencies should be used sparingly. The ideal structure is:

- one initial scaffold ticket
- several independent implementation tickets that can run in parallel after scaffold completion
- a final validation or polish ticket that depends on earlier implementation tickets

## Success Criteria

This sample project is successful if:

- agents can pick up and complete tickets in parallel with low coordination overhead
- the resulting project is easy to run and verify locally
- the test suite gives a clear pass or fail signal
- the demo is understandable to a non-expert user
- the work product is rich enough to compare model behavior, but small enough to finish quickly

## Explicit Out of Scope

The sample project does not need:

- multiplayer or interactive UI features
- graphical rendering beyond terminal/plain-text output
- performance optimization beyond clarity and correctness
- distributed execution
- persistent storage
- authentication, APIs, or external services
- advanced pattern editors

## Notes For Evaluators

This sample is intended to be reused as a benchmark harness input for HiggsAgent comparisons. The requirements and ticket graph should stay stable enough that multiple models can be evaluated against the same project definition and measured on completeness, correctness, and adherence.