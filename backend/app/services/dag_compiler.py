from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, deque


def is_source_node(node: Dict[str, Any]) -> bool:
    category = node.get("category", "").lower()
    node_type = node.get("type", "").lower()
    data_type = node.get("data", {}).get("node_type", "").lower()
    return category == "source" or "source" in node_type or "source" in data_type


def is_destination_node(node: Dict[str, Any]) -> bool:
    category = node.get("category", "").lower()
    node_type = node.get("type", "").lower()
    data_type = node.get("data", {}).get("node_type", "").lower()
    return category == "destination" or "destination" in node_type or "destination" in data_type


def validate_and_compile_dag(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]]
) -> Tuple[bool, List[str], List[Dict[str, Any]], Optional[int], Dict[str, Any]]:
    """
    Validates DAG structure and compiles it into an executable linear ETL step sequence.
    Returns: (is_valid, errors, compiled_steps, source_id, destination_config)
    """
    errors = []
    if not nodes:
        return False, ["DAG contains no nodes"], [], None, {}

    node_map = {str(n["id"]): n for n in nodes}
    source_nodes = [n for n in nodes if is_source_node(n)]
    destination_nodes = [n for n in nodes if is_destination_node(n)]

    if not source_nodes:
        errors.append("DAG must contain at least one Source node")

    if not destination_nodes:
        errors.append("DAG must contain at least one Destination node")

    # Build adjacency list & in-degree map
    adj = defaultdict(list)
    in_degree = {str(n["id"]): 0 for n in nodes}
    out_degree = {str(n["id"]): 0 for n in nodes}

    for edge in edges:
        u = str(edge.get("source"))
        v = str(edge.get("target"))

        if u not in node_map or v not in node_map:
            errors.append(f"Invalid edge connecting non-existent nodes: {u} -> {v}")
            continue

        adj[u].append(v)
        in_degree[v] += 1
        out_degree[u] += 1

        # Check invalid connection: Destination sending data to another node
        if is_destination_node(node_map[u]):
            errors.append(f"Invalid connection: Destination node '{u}' cannot have outgoing edges")

    # Check for disconnected/orphan nodes (when total nodes > 1)
    if len(nodes) > 1:
        for node_id, n in node_map.items():
            if in_degree[node_id] == 0 and out_degree[node_id] == 0:
                label = n.get("data", {}).get("label") or n.get("label") or node_id
                errors.append(f"Disconnected node detected: '{label}' (id: {node_id}) has no connections")

    if errors:
        return False, errors, [], None, {}

    # Cycle Detection & Topological Sort via Kahn's Algorithm
    queue = deque([n_id for n_id, deg in in_degree.items() if deg == 0])
    topo_order = []

    while queue:
        curr = queue.popleft()
        topo_order.append(curr)

        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(topo_order) != len(nodes):
        return False, ["DAG contains a cycle / circular dependency"], [], None, {}

    # Extract source_id from source node
    source_id = None
    first_source = source_nodes[0]
    source_data = first_source.get("data", {})
    if "source_id" in source_data:
        try:
            source_id = int(source_data["source_id"])
        except (ValueError, TypeError):
            pass

    # Extract destination_config from destination node
    first_dest = destination_nodes[0]
    dest_data = first_dest.get("data", {})
    destination_config = {
        "destination_type": dest_data.get("destination_type", "POSTGRES_TABLE"),
        "table_name": dest_data.get("table_name", "transformed_dataset"),
        "if_exists": dest_data.get("if_exists", "append"),
        "warehouse_model_id": dest_data.get("warehouse_model_id"),
        "warehouse_model_slug": dest_data.get("warehouse_model_slug") or dest_data.get("warehouse_model"),
    }




    # Compile intermediate transformation and validation nodes into steps array
    compiled_steps = []
    for n_id in topo_order:
        n = node_map[n_id]
        if is_source_node(n) or is_destination_node(n):
            continue

        n_data = n.get("data", {})
        node_type = str(n.get("type") or n_data.get("node_type") or "").lower()
        step_type = str(n_data.get("step_type") or n_data.get("rule_type") or n.get("type") or "").lower()
        raw_cat = str(n.get("category") or n_data.get("category") or "").lower()

        # Assign category for validation vs transformation nodes
        is_val_node = (
            raw_cat == "validation"
            or "validation" in node_type
            or (any(r in step_type for r in ["not_null", "unique", "primary_key", "range", "regex"]) and raw_cat != "transformation")
        )
        category = "validation" if is_val_node else (raw_cat or "transformation")

        orig_type = n_data.get("step_type") or n.get("type") or step_type
        
        # Configuration Validation
        if category == "transformation":
            if step_type == "filter_rows" and not n_data.get("condition"):
                errors.append(f"Node '{n_data.get('label', 'Filter Rows')}' requires a filter condition.")
            elif step_type in ["calculate_column", "derived_column"] and (not n_data.get("target_column") or not n_data.get("formula")):
                errors.append(f"Node '{n_data.get('label', 'Calculate Column')}' requires a destination column and formula.")
            elif step_type == "rename_columns" and not n_data.get("mapping"):
                errors.append(f"Node '{n_data.get('label', 'Rename Columns')}' requires column mapping.")
            elif step_type == "change_data_types" and not n_data.get("mapping"):
                errors.append(f"Node '{n_data.get('label', 'Change Data Types')}' requires data type mapping.")
        elif category == "validation":
            if not n_data.get("column"):
                errors.append(f"Node '{n_data.get('label', 'Validation')}' requires a target column.")
            rule_tp = str(n_data.get("rule_type") or str(orig_type).upper()).upper()
            if rule_tp == "RANGE" and n_data.get("min_val") is None and n_data.get("max_val") is None and n_data.get("min_value") is None and n_data.get("max_value") is None:
                errors.append(f"Node '{n_data.get('label', 'Range Validation')}' requires at least a minimum or maximum value.")
            elif rule_tp == "REGEX" and not n_data.get("pattern"):
                errors.append(f"Node '{n_data.get('label', 'Regex Validation')}' requires a regex pattern.")

        step_dict = {
            "category": category,
            "type": orig_type,
            **({"rule_type": n_data.get("rule_type") or str(orig_type).upper()} if category == "validation" else {}),
            **{k: v for k, v in n_data.items() if k not in ["label", "node_type", "category", "step_type"]}
        }
        compiled_steps.append(step_dict)


    if errors:
        return False, errors, [], None, {}

    return True, [], compiled_steps, source_id, destination_config


