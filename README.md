# NovAtom TCAD Agent

NovAtom TCAD Agent is a simulator-neutral research automation foundation for semiconductor device simulation. A typed `ExperimentSpec` describes regions, profiles, contacts, physics, studies, and observables. Backend adapters compile that contract for DEVSIM today and for a remote licensed Sentaurus installation before the pilot.

The project is intentionally not a collection of named-device scripts. Example devices are ordinary data fixtures that exercise the same compiler path available to researchers.

## Status

This branch implements the local foundation described in the approved design. It is not yet a fabrication-calibrated tool and does not yet execute Sentaurus.

## Development

```bash
/usr/local/bin/python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/pytest -q
```

DEVSIM is installed separately at `/Users/satyagni/Documents/NovAtom Labs/devsim/.venv`. This keeps the simulator executable behind the same process boundary that will later be used by the Sentaurus remote runner.

The installed simulator is DEVSIM `2.9.1`. Its accompanying Apache-2.0 source checkout is pinned at commit `43b41ca845184c47e22b72d144db7e7db8509377` under `/Users/satyagni/Documents/NovAtom Labs/devsim/source`.
