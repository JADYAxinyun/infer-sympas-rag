# Development Roadmap

## Phase 1 — Infer-SymPas

1. Build Infer and analyze a tiny C program.
2. Register a checker that can report analyzed procedures.
3. Implement intraprocedural backward data-dependence slicing.
4. Add control-dependence handling.
5. Add symbolic procedure summaries and call-site instantiation.
6. Export source locations and compare with hand-written expected slices.

**Minimum success criterion:** given a target variable or return value, the checker retains all relevant statements and excludes an irrelevant assignment in a small C program.

## Phase 2 — SymPas-RAG

1. Invoke the checker from a small Python adapter.
2. Convert source locations into ordered code context.
3. Build a fixed-format prompt.
4. Compare full-function, fixed-window and SymPas-slice contexts.

## Phase 3 — LLM Verification Loop

1. Ask the LLM for a structured candidate fact.
2. Validate format and evidence locations.
3. Check consistency with static facts.
4. Write accepted facts back to the analysis pipeline.

## Phase 4 — Agent Extension

Add tool selection, retry, slice expansion and compile/test feedback only after the previous phases are reproducible.
