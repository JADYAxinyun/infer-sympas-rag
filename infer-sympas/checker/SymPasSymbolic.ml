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
    | SymPasDomain.Heap site -> Format.fprintf fmt "heap:%s" site
    | SymPasDomain.Source source -> Format.fprintf fmt "%s:%d" source.file source.line
end

module Deps = AbstractDomain.FiniteSet (Dependency)
module Targets = AbstractDomain.FiniteSet (Key)
module Values = AbstractDomain.Map (Key) (Deps)
module Aliases = AbstractDomain.Map (Key) (Targets)
module Points = AbstractDomain.Map (Key) (Values)

type analysis_data =
  { interprocedural: SymPasDomain.summary InterproceduralAnalysis.t
  ; postdominators: Procdesc.NodeSet.t Procdesc.NodeMap.t }

let control_key node =
  "control:" ^ Format.asprintf "%a" Procdesc.Node.pp_id (Procdesc.Node.get_id node)

module Domain = struct
  type t = {values: Values.t; aliases: Aliases.t; modified: Targets.t; controls: Deps.t;
            idt: Values.t; points: Points.t}
  let bottom = {values= Values.empty; aliases= Aliases.empty; modified= Targets.empty;
                controls= Deps.empty; idt= Values.empty; points= Points.empty}
  let leq ~lhs ~rhs =
    Values.leq ~lhs:lhs.values ~rhs:rhs.values
    && Aliases.leq ~lhs:lhs.aliases ~rhs:rhs.aliases
    && Targets.leq ~lhs:lhs.modified ~rhs:rhs.modified
    && Deps.leq ~lhs:lhs.controls ~rhs:rhs.controls
    && Values.leq ~lhs:lhs.idt ~rhs:rhs.idt
    && Points.leq ~lhs:lhs.points ~rhs:rhs.points
  let join lhs rhs =
    {values= Values.join lhs.values rhs.values; aliases= Aliases.join lhs.aliases rhs.aliases;
     modified= Targets.join lhs.modified rhs.modified; controls= Deps.join lhs.controls rhs.controls;
     idt= Values.join lhs.idt rhs.idt; points= Points.join lhs.points rhs.points}
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

let tracked_memory state =
  Values.fold (fun key _ targets ->
      if String.is_prefix key ~prefix:"local:" || String.is_prefix key ~prefix:"global:"
         || String.is_prefix key ~prefix:"pointee:" || String.is_prefix key ~prefix:"heap:"
      then Targets.add key targets else targets) state.Domain.values Targets.empty

let read state targets =
  let targets = if Targets.is_empty targets then tracked_memory state else targets in
  Targets.fold (fun key deps -> Deps.join deps (get_value key state)) targets Deps.empty

let symbolic_aliases targets =
  Targets.elements targets |> List.filter_map ~f:(fun key ->
      if String.is_prefix key ~prefix:"pointee:" then
        Some (SymPasDomain.Pointee (Int.of_string (String.drop_prefix key 8)))
      else if String.is_prefix key ~prefix:"global:" then
        Some (SymPasDomain.Global (String.drop_prefix key 7))
      else if String.is_prefix key ~prefix:"heap:" then
        Some (SymPasDomain.Heap (String.drop_prefix key 5))
      else None)

let instantiate_aliases state actuals dependencies =
  List.fold dependencies ~init:Targets.empty ~f:(fun targets dependency ->
      let locations = match dependency with
        | SymPasDomain.Pointee i -> Option.value_map (List.nth actuals i)
            ~default:Targets.empty ~f:(fun (actual, _) -> snd (eval state actual))
        | SymPasDomain.Global name -> Targets.singleton ("global:" ^ name)
        | SymPasDomain.Heap site -> Targets.singleton ("heap:" ^ site)
        | SymPasDomain.Formal _ | SymPasDomain.Source _ -> Targets.empty in
      Targets.join targets locations)

let write ?(weak=false) state targets deps aliases =
  let unresolved = Targets.is_empty targets in
  let targets = if unresolved then tracked_memory state else targets in
  let may_alias_formals = Targets.exists (String.is_prefix ~prefix:"pointee:") targets in
  let targets = if may_alias_formals then
      Values.fold (fun key _ targets ->
        if String.is_prefix key ~prefix:"pointee:" then Targets.add key targets else targets)
        state.Domain.values targets
    else targets in
  let summarized_heap = Targets.exists (String.is_prefix ~prefix:"heap:") targets in
  let strong = not weak && not unresolved && not summarized_heap
      && Int.equal (Targets.cardinal targets) 1 in
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
        | SymPasDomain.Heap site -> get_value ("heap:" ^ site) state
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
        let unresolved = Targets.is_empty targets in
        let targets = if unresolved then tracked_memory state else targets in
        let aliases = Targets.fold (fun key aliases -> Targets.join aliases (get_alias key state))
            targets Targets.empty in
        let alias_map = Aliases.add (id_key id) aliases state.Domain.aliases in
        let alias_map = if unresolved then
            Aliases.add ("unresolved:" ^ id_key id) Targets.empty alias_map else alias_map in
        {state with Domain.values= Values.add (id_key id) deps state.Domain.values;
         aliases= alias_map}
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
    | Sil.Call ((id, _), Exp.Const (Const.Cfun pname), actuals, _, _)
      when Procname.is_c pname
           && List.mem ["malloc"; "calloc"; "__infer_malloc"] (Procname.get_method pname)
                ~equal:String.equal
           && not (Option.exists (Procdesc.load pname) ~f:Procdesc.is_defined) ->
        let site = "heap:" ^ Procname.to_unique_id (Procdesc.get_proc_name proc_desc)
                   ^ ":" ^ Format.asprintf "%a" CFG.Node.pp_id (CFG.Node.id node) in
        let deps = List.fold actuals ~init:state.Domain.controls ~f:(fun deps (actual, _) ->
            Deps.join deps (fst (eval state actual))) |> annotate in
        let values = if Values.mem site state.Domain.values then state.Domain.values
          else Values.add site Deps.empty state.Domain.values in
        {state with Domain.values= Values.add (id_key id) deps values;
         aliases= Aliases.add (id_key id) (Targets.singleton site) state.Domain.aliases}
    | Sil.Call ((id, return_type), callee, actuals, _, _) ->
        let summary = match callee with
          | Exp.Const (Const.Cfun pname) ->
              (match analyze_dependency pname with Ok summary -> Some summary | Error _ -> None)
          | _ -> None in
        let return_aliases = match summary with
          | Some summary -> instantiate_aliases state actuals summary.SymPasDomain.return_aliases
          | None -> Targets.empty in
        let deps, state = match summary with
          | Some summary ->
              let next = List.fold summary.SymPasDomain.outputs ~init:state
                  ~f:(fun next {SymPasDomain.target; dependencies; aliases} ->
                    let targets = match target with
                      | SymPasDomain.Global name -> Targets.singleton ("global:" ^ name)
                      | SymPasDomain.Heap site -> Targets.singleton ("heap:" ^ site)
                      | SymPasDomain.Pointee index ->
                          Option.value_map (List.nth actuals index) ~default:Targets.empty
                            ~f:(fun (actual, _) -> snd (eval state actual))
                      | SymPasDomain.Formal _ | SymPasDomain.Source _ -> Targets.empty in
                    write next targets (annotate (instantiate state actuals dependencies))
                      (instantiate_aliases state actuals aliases)) in
              instantiate state actuals summary.SymPasDomain.dependencies, next
          | None ->
              let deps = List.fold actuals ~init:Deps.empty ~f:(fun deps (actual, typ) ->
                  let value, targets = eval state actual in
                  let memory = if Typ.is_pointer typ && not (Typ.is_pointer_to_function typ)
                    then read state targets else Deps.empty in
                  Deps.join deps (Deps.join value memory)) in
              let next = List.fold actuals ~init:state ~f:(fun next (actual, typ) ->
                  if Typ.is_pointer typ && not (Typ.is_pointer_to_function typ) then
                    let _, targets = eval state actual in
                    (* Unknown external calls may read and write pointer arguments. *)
                    let old = read state targets in
                    write ~weak:true next targets (Deps.join old deps) Targets.empty
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
    let variables = Values.fold (fun variable deps values ->
        if String.is_prefix variable ~prefix:"local:" || String.is_prefix variable ~prefix:"global:"
        then Values.add variable (Deps.join deps next.Domain.controls) values else values)
        next.Domain.values Values.empty in
    {next with Domain.idt= Values.add key dependencies next.Domain.idt;
     points= Points.add key variables next.Domain.points}
  let pp_session_name _ fmt = Format.pp_print_string fmt "SymPas symbolic outputs"
end

module CFG = ProcCfg.OneInstrPerNode (ProcCfg.Normal)
module Analyzer = AbstractInterpreter.MakeRPO (Transfer (CFG))

let compute_once analysis_data =
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
      let point_source key = get_value key {state with Domain.values= state.Domain.idt}
        |> Deps.elements |> List.find_map ~f:(function
            | SymPasDomain.Source source when String.equal source.instruction key
                && String.equal source.procedure (Procname.to_unique_id (Procdesc.get_proc_name proc_desc))
                -> Some source
            | _ -> None) in
      let outputs = List.filter_mapi formals ~f:(fun i (_, typ) ->
          let key = memory_key i in
          if Typ.is_pointer typ && Targets.mem key state.Domain.modified then
            Some {SymPasDomain.target= SymPasDomain.Pointee i;
                  dependencies= Deps.elements (get_value key state);
                  aliases= symbolic_aliases (get_alias key state)}
          else None) in
      let outputs = Targets.fold (fun key outputs ->
          if String.is_prefix key ~prefix:"global:" then
            {SymPasDomain.target= SymPasDomain.Global (String.drop_prefix key 7);
             dependencies= Deps.elements (get_value key state);
             aliases= symbolic_aliases (get_alias key state)} :: outputs
          else if String.is_prefix key ~prefix:"heap:" then
            {SymPasDomain.target= SymPasDomain.Heap (String.drop_prefix key 5);
             dependencies= Deps.elements (get_value key state);
             aliases= symbolic_aliases (get_alias key state)} :: outputs
          else outputs) state.Domain.modified outputs in
      {SymPasDomain.dependencies=
         Deps.elements (get_value (pvar_key (Procdesc.get_ret_var proc_desc)) state);
       outputs; fixpoint_iterations= 0; fixpoint_members= [];
       variable_slices= Points.fold (fun key variables slices ->
           match point_source key with
           | None -> slices
           | Some source -> Values.fold (fun variable dependencies slices ->
               let variable = String.drop_prefix variable
                   (if String.is_prefix variable ~prefix:"global:" then 7 else 6) in
               ((source, variable), Deps.elements dependencies) :: slices) variables slices)
           state.Domain.points [];
       return_aliases= symbolic_aliases (get_alias (pvar_key (Procdesc.get_ret_var proc_desc)) state);
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

(* The SCC containing root is the intersection of forward and reverse reachability.
 * Each round reads the previous round's summaries, so traversal order cannot
 * change the result. Summary join only adds atoms from a finite SIL universe.
 *)
let recursive_component root =
  let direct_calls proc_desc =
    Procdesc.get_nodes proc_desc |> List.concat_map ~f:(fun node ->
      Instrs.fold (Procdesc.Node.get_instrs node) ~init:[] ~f:(fun callees instr ->
        match instr with
        | Sil.Call (_, Exp.Const (Const.Cfun pname), _, _, _) -> pname :: callees
        | _ -> callees)) |> List.dedup_and_sort ~compare:Procname.compare in
  let rec visit proc_desc graph =
    let pname = Procdesc.get_proc_name proc_desc in
    if Procname.Map.mem pname graph then graph else
      let callees = direct_calls proc_desc in
      let graph = Procname.Map.add pname (proc_desc, callees) graph in
      List.fold callees ~init:graph ~f:(fun graph callee ->
        match Procdesc.load callee with
        | Some desc when Procdesc.is_defined desc -> visit desc graph
        | _ -> graph) in
  let graph = visit root Procname.Map.empty in
  let root_name = Procdesc.get_proc_name root in
  let rec reverse_reachable current =
    let next = Procname.Map.fold (fun pname (_, callees) set ->
        if List.exists callees ~f:(fun callee -> Procname.Set.mem callee current)
        then Procname.Set.add pname set else set) graph current in
    if Procname.Set.equal current next then current else reverse_reachable next in
  let names = reverse_reachable (Procname.Set.singleton root_name) in
  let _, root_calls = Procname.Map.find root_name graph in
  if Int.equal (Procname.Set.cardinal names) 1
     && not (List.mem root_calls root_name ~equal:Procname.equal) then []
  else Procname.Map.bindings graph |> List.filter_map ~f:(fun (pname, (desc, _)) ->
      if Procname.Set.mem pname names then Some (pname, desc) else None)

let compute analysis_data =
  let root = analysis_data.InterproceduralAnalysis.proc_desc in
  match recursive_component root with
  | [] -> compute_once analysis_data
  | members ->
      (* Register dependency edges with Infer before using our local approximants.
       * This preserves persistent-summary invalidation across SCC members. *)
      List.iter members ~f:(fun (pname, _) ->
        ignore (analysis_data.InterproceduralAnalysis.analyze_dependency pname)) ;
      (* Cycle-cut edges alone are not used by Infer's reverse invalidation
       * graph. Register all member translation units as source dependencies,
       * preserving cycle cuts for the scheduler while invalidating the SCC. *)
      List.iter members ~f:(fun (_, desc) ->
        Dependencies.record_srcfile_dep (Procdesc.get_attributes desc).ProcAttributes.translation_unit) ;
      let initial = List.fold members ~init:Procname.Map.empty ~f:(fun map (pname, _) ->
          Procname.Map.add pname SymPasDomain.empty map) in
      let rec iterate current iterations =
        let failed = ref false in
        let next = List.fold members ~init:Procname.Map.empty ~f:(fun map (pname, proc_desc) ->
          let analyze_dependency ?specialization callee =
            match Procname.Map.find_opt callee current with
            | Some summary -> Ok summary
            | None -> analysis_data.InterproceduralAnalysis.analyze_dependency ?specialization callee in
          let data = {analysis_data with InterproceduralAnalysis.proc_desc; analyze_dependency} in
          let previous = Procname.Map.find pname current in
          let summary = match compute_once data with
            | Some summary -> SymPasDomain.join previous summary
            | None -> failed := true; previous in
          Procname.Map.add pname summary map) in
        if !failed then None
        else if Procname.Map.equal SymPasDomain.equal_summary current next then
          let summary = Procname.Map.find (Procdesc.get_proc_name root) next in
          Some {summary with SymPasDomain.fixpoint_iterations= iterations;
                fixpoint_members= List.map members ~f:(fun (pname, _) -> Procname.to_unique_id pname)}
        else iterate next (iterations + 1) in
      iterate initial 1
