open! IStd

type dependency =
  | Formal of int
  | Global of string
[@@deriving compare, equal]

type summary = {dependencies: dependency list}

let empty = {dependencies= []}

let of_formal_indices indices =
  {dependencies= List.dedup_and_sort indices ~compare:Int.compare |> List.map ~f:(fun i -> Formal i)}

let pp_dependency fmt = function
  | Formal index -> Format.fprintf fmt "formal[%d]" index
  | Global name -> Format.pp_print_string fmt name

let pp_summary fmt {dependencies} =
  Format.fprintf fmt "{%a}" (Pp.comma_seq pp_dependency) dependencies
