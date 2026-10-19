(* Symbolic formal/global and output-memory propagation over forward SIL CFGs.
 * Follows the parameter substitution in SymPas equations (3), (8), (10), (11).
 * Aggregate locations are collapsed; uncertain writes are weak updates.
 * Instruction snapshots retain transitive source tokens for criterion queries.
 * Control and aggregate-memory semantics remain conservative approximations.
 *)
open! IStd

module Key = struct
  type t = string [@@deriving compare]
  let pp = Format.pp_print_string
end

module Dependency = struct
  type t = SymPasDomain.dependency [@@deriving compare]
  let pp fmt = function
    | SymPasDomain.Formal i -> Format.fprintf fmt "formal[%d]" i
    | SymPasDomain.Pointee i -> Format.fprintf fmt "memory(formal[%d])" i
    | SymPasDomain.Global name -> Format.pp_print_string fmt name
    | SymPasDomain.Source source -> Format.fprintf fmt "%s:%d" source.file source.line
end

module Deps = AbstractDomain.FiniteSet (Dependency)
module Targets = AbstractDomain.FiniteSet (Key)
module Values = AbstractDomain.Map (Key) (Deps)
module Aliases = AbstractDomain.Map (Key) (Targets)

type analysis_data =
  { interprocedural: SymPasDomain.summary InterproceduralAnalysis.t
  ; postdominators: Procdesc.NodeSet.t Procdesc.NodeMap.t }

let control_key node =
  "control:" ^ Format.asprintf "%a" Procdesc.Node.pp_id (Procdesc.Node.get_id node)

module Domain = struct
  type t = {values: Values.t; aliases: Aliases.t; modified: Targets.t; controls: Deps.t; idt: Values.t}
  let bottom = {values= Values.empty; aliases= Aliases.empty; modified= Targets.empty; controls= Deps.empty; idt= Values.empty}
  let leq ~lhs ~rhs =
    Values.leq ~lhs:lhs.values ~rhs:rhs.values
    && Aliases.leq ~lhs:lhs.aliases ~rhs:rhs.aliases
    && Targets.leq ~lhs:lhs.modified ~rhs:rhs.modified
    && Deps.leq ~lhs:lhs.controls ~rhs:rhs.controls
    && Values.leq ~lhs:lhs.idt ~rhs:rhs.idt
  let join lhs rhs =
    {values= Values.join lhs.values rhs.values; aliases= Aliases.join lhs.aliases rhs.aliases;
     modified= Targets.join lhs.modified rhs.modified; controls= Deps.join lhs.controls rhs.controls;
     idt= Values.join lhs.idt rhs.idt}
  let widen ~prev ~next ~num_iters:_ = join prev next
  let pp fmt state = Values.pp fmt state.values
end

let id_key id = "id:" ^ Format.asprintf "%a" Ident.pp id
let pvar_key pvar =
  if Pvar.is_global pvar then "global:" ^ Pvar.to_string pvar
  else "local:" ^ Pvar.to_string pvar
let memory_key i = "pointee:" ^ Int.to_string i
let get_alias key state = Option.value (Aliases.find_opt key state.Domain.aliases) ~default:Targets.empty
let get_value key state =
  match Values.find_opt key state.Domain.values with
  | Some deps -> deps
  | None when String.is_prefix key ~prefix:"global:" ->
      Deps.singleton (SymPasDomain.Global (String.drop_prefix key 7))
  | None -> Deps.empty

let rec eval state = function
  | Exp.Var id -> get_value (id_key id) state, get_alias (id_key id) state
  | Exp.Lvar pvar -> Deps.empty, Targets.singleton (pvar_key pvar)
  | Exp.Lfield (base, _, _) -> eval state base.exp
  | Exp.Lindex (base, index) ->
      let deps, targets = eval state base in
      let index_deps, _ = eval state index in
      Deps.join deps index_deps, targets
  | Exp.Cast (_, exp) | Exp.UnOp (_, exp, _) -> eval state exp
  | Exp.BinOp (_, lhs, rhs) ->
      let ld, la = eval state lhs in
      let rd, ra = eval state rhs in
      Deps.join ld rd, Targets.join la ra
  | exp ->
      let deps = Exp.free_vars exp |> Sequence.fold ~init:Deps.empty
          ~f:(fun deps id -> Deps.join deps (get_value (id_key id) state)) in
      deps, Targets.empty

let read state targets =
  Targets.fold (fun key deps -> Deps.join deps (get_value key state)) targets Deps.empty

let write ?(weak=false) state targets deps aliases =
  let unresolved = Targets.is_empty targets in
  let targets = if unresolved then
      Values.fold (fun key _ targets ->
        if String.is_prefix key ~prefix:"local:" || String.is_prefix key ~prefix:"global:"
           || String.is_prefix key ~prefix:"pointee:" then Targets.add key targets else targets)
        state.Domain.values Targets.empty
    else targets in
  let may_alias_formals = Targets.exists (String.is_prefix ~prefix:"pointee:") targets in
  let targets = if may_alias_formals then
      Values.fold (fun key _ targets ->
        if String.is_prefix key ~prefix:"pointee:" then Targets.add key targets else targets)
        state.Domain.values targets
    else targets in
  let strong = not weak && not unresolved && Int.equal (Targets.cardinal targets) 1 in
  Targets.fold
    (fun key state ->
      let deps = Deps.join deps state.Domain.controls in
      let deps = if strong then deps else Deps.join deps (get_value key state) in
      let aliases = if strong then aliases else Targets.join aliases (get_alias key state) in
      {state with Domain.values= Values.add key deps state.Domain.values;
       aliases= Aliases.add key aliases state.Domain.aliases;
       modified= Targets.add key state.Domain.modified}) targets state

let instantiate state actuals dependencies =
  List.fold dependencies ~init:Deps.empty ~f:(fun deps dependency ->
      let value = match dependency with
        | SymPasDomain.Global name -> get_value ("global:" ^ name) state
        | SymPasDomain.Source _ -> Deps.singleton dependency
        | SymPasDomain.Formal index ->
            Option.value_map (List.nth actuals index) ~default:Deps.empty
              ~f:(fun (actual, _) -> fst (eval state actual))
        | SymPasDomain.Pointee index ->
            Option.value_map (List.nth actuals index) ~default:Deps.empty
              ~f:(fun (actual, _) -> let address, targets = eval state actual in
                Deps.join address (read state targets)) in
      Deps.join deps value)

module Transfer (CFG : ProcCfg.S) = struct
  module CFG = CFG
  module Domain = Domain
  type nonrec analysis_data = analysis_data
  let transfer state {interprocedural= {InterproceduralAnalysis.analyze_dependency; proc_desc; _}; postdominators}
      node _ instr =
    let target = CFG.Node.underlying_node node in
    let controls = Procdesc.get_nodes proc_desc |> List.fold ~init:Deps.empty
        ~f:(fun deps branch ->
          let controls_target = Procdesc.Node.get_preds branch |> List.exists ~f:(fun parent ->
              SymPasControlDependence.controls postdominators ~branch:parent ~target) in
          if controls_target then Deps.join deps (get_value (control_key branch) state) else deps) in
    let state = {state with Domain.controls= controls} in
    let loc = Sil.location_of_instr instr in
    let source = SymPasDomain.Source
        {procedure= Procname.to_unique_id (Procdesc.get_proc_name proc_desc);
         file= SourceFile.to_string loc.file; line= loc.line; column= loc.col;
         instruction= Format.asprintf "%a" CFG.Node.pp_id (CFG.Node.id node);
         control= (match instr with Sil.Prune _ -> true | _ -> false);
         callee= (match instr with
           | Sil.Call (_, Exp.Const (Const.Cfun pname), _, _, _) -> Some (Procname.to_unique_id pname)
           | Sil.Call _ -> Some "unknown"
           | _ -> None);
         target= (match instr with
           | Sil.Store {e1= Exp.Lvar pvar; _} ->
               Some (if Pvar.is_return pvar then "return"
                     else Format.asprintf "%a" Mangled.pp (Pvar.get_name pvar))
           | Sil.Load {id; _} | Sil.Call ((id, _), _, _, _, _) -> Some (id_key id)
           | _ -> None);
         event= (match instr with Sil.Load _ -> "load" | Sil.Store _ -> "store"
                   | Sil.Call _ -> "call" | Sil.Prune _ -> "control" | _ -> "other")} in
    let annotate deps = Deps.add source deps in
    match instr with
    | Sil.Load {id; e; _} ->
        let address, targets = eval state e in
        let deps = annotate (Deps.join address (read state targets)) in
        let aliases = Targets.fold (fun key aliases -> Targets.join aliases (get_alias key state))
            targets Targets.empty in
        {state with Domain.values= Values.add (id_key id) deps state.Domain.values;
         aliases= Aliases.add (id_key id) aliases state.Domain.aliases}
    | Sil.Store {e1; e2; _} ->
        let address, targets = eval state e1 in
        let deps, aliases = eval state e2 in
        let aggregate = match e1 with Exp.Lfield _ | Exp.Lindex _ -> true | _ -> false in
        write ~weak:aggregate state targets (annotate (Deps.join address deps)) aliases
    | Sil.Prune (condition, _, _, _) ->
        let deps, _ = eval state condition in
        let controls = Deps.join (annotate deps) state.Domain.controls in
        {state with Domain.controls= controls;
         values= Values.add (control_key target) controls state.Domain.values}
    | Sil.Call ((id, return_type), callee, actuals, _, _) ->
        let summary = match callee with
          | Exp.Const (Const.Cfun pname) ->
              (match analyze_dependency pname with Ok summary -> Some summary | Error _ -> None)
          | _ -> None in
        let return_aliases = match summary with
          | Some summary -> List.fold summary.SymPasDomain.return_aliases ~init:Targets.empty
              ~f:(fun targets dependency ->
                let actual_targets = match dependency with
                  | SymPasDomain.Pointee i -> Option.value_map (List.nth actuals i)
                      ~default:Targets.empty ~f:(fun (actual, _) -> snd (eval state actual))
                  | SymPasDomain.Global name -> Targets.singleton ("global:" ^ name)
                  | _ -> Targets.empty in
                Targets.join targets actual_targets)
          | None -> Targets.empty in
        let deps, state = match summary with
          | Some summary ->
              let next = List.fold summary.SymPasDomain.outputs ~init:state
                  ~f:(fun next {SymPasDomain.target; dependencies} ->
                    let targets = match target with
                      | SymPasDomain.Global name -> Targets.singleton ("global:" ^ name)
                      | SymPasDomain.Pointee index ->
                          Option.value_map (List.nth actuals index) ~default:Targets.empty
                            ~f:(fun (actual, _) -> snd (eval state actual))
                      | SymPasDomain.Formal _ | SymPasDomain.Source _ -> Targets.empty in
                    write next targets (annotate (instantiate state actuals dependencies)) Targets.empty) in
              instantiate state actuals summary.SymPasDomain.dependencies, next
          | None ->
              let deps = List.fold actuals ~init:Deps.empty ~f:(fun deps (actual, typ) ->
                  let value, targets = eval state actual in
                  let memory = if Typ.is_pointer_to_function typ then Deps.empty
                    else read state targets in
                  Deps.join deps (Deps.join value memory)) in
              let next = List.fold actuals ~init:state ~f:(fun next (actual, typ) ->
                  if Typ.is_pointer typ && not (Typ.is_pointer_to_function typ) then
                    let _, targets = eval state actual in
                    (* Unknown external calls may read and write pointer arguments. *)
                    let old = read state targets in
                    write next targets (Deps.join old deps) Targets.empty
                  else next) in
              deps, next in
        let aliases = Aliases.add (id_key id) return_aliases state.Domain.aliases in
        let aliases = if Typ.is_pointer return_type && Targets.is_empty return_aliases then
            Aliases.add ("unresolved:" ^ id_key id) Targets.empty aliases else aliases in
        {state with Domain.values= Values.add (id_key id) (annotate (Deps.join deps state.Domain.controls))
            state.Domain.values;
         aliases}
    | _ -> state
  let exec_instr state analysis_data node index instr =
    let next = transfer state analysis_data node index instr in
    let dependencies = match instr with
      | Sil.Load {id; _} | Sil.Call ((id, _), _, _, _, _) -> get_value (id_key id) next
      | Sil.Store {e1; _} -> let _, targets = eval next e1 in read next targets
      | Sil.Prune _ -> next.Domain.controls
      | _ -> Deps.empty in
    let key = Format.asprintf "%a" CFG.Node.pp_id (CFG.Node.id node) in
    {next with Domain.idt= Values.add key dependencies next.Domain.idt}
  let pp_session_name _ fmt = Format.pp_print_string fmt "SymPas symbolic outputs"
end

module CFG = ProcCfg.OneInstrPerNode (ProcCfg.Normal)
module Analyzer = AbstractInterpreter.MakeRPO (Transfer (CFG))

let compute analysis_data =
  let proc_desc = analysis_data.InterproceduralAnalysis.proc_desc in
  let formals = Procdesc.get_pvar_formals proc_desc in
  let initial = List.foldi formals ~init:Domain.bottom ~f:(fun i state (pvar, typ) ->
      let key = pvar_key pvar in
      let state = {state with Domain.values=
          Values.add key (Deps.singleton (SymPasDomain.Formal i)) state.Domain.values} in
      if Typ.is_pointer typ then
        {state with Domain.aliases= Aliases.add key (Targets.singleton (memory_key i)) state.Domain.aliases;
         values= Values.add (memory_key i) (Deps.singleton (SymPasDomain.Pointee i)) state.Domain.values}
      else state) in
  let data = {interprocedural= analysis_data;
              postdominators= SymPasControlDependence.compute_postdominators proc_desc} in
  Option.map (Analyzer.compute_post data ~initial proc_desc) ~f:(fun state ->
      let outputs = List.filter_mapi formals ~f:(fun i (_, typ) ->
          let key = memory_key i in
          if Typ.is_pointer typ && Targets.mem key state.Domain.modified then
            Some {SymPasDomain.target= SymPasDomain.Pointee i;
                  dependencies= Deps.elements (get_value key state)}
          else None) in
      let outputs = Targets.fold (fun key outputs ->
          if String.is_prefix key ~prefix:"global:" then
            {SymPasDomain.target= SymPasDomain.Global (String.drop_prefix key 7);
             dependencies= Deps.elements (get_value key state)} :: outputs
          else outputs) state.Domain.modified outputs in
      {SymPasDomain.dependencies=
         Deps.elements (get_value (pvar_key (Procdesc.get_ret_var proc_desc)) state);
       outputs;
       return_aliases= get_alias (pvar_key (Procdesc.get_ret_var proc_desc)) state
         |> Targets.elements |> List.filter_map ~f:(fun key ->
             if String.is_prefix key ~prefix:"pointee:" then
               Some (SymPasDomain.Pointee (Int.of_string (String.drop_prefix key 8)))
             else if String.is_prefix key ~prefix:"global:" then
               Some (SymPasDomain.Global (String.drop_prefix key 7))
             else None);
       alias_evidence= Aliases.fold (fun key targets evidence ->
           if Targets.is_empty targets && not (String.is_prefix key ~prefix:"unresolved:") then evidence
           else (key, Targets.elements targets) :: evidence) state.Domain.aliases [];
       instruction_slices= Values.fold (fun key dependencies slices ->
           let source = Deps.elements dependencies |> List.find_map ~f:(function
               | SymPasDomain.Source source when String.equal source.instruction key
                   && String.equal source.procedure (Procname.to_unique_id (Procdesc.get_proc_name proc_desc)) -> Some source
               | _ -> None) in
           match source with
           | Some source -> (source, Deps.elements dependencies) :: slices
           | None -> slices) state.Domain.idt []})
