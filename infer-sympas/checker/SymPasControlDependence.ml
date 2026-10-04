open! IStd

module Node = Procdesc.Node
module NodeSet = Procdesc.NodeSet
module NodeMap = Procdesc.NodeMap

let compute_postdominators proc_desc =
  let nodes = Procdesc.get_nodes proc_desc in
  let all = NodeSet.of_list nodes in
  let exit = Procdesc.get_exit_node proc_desc in
  let initial node = if phys_equal node exit then NodeSet.singleton node else all in
  let rec iterate current =
    let next =
      List.fold nodes ~init:NodeMap.empty ~f:(fun result node ->
          if phys_equal node exit then NodeMap.add node (NodeSet.singleton node) result
          else
            let successors = Node.get_succs node in
            let intersection =
              match successors with
              | [] -> NodeSet.empty
              | successor :: rest ->
                  List.fold rest ~init:(NodeMap.find successor current)
                    ~f:(fun acc successor -> NodeSet.inter acc (NodeMap.find successor current))
            in
            NodeMap.add node (NodeSet.add node intersection) result )
    in
    if List.for_all nodes ~f:(fun node -> NodeSet.equal (NodeMap.find node current) (NodeMap.find node next))
    then next
    else iterate next
  in
  iterate (List.fold nodes ~init:NodeMap.empty ~f:(fun result node -> NodeMap.add node (initial node) result))
