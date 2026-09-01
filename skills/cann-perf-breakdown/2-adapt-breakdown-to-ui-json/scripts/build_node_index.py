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
"""Walk a schema-v2 breakdown into a flat, id-stable UI node index.

Declaration order is a semantic claim, so the walk preserves it. Each node gets
one `node_id` derived from its structural path under a single namespace; the
mapping from path to id is the contract every later stage relies on.
"""
import argparse
import json
import os
import sys

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import breakdown_paths  # noqa: E402


def jload(path):
    with open(path) as handle:
        return json.load(handle)


def jdump(obj, path):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def slug(name):
    """Structural names may carry dots (`attn.c_proj`); ids use path segments."""
    return str(name).strip().replace(".", "/")


class IndexBuilder:
    def __init__(self, namespace):
        self.namespace = namespace.rstrip("/")
        self.nodes = []
        self.by_id = {}

    def add(self, node_id, **fields):
        if node_id in self.by_id:
            # Two distinct structural nodes collapsing onto one id would silently
            # merge their metrics. Fail instead of picking a winner.
            raise SystemExit(
                f"duplicate node_id {node_id!r}\n"
                f"  first : {self.by_id[node_id]['source_path']}\n"
                f"  second: {fields.get('source_path')}\n"
                "Fix the namespace derivation; never merge distinct structural nodes."
            )
        entry = {"node_id": node_id, **fields}
        self.by_id[node_id] = entry
        self.nodes.append(entry)
        return entry

    def walk(self, node, parent_id, source_path, instance_indices, repeated,
             invocation_count=None):
        """Emit one entry per structural node, depth first, in declaration order."""
        name = node.get("name")
        if not name:
            raise SystemExit(f"structural node without a name at {source_path}")
        node_id = f"{parent_id}/{slug(name)}"
        path = f"{source_path}.{name}"
        children = node.get("children") or []
        op_indices = node.get("op_indices")

        if children and op_indices:
            # A container that also owns kernels makes `aggregate` ambiguous:
            # its own ops would be counted both directly and via descendants.
            raise SystemExit(
                f"{path} declares both children and op_indices; "
                "a node is either a container or a leaf"
            )

        if children:
            kind, scope = "module", "aggregate"
        elif repeated:
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
            instance_indices=list(instance_indices) if repeated else [],
            # Every leaf under a folded group aggregates the same invocations as the group.
            invocation_count=(invocation_count if repeated else None),
            op_indices=list(op_indices or []),
            parent_id=parent_id,
            source_path=path,
            child_ids=[],
        )

        for child in children:
            child_id = self.walk(child, node_id, path, instance_indices, repeated,
                                 invocation_count)
            entry["child_ids"].append(child_id)
        return node_id


def build(config, namespace, group_names=None):
    group_names = group_names or {}
    builder = IndexBuilder(namespace)
    roots = {"stages": [], "layer_structure": {}, "runtime_auxiliary": []}

    for key, stage in (config.get("stages") or {}).items():
        node = dict(stage)
        node.setdefault("name", key)
        roots["stages"].append(
            builder.walk(node, f"{builder.namespace}/stages", "stages", [], repeated=False)
        )

    # A repeated group folds every invocation onto one representative node, so
    # its leaves aggregate matching kernels from all observed instances.
    instances = config.get("trace_instances") or []
    all_observed = sorted({
        inst.get("model_layer_index")
        for inst in instances
        if isinstance(inst.get("model_layer_index"), int)
    })
    # Invocation order is not a model layer id. When every model_layer_index is unknown,
    # preserve an empty observed layer set and carry invocation_count separately.

    # Group instances by their layer_group_type so each structure template only
    # claims the invocations that actually use it, not every observed layer.
    #
    # Layer identity and invocation count are different quantities and must not share a
    # field. For a plain decoder group they coincide (3 layers, called once each), but one
    # learned MTP module called N times has ONE layer index and N invocations -- deriving
    # the count from the index set understates it as 1 and makes an N-invocation aggregate
    # read as a single call. Keep both: distinct layer indices, and a raw invocation count.
    # What the source declares per group, independent of what ran.
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

    for key, group in (config.get("structures") or {}).items():
        node = dict(group)
        node.setdefault("name", key)
        # The breakdown names a repeated group after its source class
        # (`QWenBlock`); the report addresses it by role (`decoder_layers`).
        # Renaming must be declared, never guessed from the class name.
        node["name"] = group_names.get(key, node["name"])
        # Only the instances whose layer_group_type matches this template belong here.
        # An explicit runtime pattern is a capture partition, so a pattern with no matching
        # invocation must stay empty; inheriting all_observed would assign another pattern's
        # layers to it. The all-observed fallback exists only for legacy unsplit templates
        # whose trace instances predate layer_group_type attribution.
        is_runtime_pattern = bool(
            group.get("architecture_group_type") or group.get("runtime_pattern"))
        if key in invocations_by_group:
            group_observed = sorted(set(by_group_type.get(key, [])))
        elif is_runtime_pattern:
            group_observed = []
        else:
            group_observed = all_observed
        # Layers the source declares for this group but this capture never ran. The code is
        # the architecture truth and a one-step capture cannot shrink it, so they stay part
        # of the model and are reported as declared-not-observed rather than dropped: a
        # graph silently missing them reads as a complete model that happens to be small.
        # They carry no metrics -- `emit_ui_facts` routes zero-kernel nodes to
        # `source_only_structure`.
        # A runtime pattern does not own the learned owner's whole declared layer range.
        # Its pager may show only numeric layer ids evidenced for that pattern. Copying the
        # owner's full range into every A/B/C template manufactures duplicate coverage.
        owner_type = group.get("architecture_group_type") or key
        owner_declared = sorted(declared_by_group.get(owner_type, []))
        group_declared = [] if is_runtime_pattern else owner_declared
        # An observed index outside the group's declared set means the config filed an
        # invocation under a layer id this group does not own. Left alone it is silently
        # dropped from the pager while the layer it SHOULD have lit stays dim, so the UI
        # shows the module as never executed -- the same defect as a report claiming
        # "0 invocations", just rendered instead of printed. Refuse rather than dim it:
        # the pager is the only place the reader can see what the capture covered.
        stray = sorted(
            i for i in set(group_observed)
            if owner_declared and i not in set(owner_declared))
        if stray:
            raise SystemExit(
                f"trace instances for {key!r} observe model layer(s) {stray} that "
                f"architecture does not declare for learned owner {owner_type!r} "
                f"(declared: {owner_declared[:8]}"
                f"{'...' if len(owner_declared) > 8 else ''}). A prediction module must use "
                f"its own architecture layer id, not a main layer's; fix "
                f"analysis_config.json rather than rendering the module as unobserved."
            )
        group_unobserved = [i for i in group_declared if i not in set(group_observed)]
        group_invocations = invocations_by_group.get(key) or len(group_observed)
        group_id = builder.walk(
            node, builder.namespace, "structures", group_observed, repeated=True,
            invocation_count=group_invocations
        )
        # The folded container spans invocations, not one of them.
        builder.by_id[group_id]["instance_indices"] = list(group_observed)
        # Count invocations, not distinct layers: one MTP module called 3 times is 3.
        builder.by_id[group_id]["invocation_count"] = group_invocations
        builder.by_id[group_id]["repeat_count"] = len(group_observed)
        builder.by_id[group_id]["structure_key"] = key
        builder.by_id[group_id]["architecture_group_type"] = (
            group.get("architecture_group_type") or key)
        builder.by_id[group_id]["runtime_pattern"] = group.get("runtime_pattern")
        # Declared-but-unobserved layers fold into the group they belong to rather than
        # becoming nodes of their own. A repeated group is already the graph's device for
        # "one template, many layers", so the unrun layers are extra entries in its index:
        # the pager shows them, selecting one shows no metrics, and the declared stack stays
        # visible. Emitting one node each instead would add a top-level box per layer -- 55
        # for this model -- burying the three groups that do carry data.
        builder.by_id[group_id]["declared_instance_indices"] = group_declared
        builder.by_id[group_id]["unobserved_instance_indices"] = group_unobserved
        roots["layer_structure"][key] = group_id

    for item in (config.get("runtime_auxiliary") or []):
        name = item.get("name")
        if not name:
            raise SystemExit("runtime_auxiliary entry without a name")
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

    return builder, roots, all_observed


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
    args = parser.parse_args()

    breakdown_paths.require_breakdown_ready(
        args.breakdown, args.config, "build_node_index.py")

    group_names = {}
    for pair in args.rename_group:
        if "=" not in pair:
            raise SystemExit(f"--rename-group expects KEY=NAME, got {pair!r}")
        key, _, value = pair.partition("=")
        group_names[key.strip()] = value.strip()

    config_path = breakdown_paths.config_or_die(args.breakdown, args.config)
    config = jload(config_path)
    if config.get("schema_version") != 2:
        raise SystemExit(f"expected schema_version 2, found {config.get('schema_version')!r}")

    builder, roots, observed = build(config, args.namespace, group_names)

    leaves = [n for n in builder.nodes if not n["child_ids"]]
    declared_ops = sorted({i for n in builder.nodes for i in n["op_indices"]})

    jdump({
        "schema_version": 1,
        "id_namespace": args.namespace,
        "representative_step": config.get("representative_step"),
        "observed_instances": observed,
        "roots": roots,
        "nodes": builder.nodes,
    }, args.out)

    print(f"WROTE {args.out}")
    print(f"nodes {len(builder.nodes)} ({len(leaves)} leaves)")
    print(f"declared op_indices {len(declared_ops)}")
    print(f"observed instances {len(observed)}")
    for kind in ("module", "op", "runtime_auxiliary"):
        count = sum(1 for n in builder.nodes if n["node_kind"] == kind)
        print(f"  {kind}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
