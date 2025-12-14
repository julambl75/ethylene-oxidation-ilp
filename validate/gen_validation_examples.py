import argparse
import re
import os
import sys
import csv
import subprocess
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f'{BASE_PATH}/../database')

from generate_task import get_sim_results, rows_split_point, round_to_significant_digits, map_ranges_to_int_world, sign, N_SIG_DIGITS, NOMINAL_CLASS


HELPER_ASP_CODE = '#show identified/3.'

MAX_SCORE = 100

GRAY = color_start = np.array([0.8, 0.8, 0.8])
BLUE = color_end = np.array([0.2, 0.4, 0.6])


def read_str_int_csv(path):
    assignments = {}
    if path is not None:
        with open(path, 'r') as f:
            for row in csv.reader(f):
                k, v = tuple(row)
                assignments[k] = int(v)
    return assignments

def get_multipliers(train_results):
    ranges = defaultdict(set)
    for sim_result, _ in train_results:
        for _, component, var, val, _ in sim_result:
            ranges[(component, var)].add(val)
    return defaultdict(lambda: 1, {k: m for k, (m, _, _) in map_ranges_to_int_world(ranges).items()})

def score(classes_by_score_sum, expected_class):
    nominator = 0
    if not classes_by_score_sum:
        return nominator
    for sample in classes_by_score_sum:
        _, classes = sample[0]
        if expected_class in classes:
            nominator += 1 / len(classes)
    return nominator / len(classes_by_score_sum) * MAX_SCORE

def split_results(mode, experiment, max_retained, test_split):
    sim_results = get_sim_results(mode, experiment)
    effective_len = min(len(sim_results), max_retained) if max_retained >= 0 else len(sim_results)
    split_idx = int(rows_split_point(effective_len, test_split)) + 1
    train_results = sim_results[:split_idx]
    test_results = sim_results[split_idx:]
    return train_results, test_results

def gen_asp_code(identify_rules, sim_result, short_term, short_terms, multipliers):
    initial_state = {(component, var): val for t, component, var, val, _ in sim_result if t == 0}
    ground_truth = []
    for t, component, var, val, _ in sim_result:
        if f'{component}.{var}' in short_terms:
            if short_terms[f'{component}.{var}'] != t:
                continue
        elif short_term != t:
            continue

        component_symb = component.lower()
        var_symb = var.lower().replace('[', '_').replace(']', '')
        short_term_value_diff = round_to_significant_digits(round(val - initial_state[(component, var)], N_SIG_DIGITS), N_SIG_DIGITS) # avoid being left with tiny values

        multiplier = multipliers[(component, var)]
        val = round(val * multiplier)
        short_term_value_diff = round(short_term_value_diff * multiplier)

        ground_truth.append(f'measured_{component_symb}_{var_symb}({val}).')
        match sign(short_term_value_diff):
            case -1: change_word = 'down'
            case 1:  change_word = 'up'
            case 0:  change_word = 'none'
        if short_term_value_diff == 0:
            ground_truth.append(f'short_term_change({component_symb}_{var_symb}, none).')
            ground_truth += [f'short_term_change_{w}_{component_symb}_{var_symb}(0).' for w in {'down', 'up'} - {change_word}]
        else:
            ground_truth.append(f'short_term_change_{change_word}_{component_symb}_{var_symb}({abs(short_term_value_diff)}).')

    return '\n'.join(identify_rules) + '\n\n' + '\n'.join(ground_truth) + '\n\n' + HELPER_ASP_CODE

def plot_scores(scores_by_source, save_dir = None, save_prefix = None, show_plots = True):
    for source, scores in scores_by_source.items():
        classes, values = list(zip(*sorted(scores.items())))

        values = np.array(values)
        colors = [GRAY + val * (BLUE - GRAY) for val in values / MAX_SCORE]

        fig, ax = plt.subplots()
        bars = ax.barh(classes, values, color=colors)
        ax.bar_label(bars, labels=[int(round(v, 0)) for v in values], padding=8)
        ax.set_xlim(right=115)
        ax.set_xlabel('Score')
        ax.set_title(source)
        fig.tight_layout()

        if save_dir:
            filename = f'{save_dir}/{save_prefix if save_prefix else ""}'
            if source:
                filename += ('_' if save_prefix else '') + f'{source}.png'
            plt.savefig(filename)
    if show_plots:
        plt.show()

def run_asp_codes(asp_codes, expected_class):
    overall_classes_by_score_sum = []
    for asp_code in asp_codes:
        out = subprocess.run(['clingo', '-'], input=asp_code, text=True, capture_output=True).stdout
        for line in out.split('\n'):
            if line.startswith('SATISFIABLE'):
                answer_set = prev_line.split(' ')
                break
            prev_line = line

        if max(len(x) for x in answer_set) == 0:
            continue
        predictions = []
        for identified in answer_set:
            prob_str, loc, anomaly = re.match(r'identified\((\d+),(\w+),(\w+)\)', identified).groups()
            predictions.append((int(prob_str) / 10, f'{anomaly}_{loc}'))
        predictions = sorted(predictions, reverse=True)

        score_by_class = defaultdict(int)
        classes_by_score_sum = defaultdict(list)
        for prob, cls in predictions:
            score_by_class[cls] += prob
        for cls, prob in score_by_class.items():
            classes_by_score_sum[prob].append(cls)
        overall_classes_by_score_sum.append(sorted(classes_by_score_sum.items(), reverse=True))

    sc = score(overall_classes_by_score_sum, expected_class)
    print(f"--> Accuracy for '{expected_class}':\t{sc:.1f}")
    return sc

def main(mode, classes, short_term, short_terms, max_retained, test_split, rule_paths, save_dir, save_graph_prefix, plot_score_graphs):
    scores_by_rule_path = {}
    for rules_path in rule_paths:
        print(f'\nRules from: {rules_path}')
        identify_rules = []
        scores = {}
        with open(rules_path, 'r') as f:
            for l in f.readlines():
                if ' :- ' in l:
                    prob, rest = tuple(l.strip().split('failure('))
                    prob = float(prob[:-1]) if ':' in prob else 1
                    identify_rules.append(f'identified({prob * 10:.0f},{rest}')

        for fail_class in sorted(classes):
            train_results, test_results = split_results(mode, fail_class, max_retained, test_split)
            multipliers = get_multipliers(train_results)
            asp_codes = [gen_asp_code(identify_rules, r, short_term, short_terms, multipliers) for r, _ in test_results]
            scores[fail_class] = run_asp_codes(asp_codes, fail_class)
        scores_by_rule_path[rules_path.split('/')[-1]] = scores

    plot_scores(scores_by_rule_path, save_dir, save_graph_prefix, plot_score_graphs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='GenClingo')
    parser.add_argument('-m', '--mode', help='Mode for which to generate examples from all experiments', required=True)
    parser.add_argument('-md', '--mode-data', help='Use data from this mode instead')
    parser.add_argument('-st', '--short-term', help='Reference timepoint for short-term effects in dynamic mode', required=True)
    parser.add_argument('-stf', '--short-terms-path', help='Path to csv file specifying short-term timepoints for ASP-formatted process variables')
    parser.add_argument('-mr', '--max-retained', default=-1, help='Maxmum number of runs to retain from each experiment')
    parser.add_argument('-t', '--test-split', default=0, help='Proportion of results from each experiment to set aside as test data', required=True)
    parser.add_argument('-r', '--rule-paths', nargs='+', help='Path to file containing FastLAS ouput rules', required=True)
    parser.add_argument('-d', '--save-dir', help='Path at which to save score plots')
    parser.add_argument('-p', '--save-graph-prefix', help='Prefix to use when saving score plots')
    parser.add_argument('-ng', '--no-graphs', action=argparse.BooleanOptionalAction, help='Do not display score plots')
    parser.add_argument('-e', '--experiments', nargs='+', help='Experiments for which rules were generated')
    # hack to avoid having to deal with multi-value argument removal in bash
    parser.add_argument('-lm', nargs='+', help=argparse.SUPPRESS)
    parser.add_argument('-nu', nargs='*', help=argparse.SUPPRESS)
    parser.add_argument('-oc', nargs='+', help=argparse.SUPPRESS)
    parser.add_argument('-op', nargs='+', help=argparse.SUPPRESS)
    parser.add_argument('-nb', nargs='+', help=argparse.SUPPRESS)

    args = parser.parse_args()
    short_terms = read_str_int_csv(args.short_terms_path)

    classes = set(args.experiments) - {NOMINAL_CLASS}

    mode_data = args.mode_data if args.mode_data else args.mode
    main(mode_data, classes, int(args.short_term), short_terms, int(args.max_retained), float(args.test_split), args.rule_paths, args.save_dir, args.save_graph_prefix, not args.no_graphs)

