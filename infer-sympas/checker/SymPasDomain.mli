type source = {procedure: string; file: string; line: int; column: int;
               instruction: string; control: bool; callee: string option;
               target: string option; event: string} [@@deriving compare, equal]

type dependency =
  | Formal of int
  | Global of string
  | Pointee of int
  | Source of source
[@@deriving compare, equal]

type output = {target: dependency; dependencies: dependency list}

type summary = {dependencies: dependency list; outputs: output list;
                instruction_slices: (source * dependency list) list;
                return_aliases: dependency list; alias_evidence: (string * string list) list}

val empty : summary

val of_formal_indices : int list -> summary

val pp_summary : Format.formatter -> summary -> unit
