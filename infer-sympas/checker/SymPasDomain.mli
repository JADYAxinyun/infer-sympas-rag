type source = {procedure: string; file: string; line: int; column: int;
               instruction: string; control: bool; callee: string option;
               target: string option; event: string} [@@deriving compare, equal]

type dependency =
  | Formal of int
  | Global of string
  | Pointee of int
  | Heap of string
  | Source of source
[@@deriving compare, equal]

type output = {target: dependency; dependencies: dependency list; aliases: dependency list}
[@@deriving equal]

type summary = {dependencies: dependency list; outputs: output list;
                instruction_slices: (source * dependency list) list;
                variable_slices: ((source * string) * dependency list) list;
                return_aliases: dependency list; alias_evidence: (string * string list) list;
                fixpoint_iterations: int; fixpoint_members: string list}
[@@deriving equal]

val empty : summary

val join : summary -> summary -> summary

val of_formal_indices : int list -> summary

val pp_summary : Format.formatter -> summary -> unit
