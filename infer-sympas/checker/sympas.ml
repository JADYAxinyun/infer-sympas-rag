(*
 * Initial SymPas prototype.
 *
 * This milestone collects variables read by SIL instructions in one procedure.
 * It intentionally does not yet compute backward slices, control dependencies,
 * or interprocedural summaries.
 *)

open! IStd
module F = Format

module VarSet = AbstractDomain.FiniteSet (Var)

module Domain = struct
  include VarSet

  let initial = bottom
end

(** Add all variables read by [exp] to the current slice frontier. *)
let add_exp_vars exp state =
  let state =
    Exp.free_vars exp
    |> Sequence.fold ~init:state ~f:(fun state id -> Domain.add (Var.of_id id) state)
  in
  Exp.program_vars exp
  |> Sequence.fold ~init:state ~f:(fun state pvar -> Domain.add (Var.of_pvar pvar) state)

(** Minimal intraprocedural traversal over SIL instructions. *)
module TransferFunctions (CFG : ProcCfg.S) = struct
  module CFG = CFG
  module Domain = Domain

  type analysis_data = Procdesc.t

  (** A backward dependency transfer.

      If the slicing frontier contains the result of an assignment, replace it
      with the variables read by its right-hand side. *)
  let exec_instr state _ _ _ (instr : Sil.instr) =
    match instr with
    | Sil.Load {id; e= rhs; _} when Domain.mem (Var.of_id id) state ->
        state |> Domain.remove (Var.of_id id) |> add_exp_vars rhs
    | Sil.Store {e1= Exp.Lvar lhs; e2= rhs; _} when Domain.mem (Var.of_pvar lhs) state ->
        state |> Domain.remove (Var.of_pvar lhs) |> add_exp_vars rhs
    | _ ->
        state


  let pp_session_name _node fmt = F.pp_print_string fmt "SymPas variable collection"
end

module CFG = ProcCfg.OneInstrPerNode (ProcCfg.Backward (ProcCfg.Exceptional))
module Analyzer = AbstractInterpreter.MakeRPO (TransferFunctions (CFG))

(** Run the first SymPas prototype on one procedure.

    Registration and reporting are added only after this module compiles. *)
let collect_dependencies proc_desc =
  let return_var = Var.of_pvar (Procdesc.get_ret_var proc_desc) in
  Analyzer.compute_post proc_desc ~initial:(Domain.singleton return_var) proc_desc


let checker {IntraproceduralAnalysis.proc_desc; err_log} =
  match collect_dependencies proc_desc with
  | None ->
      ()
  | Some variables when Domain.is_bottom variables ->
      ()
  | Some variables ->
      let loc = Procdesc.Node.get_loc (Procdesc.get_exit_node proc_desc) in
      let message =
        F.asprintf "SymPas backward dependencies of the return value: %a" Domain.pp variables
      in
      Reporting.log_issue proc_desc err_log ~loc SymPas IssueType.sympas_slice message
