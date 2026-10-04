(*
 * Initial SymPas prototype.
 *
 * This milestone computes an intraprocedural backward data-dependency slice
 * from a procedure return value, including the source locations of relevant
 * assignments and branch conditions. The branch handling is a conservative
 * first control-dependency approximation; interprocedural summaries are not
 * implemented yet.
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
  type t = {frontier: VarSet.t; slice_locations: LocationSet.t}

  let leq ~lhs ~rhs =
    VarSet.leq ~lhs:lhs.frontier ~rhs:rhs.frontier
    && LocationSet.leq ~lhs:lhs.slice_locations ~rhs:rhs.slice_locations


  let join lhs rhs =
    { frontier= VarSet.join lhs.frontier rhs.frontier
    ; slice_locations= LocationSet.join lhs.slice_locations rhs.slice_locations }


  let widen ~prev ~next ~num_iters =
    { frontier= VarSet.widen ~prev:prev.frontier ~next:next.frontier ~num_iters
    ; slice_locations=
        LocationSet.widen ~prev:prev.slice_locations ~next:next.slice_locations ~num_iters }


  let pp fmt {frontier; slice_locations} =
    F.fprintf fmt "{frontier=%a; slice_locations=%a}" VarSet.pp frontier LocationSet.pp
      slice_locations


  let bottom = {frontier= VarSet.bottom; slice_locations= LocationSet.bottom}

  let is_bottom {frontier; slice_locations} =
    VarSet.is_bottom frontier && LocationSet.is_bottom slice_locations


  let initial = bottom

  let singleton var = {bottom with frontier= VarSet.singleton var}

  let mem var {frontier} = VarSet.mem var frontier

  let add_var var state = {state with frontier= VarSet.add var state.frontier}

  let remove_var var state = {state with frontier= VarSet.remove var state.frontier}

  let add_location loc state =
    let loc_string = F.asprintf "%a" Location.pp loc in
    {state with slice_locations= LocationSet.add loc_string state.slice_locations}

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

  type analysis_data = Procdesc.t

  (** A backward dependency transfer.

      If the slicing frontier contains the result of an assignment, replace it
      with the variables read by its right-hand side. *)
  let exec_instr state _ _ _ (instr : Sil.instr) =
    match instr with
    | Sil.Prune (condition, loc, _, _) when not (Domain.is_bottom state) ->
        state |> add_exp_vars condition |> Domain.add_location loc
    | Sil.Call ((ret_id, _), callee, actuals, loc, _)
      when Domain.mem (Var.of_id ret_id) state ->
        state
        |> Domain.remove_var (Var.of_id ret_id)
        |> add_exp_vars callee
        |> add_actuals actuals
        |> Domain.add_location loc
    | Sil.Load {id; e= rhs; _} when Domain.mem (Var.of_id id) state ->
        state |> Domain.remove_var (Var.of_id id) |> add_exp_vars rhs
    | Sil.Store {e1= Exp.Lvar lhs; e2= rhs; loc; _} when Domain.mem (Var.of_pvar lhs) state ->
        state
        |> Domain.remove_var (Var.of_pvar lhs)
        |> add_exp_vars rhs
        |> Domain.add_location loc
    | _ ->
        state


  let pp_session_name _node fmt = F.pp_print_string fmt "SymPas backward slice"
end

module CFG = ProcCfg.OneInstrPerNode (ProcCfg.Backward (ProcCfg.Exceptional))
module Analyzer = AbstractInterpreter.MakeRPO (TransferFunctions (CFG))

(** Run the first SymPas prototype on one procedure. *)
let collect_dependencies proc_desc =
  let return_var = Var.of_pvar (Procdesc.get_ret_var proc_desc) in
  Analyzer.compute_post proc_desc ~initial:(Domain.singleton return_var) proc_desc

let formal_summary proc_desc {Domain.frontier} =
  Procdesc.get_pvar_formals proc_desc
  |> List.filter_mapi ~f:(fun index (pvar, _) ->
         if VarSet.mem (Var.of_pvar pvar) frontier then Some index else None)
  |> SymPasDomain.of_formal_indices


let checker {IntraproceduralAnalysis.proc_desc; err_log} =
  match collect_dependencies proc_desc with
  | None ->
      ()
  | Some variables when Domain.is_bottom variables ->
      ()
  | Some variables ->
      let loc = Procdesc.Node.get_loc (Procdesc.get_exit_node proc_desc) in
      let summary = formal_summary proc_desc variables in
      let message =
        F.asprintf
          "SymPas backward dependencies of the return value: %a; candidate summary: %a"
          Domain.pp variables SymPasDomain.pp_summary summary
      in
      Reporting.log_issue proc_desc err_log ~loc SymPas IssueType.sympas_slice message
