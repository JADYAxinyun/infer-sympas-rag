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
[@@deriving equal]

type summary = {dependencies: dependency list; outputs: output list;
                instruction_slices: (source * dependency list) list;
                return_aliases: dependency list; alias_evidence: (string * string list) list;
                fixpoint_iterations: int; fixpoint_members: string list}
[@@deriving equal]

let empty = {dependencies= []; outputs= []; instruction_slices= []; return_aliases= []; alias_evidence= [];
             fixpoint_iterations= 0; fixpoint_members= []}

let union compare lhs rhs = List.dedup_and_sort (lhs @ rhs) ~compare

let union_pairs compare_key compare_value lhs rhs =
  let pairs = lhs @ rhs in
  union compare_key (List.map lhs ~f:fst) (List.map rhs ~f:fst)
  |> List.map ~f:(fun key ->
       let values = List.concat_map pairs ~f:(fun (other, values) ->
           if Int.equal (compare_key key other) 0 then values else []) in
       key, List.dedup_and_sort values ~compare:compare_value)

let join lhs rhs =
  { empty with
    dependencies= union compare_dependency lhs.dependencies rhs.dependencies;
    return_aliases= union compare_dependency lhs.return_aliases rhs.return_aliases;
    outputs= union_pairs compare_dependency compare_dependency
        (List.map lhs.outputs ~f:(fun {target; dependencies} -> target, dependencies))
        (List.map rhs.outputs ~f:(fun {target; dependencies} -> target, dependencies))
      |> List.map ~f:(fun (target, dependencies) -> {target; dependencies});
    instruction_slices= union_pairs compare_source compare_dependency lhs.instruction_slices rhs.instruction_slices;
    alias_evidence= union_pairs String.compare String.compare lhs.alias_evidence rhs.alias_evidence }

let of_formal_indices indices =
  {empty with dependencies= List.dedup_and_sort indices ~compare:Int.compare |> List.map ~f:(fun i -> Formal i)}

let pp_dependency fmt = function
  | Formal index -> Format.fprintf fmt "formal[%d]" index
  | Global name -> Format.pp_print_string fmt name
  | Pointee index -> Format.fprintf fmt "memory(formal[%d])" index
  | Source source -> Format.fprintf fmt "%s:%d:%d" source.file source.line source.column

let pp_summary fmt {dependencies} =
  Format.fprintf fmt "{%a}" (Pp.comma_seq pp_dependency) dependencies
