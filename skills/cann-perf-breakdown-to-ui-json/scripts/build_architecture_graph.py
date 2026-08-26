#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
# ----------------------------------------------------------------------------
"""Emit `model_architecture_graph.v1` from a breakdown's declared structure.

The fourth UI fact. Nodes come from the emitted analysis config; edges come only from
declarations — sequential `children` order gives activation flow, and
`structures.<group>.branches` gives residual/skip paths. Nothing is inferred from kernel
order, profiler indices, or timestamps.

Legacy UI source-overlay builders are bound to one model (hardcoded source hashes,
a fixed layer count and MTP layout), so it cannot build another model's graph. This builds the
same schema from whatever the breakdown declares.
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_paths  # noqa: E402


logger = logging.getLogger(__name__)


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


def add_pager_metadata(item, node):
    """Carry declared and observed repeated-instance coverage onto one graph item."""
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
        item["instanceIndices"] = list(pager_indices)


def item_for(node, mapped_ids, source_only_reasons):
    node_id = structural_id(node)
    is_mapped = node_id in mapped_ids
    attributes = {}
    attribute_values = (
        ("semantic", node.get("semantic")),
        ("metricScope", node.get("metric_scope")),
        ("semanticKey", node.get("semantic_key")),
    )
    for key, value in attribute_values:
        if value:
            attributes[key] = value
    item = {
        "id": node_id,
        "label": node.get("name") or node_id.rsplit("/", 1)[-1],
        "kind": "module" if node.get("children") else "op",
        "type": node.get("node_kind") or ("module" if node.get("children") else "op"),
        "origin": "hybrid" if is_mapped else "source",
        "dataState": "mapped" if is_mapped else "source_only",
        "selectable": True,
        "sourceRefs": [node["code_ref"]] if node.get("code_ref") else [],
        "attributes": attributes,
        "children": [],
    }
    # A repeated group folds every observed invocation into one item; the pager needs the
    # count. The pager spans every layer the source DECLARES for the group, not only the
    # observed ones: a capture covering 3 of 58 layers still belongs to a 58-layer stack,
    # and a pager stopping at 3 would misreport the model as small. Observed entries carry
    # metrics; the rest are selectable and metric-free.
    add_pager_metadata(item, node)
    if is_mapped:
        item["backendNodeId"] = node_id
        item["mappingKind"] = "aggregate" if node.get("children") else "exact"
    elif node_id in source_only_reasons:
        item["attributes"]["reason"] = source_only_reasons[node_id]
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


class GraphBuilder:
    """Build the declared architecture graph while keeping resolution state scoped."""

    def __init__(self, analysis, breakdown):
        self.analysis = analysis
        self.breakdown = breakdown
        self.mapped_ids = set(analysis.get("_metric_node_ids", []))
        self.source_only_reasons = {
            entry.get("structure_node_id"): entry.get("reason")
            for entry in analysis.get("source_only_structure") or []
        }
        self.roots, self.edges = [], []
        self.source_children, self.runtime_children = [], []
        self.node_id_by_group_name = {}
        self.node_id_by_structure_path = {}
        self.known_top = set()
        self.flow_alias = {}
        self.group_key_by_top_id = {}
        self.order_by_group = {}

    @staticmethod
    def matching_parallel_members(node, branch):
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

    @staticmethod
    def parallel_members_by_name(node):
        """Index sibling groups only inside their declaring container."""
        result = {}
        for group in (node or {}).get("parallel_siblings") or []:
            members = [str(member) for member in group.get("members") or []]
            for name in members:
                result.setdefault(name, set()).update(members)
        return result

    @staticmethod
    def matching_breakdown_child(parent, child, position):
        """Pair an emitted UI child with its source node in the same local scope."""
        candidates = (parent or {}).get("children") or []
        name = str(child.get("name") or "")
        if position < len(candidates) and str(candidates[position].get("name") or "") == name:
            return candidates[position]
        matches = [candidate for candidate in candidates
                   if str(candidate.get("name") or "") == name]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def activation_edge(node, source, target, provenance):
        return {
            "id": f"activation::{structural_id(source)}->{structural_id(target)}",
            "source": structural_id(source), "target": structural_id(target),
            "semanticEdgeType": "activation",
            "tensor": {"role": "activation", "from": source.get("name"),
                       "to": target.get("name")},
            "provenance": [provenance, node.get("code_ref") or "analysis_config structure"],
        }

    def add_serial_edges(self, node, breakdown_node, kids):
        explicit_parallel_targets = set()
        for branch in (breakdown_node or {}).get("branches") or []:
            if branch.get("kind") != "parallel":
                continue
            if not self.matching_parallel_members(breakdown_node or {}, branch):
                explicit_parallel_targets.add(str(branch.get("output") or "").rsplit("/", 1)[-1])
        parallel_members = self.parallel_members_by_name(breakdown_node)
        for left, right in zip(kids, kids[1:]):
            left_members = parallel_members.get(str(left.get("name")), set())
            if str(right.get("name")) in left_members:
                continue
            if str(right.get("name")) in explicit_parallel_targets:
                continue
            provenance = f"declared children order in {structural_id(node)}"
            self.edges.append(self.activation_edge(node, left, right, provenance))
        return parallel_members

    def add_parallel_fanout(self, node, kids, parallel_members):
        for position, child in enumerate(kids):
            members = parallel_members.get(str(child.get("name")))
            if not members or position == 0:
                continue
            previous = kids[position - 1]
            if str(previous.get("name")) not in members:
                continue
            first = position
            while first > 0 and str(kids[first - 1].get("name")) in members:
                first -= 1
            if first == 0:
                continue
            producer = kids[first - 1]
            provenance = f"parallel_siblings fan-out in {structural_id(node)}"
            self.edges.append(self.activation_edge(node, producer, child, provenance))

    def add_tree(self, node, sink, breakdown_node=None):
        item = item_for(node, self.mapped_ids, self.source_only_reasons)
        sink.append(item)
        kids = node.get("children") or []
        for position, child in enumerate(kids):
            source_child = self.matching_breakdown_child(breakdown_node, child, position)
            self.add_tree(child, item["children"], source_child)
        parallel_members = self.add_serial_edges(node, breakdown_node, kids)
        self.add_parallel_fanout(node, kids, parallel_members)
        return item

    def index_names(self, group_key, node, parent_path=()):
        for child in node.get("children") or []:
            name = str(child.get("name") or "")
            node_id = structural_id(child)
            if name and node_id:
                self.node_id_by_group_name.setdefault(group_key, {}).setdefault(name, node_id)
                child_path = parent_path + (name,)
                self.node_id_by_structure_path[
                    f"structures/{group_key}/{'/'.join(child_path)}"
                ] = node_id
            else:
                child_path = parent_path
            self.index_names(group_key, child, child_path)

    def resolve_endpoint(self, group_key, endpoint):
        """Resolve a bare name or a Stage 1 ``structures/<group>/<path>`` reference."""
        endpoint = str(endpoint)
        return (self.node_id_by_structure_path.get(endpoint)
                or self.node_id_by_group_name.get(group_key, {}).get(endpoint)
                or endpoint)

    def add_analysis_section(self, section_name):
        section = self.analysis.get(section_name) or {}
        if not isinstance(section, dict):
            for node in section:
                self.add_tree(node, self.source_children)
            return
        breakdown_key = "stages" if section_name == "stages" else "structures"
        breakdown_section = self.breakdown.get(breakdown_key) or {}
        for key, node in section.items():
            item = self.add_tree(node, self.source_children, breakdown_section.get(key))
            if section_name == "layer_structure" and item is not None:
                item["structureKey"] = key

    def add_declared_trees(self):
        for section_name in ("stages", "layer_structure"):
            for group_key, node in (self.analysis.get(section_name) or {}).items():
                self.node_id_by_group_name.setdefault(group_key, {})
                root_name = str(node.get("name") or "")
                if root_name and structural_id(node):
                    self.node_id_by_group_name[group_key][root_name] = structural_id(node)
                self.index_names(group_key, node)
            self.add_analysis_section(section_name)
        for node in self.analysis.get("runtime_auxiliary") or []:
            self.add_tree(node, self.runtime_children)

    def index_top_level(self):
        self.known_top = {item["id"] for item in self.source_children}
        for section_name in ("stages", "layer_structure"):
            for key, node in (self.analysis.get(section_name) or {}).items():
                node_id = structural_id(node)
                if node_id:
                    self.flow_alias[str(key)] = node_id
                    self.flow_alias[str(node.get("semantic_key") or key)] = node_id
                    self.group_key_by_top_id[node_id] = str(key)

    def top_id(self, name):
        name = str(name)
        return name if name in self.known_top else self.flow_alias.get(name)

    def stable_topological_order(self, constraints):
        """Order roots for top-to-bottom ports while preserving unrelated declaration order."""
        original = [item["id"] for item in self.source_children]
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
            raise breakdown_paths.ConversionError(
                "dataflow contains a same-invocation cycle; declare a previous-invocation "
                "edge as runtime_carry instead of forcing a cyclic layout"
            )
        rank = {node_id: index for index, node_id in enumerate(ordered)}
        self.source_children.sort(key=lambda item: rank[item["id"]])

    def declared_endpoint_roots(self, declared_dataflow):
        declared_nodes = {str(node.get("id")): node
                          for node in (declared_dataflow.get("nodes") or [])
                          if node.get("id") is not None}
        endpoint_roots = {}
        unresolved_nodes = []
        for endpoint_id, node in declared_nodes.items():
            structure = node.get("structure") or endpoint_id
            root_id = self.top_id(structure) or self.top_id(endpoint_id)
            if root_id is None:
                unresolved_nodes.append(endpoint_id)
            else:
                endpoint_roots[endpoint_id] = root_id
        if unresolved_nodes:
            raise breakdown_paths.ConversionError(
                "dataflow nodes do not resolve to top-level structures: "
                f"{sorted(unresolved_nodes)}. Known keys: {sorted(self.flow_alias)}"
            )
        return endpoint_roots

    def dataflow_resolution_context(self, endpoint_roots):
        descendant_ids_by_top = {
            item["id"]: {node["id"] for node in walk(item, [])}
            for item in self.source_children
        }
        known_source_ids = set().union(*descendant_ids_by_top.values())
        return endpoint_roots, descendant_ids_by_top, known_source_ids

    def resolve_dataflow_endpoint(self, endpoint_id, port, context):
        endpoint_roots, descendant_ids_by_top, known_source_ids = context
        endpoint_id = str(endpoint_id)
        if endpoint_id not in endpoint_roots:
            raise breakdown_paths.ConversionError(
                f"dataflow edge references undeclared endpoint: {endpoint_id}"
            )
        root_id = endpoint_roots[endpoint_id]
        if not port:
            return root_id
        group_key = self.group_key_by_top_id[root_id]
        resolved = self.resolve_endpoint(group_key, port)
        if resolved not in known_source_ids or resolved not in descendant_ids_by_top[root_id]:
            raise breakdown_paths.ConversionError(
                f"dataflow port {endpoint_id}.{port} does not resolve inside {group_key}"
            )
        return resolved

    def declared_dataflow_edge(self, index, declared_edge, context):
        semantic_types = {
            "activation": "activation",
            "residual": "residual",
            "parameter": "parameter",
            "cache": "state",
            "index": "control",
            "runtime_carry": "state",
        }
        source_name = str(declared_edge.get("source"))
        target_name = str(declared_edge.get("target"))
        kind = declared_edge.get("kind")
        if kind not in semantic_types:
            raise breakdown_paths.ConversionError(
                f"dataflow edge {index} has unsupported kind: {kind}"
            )
        source = self.resolve_dataflow_endpoint(
            source_name, declared_edge.get("source_port"), context)
        target = self.resolve_dataflow_endpoint(
            target_name, declared_edge.get("target_port"), context)
        edge_type = semantic_types[kind]
        graph_edge = {
            "id": f"dataflow::{index}::{source_name}->{target_name}",
            "source": source, "target": target, "semanticEdgeType": edge_type,
            "tensor": {"role": edge_type,
                       "from": declared_edge.get("source_port") or source_name,
                       "to": declared_edge.get("target_port") or target_name},
            "provenance": [f"analysis_config dataflow.edges[{index}]",
                           declared_edge.get("source_ref") or "analysis_config dataflow"],
        }
        if edge_type == "residual":
            graph_edge.update({"dashed": True, "tag": "residual"})
        if kind == "runtime_carry":
            offset = declared_edge.get("invocation_offset")
            if not isinstance(offset, int) or isinstance(offset, bool) or offset <= 0:
                raise breakdown_paths.ConversionError(
                    f"dataflow runtime_carry edge {index} requires a positive integer "
                    "invocation_offset"
                )
            graph_edge.update({"crossInvocation": True, "crossStep": offset})
        return graph_edge, kind, source_name, target_name

    def add_declared_dataflow(self, declared_dataflow):
        endpoint_roots = self.declared_endpoint_roots(declared_dataflow)
        context = self.dataflow_resolution_context(endpoint_roots)
        constraints = []
        for index, declared_edge in enumerate(declared_dataflow.get("edges") or []):
            graph_edge, kind, source_name, target_name = self.declared_dataflow_edge(
                index, declared_edge, context)
            self.edges.append(graph_edge)
            if kind != "runtime_carry":
                constraints.append((endpoint_roots[source_name], endpoint_roots[target_name]))
        if constraints:
            self.stable_topological_order(constraints)

    def add_legacy_flow(self):
        declared_flow = [str(name) for name in (self.analysis.get("model_flow") or [])]
        flow, unresolved_flow = [], []
        for name in declared_flow:
            node_id = self.top_id(name)
            if node_id in self.known_top:
                flow.append(node_id)
            else:
                unresolved_flow.append(name)
        if unresolved_flow:
            raise breakdown_paths.ConversionError(
                f"model_flow entries do not resolve to top-level nodes: {unresolved_flow}. "
                f"Known keys: {sorted(self.flow_alias)}"
            )
        if flow:
            rank = {node_id: position for position, node_id in enumerate(flow)}
            self.source_children.sort(key=lambda item: rank.get(item["id"], len(rank)))
        for left, right in zip(flow, flow[1:]):
            self.edges.append({
                "id": f"activation::{left}->{right}",
                "source": left,
                "target": right,
                "semanticEdgeType": "activation",
                "tensor": {"role": "activation",
                           "from": left.rsplit("/", 1)[-1], "to": right.rsplit("/", 1)[-1]},
                "provenance": ["analysis_config model_flow",
                               self.analysis.get("architecture", {}).get(
                                   "source_of_truth", [""])[0]
                               or "analysis_config model_flow"],
            })

    def add_top_level_dataflow(self):
        self.index_top_level()
        declared_dataflow = self.analysis.get("dataflow")
        if declared_dataflow is None:
            declared_dataflow = self.breakdown.get("dataflow")
        if declared_dataflow is not None:
            self.add_declared_dataflow(declared_dataflow)
        else:
            self.add_legacy_flow()

    def index_order(self, group_key, node):
        names = [c.get("name") for c in (node.get("children") or [])]
        for name in names:
            if name:
                self.order_by_group.setdefault((group_key, name), names)
        for child in node.get("children") or []:
            self.index_order(group_key, child)

    def crosses_invocation(self, group_key, source, target):
        """True when the sink sits at or before the fork in declaration order."""
        s_leaf = str(source).rsplit("/", 1)[-1]
        order = self.order_by_group.get((group_key, s_leaf)) or []
        pos = {n: i for i, n in enumerate(order) if n}
        s, t = str(source).rsplit("/", 1)[-1], str(target).rsplit("/", 1)[-1]
        return s in pos and t in pos and pos[t] <= pos[s]

    def branch_nodes(self, node):
        yield node
        for child in node.get("children") or []:
            yield from self.branch_nodes(child)

    def parallel_rejoin_sources(self, node, branch):
        """Return parallel members whose join edge is absent from children order.

        The branch inputs name the fork point, while the output names the join. The last
        parallel member already reaches that join through sequential children order, so the
        explicit branch supplies the missing join edges from the other members.
        """
        members = self.matching_parallel_members(node, branch)
        if members:
            return members[:-1]
        return list(branch.get("inputs") or [])

    def branch_edge(self, key, source, branch):
        output = branch.get("output")
        cross = (branch.get("kind") == "cross_invocation"
                 or self.crosses_invocation(key, source, output))
        cross_step = branch.get("invocation_offset")
        if cross and not isinstance(cross_step, int):
            cross_step = 1
        kind = "activation" if branch.get("kind") == "parallel" else "residual"
        edge = {
            "id": f"{kind}::{key}::{source}->{output}",
            "source": self.resolve_endpoint(key, source),
            "target": self.resolve_endpoint(key, output),
            "semanticEdgeType": kind, "dashed": kind == "residual", "tag": kind,
            "crossInvocation": cross,
            "tensor": {"role": kind, "from": source, "to": output},
            "provenance": [f"structures.{key}.branches: {branch.get('name')}",
                           branch.get("source_ref") or "analysis_config branches"],
        }
        if cross:
            edge["crossStep"] = cross_step
        return edge

    def add_branches(self):
        for key, structure in (self.breakdown.get("structures") or {}).items():
            self.index_order(key, structure)
        for key, structure in (self.breakdown.get("structures") or {}).items():
            for declaring in self.branch_nodes(structure):
                self.add_declaring_branches(key, declaring)

    def add_declaring_branches(self, key, declaring):
        for branch in declaring.get("branches") or []:
            sources = (self.parallel_rejoin_sources(declaring, branch)
                       if branch.get("kind") == "parallel"
                       else list(branch.get("inputs") or []))
            for source in sources:
                self.edges.append(self.branch_edge(key, source, branch))

    def add_roots(self):
        sections = (
            ("section/source_architecture", "Source architecture", "source_only",
             self.source_children),
            ("section/runtime_auxiliary", "Runtime auxiliary", "runtime",
             self.runtime_children),
        )
        for node_id, label, data_state, children in sections:
            self.roots.append({
                "id": node_id, "label": label, "kind": "section", "type": "section",
                "origin": "synthetic", "synthetic": True, "dataState": data_state,
                "selectable": False, "children": children, "sourceRefs": [],
                "attributes": {},
            })

    def validate_edges(self):
        known = set()
        for root in self.roots:
            for node in walk(root, []):
                known.add(node["id"])
        unresolved = sorted({edge["source"] for edge in self.edges
                             if edge["source"] not in known}
                            | {edge["target"] for edge in self.edges
                               if edge["target"] not in known})
        if unresolved:
            raise breakdown_paths.ConversionError(
                "branches reference undeclared structure nodes: " + ", ".join(unresolved)
            )
        return known

    def layout(self):
        cursor_y = MARGIN
        for root in self.roots:
            _, height = layout_tree(root, MARGIN, cursor_y)
            cursor_y += height + ROW_GAP * 2
        nodes, clusters = flatten_layout(self.roots)
        width = max((node["x"] + node["width"] for node in nodes + clusters),
                    default=0) + MARGIN
        height = max((node["y"] + node["height"] for node in nodes + clusters),
                     default=0) + MARGIN
        return nodes, clusters, width, height

    def payload(self, known):
        nodes, clusters, width, height = self.layout()
        return {
            "schema_version": "model_architecture_graph.v1",
            "metadata": {
                "modelId": self.analysis.get("model_id"),
                "reportId": self.analysis.get("report_id"),
                "extractionScope": "hybrid", "sourceScope": "declared_structure",
                "backendScope": self.analysis.get("representative_step"),
                "sourceNodeCount": len(known), "backendNodeCount": len(self.mapped_ids),
            },
            "roots": self.roots, "edges": self.edges, "width": width, "height": height,
            "nodes": nodes, "clusters": clusters,
        }

    def run(self):
        self.add_declared_trees()
        self.add_top_level_dataflow()
        self.add_branches()
        self.add_roots()
        known = self.validate_edges()
        return self.payload(known)


def build(analysis, breakdown):
    """Build a graph from declared analysis and breakdown structure."""
    return GraphBuilder(analysis, breakdown).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, help="emitted UI analysis config")
    parser.add_argument("--performance", required=True, help="emitted UI perf data")
    parser.add_argument("--breakdown", required=True, help="analysis_config_v2.json")
    parser.add_argument("--out", required=True, help="model_architecture_graph.json")
    breakdown_paths.add_score_gate_args(parser)
    args = parser.parse_args()

    # `--breakdown` here is the config file, so the score sits beside it in its directory.
    breakdown_paths.require_convertible_score(
        os.path.dirname(os.path.abspath(args.breakdown)), args.allow_unscored,
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

    logger.info("WROTE %s", args.out)
    logger.info("  source nodes %s  mapped %s  edges %s",
                graph["metadata"]["sourceNodeCount"],
                graph["metadata"]["backendNodeCount"], len(graph["edges"]))


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
