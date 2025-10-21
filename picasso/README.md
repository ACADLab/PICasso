# PICasso (refactored)

This refactor wraps your proven validators and API clients in a clean, testable
package with a stable interface.

## Highlights
- Clear package layout with cohesive modules
- `ChatClient` abstraction with OpenAI and HF backends
- Unified `Validator` interface with adapters for your DRC/PNR/SAX implementations
- Adaptive retry policy that feeds validator feedback to the LLM
- `PICasso.generate(prompt)` orchestrates the full loop
- Small CLI: `python -m picasso.cli "Design a 50:50 MMI"`

## Keeping your functionality
The adapters import your original modules (`drc_validator.py`, `pnr_validator.py`,
`sax_validator.py`) at runtime when available, so your existing, fully working
validators are used as-is. The same approach applies to the OpenAI/HF clients if
you prefer to swap them in.

## Optional deps
- DRC may require KLayout
- SAX requires `sax`, `jax`, `jaxlib`

