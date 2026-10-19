open! IStd

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

let empty = {dependencies= []; outputs= []; instruction_slices= []; return_aliases= []; alias_evidence= []}

let of_formal_indices indices =
  {empty with dependencies= List.dedup_and_sort indices ~compare:Int.compare |> List.map ~f:(fun i -> Formal i)}

let pp_dependency fmt = function
  | Formal index -> Format.fprintf fmt "formal[%d]" index
  | Global name -> Format.pp_print_string fmt name
  | Pointee index -> Format.fprintf fmt "memory(formal[%d])" index
  | Source source -> Format.fprintf fmt "%s:%d:%d" source.file source.line source.column

let pp_summary fmt {dependencies} =
  Format.fprintf fmt "{%a}" (Pp.comma_seq pp_dependency) dependencies
