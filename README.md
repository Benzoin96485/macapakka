# macapakka

An agent system that turns local audio evidence into a cappella arrangement drafts, using Prime Inference for arrangement and review tool calls.

## Development entry points

- [`agent_system/`](agent_system/README.md): current source, installation, configuration, and usage.
- [`agent_system/vibacappella/`](agent_system/vibacappella/): audio analysis, arrangement, validation, and export.
- [`agent_system/tests/`](agent_system/tests/): offline tests.
- [`agent_system/examples/prime.toml`](agent_system/examples/prime.toml): Prime configuration.
- [`tools/`](tools/) and [`legacy/`](legacy/README.md): packaging tools and historical source. Some require historical data available only on the original machine.

## Installation and checks

Python 3.11 or later is required:

```sh
cd agent_system
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Install audio analysis, rendering, and font dependencies as described in the system documentation. These dependencies are not distributed with the repository.

## Prime API key

Copy `agent_system/secrets/prime.env.example` to `prime.env` in the same directory and set `PRIME_API_KEY`. Edit an existing file directly. Optional `PRIME_MODEL` and `PRIME_TEAM_ID` values select the model and billing team. Environment variables override file values.

Actual credentials, environment files, recordings, run directories, experimental results, models, and local dependencies are excluded from version control. The example model is `z-ai/glm-5.3`; consult the Prime model catalog for availability and tool capabilities. Generated arrangements require human listening review.

## Ongoing development

This directory is connected to `Benzoin96485/macapakka` on GitHub. Continue development and commit changes here. Tests and configuration instructions are maintained under `agent_system/`. Historical experimental data remains in its original local location and is not uploaded.

Repository documentation is maintained in English.
