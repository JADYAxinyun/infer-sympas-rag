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

(** Add all temporary variables read by [exp] to the current state. *)
let add_exp_vars exp state =
  Exp.free_vars exp
  |> Sequence.fold ~init:state ~f:(fun state id -> Domain.add (Var.of_id id) state)

(** Minimal intraprocedural traversal over SIL instructions. *)
module TransferFunctions (CFG : ProcCfg.S) = struct
  module CFG = CFG
  module Domain = Domain

  type analysis_data = Procdesc.t

  let exec_instr state _ _ _ (instr : Sil.instr) =
    List.fold (Sil.exps_of_instr instr) ~init:state ~f:(fun state exp -> add_exp_vars exp state)


  let pp_session_name _node fmt = F.pp_print_string fmt "SymPas variable collection"
end

module CFG = ProcCfg.Normal
module Analyzer = AbstractInterpreter.MakeRPO (TransferFunctions (CFG))

(** Run the first SymPas prototype on one procedure.

    Registration and reporting are added only after this module compiles. *)
let collect_variables proc_desc =
  let cfg = CFG.from_pdesc proc_desc in
  Analyzer.exec_cfg cfg proc_desc ~initial:Domain.initial


let checker {IntraproceduralAnalysis.proc_desc; err_log} =
  match Analyzer.compute_post proc_desc ~initial:Domain.initial proc_desc with
  | None ->
      ()
  | Some variables when Domain.is_bottom variables ->
      ()
  | Some variables ->
      let loc = Procdesc.Node.get_loc (Procdesc.get_exit_node proc_desc) in
      let message = F.asprintf "SymPas prototype collected variables: %a" Domain.pp variables in
      Reporting.log_issue proc_desc err_log ~loc SymPas IssueType.sympas_slice message
