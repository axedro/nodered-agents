"""
Node-RED utilities
Helper functions for working with Node-RED flows
"""
import json
from typing import Dict, Any, List


def validate_nodered_flow(flow_json: str) -> tuple[bool, str]:
    """
    Validate a Node-RED flow JSON
    Returns: (is_valid, error_message)
    """
    try:
        flow = json.loads(flow_json)

        if not isinstance(flow, list):
            return False, "Flow must be a JSON array"

        node_ids = set()

        for node in flow:
            if 'id' not in node:
                return False, "Node missing 'id' field"

            if node['id'] in node_ids:
                return False, f"Duplicate node ID: {node['id']}"

            node_ids.add(node['id'])

            if 'type' not in node:
                return False, f"Node {node['id']} missing 'type' field"

        return True, ""

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def get_node_types(flow_json: str) -> List[str]:
    """
    Extract all node types from a flow
    """
    try:
        flow = json.loads(flow_json)
        return list(set(node.get('type', 'unknown') for node in flow))
    except:
        return []


def count_nodes(flow_json: str) -> int:
    """
    Count nodes in a flow
    """
    try:
        flow = json.loads(flow_json)
        return len(flow)
    except:
        return 0
