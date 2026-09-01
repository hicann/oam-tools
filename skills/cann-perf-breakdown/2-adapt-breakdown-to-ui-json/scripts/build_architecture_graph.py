#!/usr/bin/env python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Emit `model_architecture_graph.v1` from a breakdown's declared structure.

The fourth UI fact. Nodes come from the emitted analysis config; edges come only from
declarations — sequential `children` order gives activation flow, and
`structures.<group>.branches` gives residual/skip paths. Nothing is inferred from kernel
order, profiler indices, or timestamps.

The UI skill's own `build-source-overlay.mjs` is bound to one model (hardcoded source hashes,
a fixed layer count and MTP layout), so it cannot build another model's graph. This builds the
same schema from whatever the breakdown declares.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_paths  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def walk(node, out):
    out.append(node)
    for child in node.get("children") or []:
        walk(child, out)
    return out


def structural_id(node):
    """A node's id under either key.

    An observed node carries `node_id`; a source-only one carries `structure_node_id`, so it
    stays out of the UI runtime's backend index. The graph still needs to place and address
    it, so both spellings resolve here rather than at every call site.
    """
    return node.get("node_id") or node.get("structure_node_id")


def item_for(node, mapped_ids, source_only_reasons):
    node_id = structural_id(node)
    is_mapped = node_id in mapped_ids
    item = {
        "id": node_id,
        "label": node.get("name") or node_id.rsplit("/", 1)[-1],
        "kind": "module" if node.get("children") else "op",
        "type": node.get("node_kind") or ("module" if node.get("children") else "op"),
        "origin": "hybrid" if is_mapped else "source",
        "dataState": "mapped" if is_mapped else "source_only",
        "selectable": True,
        "sourceRefs": [node["code_ref"]] if node.get("code_ref") else [],
        "attributes": {k: v for k, v in (
            ("semantic", node.get("semantic")),
            ("metricScope", node.get("metric_scope")),
            ("semanticKey", node.get("semantic_key")),
        ) if v},
        "children": [],
    }
    # A repeated group folds every observed invocation into one item; the pager needs the
    # count. The pager spans every layer the source DECLARES for the group, not only the
    # observed ones: a capture covering 3 of 58 layers still belongs to a 58-layer stack,
    # and a pager stopping at 3 would misreport the model as small. Observed entries carry
    # metrics; the rest are selectable and metric-free.
    instances = node.get("instance_indices") or []
    declared = node.get("declared_instance_indices") or []
    unobserved = node.get("unobserved_instance_indices") or []
    pager_indices = sorted(set(instances) | set(declared)) if declared else list(instances)
    if len(pager_indices) > 1:
        item["repeatCount"] = len(pager_indices)
        item["instanceIndices"] = pager_indices
        item["defaultCollapsed"] = False
        if unobserved:
            item["observedInstanceIndices"] = list(instances)
            item["unobservedInstanceIndices"] = sorted(unobserved)
    elif pager_indices:
        # A group with exactly one instance needs no pager, but the layer it stands for is
        # still part of the declared stack. Record the index without the repeat affordances,
        # otherwise coverage reads the layer as absent from the graph -- which is how a
        # single-layer group (LongCat's unfused layer 0) looked like a missing layer.
        item["instanceIndices"] = list(pager_indices)
    if is_mapped:
        item["backendNodeId"] = node_id
        item["mappingKind"] = "aggregate" if node.get("children") else "exact"
    elif node_id in source_only_reasons:
        item["attributes"]["reason"] = source_only_reasons[node_id]
    if node.get("structure_key"):
        item["structureKey"] = node["structure_key"]
    if node.get("architecture_group_type"):
        item["architectureGroupType"] = node["architecture_group_type"]
    if node.get("runtime_pattern"):
        item["runtimePattern"] = node["runtime_pattern"]
    return item



#: Layout constants. The graph carries positions because the UI's port policy is validated
#: geometrically: a semantic dataflow edge must run from a source's bottom into a target's top,
#: which can only be checked against real coordinates. Declaration order is the only ordering
#: claim available, so children stack vertically in that order — never side by side, which would
#: assert the two are unordered.
NODE_WIDTH = 336
NODE_HEIGHT = 56
ROW_GAP = 32
PAD_X = 24
PAD_Y = 56
MARGIN = 40


def layout_tree(item, x, y):
    """Place `item` at (x, y) and return (width, height) of its occupied box.

    Leaves get a fixed box. A container wraps its children in declaration order, top to bottom,
    so every activation edge derived from that order runs strictly downward.
    """
    if not item["children"]:
        item["_box"] = {"x": x, "y": y, "width": NODE_WIDTH, "height": NODE_HEIGHT}
        return NODE_WIDTH, NODE_HEIGHT

    child_x = x + PAD_X
    child_y = y + PAD_Y
    widest = 0
    for child in item["children"]:
        width, height = layout_tree(child, child_x, child_y)
        widest = max(widest, width)
        child_y += height + ROW_GAP
    total_height = (child_y - ROW_GAP) - y + PAD_X
    item["_box"] = {"x": x, "y": y, "width": widest + 2 * PAD_X, "height": total_height}
    return item["_box"]["width"], item["_box"]["height"]


def flatten_layout(roots):
    """Split the laid-out tree into the `nodes` / `clusters` arrays the runtime reads."""
    nodes, clusters = [], []

    def emit(item, parent_id):
        box = item.pop("_box")
        common = {
            "id": item["id"], "label": item["label"], "kind": item["kind"],
            "x": box["x"], "y": box["y"], "width": box["width"], "height": box["height"],
            "dataState": item["dataState"], "origin": item["origin"],
            "selectable": item["selectable"],
        }
        for key in ("structureKey", "architectureGroupType", "runtimePattern"):
            if item.get(key):
                common[key] = item[key]
        if item.get("backendNodeId"):
            common["backendNodeId"] = item["backendNodeId"]
        if item["children"]:
            clusters.append({**common,
                             "children": [c["id"] for c in item["children"]],
                             "nodes": [],
                             "repeat": bool(item.get("repeatCount")),
                             "collapsible": True,
                             "structuralRoot": parent_id == "",
                             "parent": parent_id})
        else:
            common["parent"] = parent_id
            common["typeLabel"] = "Op"
            nodes.append(common)
        for child in item["children"]:
            emit(child, item["id"])

    for root in roots:
        emit(root, "")
    return nodes, clusters


def build(analysis, breakdown):
    mapped_ids = {node_id for node_id in analysis.get("_metric_node_ids", [])}
    source_only_reasons = {entry.get("structure_node_id"): entry.get("reason")
                           for entry in analysis.get("source_only_structure") or []}

    roots, edges = [], []
    source_children, runtime_children = [], []

    def _matching_parallel_members(node, branch):
        """Return an ordered parallel_siblings group described by this branch, if any."""
        names = [str(child.get("name") or "") for child in node.get("children") or []]
        positions = {name: index for index, name in enumerate(names) if name}
        inputs = {str(value).rsplit("/", 1)[-1] for value in branch.get("inputs") or []}
        output = str(branch.get("output") or "").rsplit("/", 1)[-1]
        for sibling_group in node.get("parallel_siblings") or []:
            members = [str(value) for value in sibling_group.get("members") or []]
            if not members or any(member not in positions for member in members):
                continue
            members.sort(key=positions.get)
            first, last = positions[members[0]], positions[members[-1]]
            if first == 0 or last + 1 >= len(names):
                continue
            if names[first - 1] in inputs and names[last + 1] == output:
                return members
        return None

    def _parallel_members_by_name(node):
        """Index sibling groups only inside their declaring container."""
        result = {}
        for group in (node or {}).get("parallel_siblings") or []:
            members = [str(member) for member in group.get("members") or []]
            for name in members:
                result.setdefault(name, set()).update(members)
        return result

    def _matching_breakdown_child(parent, child, position):
        """Pair an emitted UI child with its source node in the same local scope."""
        candidates = (parent or {}).get("children") or []
        name = str(child.get("name") or "")
        if position < len(candidates) and str(candidates[position].get("name") or "") == name:
            return candidates[position]
        matches = [candidate for candidate in candidates
                   if str(candidate.get("name") or "") == name]
        return matches[0] if len(matches) == 1 else None

    def add_tree(node, sink, breakdown_node=None):
        item = item_for(node, mapped_ids, source_only_reasons)
        sink.append(item)
        kids = node.get("children") or []
        for position, child in enumerate(kids):
            source_child = _matching_breakdown_child(breakdown_node, child, position)
            add_tree(child, item["children"], source_child)
        # Activation flow: declaration order inside one container, and nothing else.
        explicit_parallel_targets = {
            str(branch.get("output") or "").rsplit("/", 1)[-1]
            for branch in (breakdown_node or {}).get("branches") or []
            if branch.get("kind") == "parallel"
            and not _matching_parallel_members(breakdown_node or {}, branch)
        }
        parallel_members = _parallel_members_by_name(breakdown_node)
        for left, right in zip(kids, kids[1:]):
            # Siblings declared parallel share a producer rather than feeding one another;
            # the fan-out edge into each of them comes from the sibling before the group.
            if str(right.get("name")) in parallel_members.get(str(left.get("name")), set()):
                continue
            # A parallel branch without a contiguous parallel_siblings group supplies the
            # target's complete inbound dataflow explicitly. Keeping the adjacency edge would
            # fabricate a dependency on the preceding declaration and may duplicate a join.
            if str(right.get("name")) in explicit_parallel_targets:
                continue
            edges.append({
                "id": f"activation::{structural_id(left)}->{structural_id(right)}",
                "source": structural_id(left),
                "target": structural_id(right),
                "semanticEdgeType": "activation",
                "tensor": {"role": "activation", "from": left.get("name"),
                           "to": right.get("name")},
                "provenance": [
                    f"declared children order in {node['node_id']}",
                    node.get("code_ref") or "analysis_config structure",
                ],
            })
        # Fan-out into a parallel group: every member takes its input from the sibling that
        # precedes the group, so the members after the first would otherwise have no producer
        # once their serial edge is suppressed above.
        for position, child in enumerate(kids):
            members = parallel_members.get(str(child.get("name")))
            if not members or position == 0:
                continue
            previous = kids[position - 1]
            if str(previous.get("name")) in members:
                # Walk back to the first member of the group; its predecessor is the producer.
                first = position
                while first > 0 and str(kids[first - 1].get("name")) in members:
                    first -= 1
                if first == 0:
                    continue
                producer = kids[first - 1]
                edges.append({
                    "id": f"activation::{structural_id(producer)}->{structural_id(child)}",
                    "source": structural_id(producer),
                    "target": structural_id(child),
                    "semanticEdgeType": "activation",
                    "tensor": {"role": "activation", "from": producer.get("name"),
                               "to": child.get("name")},
                    "provenance": [
                        f"parallel_siblings fan-out in {node['node_id']}",
                        node.get("code_ref") or "analysis_config structure",
                    ],
                })
        return item

    # A branch endpoint may be spelled as a bare child name or as a fully-qualified node id
    # (both are legal in schema-v2 analysis_config.json, and schema-mapping.md § Graph shows
    # the bare form). Edges are keyed by node id, so the bare form has to be resolved against
    # the group that declares it before the endpoints can be checked. Without this, a
    # correctly-declared residual looked like a branch naming an undefined node.
    node_id_by_group_name = {}
    node_id_by_structure_path = {}

    def _index_names(group_key, node, parent_path=()):
        for child in node.get("children") or []:
            name = str(child.get("name") or "")
            node_id = structural_id(child)
            if name and node_id:
                node_id_by_group_name.setdefault(group_key, {}).setdefault(name, node_id)
                child_path = parent_path + (name,)
                node_id_by_structure_path[
                    f"structures/{group_key}/{'/'.join(child_path)}"
                ] = node_id
            else:
                child_path = parent_path
            _index_names(group_key, child, child_path)

    for section_name in ("stages", "layer_structure"):
        for group_key, node in (analysis.get(section_name) or {}).items():
            node_id_by_group_name.setdefault(group_key, {})
            root_name = str(node.get("name") or "")
            if root_name and structural_id(node):
                node_id_by_group_name[group_key][root_name] = structural_id(node)
            _index_names(group_key, node)

    def _resolve_endpoint(group_key, endpoint):
        """Resolve a bare name or a Stage 1 ``structures/<group>/<path>`` reference."""
        endpoint = str(endpoint)
        return (node_id_by_structure_path.get(endpoint)
                or node_id_by_group_name.get(group_key, {}).get(endpoint)
                or endpoint)

    for group in ("stages", "layer_structure"):
        section = analysis.get(group) or {}
        if isinstance(section, dict):
            for key, node in section.items():
                breakdown_section = (breakdown.get("stages") or {}) if group == "stages" \
                    else (breakdown.get("structures") or {})
                item = add_tree(node, source_children, breakdown_section.get(key))
                # `--rename-group` addresses a group by role (`decoder_layers`) instead of
                # its source class (`LongcatFlashDecoderLayer`), and the renamed value
                # replaces both the node id and semantic_key. Carry the declaring key so
                # coverage checks can still match the group against `architecture`, which
                # only ever names the class. Without it a renamed group looks undeclared.
                if group == "layer_structure" and item is not None:
                    item["structureKey"] = key
        else:
            for node in section:
                add_tree(node, source_children)
    for node in analysis.get("runtime_auxiliary") or []:
        add_tree(node, runtime_children)

    # Top-level dataflow. Stages and layer groups are separate roots, so children order cannot
    # connect them. Prefer the explicit graph, which can preserve forks, joins and named ports;
    # use the legacy linear model_flow only when no explicit graph was declared.
    known_top = {item["id"] for item in source_children}
    flow_alias = {}
    group_key_by_top_id = {}
    for key, node in (analysis.get("stages") or {}).items():
        node_id = structural_id(node)
        if node_id:
            flow_alias[str(key)] = node_id
            flow_alias[str(node.get("semantic_key") or key)] = node_id
            group_key_by_top_id[node_id] = str(key)
    for key, node in (analysis.get("layer_structure") or {}).items():
        node_id = structural_id(node)
        if node_id:
            flow_alias[str(key)] = node_id
            flow_alias[str(node.get("semantic_key") or key)] = node_id
            group_key_by_top_id[node_id] = str(key)

    def _top_id(name):
        name = str(name)
        return name if name in known_top else flow_alias.get(name)

    def _stable_topological_order(constraints):
        """Order roots for top-to-bottom ports while preserving unrelated declaration order."""
        original = [item["id"] for item in source_children]
        position = {node_id: index for index, node_id in enumerate(original)}
        successors = {node_id: set() for node_id in original}
        indegree = {node_id: 0 for node_id in original}
        for left, right in constraints:
            if left == right or right in successors[left]:
                continue
            successors[left].add(right)
            indegree[right] += 1
        ready = sorted((node_id for node_id in original if indegree[node_id] == 0),
                       key=position.get)
        ordered = []
        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for target in sorted(successors[node_id], key=position.get):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort(key=position.get)
        if len(ordered) != len(original):
            raise SystemExit(
                "dataflow contains a same-invocation cycle; declare a previous-invocation "
                "edge as runtime_carry instead of forcing a cyclic layout"
            )
        rank = {node_id: index for index, node_id in enumerate(ordered)}
        source_children.sort(key=lambda item: rank[item["id"]])

    declared_dataflow = analysis.get("dataflow")
    if declared_dataflow is None:
        declared_dataflow = breakdown.get("dataflow")

    if declared_dataflow is not None:
        declared_nodes = {str(node.get("id")): node
                          for node in (declared_dataflow.get("nodes") or [])
                          if node.get("id") is not None}
        endpoint_roots = {}
        unresolved_nodes = []
        for endpoint_id, node in declared_nodes.items():
            structure = node.get("structure") or endpoint_id
            root_id = _top_id(structure) or _top_id(endpoint_id)
            if root_id is None:
                unresolved_nodes.append(endpoint_id)
            else:
                endpoint_roots[endpoint_id] = root_id
        if unresolved_nodes:
            raise SystemExit(
                "dataflow nodes do not resolve to top-level structures: "
                f"{sorted(unresolved_nodes)}. Known keys: {sorted(flow_alias)}"
            )

        descendant_ids_by_top = {
            item["id"]: {node["id"] for node in walk(item, [])}
            for item in source_children
        }
        known_source_ids = set().union(*descendant_ids_by_top.values())

        def _resolve_dataflow_endpoint(endpoint_id, port):
            endpoint_id = str(endpoint_id)
            if endpoint_id not in endpoint_roots:
                raise SystemExit(f"dataflow edge references undeclared endpoint: {endpoint_id}")
            root_id = endpoint_roots[endpoint_id]
            if not port:
                return root_id
            group_key = group_key_by_top_id[root_id]
            resolved = _resolve_endpoint(group_key, port)
            if (resolved not in known_source_ids
                    or resolved not in descendant_ids_by_top[root_id]):
                raise SystemExit(
                    f"dataflow port {endpoint_id}.{port} does not resolve inside {group_key}"
                )
            return resolved

        semantic_type = {
            "activation": "activation",
            "residual": "residual",
            "parameter": "parameter",
            "cache": "state",
            "index": "control",
            "runtime_carry": "state",
        }
        constraints = []
        for index, declared_edge in enumerate(declared_dataflow.get("edges") or []):
            source_name = str(declared_edge.get("source"))
            target_name = str(declared_edge.get("target"))
            kind = declared_edge.get("kind")
            if kind not in semantic_type:
                raise SystemExit(f"dataflow edge {index} has unsupported kind: {kind}")
            source = _resolve_dataflow_endpoint(source_name, declared_edge.get("source_port"))
            target = _resolve_dataflow_endpoint(target_name, declared_edge.get("target_port"))
            edge_type = semantic_type[kind]
            graph_edge = {
                "id": f"dataflow::{index}::{source_name}->{target_name}",
                "source": source,
                "target": target,
                "semanticEdgeType": edge_type,
                "tensor": {
                    "role": edge_type,
                    "from": declared_edge.get("source_port") or source_name,
                    "to": declared_edge.get("target_port") or target_name,
                },
                "provenance": [
                    f"analysis_config dataflow.edges[{index}]",
                    declared_edge.get("source_ref") or "analysis_config dataflow",
                ],
            }
            if edge_type == "residual":
                graph_edge.update({"dashed": True, "tag": "residual"})
            if kind == "runtime_carry":
                offset = declared_edge.get("invocation_offset")
                if (not isinstance(offset, int) or isinstance(offset, bool) or offset <= 0):
                    raise SystemExit(
                        f"dataflow runtime_carry edge {index} requires a positive integer "
                        "invocation_offset"
                    )
                graph_edge.update({"crossInvocation": True, "crossStep": offset})
            edges.append(graph_edge)
            if kind != "runtime_carry":
                constraints.append((endpoint_roots[source_name], endpoint_roots[target_name]))
        if constraints:
            _stable_topological_order(constraints)
    else:
        # Compatibility for older linear breakdowns.
        declared_flow = [str(n) for n in (analysis.get("model_flow") or [])]
        flow, unresolved_flow = [], []
        for name in declared_flow:
            node_id = _top_id(name)
            if node_id in known_top:
                flow.append(node_id)
            else:
                unresolved_flow.append(name)
        if unresolved_flow:
            raise SystemExit(
                f"model_flow entries do not resolve to top-level nodes: {unresolved_flow}. "
                f"Known keys: {sorted(flow_alias)}"
            )
        if flow:
            rank = {node_id: position for position, node_id in enumerate(flow)}
            source_children.sort(key=lambda item: rank.get(item["id"], len(rank)))
        for left, right in zip(flow, flow[1:]):
            edges.append({
                "id": f"activation::{left}->{right}",
                "source": left,
                "target": right,
                "semanticEdgeType": "activation",
                "tensor": {"role": "activation",
                           "from": left.rsplit("/", 1)[-1], "to": right.rsplit("/", 1)[-1]},
                "provenance": ["analysis_config model_flow",
                               analysis.get("architecture", {}).get("source_of_truth", [""])[0]
                               or "analysis_config model_flow"],
            })

    # Residual/skip edges exist only where the breakdown declares a branch.
    #
    # These are drawn, not shelved. A residual spans the block it bypasses, and when the
    # block is a folded repeated group its sink is the next invocation -- i.e. it points back
    # at an earlier child of the same template. The renderer gives residual edges their own
    # side lane, so spanning or reversing rows is expected rather than a contract violation.
    # `crossInvocation` marks the ones whose sink is the next call, so the UI can label them.
    # Sibling order is per DECLARING node, not per structure root: a branch declared on the
    # `mlp` node orders itself against mlp's children, and reusing the root's children would
    # find neither endpoint and silently call every nested branch forward.
    order_by_group = {}

    def _index_order(group_key, node):
        names = [c.get("name") for c in (node.get("children") or [])]
        for name in names:
            if name:
                order_by_group.setdefault((group_key, name), names)
        for child in node.get("children") or []:
            _index_order(group_key, child)

    for key, structure in (breakdown.get("structures") or {}).items():
        _index_order(key, structure)

    def _crosses_invocation(group_key, source, target):
        """True when the sink sits at or before the fork in declaration order."""
        s_leaf = str(source).rsplit("/", 1)[-1]
        order = order_by_group.get((group_key, s_leaf)) or []
        pos = {n: i for i, n in enumerate(order) if n}
        s, t = str(source).rsplit("/", 1)[-1], str(target).rsplit("/", 1)[-1]
        return s in pos and t in pos and pos[t] <= pos[s]

    # `branches` is legal on ANY node, not just a structure root -- the MoE shared-expert
    # fan-out is declared on the `mlp` node, one level down. Reading only the root dropped it
    # silently, leaving the shared expert with an inbound edge and no rejoin, so the report
    # showed a dead-end branch. `_collect_parallel` above already recurses for the same
    # reason; this loop has to as well.
    def _branch_nodes(node):
        yield node
        for child in node.get("children") or []:
            yield from _branch_nodes(child)

    def _parallel_rejoin_sources(node, branch):
        """Return parallel members whose join edge is absent from children order.

        The branch inputs name the fork point, while the output names the join. The last
        parallel member already reaches that join through sequential children order, so the
        explicit branch supplies the missing join edges from the other members.
        """
        members = _matching_parallel_members(node, branch)
        if members:
            return members[:-1]
        return list(branch.get("inputs") or [])

    for key, structure in (breakdown.get("structures") or {}).items():
        branch_ordinal = 0
        for declaring in _branch_nodes(structure):
            for branch in declaring.get("branches") or []:
                declaration_id = f"{branch_ordinal}:{branch.get('name') or 'unnamed'}"
                branch_ordinal += 1
                output = branch.get("output")
                sources = (_parallel_rejoin_sources(declaring, branch)
                           if branch.get("kind") == "parallel"
                           else list(branch.get("inputs") or []))
                for source in sources:
                    cross = (branch.get("kind") == "cross_invocation"
                             or _crosses_invocation(key, source, output))
                    # A cross-invocation carry has to say WHICH invocation it comes from, or
                    # the UI cannot label it and its validator rejects the edge. The breakdown
                    # already declares that distance as `invocation_offset`; default to the
                    # immediately preceding call, which a fused entry norm produces.
                    cross_step = branch.get("invocation_offset")
                    if cross and not isinstance(cross_step, int):
                        cross_step = 1
                    # A declared parallel branch is not a residual: it carries a real tensor
                    # into the join (the MoE shared expert's output is finalize_routing's
                    # `skip1`), so it is an `activation` edge, drawn solid. `residual` would
                    # put it dashed in the bypass lane and imply nothing flows along it.
                    # The graph vocabulary has no `parallel` type -- concurrency is expressed
                    # by `parallel_siblings` plus the fan-out edges, not by an edge type.
                    kind = "activation" if branch.get("kind") == "parallel" else "residual"
                    edges.append({
                        "id": f"{kind}::{key}::{declaration_id}::{source}->{output}",
                        "source": _resolve_endpoint(key, source),
                        "target": _resolve_endpoint(key, output),
                        "semanticEdgeType": kind,
                        # A residual carries the unmodified input past the block it skips, so
                        # it must not read as another activation step. `dashed` is the
                        # renderer's existing hook for exactly that distinction.
                        "dashed": kind == "residual",
                        "tag": kind,
                        "crossInvocation": cross,
                        **({"crossStep": cross_step} if cross else {}),
                        "tensor": {"role": kind, "from": source, "to": output},
                        "provenance": [f"structures.{key}.branches: {branch.get('name')}",
                                       branch.get("source_ref") or "analysis_config branches"],
                    })

    # The two section roots are containers this generator introduces to separate model dataflow
    # from runtime auxiliary. They correspond to no source construct, so they are `synthetic`
    # and carry no sourceRefs -- the graph validator requires every non-synthetic source item to
    # cite a source line, which is the right rule for real modules.
    roots.append({
        "id": "section/source_architecture", "label": "Source architecture",
        "kind": "section", "type": "section", "origin": "synthetic",
        "synthetic": True, "dataState": "source_only", "selectable": False,
        "children": source_children, "sourceRefs": [], "attributes": {},
    })
    roots.append({
        "id": "section/runtime_auxiliary", "label": "Runtime auxiliary",
        "kind": "section", "type": "section", "origin": "synthetic",
        "synthetic": True, "dataState": "runtime", "selectable": False,
        "children": runtime_children, "sourceRefs": [], "attributes": {},
    })

    known = set()
    for root in roots:
        for node in walk(root, []):
            known.add(node["id"])
    # A branch naming an undefined input is a breakdown defect, not something to drop silently.
    unresolved = sorted({e["source"] for e in edges if e["source"] not in known}
                        | {e["target"] for e in edges if e["target"] not in known})
    if unresolved:
        raise SystemExit("branches reference undeclared structure nodes: "
                         + ", ".join(unresolved))

    cursor_y = MARGIN
    for root in roots:
        _, height = layout_tree(root, MARGIN, cursor_y)
        cursor_y += height + ROW_GAP * 2
    nodes, clusters = flatten_layout(roots)
    width = max((n["x"] + n["width"] for n in nodes + clusters), default=0) + MARGIN
    height = max((n["y"] + n["height"] for n in nodes + clusters), default=0) + MARGIN

    return {
        "schema_version": "model_architecture_graph.v1",
        "metadata": {
            "modelId": analysis.get("model_id"),
            "reportId": analysis.get("report_id"),
            "extractionScope": "hybrid",
            "sourceScope": "declared_structure",
            "backendScope": analysis.get("representative_step"),
            "sourceNodeCount": len(known),
            "backendNodeCount": len(mapped_ids),
        },
        "roots": roots,
        "edges": edges,
        "width": width,
        "height": height,
        "nodes": nodes,
        "clusters": clusters,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, help="emitted UI analysis config")
    parser.add_argument("--performance", required=True, help="emitted UI perf data")
    parser.add_argument("--breakdown", required=True, help="schema-v2 analysis_config.json")
    parser.add_argument("--out", required=True, help="model_architecture_graph.json")
    args = parser.parse_args()

    # `--breakdown` here is the config file, so the other formal files sit beside it.
    breakdown_paths.require_breakdown_ready(
        os.path.dirname(os.path.abspath(args.breakdown)), args.breakdown,
        "build_architecture_graph.py")

    analysis = load(args.analysis)
    performance = load(args.performance)
    # A node carries metrics exactly when performance has a record for it.
    analysis["_metric_node_ids"] = [m["node_id"] for m in performance.get("modules") or []]
    graph = build(analysis, load(args.breakdown))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(graph, handle, ensure_ascii=False, indent=1)
        handle.write("\n")

    print(f"WROTE {args.out}")
    print(f"  source nodes {graph['metadata']['sourceNodeCount']}"
          f"  mapped {graph['metadata']['backendNodeCount']}"
          f"  edges {len(graph['edges'])}")


if __name__ == "__main__":
    main()
