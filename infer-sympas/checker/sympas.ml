(*
 * Initial SymPas prototype.
 *
 * This milestone computes a backward data-dependency slice from a procedure
 * return value, including relevant assignments and branch conditions. It also
 * propagates formal-parameter/global summaries across direct calls. Pointer,
 * alias, recursion, and richer symbolic-summary cases remain future work.
 *)

open! IStd
module F = Format

module VarSet = AbstractDomain.FiniteSet (Var)

module LocationString = struct
  type t = string [@@deriving compare]

  let pp = F.pp_print_string
end

module LocationSet = AbstractDomain.FiniteSet (LocationString)

module Domain = struct
  type t = {frontier: VarSet.t; slice_locations: LocationSet.t; path_conditions: LocationSet.t; global_dependencies: LocationSet.t}

  let leq ~lhs ~rhs =
    VarSet.leq ~lhs:lhs.frontier ~rhs:rhs.frontier
    && LocationSet.leq ~lhs:lhs.slice_locations ~rhs:rhs.slice_locations
    && LocationSet.leq ~lhs:lhs.path_conditions ~rhs:rhs.path_conditions
    && LocationSet.leq ~lhs:lhs.global_dependencies ~rhs:rhs.global_dependencies


  let join lhs rhs =
    { frontier= VarSet.join lhs.frontier rhs.frontier
    ; slice_locations= LocationSet.join lhs.slice_locations rhs.slice_locations
    ; path_conditions= LocationSet.join lhs.path_conditions rhs.path_conditions
    ; global_dependencies= LocationSet.join lhs.global_dependencies rhs.global_dependencies }


  let widen ~prev ~next ~num_iters =
    { frontier= VarSet.widen ~prev:prev.frontier ~next:next.frontier ~num_iters
    ; slice_locations=
        LocationSet.widen ~prev:prev.slice_locations ~next:next.slice_locations ~num_iters
    ; path_conditions=
        LocationSet.widen ~prev:prev.path_conditions ~next:next.path_conditions ~num_iters
    ; global_dependencies=
        LocationSet.widen ~prev:prev.global_dependencies ~next:next.global_dependencies ~num_iters }


  let pp fmt {frontier; slice_locations; path_conditions; global_dependencies} =
    F.fprintf fmt "{frontier=%a; slice_locations=%a; path_conditions=%a; global_dependencies=%a}" VarSet.pp frontier LocationSet.pp
      slice_locations LocationSet.pp path_conditions LocationSet.pp global_dependencies


  let bottom =
    {frontier= VarSet.bottom; slice_locations= LocationSet.bottom; path_conditions= LocationSet.bottom; global_dependencies= LocationSet.bottom}

  let is_bottom {frontier; slice_locations; path_conditions; global_dependencies} =
    VarSet.is_bottom frontier && LocationSet.is_bottom slice_locations
    && LocationSet.is_bottom path_conditions
    && LocationSet.is_bottom global_dependencies


  let initial = bottom

  let singleton var = {bottom with frontier= VarSet.singleton var}

  let mem var {frontier} = VarSet.mem var frontier

  let add_var var state = {state with frontier= VarSet.add var state.frontier}

  let remove_var var state = {state with frontier= VarSet.remove var state.frontier}

  let add_location loc state =
    let loc_string = F.asprintf "%a" Location.pp loc in
    {state with slice_locations= LocationSet.add loc_string state.slice_locations}

  let add_condition condition state =
    let condition_string = F.asprintf "%a" Exp.pp condition in
    {state with path_conditions= LocationSet.add condition_string state.path_conditions}

end

(** Add all variables read by [exp] to the current slice frontier. *)
let add_exp_vars exp state =
  let state =
    Exp.free_vars exp
    |> Sequence.fold ~init:state ~f:(fun state id -> Domain.add_var (Var.of_id id) state)
  in
  Exp.program_vars exp
    |> Sequence.fold ~init:state ~f:(fun state pvar -> Domain.add_var (Var.of_pvar pvar) state)

let add_actuals actuals state =
  List.fold actuals ~init:state ~f:(fun state (actual, _) -> add_exp_vars actual state)

(** Intraprocedural backward traversal over SIL instructions. *)
module TransferFunctions (CFG : ProcCfg.S) = struct
  module CFG = CFG
  module Domain = Domain

  type analysis_data = SymPasDomain.summary InterproceduralAnalysis.t

  (** A backward dependency transfer.

      If the slicing frontier contains the result of an assignment, replace it
      with the variables read by its right-hand side. *)
  let exec_instr state {InterproceduralAnalysis.analyze_dependency; _} _ _
      (instr : Sil.instr) =
    match instr with
    | Sil.Prune (condition, loc, _, _) when not (Domain.is_bottom state) ->
        state |> add_exp_vars condition |> Domain.add_location loc |> Domain.add_condition condition
    | Sil.Call ((ret_id, _), callee, actuals, loc, _)
      when not (Domain.is_bottom state) ->
        let return_relevant = Domain.mem (Var.of_id ret_id) state in
        let state, summary_found, output_relevant =
          match callee with
          | Exp.Const (Const.Cfun callee_pname) -> (
              match analyze_dependency callee_pname with
              | Ok summary ->
                  let output_dependencies =
                    List.concat_map summary.SymPasDomain.outputs
                      ~f:(fun {SymPasDomain.target; dependencies} ->
                        let relevant = match target with
                          | SymPasDomain.Pointee index ->
                              Option.value_map (List.nth actuals index) ~default:false
                                ~f:(fun (actual, _) ->
                                  let referenced = add_exp_vars actual Domain.bottom in
                                  not (VarSet.is_empty
                                    (VarSet.inter referenced.Domain.frontier state.Domain.frontier)))
                          | SymPasDomain.Global _ -> true
                          | SymPasDomain.Formal _ | SymPasDomain.Source _ -> false in
                        if relevant then dependencies else [])
                  in
                  let dependencies =
                    (if return_relevant then summary.SymPasDomain.dependencies else [])
                    @ output_dependencies
                  in
                  ( List.fold dependencies ~init:state ~f:(fun state dependency ->
                        match dependency with
                        | SymPasDomain.Formal index | SymPasDomain.Pointee index ->
                            Option.value_map (List.nth actuals index) ~default:state
                              ~f:(fun (actual, _) -> add_exp_vars actual state)
                        | SymPasDomain.Global name ->
                            {state with Domain.global_dependencies=
                              LocationSet.add name state.Domain.global_dependencies}
                        | SymPasDomain.Source _ -> state )
                  , true, not (List.is_empty output_dependencies) )
              | Error _ ->
                  state, false, false )
          | _ ->
              state, false, false
        in
        state
        |> Domain.remove_var (Var.of_id ret_id)
        |> (if summary_found || not return_relevant then Fn.id else add_actuals actuals)
        |> (if return_relevant || output_relevant then Domain.add_location loc else Fn.id)
    | Sil.Load {id; e= rhs; _} when Domain.mem (Var.of_id id) state ->
        state |> Domain.remove_var (Var.of_id id) |> add_exp_vars rhs
    | Sil.Store {e1= Exp.Lvar lhs; e2= rhs; loc; _} when Domain.mem (Var.of_pvar lhs) state ->
        state
        |> Domain.remove_var (Var.of_pvar lhs)
        |> add_exp_vars rhs
        |> Domain.add_location loc
    | Sil.Store {e1= Exp.Lfield (base, _, _); e2= rhs; loc; _}
      when not (Domain.is_bottom state) ->
        state |> add_exp_vars base.exp |> add_exp_vars rhs |> Domain.add_location loc
    | Sil.Store {e1= Exp.Lindex (base, index); e2= rhs; loc; _}
      when not (Domain.is_bottom state) ->
        state
        |> add_exp_vars base
        |> add_exp_vars index
        |> add_exp_vars rhs
        |> Domain.add_location loc
    | Sil.Store {e1= Exp.Lvar _; _} ->
        state
    | Sil.Store {e1= lhs; e2= rhs; loc; _} when not (Domain.is_bottom state) ->
        state |> add_exp_vars lhs |> add_exp_vars rhs |> Domain.add_location loc
    | _ ->
        state


  let pp_session_name _node fmt = F.pp_print_string fmt "SymPas backward slice"
end

module CFG = ProcCfg.OneInstrPerNode (ProcCfg.Backward (ProcCfg.Exceptional))
module Analyzer = AbstractInterpreter.MakeRPO (TransferFunctions (CFG))

(** Run the first SymPas prototype on one procedure. *)
let collect_dependencies analysis_data =
  let proc_desc = analysis_data.InterproceduralAnalysis.proc_desc in
  let return_var = Var.of_pvar (Procdesc.get_ret_var proc_desc) in
  Analyzer.compute_post analysis_data ~initial:(Domain.singleton return_var) proc_desc

let formal_summary proc_desc {Domain.frontier; global_dependencies} =
  let formals =
    Procdesc.get_pvar_formals proc_desc
    |> List.filter_mapi ~f:(fun index (pvar, _) ->
           if VarSet.mem (Var.of_pvar pvar) frontier then Some (SymPasDomain.Formal index) else None)
  in
  let globals =
    VarSet.elements frontier
    |> List.fold ~init:[] ~f:(fun globals var ->
           if Var.is_global var then
             match Var.get_pvar var with
             | Some pvar ->
                 let name = F.asprintf "%a" Mangled.pp (Pvar.get_name pvar) in
                 SymPasDomain.Global name :: globals
             | None -> globals
           else globals )
  in
  let carried_globals =
    LocationSet.elements global_dependencies
    |> List.map ~f:(fun name -> SymPasDomain.Global name)
  in
  {SymPasDomain.dependencies=
     List.dedup_and_sort (formals @ globals @ carried_globals) ~compare:SymPasDomain.compare_dependency;
   outputs= []; instruction_slices= []; return_aliases= []; alias_evidence= [];
   fixpoint_iterations= 0; fixpoint_members= []}

let precise_control_locations proc_desc {Domain.slice_locations} =
  let postdominators = SymPasControlDependence.compute_postdominators proc_desc in
  let nodes = Procdesc.get_nodes proc_desc in
  let is_slice_node node =
    let location = F.asprintf "%a" Location.pp (Procdesc.Node.get_loc node) in
    LocationSet.mem location slice_locations
  in
  (* The slicing criterion is the procedure return. Its exit node may not have
     an explicit source location in [slice_locations], so include it as a
     synthetic target when the backward slice is non-empty. *)
  let is_controlled_target node =
    is_slice_node node
    || (phys_equal node (Procdesc.get_exit_node proc_desc)
       && not (LocationSet.is_bottom slice_locations))
  in
  let controlled_prunes =
    List.fold nodes ~init:LocationSet.bottom ~f:(fun locations branch ->
        let controls_slice_node =
          List.exists nodes ~f:(fun target ->
              is_controlled_target target
              && SymPasControlDependence.controls postdominators ~branch ~target)
        in
        if controls_slice_node then
          Instrs.fold (Procdesc.Node.get_instrs branch) ~init:locations ~f:(fun locations instr ->
              match instr with
              | Sil.Prune (_, loc, _, _) ->
                  Domain.add_location loc {Domain.bottom with slice_locations= locations}
                  |> fun state -> state.Domain.slice_locations
              | _ ->
                  locations )
        else locations )
  in
  if not (LocationSet.is_bottom controlled_prunes) then controlled_prunes
  else
    (* Some frontend CFGs collapse the return criterion into the exit node and
       do not expose a usable post-dominator edge. Keep branch locations that
       are already part of the backward slice as a conservative fallback. *)
    List.fold nodes ~init:LocationSet.bottom ~f:(fun locations node ->
        Instrs.fold (Procdesc.Node.get_instrs node) ~init:locations ~f:(fun locations instr ->
            match instr with
            | Sil.Prune (_, loc, _, _) ->
                let loc_string = F.asprintf "%a" Location.pp loc in
                if LocationSet.mem loc_string slice_locations then LocationSet.add loc_string locations
                else locations
            | _ -> locations ) )


let rec is_negative_integer_literal = function
  | Exp.Const (Const.Cint value) ->
      IntLit.isnegative value
  | Exp.UnOp (Unop.Neg, Exp.Const (Const.Cint value), _) ->
      not (IntLit.iszero value)
  | Exp.Cast (_, exp) ->
      is_negative_integer_literal exp
  | _ ->
      false


let has_negative_integer_return proc_desc =
  let has_direct_return = ref false in
  let has_negative_store = ref false in
  Procdesc.get_nodes proc_desc
  |> List.iter ~f:(fun node ->
         Instrs.iter (Procdesc.Node.get_instrs node) ~f:(fun instr ->
             match instr with
             | Sil.Store {e1= Exp.Lvar lhs; e2; _} when Pvar.is_return lhs ->
                 has_direct_return := !has_direct_return || is_negative_integer_literal e2
             | Sil.Store {e2; _} ->
                 has_negative_store := !has_negative_store || is_negative_integer_literal e2
             | _ -> () ) ) ;
  !has_direct_return || !has_negative_store


let structured_evidence proc_desc _variables summary controls =
  let procedure = Procname.to_unique_id (Procdesc.get_proc_name proc_desc) in
  let location (loc : Location.t) =
    `Assoc
      [ ("file", `String (SourceFile.to_string loc.file))
      ; ("line", `Int loc.line)
      ; ("column", `Int loc.col) ]
  in
  let locations selected =
    Procdesc.get_nodes proc_desc
    |> List.concat_map ~f:(fun node ->
           Instrs.fold (Procdesc.Node.get_instrs node) ~init:[] ~f:(fun locations instr ->
             let loc = Sil.location_of_instr instr in
             if LocationSet.mem (F.asprintf "%a" Location.pp loc) selected then loc :: locations
             else locations))
    |> List.dedup_and_sort ~compare:Location.compare
    |> List.map ~f:location
  in
  let strings values = `List (List.map values ~f:(fun value -> `String value)) in
  let dependency_string = function
      | SymPasDomain.Formal index -> F.asprintf "formal[%d]" index
      | SymPasDomain.Pointee index -> F.asprintf "memory(formal[%d])" index
      | SymPasDomain.Global name -> "global:" ^ name
      | SymPasDomain.Source source -> F.asprintf "%s:%d:%d" source.file source.line source.column
  in
  let input_dependencies dependencies =
    List.filter_map dependencies ~f:(function
      | SymPasDomain.Source _ -> None
      | dependency -> Some (dependency_string dependency))
  in
  let dependencies = input_dependencies summary.SymPasDomain.dependencies
  in
  let source_json (source : SymPasDomain.source) =
    `Assoc [("procedure", `String source.procedure); ("file", `String source.file);
            ("line", `Int source.line); ("column", `Int source.column);
            ("instruction", `String source.instruction); ("event", `String source.event);
            ("target", Option.value_map source.target ~default:`Null ~f:(fun value -> `String value));
            ("callee", Option.value_map source.callee ~default:`Null ~f:(fun value -> `String value))]
  in
  let sources = List.filter_map summary.SymPasDomain.dependencies ~f:(function
      | SymPasDomain.Source source -> Some source | _ -> None)
    |> List.dedup_and_sort ~compare:SymPasDomain.compare_source
  in
  let source_locations dependencies =
    `List (List.filter_map dependencies ~f:(function
      | SymPasDomain.Source source -> Some (source_json source) | _ -> None))
  in
  `Assoc
    [ ("kind", `String "SYMPAS_SLICE")
    ; ("procedure", `String procedure)
    ; ( "criterion"
      , `Assoc
          [ ("type", `String "return_value")
          ; ("target", `String "return")
          ; ("location", location (Procdesc.Node.get_loc (Procdesc.get_exit_node proc_desc))) ] )
    ; ("data_dependencies", strings dependencies)
    ; ( "control_dependencies"
      , `List
          (List.map (List.filter sources ~f:(fun source -> source.SymPasDomain.control)
                     |> List.map ~f:source_json) ~f:(fun loc ->
               `Assoc
                 [ ("location", loc)
                 ; ("target", `String "return")
                 ; ("reason", `String "symbolic_predicate_dependency_conservative") ] )) )
    ; ("backward_control_candidates", `List (locations controls))
    ; ( "procedure_summary"
      , `Assoc
          [ ("procedure", `String procedure)
          ; ("return_dependencies", strings dependencies)
          ; ("return_aliases", strings (input_dependencies summary.SymPasDomain.return_aliases))
          ; ("global_dependencies", strings (List.filter dependencies
                ~f:(String.is_prefix ~prefix:"global:")))
          ; ("memory_dependencies", strings (List.filter dependencies
                ~f:(String.is_prefix ~prefix:"memory(")))
          ; ("source_locations", `List (List.map sources ~f:source_json))
          ; ("control_locations", `List (List.filter sources
                ~f:(fun source -> source.SymPasDomain.control) |> List.map ~f:source_json))
          ; ( "outputs", `List (List.map summary.SymPasDomain.outputs
                ~f:(fun {SymPasDomain.target; dependencies} ->
                  `Assoc [("target", `String (dependency_string target));
                  ("dependencies", strings (input_dependencies dependencies));
                  ("source_locations", source_locations dependencies)])) )
          ; ("summary_version", `Int 6)
          ; ("fixed_point", `Assoc
                [("mode", `String (if List.is_empty summary.SymPasDomain.fixpoint_members
                    then "acyclic" else "synchronous_scc_iteration"));
                 ("members", strings summary.SymPasDomain.fixpoint_members);
                 ("iterations", `Int summary.SymPasDomain.fixpoint_iterations);
                 ("status", `String (if List.is_empty summary.SymPasDomain.fixpoint_members
                    then "not_applicable" else "converged"))])
          ; ("source", `String "infer_sil_symbolic_outputs_and_backward_slice")
          ; ("memory_dependencies_status", `String "conservative") ] )
    ; ("call_chain", `List (List.filter_map sources ~f:(fun source ->
         Option.map source.SymPasDomain.callee ~f:(fun callee ->
           `Assoc [("caller", `String source.SymPasDomain.procedure); ("callee", `String callee);
                   ("location", source_json source)]))))
    ; ("call_chain_status", `String "static_dependency_edges")
    ; ("alias_evidence", `List (List.map summary.SymPasDomain.alias_evidence
         ~f:(fun (pointer, targets) ->
           let symbolic = List.exists targets ~f:(String.is_prefix ~prefix:"pointee:") in
           `Assoc [("pointer", `String pointer); ("targets", strings targets);
                   ("status", `String (if List.is_empty targets then "unresolved"
                     else if symbolic || List.length targets > 1 then "possible" else "confirmed"));
                   ("reason", `String (if symbolic then "symbolic_formal_memory"
                     else "flow_sensitive_local_points_to"))])))
    ; ("alias_limitations", strings ["formal_parameters_may_alias";
         "aggregate_fields_and_elements_collapsed";
         "unresolved_writes_weakly_update_tracked_memory";
         "unresolved_or_escaped_return_aliases_unknown"])
    ; ("instruction_slices", `List (List.map summary.SymPasDomain.instruction_slices
         ~f:(fun (source, dependencies) ->
           `Assoc [("instruction", source_json source);
                   ("data_dependencies", strings (input_dependencies dependencies));
                   ("source_locations", source_locations dependencies)])))
    ; ("source_locations", `List (List.map sources ~f:source_json))
    ; ("precision", `String "conservative")
    ; ("analysis_status", `String "partial") ]
  |> Yojson.Safe.to_string


let checker ({InterproceduralAnalysis.proc_desc; err_log} as analysis_data) =
  match collect_dependencies analysis_data with
  | None ->
      None
  | Some variables when Domain.is_bottom variables ->
      None
  | Some variables ->
      let loc = Procdesc.Node.get_loc (Procdesc.get_exit_node proc_desc) in
      let backward_summary = formal_summary proc_desc variables in
      let summary =
        match SymPasSymbolic.compute analysis_data with
        | Some symbolic -> symbolic
        | None -> backward_summary
      in
      let precise_controls = precise_control_locations proc_desc variables in
      let message =
        F.asprintf
          "SymPas backward dependencies of the return value: %a; candidate summary: %a; precise control locations: %a; sympas_json=%s"
          Domain.pp variables SymPasDomain.pp_summary backward_summary LocationSet.pp precise_controls
          (structured_evidence proc_desc variables summary precise_controls)
      in
      Reporting.log_issue proc_desc err_log ~loc SymPas IssueType.sympas_slice message ;
      (* An integral return type alone does not prove an error-code convention.
         Emit an explicit low-confidence candidate for the Python Agent to
         display as evidence only; it must not auto-enable a review rule. *)
      if Typ.is_int (Procdesc.get_ret_type proc_desc) then (
        let callee = F.asprintf "%a" Procname.pp (Procdesc.get_proc_name proc_desc) in
        let confidence, evidence =
          if has_negative_integer_return proc_desc then ("medium", "negative_integer_return")
          else ("low", "integral_return_type")
        in
        let contract_message =
          F.asprintf
            "SymPas return contract candidate: callee=%s; kind=status_candidate; confidence=%s; evidence=%s"
            callee confidence evidence
        in
        Reporting.log_issue proc_desc err_log ~loc SymPas IssueType.sympas_return_contract_candidate
          contract_message ) ;
      Some summary
