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
"""AI Core counter metrics: correct key names, time weighting, and null vs zero."""
import os
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)
import attribute_kernels as ak  # noqa: E402
import emit_ui_facts as ef  # noqa: E402


def kernel(duration=10.0, aicore=None, mac=None, mte2=None, cycles=None,
           block=None, mix=None, aiv_us=None, aiv_cycles=None, op_type="MatMul"):
    row = {"duration_us": duration, "op_type": op_type,
           "input_shapes": [], "output_shapes": []}
    for key, value in (("aicore_time_us", aicore), ("aic_mac_ratio", mac),
                       ("aic_mte2_ratio", mte2), ("aic_total_cycles", cycles),
                       ("block_dim", block), ("mix_block_dim", mix),
                       ("aiv_time_us", aiv_us), ("aiv_total_cycles", aiv_cycles)):
        if value is not None:
            row[key] = value
    return row


def test_reads_prefixed_csv_key_names():
    """The CSV spells these `aic_mac_ratio`/`aic_mte2_ratio`.

    Looking up the unprefixed `mac_ratio` matched nothing and reported every node's cube
    behaviour as unavailable while the data sat in the file.
    """
    rows = [kernel(aicore=100.0, mac=0.5, mte2=0.3)]
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0)
    assert metrics["mac_ratio"] == pytest.approx(0.5)
    assert metrics["mte2_ratio"] == pytest.approx(0.3)
    assert metrics["aicore_time_us"] == pytest.approx(100.0)


def test_ratios_are_time_weighted_not_flat_mean():
    """A 1 us kernel must not weigh as much as a 99 us one.

    Flat mean of 1.0 and 0.0 is 0.50; weighted by the cube time the ratios describe it is 0.01.
    """
    rows = [kernel(aicore=1.0, mac=1.0), kernel(aicore=99.0, mac=0.0)]
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0)
    assert metrics["mac_ratio"] == pytest.approx(0.01, abs=1e-6)


def test_absent_counters_report_null_not_zero():
    """Null means the capture did not measure it; 0.0 would read as a real cube-idle finding."""
    metrics = ef.node_metrics([kernel()], 376.0, 2, 1000.0)
    assert metrics["aicore_time_us"] is None
    assert metrics["mac_ratio"] is None
    assert metrics["cube_utilization_pct"] is None
    assert metrics["counter_coverage"]["kernels_with_counters"] == 0


def test_partial_counter_coverage_is_reported():
    """Mixed coverage must be visible, or a ratio from 1 of 50 kernels looks node-wide."""
    rows = [kernel(aicore=10.0, mac=0.5), kernel(), kernel()]
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0)
    coverage = metrics["counter_coverage"]
    assert (coverage["kernels_with_counters"], coverage["kernels_total"]) == (1, 3)
    assert coverage["pct"] == pytest.approx(33.33, abs=0.01)


def test_cycle_time_divides_by_core_count():
    """aic_total_cycles is core-summed, so cycles/freq alone yields core-us.

    24 cores x 1850 MHz x 100 us = 4,440,000 cycles must imply 100 us, not 2400 us. This is
    the regression that made every module's cycle time read ~22x its counter time.
    """
    rows = [kernel(aicore=100.0, cycles=1850 * 24 * 100, block=24)]
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0, freq_mhz=1850.0)
    assert metrics["aicore_cycle_time_us"] == pytest.approx(100.0, rel=1e-4)
    # The whole point: the two independent routes to the same quantity agree.
    assert metrics["aicore_cycle_time_us"] == pytest.approx(metrics["aicore_time_us"], rel=1e-3)


def test_vector_cycle_time_prefers_mix_block_dim():
    rows = [kernel(aiv_us=100.0, aiv_cycles=1850 * 48 * 100, block=24, mix=48)]
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0, freq_mhz=1850.0)
    assert metrics["aiv_cycle_time_us"] == pytest.approx(100.0, rel=1e-4)


def test_inconsistent_mixed_kernel_core_divisor_nulls_cycle_time():
    """Do not derive durations when profiler block dims contradict its own counters."""
    rows = [kernel(
        aicore=10.046,
        cycles=331_490,
        block=8,
        mix=16,
        aiv_us=5.739,
        aiv_cycles=9_469,
        op_type="FusedInferAttentionScore",
    )]

    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0, freq_mhz=1650.0)

    assert metrics["aic_total_cycles"] == 331_490
    assert metrics["aiv_total_cycles"] == 9_469
    assert metrics["aicore_cycle_time_us"] is None
    assert metrics["aiv_cycle_time_us"] is None


def test_no_clock_nulls_derived_but_keeps_raw_cycles():
    """Raw cycle counts need no clock; the derived durations must not be invented from one."""
    rows = [kernel(aicore=100.0, cycles=4_440_000, block=24)]
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0, freq_mhz=None)
    assert metrics["aic_total_cycles"] == pytest.approx(4_440_000)
    assert metrics["aicore_cycle_time_us"] is None


def test_aicore_time_pct_is_share_of_wall():
    rows = [kernel(duration=200.0, aicore=100.0)]
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0)
    assert metrics["aicore_time_pct"] == pytest.approx(50.0)


def test_every_counter_key_is_written_even_when_null():
    """A missing key and a null value are different claims; the UI depends on the shape."""
    metrics = ef.node_metrics([kernel()], 376.0, 2, 1000.0)
    for key in ("aicore_time_us", "aiv_time_us", "aicore_time_pct", "mac_ratio",
                "mte2_ratio", "mte1_ratio", "scalar_ratio", "fixpipe_ratio", "vec_ratio",
                "aiv_mte2_ratio", "cube_utilization_pct", "aic_total_cycles",
                "aiv_total_cycles", "aicore_cycle_time_us", "aiv_cycle_time_us",
                "counter_coverage"):
        assert key in metrics, f"{key} must be present even when unmeasured"


def test_duplicate_collective_excluded_from_wall_but_counters_intact():
    """The duplicate guard applies to durations; it must not silently drop counter rows."""
    rows = [kernel(duration=10.0, aicore=8.0)]
    rows.append(dict(rows[0], duplicate_of=0))
    metrics = ef.node_metrics(rows, 376.0, 2, 1000.0)
    assert metrics["time_us"] == pytest.approx(10.0)


def test_counter_loader_skips_missing_file():
    """A capture profiled without counters must attribute normally, not crash."""
    assert ak.load_counters("/nonexistent/raw_ops_details.json") == {}
    assert ak.load_counters(None) == {}


def test_counter_loader_omits_absent_fields(tmp_path):
    """An omitted key means unmeasured; writing null would claim the counter read zero."""
    import json
    path = tmp_path / "raw_ops_details.json"
    path.write_text(json.dumps({"operators": [
        {"index": 0, "aicore_time_us": 12.5, "aic_mac_ratio": 0.4},
        {"index": 1, "duration_us": 3.0},
    ]}))
    counters = ak.load_counters(str(path))
    assert counters[0] == {"aicore_time_us": 12.5, "aic_mac_ratio": 0.4}
    assert 1 not in counters, "a row with no counters contributes no keys"
