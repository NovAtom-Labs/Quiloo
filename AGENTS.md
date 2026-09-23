# TCAD Agent Engineering Rules

- Treat `ExperimentSpec` as the simulator-neutral product contract.
- Never branch product behavior on a named device such as a diode, MOS capacitor, or MOSFET.
- Keep simulator syntax inside its adapter package.
- Refuse unsupported physics instead of approximating it silently.
- Derive reported numeric values from canonical result fields.
- Preserve source, version, hash, compiler, simulator, and validation provenance.
- Never place proprietary Sentaurus documentation or credentials in the repository.
- Add behavior with a failing test first and run the complete suite before committing.

