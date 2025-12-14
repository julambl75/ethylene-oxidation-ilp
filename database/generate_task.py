import sqlite3
import pandas as pd
import argparse
import os
import sys
import re
import itertools
import numpy as np
import csv
import zipfile
from math import log10, floor, ceil, inf
from pathlib import Path
from matplotlib import pyplot as plt
from collections import defaultdict
from sklearn.ensemble import RandomForestClassifier

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f'{BASE_PATH}/../simulation/topology')

from parse_topology import get_component_order


STATIC_MODE = 'static'
DYNAMIC_MODE = 'dynamic'

LEARN_MODE_BOTH = 0
LEARN_MODE_FAIL = 1
LEARN_MODE_TRENDS = 2

N_SIG_DIGITS = 4

NOMINAL_CLASS = 'nominal'

LOW_BUCKET = 'low'
NORMAL_BUCKET = 'normal'
HIGH_BUCKET = 'high'

FLAMMABLE_TAG = 'flammability_range'

INITIAL_ERA = 'initial'
SHORT_TERM_ERA = 'short_term'
LONG_TERM_ERA = 'long_term'

PENALTY_MULTIPLIER = 100
NOMINAL_PENALTY_MULTIPLIER = 225

SIM_TOPOLOGY_JSON = f'{BASE_PATH}/../simulation/topology/topology.json'
DB_FILE = f'{BASE_PATH}/knowledge.db'
DB_ZIP = f'{BASE_PATH}/knowledge.db.zip'


if not Path(DB_FILE).exists():
    with zipfile.ZipFile(DB_ZIP, 'r') as db_zip:
        db_zip.extract(os.path.basename(DB_FILE), path=os.path.dirname(DB_FILE))
conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

# --- DB read --- #

def get_sim_name(mode):
    return cur.execute(f'SELECT sim_name FROM SimMode WHERE name = "{mode}"').fetchone()[0]

def get_sim_nodes(mode):
    return cur.execute(f'SELECT SimComponent.name, SimComponent.type FROM SimComponent JOIN SimMode ON SimComponent.mode_id = SimMode.id WHERE SimMode.name = "{mode}"').fetchall()

def get_sim_var_values(mode, include_id = False):
    sim_var_entries = cur.execute(f'SELECT SimVar.id, SimComponent.name, SimVar.name, SimVar.unit, SimVar.default_val FROM SimVar JOIN SimComponent ON SimVar.component_id = SimComponent.id JOIN SimMode ON SimComponent.mode_id = SimMode.id WHERE SimMode.name = "{mode}"').fetchall()
    return {'.'.join([node, var]): (id, unit, default) if include_id else (unit, default)
            for (id, node, var, unit, default) in sim_var_entries}

def get_sim_var_specs(mode):
    sim_var_entries = cur.execute(f'SELECT SimComponent.name, SimVar.name, SimVar.unit, SimVar.cost FROM SimVar JOIN SimComponent on SimVar.component_id = SimComponent.id JOIN SimMode ON SimComponent.mode_id = SimMode.id WHERE SimMode.name = "{mode}"').fetchall()
    return {'.'.join([node, var]): {'unit': unit, 'cost': cost} for (node, var, unit, cost) in sim_var_entries}

def get_fuzzy_boundaries(mode, node_name, var_name):
    df = pd.read_sql(f'SELECT FromBucket.bucket_order AS from_bucket, ToBucket.bucket_order AS to_bucket, BucketBoundary.value, SimVar.default_val FROM SimVar JOIN SimComponent ON SimVar.component_id = SimComponent.id JOIN SimMode ON SimComponent.mode_id = SimMode.id JOIN BucketBoundaryGroup ON SimVar.fuzzy_group_id = BucketBoundaryGroup.id JOIN BucketBoundary ON BucketBoundaryGroup.id = BucketBoundary.group_id JOIN FuzzyBucket AS FromBucket ON BucketBoundary.from_bucket_id = FromBucket.id JOIN FuzzyBucket AS ToBucket ON BucketBoundary.to_bucket_id = ToBucket.id WHERE SimMode.name = "{mode}" AND SimComponent.name = "{node_name}" AND SimVar.name = "{var_name}" ORDER BY FromBucket.bucket_order', conn)
    # use absolute variable of default for comparison
    return [(r.from_bucket, r.to_bucket, r.value * abs(r.default_val)) for _, r in df.iterrows()]

def get_sim_experiments(mode):
    return [r[0] for r in cur.execute(f'SELECT SimExperiment.name FROM SimExperiment JOIN SimMode ON SimExperiment.mode_id = SimMode.id WHERE SimMode.name = "{mode}"').fetchall()]

def get_sim_results(mode, experiment_name):
    df = pd.read_sql(f'SELECT ExperimentRun.id, ExperimentRun.solved, ExperimentDatapoint.time, SimComponent.name AS node_name, SimVar.name AS var_name, ExperimentDatapoint.value, SimVar.unit AS unit FROM SimExperiment JOIN ExperimentRun ON SimExperiment.id = ExperimentRun.experiment_id JOIN ExperimentDatapoint ON ExperimentDatapoint.row_id = ExperimentRun.id JOIN SimVar ON ExperimentDatapoint.var_id = SimVar.id JOIN SimComponent ON SimVar.component_id = SimComponent.id JOIN SimMode ON SimExperiment.mode_id = SimMode.id AND SimComponent.mode_id = SimMode.id WHERE SimMode.name = "{mode}" AND SimExperiment.name = "{experiment_name}"', conn)
    return [([(r.time, r.node_name, r.var_name, r.value, r.unit) for _, r in row.iterrows()], bool(int(row.solved.unique()[0])))
            for _, row in df.groupby(['id', 'solved'])]

# --- DB write --- #

def add_missing_vars(mode: str, runs: list[dict[str, any]]):
    existing_components = [name for name, _ in get_sim_nodes(mode)]
    existing_variables = list(get_sim_var_specs(mode).keys())
    variables = list(list(runs[0][1].values())[0].keys())
    if all([v in existing_variables for v in variables if '.' in v]):
        return
    mode_id = cur.execute(f'SELECT id FROM SimMode WHERE name = "{mode}"').fetchone()[0]
    for variable in variables:
        if '.' not in variable:
            continue
        component, var_name = tuple(variable.split('.'))
        if component not in existing_components:
            cur.execute('INSERT INTO SimComponent (mode_id, name, type, aveva_model) VALUES (?, ?, ?, ?)', (mode_id, component, '', None))
            existing_components.append(component)
        component_id = cur.execute(f'SELECT SimComponent.id FROM SimComponent JOIN SimMode ON SimComponent.mode_id = SimMode.id WHERE SimMode.name = "{mode}" AND SimComponent.name = "{component}"').fetchone()[0]
        if variable not in existing_variables:
            cur.execute('INSERT INTO SimVar (component_id, name, unit, default_val, fuzzy_group_id) VALUES (?, ?, ?, ?, ?)', (component_id, var_name, '', '', ''))
            existing_variables.append(variable)
    conn.commit()
    raise Exception('Manual intervention required: please specify SimComponent.{type,aveva_model} and SimVar.{unit,default_val,fuzzy_group_id}')

def create_experiment(name: str, mode: str, runs: list[dict[str, any]]) -> bool:
    if len(runs) == 0:
        return True
    if cur.execute(f'SELECT * FROM SimExperiment JOIN SimMode ON SimExperiment.mode_id = SimMode.id WHERE SimExperiment.name = "{name}" AND SimMode.name = "{mode}"').fetchone() is not None:
        print(f'The experiment "{name}" has already been loaded, skipping...')
        return False
    # add missing simulation variables
    add_missing_vars(mode, runs)
    # add experiment
    mode_id = cur.execute(f'SELECT id FROM SimMode WHERE name = "{mode}"').fetchone()[0]
    cur.execute(f'INSERT INTO SimExperiment (name, mode_id) VALUES ("{name}", "{mode_id}")')
    exp_id = cur.execute(f'SELECT SimExperiment.id FROM SimExperiment JOIN SimMode ON SimExperiment.mode_id = SimMode.id WHERE SimExperiment.name = "{name}" AND SimMode.id = "{mode_id}"').fetchone()[0]
    # add experiment runs
    for solved, _ in runs:
        cur.execute(f'INSERT INTO ExperimentRun (experiment_id, solved) VALUES ({exp_id}, {solved})')
    run_ids = cur.execute(f'SELECT id FROM ExperimentRun WHERE experiment_id = "{exp_id}"').fetchall()
    # add experiment row entries
    sim_vars = get_sim_var_values(mode, True)
    datapoint_entries = []
    for i in range(len(runs)):
        run_id = run_ids[i][0]
        _, sim_run = runs[i]
        if not isinstance(list(sim_run.values())[0], dict):
            sim_run = {0: sim_run} # static mode

        for time, assignments in sim_run.items():
            for var, value in assignments.items():
                if var not in sim_vars or value == '':
                    continue
                datapoint_entries.append((time, run_id, sim_vars[var][0], value))
    cur.executemany('INSERT INTO ExperimentDatapoint (time, row_id, var_id, value) VALUES (?, ?, ?, ?)', datapoint_entries)
    conn.commit()
    return True

# --- Helpers --- #

def get_bucket_names(num_buckets: int) -> list[str]:
    if num_buckets == 3:
        return [LOW_BUCKET, NORMAL_BUCKET, HIGH_BUCKET]
    return [f'{LOW_BUCKET}{i+1}' for i in reversed(range(num_buckets//2))] + [NORMAL_BUCKET] + [f'{HIGH_BUCKET}{i+1}' for i in range(num_buckets//2)]

def get_bucket_numbers(num_buckets: int) -> list[int]:
    return [i+1 for i in range(num_buckets)]

def get_bucket_idx(mode: str, adapted_boundaries: dict[tuple[str, str], any], node: str, var: str, value: float, num_buckets: int) -> int:
    if (node, var) not in adapted_boundaries:
        var_boundaries = get_fuzzy_boundaries(mode, node, var)
        adapted_var_boundaries = adapt_bucket_boundaries(var_boundaries, num_buckets)
        adapted_boundaries[(node, var)] = adapted_var_boundaries
    else:
        adapted_var_boundaries = adapted_boundaries[(node, var)]
    bucket_id = round(pick_bucket(value, adapted_var_boundaries))
    return num_buckets // 2 + bucket_id

def adapt_bucket_boundaries(buckets: list[tuple[str, str, float]], num_buckets: int):
    if len(buckets) == num_buckets - 1:
        return buckets
    # temporary implementation for now
    bounds = [b for _, _, b in buckets]
    if num_buckets == 3:
        return [(-1, 0, (bounds[0] + bounds[1]) / 2),
                (0, 1, (bounds[2] + bounds[3]) / 2)]
    elif num_buckets == 9:
        return [(-4, -3, bounds[0]),
                (-3, -2, (bounds[0] + bounds[1]) / 2),
                (-2, -1, bounds[1]),
                (-1, 0, 3/4 * bounds[1] + 1/4 * bounds[2]),
                (0, 1, 1/4 * bounds[1] + 3/4 * bounds[2]),
                (1, 2, bounds[2]),
                (2, 3, (bounds[2] + bounds[3]) / 2),
                (3, 4, bounds[3])]
    raise Exception('Only 3, 5 and 9 buckets are supported')

def pick_bucket(value: float, buckets: list[tuple[str, str, float]]) -> int:
    # limitation: we assume that values are not centered around 0
    for from_bucket, to_bucket, boundary in buckets:
        # use absolute value for comparison
        if abs(value) < boundary:
            return from_bucket
    return buckets[-1][1]

def experiment_name_to_failure_atoms(exp_name: str) -> [str]:
    failure_atoms = []
    for fail_simulation in exp_name.split('+'):
        if '_' in fail_simulation: # not the nominal case
            fail_component, fail_cause = tuple(fail_simulation.split('_'))
            failure_atoms.append(f'failure({fail_cause}, {fail_component})')
        else:
            failure_atoms.append(NOMINAL_CLASS)
    return failure_atoms

def get_penalty(sim_results: dict[str, list], exp_name: str):
    max_num_results = 0
    for sim_result in sim_results.values():
        max_num_results = max(len(sim_result), max_num_results)
    return max_num_results // len(sim_results[exp_name])

def unique_sorted_merge(lists: list[list[any]]):
    return sorted(set(sum(lists, [])))

# --- Expert knowledge --- #

def gas_is_flammable(component, variable, value):
    return component == 'SNK1' and ((variable == 'z[C2H4O]' and value >= 0.026))# or (variable == 'z[C2H4]' and 0.0275 <= value <= 28.6))

def get_expert_tags(node: str, var: str, value: float) -> set[str]:
    tags = set()
    if gas_is_flammable(node, var, value):
        tags.add(FLAMMABLE_TAG)
    return tags

def get_all_expert_tags():
    return {FLAMMABLE_TAG}

def rows_split_point(n_rows, test_split):
    return n_rows * (1 - test_split)

def get_measures(exp_row: list[tuple[str, str, str, float, str]], mode: str, num_buckets: int, adapted_boundaries: dict[tuple[str, str], any], keep_timepoint: int = None, special_keep_timepoints: dict[str, int] = {}) -> dict[str, list[tuple[int, str, str, tuple[float, int]]]]:
    measures = defaultdict(list)
    expert_tags = set()
    for time, component, var, value, unit in exp_row:
        if keep_timepoint is not None and (time != special_keep_timepoints[f'{component}.{var}'] if f'{component}.{var}' in special_keep_timepoints else time != keep_timepoint):
            continue
        expert_tags.update(get_expert_tags(component, var, value))
        bucket_idx = get_bucket_idx(mode, adapted_boundaries, component, var, value, num_buckets)
        component = component.lower()
        var = var.lower().replace("[", "_").replace("]", "")
        kept_measure = (time, component, var, (value, bucket_idx))

        if unit == 'C':
            measures['temp'].append(kept_measure)
        elif unit == 'bar':
            measures['pressure'].append(kept_measure)
        elif unit == 'kg/s':
            measures['flowRate'].append(kept_measure)
        elif var.lower() == 'xmax':
            measures['conversion'].append(kept_measure)
        elif var.lower() == 'pos':
            measures['valvePos'].append(kept_measure)
        elif var.lower() == 'tau':
            measures['time'].append(kept_measure)
        elif var.lower().startswith('m_') or var.lower().startswith('z_'):
            match var[2:].lower():
                case 'o2': measures['concentration_o'].append(kept_measure)
                case 'c2h4': measures['concentration_e'].append(kept_measure)
                case 'c2h4o': measures['concentration_eo'].append(kept_measure)
    return measures, expert_tags

def compare_group_measures(from_measures: dict[str, list[tuple[int, str, str, tuple[float, int]]]], to_measures: dict[str, list[tuple[int, str, str, tuple[float, int]]]]) -> dict[str, list[tuple[int, str, str, tuple[float, int]]]]:
    diff_measures = defaultdict(list)
    for measure, to_measurements in to_measures.items():
        if measure not in from_measures:
            continue
        for to_time, component, var, (to_value, to_bucket_idx) in to_measurements:
            matches = [(t, val, idx) for t, c, v, (val, idx) in from_measures[measure] if c == component and v == var]
            if not matches:
                continue
            from_time, from_value, from_bucket_idx = tuple(matches[0])
            diff_value = round_to_significant_digits(round(to_value - from_value, N_SIG_DIGITS), N_SIG_DIGITS) # avoid being left with tiny values
            diff_measures[measure].append((to_time - from_time, component, var, (diff_value, to_bucket_idx - from_bucket_idx)))
    return diff_measures

def round_to_significant_digits(x, n_digits):
    if x == 0:
        return 0
    return round(x, n_digits - int(ceil(log10(abs(x)))))

def map_ranges_to_int_world(ranges, reference = None):
    mapped_ranges = {}
    for comp_var, values in ranges.items():
        min_value = max(min(values), 0.01) # avoid divide by zero when compute multiplier
        max_value = max(values)
        if reference:
            reference_key = comp_var
            if type(comp_var) is tuple: # hack to support value changes over time
                reference_key, change_word = comp_var
                comp_var = f'{reference_key}_{change_word}'
            multiplier = reference[reference_key][0]
        else:
            multiplier = 1 if min_value >= 1 else 10 ** ceil(-log10(min_value))
        mapped_ranges[comp_var] = (multiplier, floor(min_value * multiplier), ceil(max(values) * multiplier))
    return mapped_ranges

def convert_ctx_to_int(code, mapped_ranges, modebs = None):
    new_code = ''
    for line in code.split('\n'):
        match = re.match(r'^(\s+)(measured|short_term_change_[a-z]+)_(\w+)\(([\d.e-]+)(.*)', line)
        if match:
            indent, prefix, comp_var, value_str, suffix = match.groups()
            multiplier = mapped_ranges[comp_var][0]
            value_int = round(float(value_str) * multiplier)
            if value_int == 0 and prefix.startswith('short_term_change_'):
                if modebs is not None:
                    modebs.add(f'short_term_change({comp_var}, none)')
                line = f'{indent}short_term_change({comp_var}, none{suffix}'
            else:
                line = f'{indent}{prefix}_{comp_var}({value_int}{suffix}'
        new_code += line + '\n'
    return new_code

def convert_mode_arg_to_numvar(mode_arg):
    match = re.match(r'^(measured|short_term_change_[a-z]+)_(\w+)\([\d\.e-]+', mode_arg)
    if not match:
        return mode_arg
    prefix, comp_var = match.groups()
    num_var_name = comp_var
    if 'down' in mode_arg or 'up' in mode_arg: # hack to support value changes over time
        num_var_name += '_' + prefix.split('_')[-1]
    return f'{prefix}_{comp_var}(num_var({num_var_name}))'

def sign(x):
    return (x > 0) - (x < 0)
    adapted_boundaries = {}

def filter_mode_bias(preds, learn_mode):
    return [pred for pred in preds if (learn_mode == LEARN_MODE_FAIL and (pred.strip().startswith('failure(') or pred == NOMINAL_CLASS) or
                                       learn_mode == LEARN_MODE_TRENDS and not (pred.strip().startswith('failure(') or pred == NOMINAL_CLASS) or
                                       learn_mode == LEARN_MODE_BOTH)]

# --- Generate examples --- #

def gen_fastlas_examples(mode: str, sim_experiments: list[str], max_retained: int, learn_mode: int, example_params: tuple, num_buckets: int, test_split: float, fuzzy_symbols: bool = True, equi_penalty: bool = False) -> tuple[str, str, str]:
    if mode.startswith(STATIC_MODE):
        return gen_fastlas_examples_static(mode, sim_experiments, max_retained, learn_mode, example_params[3], example_params[4], num_buckets, test_split, fuzzy_symbols, equi_penalty)
    if mode.startswith(DYNAMIC_MODE):
        return gen_fastlas_examples_dynamic(mode, sim_experiments, max_retained, learn_mode, example_params, num_buckets, test_split, fuzzy_symbols, equi_penalty)
    raise Exception('Invalid mode specified')

def gen_fastlas_examples_static(mode: str, sim_experiments: list[str], max_retained: int, learn_mode: int, only_components: list[str], only_parameters: list[tuple[str, str]], num_buckets: int, test_split: float, fuzzy_symbols: bool = True, equi_penalty: bool = False) -> tuple:
    comp_links, comp_paths = get_component_order(SIM_TOPOLOGY_JSON)
    sim_results = {exp_name: get_sim_results(mode, exp_name) for exp_name in sim_experiments}
    bucket_names = get_bucket_names(num_buckets)
    all_failure_atoms = {e: experiment_name_to_failure_atoms(e) for e in sim_experiments}
    all_expert_tags = {f'expert({t})' for t in get_all_expert_tags()}

    fastlas_code = ''
    test_codes = {}
    ranges = defaultdict(set)
    modehs = set()
    modebs = set()
    adapted_boundaries = {}
    eg_idx = 0

    for exp_name in sim_experiments:
        fastlas_code += f'% Experiment: {exp_name}\n\n'
        exp_test_codes = []
        exp_results = sim_results[exp_name]
        penalty = PENALTY_MULTIPLIER * (get_penalty(sim_results, exp_name) if equi_penalty else 1)

        for i in range(len(exp_results)):
            if max_retained >= 0 and i >= max_retained:
                break
            effective_len = min(len(exp_results), max_retained) if max_retained >= 0 else len(exp_results)
            is_test = (i + 1) > rows_split_point(effective_len, test_split)
            row = exp_results[i]
            unsolved = not row[1]

            grouped_measures, expert_tags = get_measures(row[0], mode, num_buckets, adapted_boundaries)
            expert_tags = {f'expert({t})' for t in expert_tags}
            is_failure = not all([r[-1][1] == num_buckets // 2 for r in sum(grouped_measures.values(), [])])
            for _, component, var, (value, bucket_idx) in sum(grouped_measures.values(), []):
                if not fuzzy_symbols:
                    ranges[f'{component}_{var}'].add(value)
                incs = [f'measured({component}_{var}, {bucket_names[bucket_idx]})'] + list(expert_tags)
                excs = [f'measured({component}_{var}, {bucket_names[idx]})' for idx in range(num_buckets) if idx != bucket_idx] + list(all_expert_tags - expert_tags)
                (incs if unsolved else excs).append('unsolved')
                ctx_items = [f'  {f}.' for f in all_failure_atoms[exp_name]]

                ancestors = [a for a, b in comp_paths if b == component]
                for _, anc_component, anc_var, (anc_value, anc_bucket_idx) in sum(grouped_measures.values(), []):
                    if only_components is not None and anc_component not in only_components:
                        continue
                    if only_parameters is not None and (anc_component, anc_var) not in only_parameters:
                        continue
                    if anc_component in ancestors:
                        if fuzzy_symbols:
                            ctx_items.append(f'  measured({anc_component}_{anc_var}, {bucket_names[anc_bucket_idx]}).')
                        else:
                            ctx_items.append(f'  measured_{anc_component}_{anc_var}({anc_value}).')
                ctx_items = filter_mode_bias(ctx_items, learn_mode)

                if is_test:
                    exp_test_codes.append('\n'.join(ctx_items + [f'expected({expected}).' for expected in incs]))
                    continue
                fastlas_code += f'#pos(eg{eg_idx}@{penalty}, {{{", ".join(incs)}}}, {{{", ".join(excs)}}}, {{\n{"\n".join(ctx_items)}\n}}).\n\n'
                modehs.update(incs)
                modebs.update([item.strip()[:-1] for item in ctx_items])
                eg_idx += 1
        test_codes[exp_name] = exp_test_codes

    if not fuzzy_symbols:
        mapped_ranges = map_ranges_to_int_world(ranges)
        fastlas_code = convert_ctx_to_int(fastlas_code, mapped_ranges)
        fastlas_code += '\n' + '\n'.join([f'{comp_var}({mapped_ranges[comp_var][1]}..{mapped_ranges[comp_var][2]}). % multiplier: {mapped_ranges[comp_var][0]}' for comp_var, values in ranges.items()]) + '\n'
        modebs = sorted(set(map(convert_mode_arg_to_numvar, modebs)))
    fastlas_code += '\n' + '\n'.join(f'#modeh({modeh}).' for modeh in modehs)
    fastlas_code += '\n' + '\n'.join(f'#modeb({modeb}).' for modeb in modebs)
    return fastlas_code, test_codes, modehs

def get_retained_comp_params(sim_results, only_components, only_parameters, n_filter_important):
    data = []
    for exp_name, exp_results in sim_results.items():
        exp_data = []
        for run in exp_results:
            entries = defaultdict(lambda: defaultdict(float))
            for time, component, var, value, _ in run[0]:
                component = component.lower()
                var = var.lower().replace('[', '_').replace(']', '')
                if only_components and component not in only_components:
                    continue
                if only_parameters and (component, var) not in only_parameters:
                    continue
                entries[component + '.' + var][time] = value
            exp_data.append(pd.DataFrame.from_dict(entries))
        exp_data = pd.concat(exp_data)
        exp_data['y'] = exp_name
        data.append(exp_data)
    data = pd.concat(data)

    X, y = np.array_split(data.to_numpy(), [-1], axis=1)
    clf = RandomForestClassifier()
    clf.fit(X, y.ravel())

    importances = clf.feature_importances_
    importance_df = pd.DataFrame({
        'Feature': data.columns.values[:-1],
        'Importance': importances
    }).sort_values(by='Importance', ascending=False)

    if n_filter_important < 0:
        n_filter_important = len(importance_df)
    return [tuple(x.split('.', 1)) for x in importance_df['Feature'][:n_filter_important]]

def gen_fastlas_examples_dynamic(mode: str, sim_experiments: list[str], max_retained: int, learn_mode: int, example_params: tuple, num_buckets: int, test_split: float, fuzzy_symbols: bool = True, equi_penalty: bool = False) -> tuple:
    short_term_t, short_term_ts, long_term_t, only_components, only_parameters, n_filter_important = example_params
    for t in [short_term_t] + list(short_term_ts.values()):
        if long_term_t >= 0 and t >= long_term_t or t <= 0:
            raise Exception('Short term t(s) must be positive and < long term t')

    sim_results = {exp_name: get_sim_results(mode, exp_name) for exp_name in sim_experiments}
    # ignore missing experiment data
    sim_results = {e: data for e, data in sim_results.items() if data}
    sim_experiments = [e for e in sim_experiments if e in sim_results]

    retained_comp_params = get_retained_comp_params(sim_results, only_components, only_parameters, n_filter_important)
    bucket_names = get_bucket_names(num_buckets)
    all_failure_atoms = {e: experiment_name_to_failure_atoms(e) for e in sim_experiments}
    all_expert_tags = {f'expert({t})' for t in get_all_expert_tags()}

    fastlas_code = ''
    test_codes = {}
    ranges = defaultdict(list)
    diff_ranges = defaultdict(list)
    modehs = set()
    modebs = set()
    adapted_boundaries = {}
    nominal_eg_idxs = []
    eg_idx = 0
    for exp_name in sim_experiments:
        fastlas_code += f'% Experiment: {exp_name}\n\n'
        exp_test_codes = []
        exp_results = sim_results[exp_name]
        penalty_multiplier = PENALTY_MULTIPLIER if '_' in exp_name else NOMINAL_PENALTY_MULTIPLIER
        penalty = penalty_multiplier * (get_penalty(sim_results, exp_name) if equi_penalty else 1)

        for i in range(len(exp_results)):
            if max_retained >= 0 and i >= max_retained:
                break
            effective_len = min(len(exp_results), max_retained) if max_retained >= 0 else len(exp_results)
            is_test = (i + 1) > rows_split_point(effective_len, test_split) and len(exp_results) > 1

            row = exp_results[i]

            unsolved = not row[1]
            timepoints = {t for t, _, _, _, _ in row[0]}
            if max(timepoints) < max([short_term_t] + list(short_term_ts.values())):
                continue
            era_timepoints = {INITIAL_ERA: min(timepoints),
                              SHORT_TERM_ERA: min(t for t in timepoints if t >= short_term_t),
                              LONG_TERM_ERA: max(timepoints) if long_term_t < 0 else min(t for t in timepoints if t >= long_term_t)}

            initial_group_measures, _ = get_measures(row[0], mode, num_buckets, adapted_boundaries, keep_timepoint=era_timepoints[INITIAL_ERA])
            short_term_group_measures, _ = get_measures(row[0], mode, num_buckets, adapted_boundaries, keep_timepoint=era_timepoints[SHORT_TERM_ERA], special_keep_timepoints=short_term_ts)
            long_term_group_measures, expert_tags = get_measures(row[0], mode, num_buckets, adapted_boundaries, keep_timepoint=era_timepoints[LONG_TERM_ERA])

            expert_tags = {f'expert({t})' for t in expert_tags}
            is_failure = not all([r[-1][1] == num_buckets // 2 for r in sum(long_term_group_measures.values(), [])])
            short_term_diff_measures = compare_group_measures(initial_group_measures, short_term_group_measures)

            incs = list(expert_tags) + ([f'unsolved_from({era_timepoints[LONG_TERM_ERA]})'] if not fuzzy_symbols and unsolved else [])
            excs = list(all_expert_tags - expert_tags)
            ctx_items = []

            if is_failure:
                incs += all_failure_atoms[exp_name]
                excs += sum([f for e, f in all_failure_atoms.items() if e != exp_name], [])
            else:
                incs += all_failure_atoms[NOMINAL_CLASS]
                excs += sum([f for e, f in all_failure_atoms.items() if e != NOMINAL_CLASS], [])

            for _, component, var, (long_term_value, long_term_bucket_idx) in sum(long_term_group_measures.values(), []):
                incs.append(f'measured(long_term, {component}_{var}, {bucket_names[long_term_bucket_idx]})')
                excs += [f'measured(long_term, {component}_{var}, {bucket_names[idx]})' for idx in range(num_buckets) if idx != long_term_bucket_idx]

            for measure, measurements in short_term_diff_measures.items():
                for time_diff, component, var, (short_term_value_diff, short_term_bucket_idx_diff) in measurements:
                    if (component, var) not in retained_comp_params:
                        continue
                    short_term_value, short_term_bucket_idx = [(val, idx) for _, c, v, (val, idx) in short_term_group_measures[measure] if c == component and v == var][0]
                    if fuzzy_symbols:
                        match sign(short_term_bucket_idx_diff):
                            case -1: change_word = 'down'
                            case 1:  change_word = 'up'
                            case 0:  change_word = 'none'
                        ctx_items.append(f'  measured(short_term, {component}_{var}, {bucket_names[short_term_bucket_idx]}).')
                        ctx_items.append(f'  short_term_bucket_change({component}_{var}, {change_word}).')
                    else:
                        match sign(short_term_value_diff):
                            case -1: change_word = 'down'
                            case 1:  change_word = 'up'
                            case 0:  change_word = 'none'
                        ranges[f'{component}_{var}'].append(short_term_value)
                        ctx_items.append(f'  measured_{component}_{var}({short_term_value}).')
                        if short_term_value_diff == 0:
                            ctx_items.append(f'  short_term_change({component}_{var}, none).')
                        else:
                            ctx_items.append(f'  short_term_change_{change_word}_{component}_{var}({abs(short_term_value_diff)}).')
                            diff_ranges[(f'{component}_{var}', change_word)].append(abs(short_term_value_diff))
            incs = filter_mode_bias(incs, learn_mode)
            excs = filter_mode_bias(excs, learn_mode)

            if is_test:
                exp_test_codes.append('\n'.join(ctx_items + [f'expected({expected}).' for expected in incs]))
                continue
            fastlas_code += f'#pos(eg{eg_idx}@{penalty}, {{{", ".join(incs)}}}, {{{", ".join(excs)}}}, {{\n{"\n".join(ctx_items)}\n}}).\n\n'
            modehs.update(incs)
            modebs.update([item.strip()[:-1] for item in ctx_items])
            if exp_name == NOMINAL_CLASS:
                nominal_eg_idxs.append(eg_idx)
            eg_idx += 1
        test_codes[exp_name] = exp_test_codes

    if not fuzzy_symbols:
        mapped_ranges = map_ranges_to_int_world(ranges)
        mapped_diff_ranges = map_ranges_to_int_world(diff_ranges, mapped_ranges)
        fastlas_code = convert_ctx_to_int(fastlas_code, mapped_ranges)
        fastlas_code += '\n'.join([f'{comp_var}({min_v}..{max_v}). % multiplier: {mult}' for comp_var, (mult, min_v, max_v) in mapped_ranges.items()]) + '\n'
        fastlas_code += '\n'.join([f'{comp_var}({min_v}..{max_v}).' for comp_var, (_, min_v, max_v) in mapped_diff_ranges.items()]) + '\n'
        modebs = set(map(convert_mode_arg_to_numvar, modebs))
        for exp_name in test_codes:
            test_codes[exp_name] = [convert_ctx_to_int(code, mapped_ranges, modebs) for code in test_codes[exp_name]]
    fastlas_code += '\n' + '\n'.join(f'#modeh({modeh}).' for modeh in modehs if NOMINAL_CLASS not in modeh)
    fastlas_code += '\n' + '\n'.join(f'#modeb({modeb}).' for modeb in sorted(modebs))
    fastlas_code += '\n\n' + '\n'.join(f'#final_bias("possible_head({modeh}).").' for modeh in modehs if NOMINAL_CLASS not in modeh)
    fastlas_code += '\n\n' + '\n'.join(f'#final_bias("nominal_eg(eg{eg_idx}).").' for eg_idx in nominal_eg_idxs)
    return fastlas_code, test_codes, modehs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='GenerateBackgroundKnowledge')
    prune_data_group = parser.add_mutually_exclusive_group()
    parser.add_argument('-m', '--mode', help='Mode for which to generate examples from all experiments', required=True)
    parser.add_argument('-md', '--mode-data', help='Use data from this mode instead')
    parser.add_argument('-e', '--experiments', nargs='+', help='Experiments to generate examples from')
    parser.add_argument('-mr', '--max-retained', default=-1, help='Maxmum number of runs to retain from each experiment')
    parser.add_argument('-lm', '--learn-mode', default='both', help='Learning mode (says what should be added to the mode bias): "failure", "trends" or "both" (defaults to last case)')
    parser.add_argument('-st', '--short-term', default=-1, help='Reference timepoint for short-term effects in dynamic mode')
    parser.add_argument('-stf', '--short-terms-path', help='Path to csv file specifying short-term timepoints for ASP-formatted process variables')
    parser.add_argument('-lt', '--long-term', default=-1, help='Reference timepoint for long-term effects in dynamic mode(defaults to latest timepoint available)')
    prune_data_group.add_argument('-oc', '--only-components', nargs='+', help='Restrict the set of components that can be used in the context and modeb')
    prune_data_group.add_argument('-op', '--only-parameters', nargs='+', help='Restrict the set of process parameters that can be used in the context and modeb (specify them using _ to seperate components from parameters')
    parser.add_argument('-fi', '--n-filter-important', help='Number of most important process parameters to keep (determined using random forest, only for dynamic mode)')
    parser.add_argument('-nb', '--num-buckets', default=5, help='Number of fuzzy buckets for experiment values')
    parser.add_argument('-nu', '--numeric-fuzzy', action=argparse.BooleanOptionalAction, help='Use numbers instead of symbols for fuzzy values')
    parser.add_argument('-ep', '--equi-penalty', action=argparse.BooleanOptionalAction, help='Set example penalties such that each example has the same total weight')
    parser.add_argument('-t', '--test-split', default=0, help='Proportion of results from each experiment to set aside as test data')
    parser.add_argument('--alpha', default=10, help='Cost penalty multiplier for cost-based weak constraint')
    parser.add_argument('--beta', default=1.05, help='Coverage penalty threshold multiplier for coverage constraint')
    parser.add_argument('--num-sensors', help='Number of sensors to include in the solution specified via a bias constraint')
    parser.add_argument('-ocp', '--optimal-coverage-penalty', help='Optimal coverage penalty obtained from step 1 of cost optimization')
    parser.add_argument('-pp', '--pretty-print', action=argparse.BooleanOptionalAction, help='Print the formatted FastLAS training code, rather than saving it')
    args = parser.parse_args()

    args.max_retained = int(args.max_retained)
    args.short_term = int(args.short_term)
    args.short_terms = {}
    args.long_term = int(args.long_term)
    args.n_filter_important = int(args.n_filter_important) if args.n_filter_important else -1
    args.num_buckets = int(args.num_buckets)
    args.test_split = float(args.test_split)
    if args.short_terms_path is not None:
        with open(args.short_terms_path, 'r') as short_terms_file:
            for row in csv.reader(short_terms_file):
                comp_var, short_term_val = tuple(row)
                args.short_terms[comp_var] = int(short_term_val)
    if args.experiments is None:
        args.experiments = get_sim_experiments(args.mode)
    if args.num_buckets % 2 == 0 or args.num_buckets < 2:
        raise Exception('The number of fuzzy buckets must be even and more than 1')
    if args.test_split < 0 or args.test_split > 1:
        raise Exception('The test split proportion should be in [0,1]')

    if args.learn_mode.lower().startswith('fail'):
        learn_mode = LEARN_MODE_FAIL
    elif args.learn_mode.lower().startswith('trend'):
        learn_mode = LEARN_MODE_TRENDS
    else:
        learn_mode = LEARN_MODE_BOTH

    if args.only_parameters is not None:
        args.only_parameters = [tuple(x for x in op.split('_',1)) for op in args.only_parameters]

    mode_data = args.mode_data if args.mode_data else args.mode
    train_code, test_codes, classes = gen_fastlas_examples(mode_data, args.experiments, args.max_retained, learn_mode, (args.short_term, args.short_terms, args.long_term, args.only_components, args.only_parameters, args.n_filter_important), args.num_buckets, args.test_split, not args.numeric_fuzzy, args.equi_penalty)

    with open(f'{BASE_PATH}/../logic/{args.mode}/bias_extra.las', 'w') as bias_extra_file:
        bias_extra_file.write('')
        if args.optimal_coverage_penalty:
            cost_alpha = int(args.alpha)
            cost_beta_scaled = int(float(args.beta) * 100)
            opt_cov_pen = int(args.optimal_coverage_penalty)
            bias_extra_file.write(f'#final_bias("optimal_coverage_pen({opt_cov_pen}).").\n')
            bias_extra_file.write(f'#final_bias(":~ cost_pen(P). [P*{cost_alpha}@0]").\n')
            bias_extra_file.write(f'#final_bias(":- optimal_coverage_pen(Po), coverage_pen(P), P*100 > Po*{cost_beta_scaled}.").')
        if args.num_sensors:
            num_sensors = int(args.num_sensors)
            bias_extra_file.write(f'#final_bias(":- not n_sensors({num_sensors}).").')

    if args.pretty_print:
        print(train_code)
    else:
        Path(f'{BASE_PATH}/../logic/{args.mode}').mkdir(parents=True, exist_ok=True)
        # train
        with open(f'{BASE_PATH}/../logic/{args.mode}/train.las', 'w') as train_file:
            train_file.write(train_code)
        # test
        test_path = f'{BASE_PATH}/../logic/{args.mode}/test'
        if os.path.exists(test_path):
            [os.remove(f'{test_path}/{f}') for f in os.listdir(test_path) if f.endswith('.las')]
        else:
            os.makedirs(test_path)
        for exp_name, example_codes in test_codes.items():
            if exp_name == NOMINAL_CLASS:
                continue
            for i in range(len(example_codes)):
                filename = f'{exp_name}:{i}.las'
                with open(f'{test_path}/{filename}', 'w') as test_file:
                    test_file.write(example_codes[i])
        with open(f'{BASE_PATH}/../logic/{args.mode}/classes.asp', 'w') as classes_file:
            for c in sorted(classes):
                classes_file.write(f'class({c}).\n')

