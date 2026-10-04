type dependency =
  | Formal of int
  | Global of string
[@@deriving compare, equal]

type summary = {dependencies: dependency list}

val empty : summary

val of_formal_indices : int list -> summary

val pp_summary : Format.formatter -> summary -> unit
