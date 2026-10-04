type dependency =
  | Formal of int
  | Global of string
[@@deriving compare, equal]

type summary = {dependencies: dependency list}

val pp_summary : Format.formatter -> summary -> unit
