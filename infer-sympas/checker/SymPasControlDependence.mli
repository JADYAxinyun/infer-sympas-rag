val compute_postdominators : Procdesc.t -> Procdesc.NodeSet.t Procdesc.NodeMap.t

val controls :
     Procdesc.NodeSet.t Procdesc.NodeMap.t
  -> branch:Procdesc.Node.t
  -> target:Procdesc.Node.t
  -> bool
