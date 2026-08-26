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
"""Walk a schema-v2 breakdown into a flat, id-stable UI node index.

Declaration order is a semantic claim, so the walk preserves it. Each node gets
one `node_id` derived from its structural path under a single namespace; the
mapping from path to id is the contract every later stage relies on.
"""
import argparse
import logging
import sys
from dataclasses import dataclass
from typing import Optional

import breakdown_paths


logger = logging.getLogger(__name__)


def slug(name):
    """Structural names may carry dots (`attn.c_proj`); ids use path segments."""
    return str(name).strip().replace(".", "/")


@dataclass(frozen=True)
class WalkContext:
    parent_id: str
    source_path: str
    instance_indices: list
    repeated: bool
    invocation_count: Optional[int] = None


@dataclass(frozen=True)
class GroupObservations:
    all_observed: list
    declared_by_group: dict
    by_group_type: dict
    invocations_by_group: dict


class IndexBuilder:
    def __init__(self, namespace):
        self.namespace = namespace.rstrip("/")
        self.nodes = []
        self.by_id = {}

    def add(self, node_id, **fields):
        if node_id in self.by_id:
            # Two distinct structural nodes collapsing onto one id would silently
            # merge their metrics. Fail instead of picking a winner.
            raise breakdown_paths.ConversionError(
                f"duplicate node_id {node_id!r}\n"
                f"  first : {self.by_id[node_id]['source_path']}\n"
                f"  second: {fields.get('source_path')}\n"
                "Fix the namespace derivation; never merge distinct structural nodes."
            )
        entry = {"node_id": node_id, **fields}
        self.by_id[node_id] = entry
        self.nodes.append(entry)
        return entry

    def walk(self, node, context):
        """Emit one entry per structural node, depth first, in declaration order."""
        name = node.get("name")
        if not name:
            raise breakdown_paths.ConversionError(
                f"structural node without a name at {context.source_path}"
            )
        node_id = f"{context.parent_id}/{slug(name)}"
        path = f"{context.source_path}.{name}"
        children = node.get("children") or []
        op_indices = node.get("op_indices")

        if children and op_indices:
            # A container that also owns kernels makes `aggregate` ambiguous:
            # its own ops would be counted both directly and via descendants.
            raise breakdown_paths.ConversionError(
                f"{path} declares both children and op_indices; "
                "a node is either a container or a leaf"
            )

        if children:
            kind, scope = "module", "aggregate"
        elif context.repeated:
            kind, scope = "op", "all_observed_instances"
        else:
            kind, scope = "op", "single_instance"

        entry = self.add(
            node_id,
            semantic_key=str(name),
            node_kind=kind,
            metric_scope=scope,
            name=str(name),
            semantic=node.get("semantic") or "",
            code_ref=node.get("code_ref") or "",
            instance_indices=list(context.instance_indices) if context.repeated else [],
            # Every leaf under a folded group aggregates the same invocations as the group.
            invocation_count=(context.invocation_count if context.repeated else None),
            op_indices=list(op_indices or []),
            parent_id=context.parent_id,
            source_path=path,
            child_ids=[],
        )

        for child in children:
            child_context = WalkContext(
                node_id, path, context.instance_indices, context.repeated,
                context.invocation_count,
            )
            child_id = self.walk(child, child_context)
            entry["child_ids"].append(child_id)
        return node_id


def add_stages(builder, roots, stages):
    for key, stage in stages.items():
        node = dict(stage)
        node.setdefault("name", key)
        context = WalkContext(f"{builder.namespace}/stages", "stages", [], False)
        roots["stages"].append(builder.walk(node, context))


def collect_group_observations(config):
    instances = config.get("trace_instances") or []
    all_observed = sorted({
        inst.get("model_layer_index")
        for inst in instances
        if isinstance(inst.get("model_layer_index"), int)
    })
    if not all_observed and instances:
        all_observed = list(range(len(instances)))

    architecture = config.get("architecture") or {}
    declared_by_group: dict[str, list[int]] = {}
    for group in ((architecture.get("layer_groups") or [])
                  + (architecture.get("prediction_modules") or [])):
        gtype = group.get("type")
        if gtype is None:
            continue
        idx = list(group.get("model_layer_indices") or [])
        rng = group.get("model_layer_range")
        if not idx and rng and len(rng) == 2:
            idx = list(range(rng[0], rng[1] + 1))
        declared_by_group.setdefault(gtype, []).extend(idx)

    by_group_type: dict[str, list[int]] = {}
    invocations_by_group: dict[str, int] = {}
    for inst in instances:
        gtype = inst.get("layer_group_type")
        mli = inst.get("model_layer_index")
        if gtype is None:
            continue
        invocations_by_group[gtype] = invocations_by_group.get(gtype, 0) + 1
        if isinstance(mli, int):
            by_group_type.setdefault(gtype, []).append(mli)
    return GroupObservations(
        all_observed, declared_by_group, by_group_type, invocations_by_group
    )


def add_structure(builder, key, group, group_name, observations):
    node = dict(group)
    node.setdefault("name", key)
    node["name"] = group_name
    observed = sorted(set(observations.by_group_type.get(key, observations.all_observed)))
    declared = sorted(observations.declared_by_group.get(key, []))
    stray = sorted(index for index in set(observed) if declared and index not in set(declared))
    if stray:
        suffix = "..." if len(declared) > 8 else ""
        raise breakdown_paths.ConversionError(
            f"trace instances for {key!r} observe model layer(s) {stray} that "
            f"architecture does not declare for it (declared: {declared[:8]}{suffix}). "
            "A prediction module must use its own architecture layer id, not a main layer's; "
            "fix analysis_config.json rather than rendering the module as unobserved."
        )
    unobserved = [index for index in declared if index not in set(observed)]
    invocation_count = observations.invocations_by_group.get(key) or len(observed)
    context = WalkContext(builder.namespace, "structures", observed, True, invocation_count)
    group_id = builder.walk(node, context)
    entry = builder.by_id[group_id]
    entry["instance_indices"] = list(observed)
    entry["invocation_count"] = invocation_count
    entry["repeat_count"] = len(observed)
    entry["declared_instance_indices"] = declared
    entry["unobserved_instance_indices"] = unobserved
    return group_id


def add_runtime_nodes(builder, roots, runtime_auxiliary):
    for item in runtime_auxiliary:
        name = item.get("name")
        if not name:
            raise breakdown_paths.ConversionError("runtime_auxiliary entry without a name")
        node_id = f"{builder.namespace}/runtime/{slug(name)}"
        builder.add(
            node_id,
            semantic_key=str(name),
            node_kind="runtime_auxiliary",
            metric_scope="direct",
            name=str(name),
            semantic=item.get("semantic") or "",
            code_ref=item.get("code_ref") or "",
            instance_indices=[],
            op_indices=list(item.get("op_indices") or []),
            parent_id=f"{builder.namespace}/runtime",
            source_path=f"runtime_auxiliary.{name}",
            child_ids=[],
        )
        roots["runtime_auxiliary"].append(node_id)


def build(config, namespace, group_names=None):
    group_names = group_names or {}
    builder = IndexBuilder(namespace)
    roots = {"stages": [], "layer_structure": {}, "runtime_auxiliary": []}
    add_stages(builder, roots, config.get("stages") or {})
    observations = collect_group_observations(config)
    for key, group in (config.get("structures") or {}).items():
        group_name = group_names.get(key, group.get("name") or key)
        roots["layer_structure"][key] = add_structure(
            builder, key, group, group_name, observations
        )
    add_runtime_nodes(builder, roots, config.get("runtime_auxiliary") or [])
    return builder, roots, observations.all_observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="explicit breakdown config path")
    parser.add_argument("--breakdown", required=True)
    parser.add_argument("--namespace", required=True,
                        help="id namespace, e.g. model/qwen-7b")
    parser.add_argument("--rename-group", action="append", default=[],
                        metavar="STRUCTURE_KEY=NODE_NAME",
                        help="rename a repeated group's id segment, e.g. "
                             "QWenBlock=decoder_layers. Declare it; never let the "
                             "conversion guess a role name from a class name.")
    parser.add_argument("--out", required=True)
    breakdown_paths.add_score_gate_args(parser)
    args = parser.parse_args()

    breakdown_paths.require_convertible_score(args.breakdown, args.allow_unscored,
                                              "build_node_index.py")

    group_names = {}
    for pair in args.rename_group:
        if "=" not in pair:
            raise breakdown_paths.ConversionError(
                f"--rename-group expects KEY=NAME, got {pair!r}"
            )
        key, _, value = pair.partition("=")
        group_names[key.strip()] = value.strip()

    config_path = breakdown_paths.config_or_die(args.breakdown, args.config)
    config = breakdown_paths.load_json(config_path)
    if config.get("schema_version") != 2:
        raise breakdown_paths.ConversionError(
            f"expected schema_version 2, found {config.get('schema_version')!r}"
        )

    builder, roots, observed = build(config, args.namespace, group_names)

    leaves = [n for n in builder.nodes if not n["child_ids"]]
    declared_ops = sorted({i for n in builder.nodes for i in n["op_indices"]})

    breakdown_paths.dump_json({
        "schema_version": 1,
        "id_namespace": args.namespace,
        "representative_step": config.get("representative_step"),
        "observed_instances": observed,
        "roots": roots,
        "nodes": builder.nodes,
    }, args.out)

    logger.info("WROTE %s", args.out)
    logger.info("nodes %s (%s leaves)", len(builder.nodes), len(leaves))
    logger.info("declared op_indices %s", len(declared_ops))
    logger.info("observed instances %s", len(observed))
    for kind in ("module", "op", "runtime_auxiliary"):
        count = sum(1 for n in builder.nodes if n["node_kind"] == kind)
        logger.info("  %s: %s", kind, count)
    return 0


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
