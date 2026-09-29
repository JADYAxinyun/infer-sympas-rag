# Infer-SymPas

This directory contains the planned adaptation of SymPas symbolic program slicing to Infer SIL.

## Planned Components

- `checker/`: OCaml checker and abstract domain.
- `configs/`: analysis and slicing-criterion configuration.
- `tests/`: small C programs and expected slices.

## Intended Input

```text
function + target variable or return value
```

## Intended Output

Structured source locations with dependency reasons, for example:

```json
{
  "function": "foo",
  "criterion": "return",
  "locations": [
    {"file": "data_dependency.c", "line": 4, "reason": "data-dependency"}
  ]
}
```

The checker is not implemented yet.
