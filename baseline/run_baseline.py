import os
import sys
import argparse
import csv
import optuna
import graphviz
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from math import isnan
from sklearn import svm, tree
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier, AdaBoostClassifier
from sklearn.metrics import RocCurveDisplay, auc, precision_score, recall_score, f1_score, confusion_matrix, ConfusionMatrixDisplay
from sklearn.model_selection import RandomizedSearchCV
from sklearn.tree import DecisionTreeClassifier, export_graphviz
from collections import defaultdict

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f'{BASE_PATH}/../database')
sys.path.append(f'{BASE_PATH}/../logic')
sys.path.append(f'{BASE_PATH}/../logic/run_scripts')
sys.path.append(f'{BASE_PATH}/../validate')

from generate_task import rows_split_point, get_bucket_idx
from plot_roc import compute_tpr_fpr
from gen_validation_examples import plot_scores
from confusion_matrix import generate_plot


N_CUTOFFS = 10

NOMINAL_CL = 'nominal'

MULTI_OUT_INC_THRESH = 0.04
MULTI_OUT_INC_TOP_N = -1

PLOT_NAMES = {'SVC': 'SupportVectorMachine', 'MLPClassifier': 'MultiLayerPerceptron', 'RandomForestClassifier': 'RandomForest', 'HistGradientBoostingClassifier': 'HistGradientBoosting', 'AdaBoostClassifier': 'AdaBoost'}


def get_cutoffs(n_cutoffs):
    return [i/10 for i in range(n_cutoffs)] + [1]

def get_models():
    return {'svm': create_svm, 'mlp': create_mlp, 'random_forest': create_random_forest, 'hist_gradient': create_hist_gradient, 'ada_boost': create_ada_boost}

def create_svm(trial = None):
    # [I 2025-08-08 10:21:42,895] Trial 19 finished with value: 0.5102040816326531 and parameters: {'svc_c': 201.2751203683011, 'svc_kernel': 'poly', 'svc_degree': 4, 'svc_gamma': 'scale', 'svc_coef0': 0.6159955335847076}. Best is trial 19 with value: 0.5102040816326531.
    if not trial:
        return svm.SVC(probability=True, C=200, kernel='poly', degree=4, gamma='scale', coef0=0.62)
        # return svm.SVC(probability=True)
    C = trial.suggest_float('svc_c', 1e-3, 1e3, log=True)
    kernel = trial.suggest_categorical('svc_kernel', ['rbf', 'poly', 'sigmoid'])
    if kernel == 'poly':
        degree = trial.suggest_int('svc_degree', 2, 5)
    else:
        degree = 3  # default
    gamma = trial.suggest_categorical('svc_gamma', ['scale', 'auto'])
    coef0 = trial.suggest_float('svc_coef0', 0.0, 1.0) if kernel in ['poly', 'sigmoid'] else 0.0
    return svm.SVC(probability=True, C=C, kernel=kernel, degree=degree, gamma=gamma, coef0=coef0)

def create_mlp(trial = None):
    # [I 2025-08-08 10:23:18,631] Trial 19 finished with value: 0.35374149659863946 and parameters: {'mlp_n_layers': 2, 'mlp_layer_0_units': 55, 'mlp_layer_1_units': 72, 'mlp_activation': 'relu', 'mlp_alpha': 0.009089342798915436, 'mlp_lr_init': 0.0003788631631375107}. Best is trial 19 with value: 0.35374149659863946.
    if not trial:
        return MLPClassifier(solver='lbfgs', hidden_layer_sizes=(55, 72), activation='relu', alpha=0.009, learning_rate_init=0.0004, max_iter=300)
        # return MLPClassifier(solver='lbfgs', alpha=1e-5, hidden_layer_sizes=(5, 2))
    hidden_layer_sizes = tuple(trial.suggest_int(f'mlp_layer_{i}_units', 10, 100) for i in range(trial.suggest_int('mlp_n_layers', 1, 3)))
    activation = trial.suggest_categorical('mlp_activation', ['relu', 'tanh', 'logistic'])
    alpha = trial.suggest_float('mlp_alpha', 1e-6, 1e-2, log=True)
    learning_rate_init = trial.suggest_float('mlp_lr_init', 1e-4, 1e-1, log=True)
    return MLPClassifier(solver='lbfgs', hidden_layer_sizes=hidden_layer_sizes, activation=activation, alpha=alpha, learning_rate_init=learning_rate_init)

def create_random_forest(trial = None):
    # [I 2025-08-08 10:23:32,650] Trial 19 finished with value: 0.5469387755102041 and parameters: {'rf_n_estimators': 77, 'rf_max_depth': 11, 'rf_min_samples_split': 7, 'rf_min_samples_leaf': 4, 'rf_max_features': 'sqrt', 'rf_bootstrap': False}. Best is trial 19 with value: 0.5469387755102041.
    # [I 2025-08-08 10:48:14,484] Trial 19 finished with value: 0.580952380952381 and parameters: {'rf_n_estimators': 119, 'rf_max_depth': 18, 'rf_min_samples_split': 4, 'rf_min_samples_leaf': 3, 'rf_max_features': 'sqrt', 'rf_bootstrap': True}. Best is trial 7 with value: 0.5828571428571429.
    if not trial:
        return RandomForestClassifier(n_estimators=100, max_depth=15, min_samples_split=4, min_samples_leaf=2, max_features='sqrt', bootstrap=False)
        # return RandomForestClassifier(n_estimators=50)#, max_depth=3)
    n_estimators = trial.suggest_int('rf_n_estimators', 50, 200)
    max_depth = trial.suggest_int('rf_max_depth', 3, 20)
    min_samples_split = trial.suggest_int('rf_min_samples_split', 2, 10)
    min_samples_leaf = trial.suggest_int('rf_min_samples_leaf', 1, 5)
    max_features = trial.suggest_categorical('rf_max_features', ['sqrt', 'log2', None])
    bootstrap = trial.suggest_categorical('rf_bootstrap', [True, False])
    return RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf, max_features=max_features, bootstrap=bootstrap)

def create_hist_gradient(trial = None):
    # [I 2025-08-08 10:25:31,325] Trial 19 finished with value: 0.54421768707483 and parameters: {'hgb_learning_rate': 0.03478353339230946, 'hgb_max_iter': 164, 'hgb_max_leaf_nodes': 29, 'hgb_max_depth': 13, 'hgb_min_samples_leaf': 78, 'hgb_l2_reg': 0.8518311972065088}. Best is trial 11 with value: 0.5551020408163265.
    # [I 2025-08-08 10:49:04,860] Trial 19 finished with value: 0.5866666666666667 and parameters: {'hgb_learning_rate': 0.028337185717466528, 'hgb_max_iter': 113, 'hgb_max_leaf_nodes': 33, 'hgb_max_depth': 13, 'hgb_min_samples_leaf': 20, 'hgb_l2_reg': 0.010469754791278324}. Best is trial 14 with value: 0.5885714285714285.
    if not trial:
        return HistGradientBoostingClassifier(learning_rate=0.03, max_iter=150, max_leaf_nodes=30, max_depth=13, min_samples_leaf=20, l2_regularization=0.3)
        # return HistGradientBoostingClassifier()
    learning_rate = trial.suggest_float('hgb_learning_rate', 0.01, 0.3, log=True)
    max_iter = trial.suggest_int('hgb_max_iter', 50, 200)
    max_leaf_nodes = trial.suggest_int('hgb_max_leaf_nodes', 15, 50)
    max_depth = trial.suggest_int('hgb_max_depth', 3, 15)
    min_samples_leaf = trial.suggest_int('hgb_min_samples_leaf', 20, 100)
    l2_regularization = trial.suggest_float('hgb_l2_reg', 1e-8, 10.0, log=True)
    return HistGradientBoostingClassifier(learning_rate=learning_rate, max_iter=max_iter, max_leaf_nodes=max_leaf_nodes, max_depth=max_depth, min_samples_leaf=min_samples_leaf, l2_regularization=l2_regularization)

def create_ada_boost(trial = None):
    # [I 2025-08-08 10:31:58,609] Trial 19 finished with value: 0.5401360544217687 and parameters: {'ada_n_estimators': 86, 'ada_learning_rate': 0.21780141283856383, 'ada_base_max_depth': 4}. Best is trial 19 with value: 0.5401360544217687.
    # [I 2025-08-08 10:49:14,655] Trial 19 finished with value: 0.5714285714285714 and parameters: {'ada_n_estimators': 174, 'ada_learning_rate': 0.2644871561111227, 'ada_base_max_depth': 5}. Best is trial 16 with value: 0.5828571428571429.
    if not trial:
        return AdaBoostClassifier(n_estimators=100, learning_rate=0.24, estimator=DecisionTreeClassifier(max_depth=4))
        # return AdaBoostClassifier(n_estimators=50)
    n_estimators = trial.suggest_int('ada_n_estimators', 50, 200)
    learning_rate = trial.suggest_float('ada_learning_rate', 0.01, 1.0, log=True)
    base_estimator_max_depth = trial.suggest_int('ada_base_max_depth', 1, 5)
    base_estimator = DecisionTreeClassifier(max_depth=base_estimator_max_depth)
    return AdaBoostClassifier(n_estimators=n_estimators, learning_rate=learning_rate, estimator=base_estimator)

def process_param_to_symbolic(param):
    component, var = tuple(param.split('.'))
    component = component.lower()
    var = var.lower().replace('[', '_').replace(']', '')
    return component, f'{component}_{var}'

def prune_data_cols(data, only_components, only_parameters):
    if 'solved' in data.columns:
        del data['solved']
    cols = data.keys()
    hyperparams = [c for c in cols if not c[0].isupper()]
    process_params = [c for c in cols if c[0].isupper()]
    if only_components is not None:
        process_params = [p for p in process_params if process_param_to_symbolic(p)[0] in only_components]
    if only_parameters is not None:
        process_params = [p for p in process_params if process_param_to_symbolic(p)[1] in only_parameters]
    return data[hyperparams + process_params]

def filter_short_term(rows, short_term, short_terms=None):
    rows = rows.set_index(['sample', 'time'])
    normal_rows = rows.loc[rows.index.get_level_values(1) == short_term]
    if not short_terms:
        return normal_rows
    special_rows = []
    for p, st in short_terms.items():
        special_rows.append(rows[p].loc[rows.index.get_level_values(1) <= st])
    special_rows = pd.concat(special_rows, axis=1)
    res = normal_rows.merge(special_rows, how='outer', left_index=True, right_index=True, suffixes=('_n',''))
    res = res.loc[:, ~res.columns.str.endswith('_n')]
    return res

def save_decision_tree(model, X_train, experiments, save_path, tree_index=0):
    tree = None
    if isinstance(model, DecisionTreeClassifier):
        tree = model
    elif isinstance(model, RandomForestClassifier):
        tree = model.estimators_[tree_index]
    elif isinstance(model, AdaBoostClassifier):
        est = model.estimators_[tree_index]
        if hasattr(est, "tree_"):
            tree = est
        else:
            print('AdaBoost base estimator is not a decision tree')
    else:
        print('Unsupported model type for decsion tree generation')
    if not tree:
        return

    values = tree.tree_.value[:, 0, :]
    samples = tree.tree_.n_node_samples
    features = X_train.columns
    thresholds = tree.tree_.threshold

    node_labels = []
    for i in range(tree.tree_.node_count):
        if tree.tree_.children_left[i] == tree.tree_.children_right[i]:
            decision = "Leaf"
        else:
            decision = f"{features[tree.tree_.feature[i]]} <= {thresholds[i]:.2f}"
        proportions = np.round(values[i] / values[i].sum(), 2)
        cls_name = experiments[values[i].argmax()]
        pct = (samples[i] / samples[0]) * 100

        label = f"{decision}\n{pct:.1f}% samples\nvalue={list(proportions)}\nclass={cls_name}"
        node_labels.append(label)

    dot = export_graphviz(tree, out_file=None, feature_names=features, class_names=experiments, filled=True,
                          rounded=True, special_characters=True, impurity=False, proportion=True, label='none')

    lines = dot.splitlines()
    new_lines = []
    node_idx = 0
    for line in lines:
        if line.strip().endswith("];"):
            if "label=" in line:
                line = line.replace("label=", f'label="{node_labels[node_idx]}"')
                node_idx += 1
        new_lines.append(line)
    dot_custom = "\n".join(new_lines)

    graph = graphviz.Source(dot_custom)
    graph.format = "png"
    graph.render(filename=save_path, cleanup=True)

def plot_neural_training(learning_algorithms, mode, experiments, max_retained, only_components, only_parameters, test_split, short_term, short_terms, classification_threshold, classification_top_n, num_buckets=None, confusion_matrix_path=None, save_dir=None, remove_nans=True):
    if experiments is None:
        experiments = [f.replace('.csv', '') for f in os.listdir(f'{BASE_PATH}/../sampling/results/{mode}') if f.endswith('.csv')]
    if classification_top_n <= 0:
        classification_top_n = len(experiments)

    classes = {experiments[i]: i for i in range(len(experiments))}

    train = []
    test = []
    fuzzy_boundaries = {}
    for exp_name in experiments:
        filename = f'{BASE_PATH}/../simulation/sampling_results/{mode}/{exp_name}.csv'
        if not os.path.isfile(filename):
            print(f'Warning: file not found — {filename}')
            continue
        with open(filename, 'r') as results_csv_file:
            # Int64 allows value <NA> to present automatic column type change to float (for NaN)
            rows = pd.read_csv(results_csv_file, header=0, dtype={'sample': 'Int64', 'time': 'Int64'})
        if max_retained >= 0:
            rows = rows[rows['sample'] < max_retained]
        rows = prune_data_cols(rows, only_components, only_parameters)
        rows = filter_short_term(rows, short_term, short_terms)

        if num_buckets is not None:
            for col in rows.keys():
                if '.' in col:
                    node, var = tuple(col.split('.'))
                    for i in rows.index:
                        if not isnan(rows.at[i, col]):
                            rows.at[i, col] = get_bucket_idx(mode, fuzzy_boundaries, node, var, float(rows.at[i, col]), num_buckets)
        if remove_nans:
            rows = rows.fillna(-1) # replace with -1
        rows['y'] = classes[exp_name]
        split_idx = int(rows_split_point(len(rows), test_split))
        exp_train, exp_test = rows[:split_idx], rows[split_idx:]
        train.append(exp_train)
        test.append(exp_test)

    X_train = pd.concat(train).reset_index()
    X_test = pd.concat(test).reset_index()
    y_train = X_train.pop('y')
    y_test = X_test.pop('y')

    cutoffs = get_cutoffs(N_CUTOFFS)
    models = []
    scores_by_model = {}
    for a in learning_algorithms:
        try:
            # set this to True to run fine-tuning with optuna
            do_trial = False
            if do_trial:
                study = optuna.create_study(direction='maximize')
                study.optimize(lambda trial : get_models()[a](trial).fit(X_train, y_train).score(X_test, y_test), n_trials=20)
                continue
            model = get_models()[a]()
            model.fit(X_train, y_train)
            accuracy = model.score(X_test, y_test)

            y_pred = model.predict(X_test)
            precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            print(f'{a}: Accuracy={accuracy:.3f};Precision={precision:.3f};Recall={recall:.3f};F1={f1:.3f}')

            predictions = model.predict_proba(X_test)
            n_correct_preds = defaultdict(int)
            n_expected_preds = defaultdict(int)
            tp_fp_rows = []
            for i in range(len(predictions)):
                top_prob = None
                expected_cl = experiments[y_test[i]]
                if expected_cl == NOMINAL_CL:
                    continue
                pred_classes = []
                # important: we eliminate nominal under the assumption we know a failure has occurred
                n_included_cl = 0
                for prob, cl in sorted(((predictions[i][j], k) for k, j in classes.items() if experiments[j] != NOMINAL_CL), reverse=True):
                    if not top_prob:
                        top_prob = prob
                        n_included_cl = 1
                        pred_classes.append(cl)
                    elif n_included_cl < classification_top_n and top_prob - prob < classification_threshold:
                        n_included_cl += 1
                        if cl != NOMINAL_CL:
                            pred_classes.append(cl)
                    else:
                        break
                if expected_cl in pred_classes:
                    n_correct_preds[expected_cl] += 1
                n_expected_preds[expected_cl] += 1
                tp = int(expected_cl in pred_classes)
                fp = len(pred_classes) - tp
                tp_fp_rows.append((expected_cl, tp, fp))
            cm_df = pd.DataFrame(tp_fp_rows, columns=['class', 'tp', 'fp'])

            overall_sc = sum(n_correct_preds.values()) / sum(n_expected_preds.values()) * 100
            scores = {}
            print(f"--> Multi-output accuracy:\t{overall_sc:.1f}")
            for expected_cl, n_correct_preds_cl in n_correct_preds.items():
                sc = n_correct_preds_cl / n_expected_preds[expected_cl] * 100
                print(f"--> Accuracy for '{expected_cl}':\t{sc:.1f}")
                scores[expected_cl] = sc
            scores_by_model[a] = scores

            classes_to_keep = list(range(len(experiments) - 1))
            generate_plot(cm_df, a, f'{save_dir}/confusion_matrix_{a}.png' if save_dir else None)
            save_decision_tree(model, X_train, experiments, f'{save_dir}/decision_tree_{a}')
            models.append(model)
        except Exception as e:
            if 'contains NaN' in str(e):
                print(f'Warning: {a} does not support NaNs, skipping this model')
            else:
                raise e

    plot_scores(scores_by_model, save_dir, 'baseline_scores', False)

    if os.path.isfile(confusion_matrix_path or ''):
        symbolic_tprs, symbolic_fprs = compute_tpr_fpr(confusion_matrix_path)
    else:
        symbolic_tprs, symbolic_fprs = (None, None)

    for class_name, i in classes.items():
        if class_name not in experiments:
            continue
        try:
            #plt.rcParams.update({'font.size': 12})
            plt.figure()
            ax = plt.gca()

            default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
            if symbolic_tprs is None:
                ax.set_prop_cycle(color=default_colors[1:])
            else:
                symbolic_display = RocCurveDisplay(fpr=[0] + symbolic_fprs[class_name] + [1], tpr=[0] + symbolic_tprs[class_name] + [1], roc_auc=1-auc(symbolic_fprs[class_name], symbolic_tprs[class_name]), estimator_name='ProbFastLAS')
                symbolic_display.plot(ax=ax, linewidth=3)
            for model in models:
                y_pred_proba = model.predict_proba(X_test)[:, i]
                RocCurveDisplay.from_predictions(y_test == i, y_pred_proba, ax=plt.gca(), name=PLOT_NAMES[model.__class__.__name__])

            plt.plot([0, 1], [0, 1], 'k--')
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title(f'ROC Curve for "{class_name}"')
            plt.legend()
            #ratio = 0.55
            #xleft, xright = display.ax_.get_xlim()
            #ybottom, ytop = display.ax_.get_ylim()
            #display.ax_.set_aspect(abs((xright-xleft)/(ybottom-ytop))*ratio)

            if save_dir:
                plt.savefig(f'{save_dir}/baseline_{class_name}.png')
        except:
            print(f'Warning: unable to plot for class "{class_name}"')

    if not save_dir:
        plt.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='GenerateNeuralTraining')
    prune_data_group = parser.add_mutually_exclusive_group()
    parser.add_argument('-l', '--learning-algorithms', nargs='+', default=list(get_models().keys()), help=f'Types of neural models to use as baseline(s) — choose from: {', '.join(get_models().keys())}')
    parser.add_argument('-m', '--mode', help='Mode for which to generate examples from all experiments', required=True)
    parser.add_argument('-md', '--mode-data', help='Use data from this mode instead')
    parser.add_argument('-e', '--experiments', nargs='+', help='Experiments to generate examples from')
    prune_data_group.add_argument('-oc', '--only-components', nargs='+', help='Restrict the set of components that can be used in the context and modeb')
    prune_data_group.add_argument('-op', '--only-parameters', nargs='+', help='Restrict the set of process parameters that can be used in the context and modeb (specify them using _ to seperate components from parameters')
    parser.add_argument('-mr', '--max-retained', default=-1, help='Maxmum number of runs to retain from each experiment')
    parser.add_argument('-st', '--short-term', default=-1, help='Reference timepoint for short-term effects in dynamic mode')
    parser.add_argument('-stf', '--short-terms-path', help='Path to csv file specifying short-term timepoints for ASP-formatted process variables')
    parser.add_argument('-t', '--test-split', help='Proportion of results from each experiment to set aside as test data', required=True)
    parser.add_argument('-nb', '--num-buckets', help='Number of fuzzy buckets for experiment values (if discretizing)')
    parser.add_argument('-cth', '--classification-threshold', default=MULTI_OUT_INC_THRESH, help='For the multi-output prediction, keep the classes predicted with probability down to x percentage points less than the probability of the most likely prediction')
    parser.add_argument('-ctn', '--classification-top-n', default=MULTI_OUT_INC_TOP_N, help='For the multi-output prediction, keep up to n top predicted labels')
    parser.add_argument('-cm', '--confusion-matrix', help='Path to a confusion matrix to use as the symbolic comparison')
    parser.add_argument('-s', '--save-dir', help='If set, the directory to which to save the plot images; otherwise, display the plots')
    args = parser.parse_args()

    args.short_term = int(args.short_term)
    args.short_terms = {}
    if args.short_terms_path is not None:
        with open(args.short_terms_path, 'r') as short_terms_file:
            for row in csv.reader(short_terms_file):
                comp_var, short_term_val = tuple(row)
                args.short_terms[comp_var] = int(short_term_val)
    if args.num_buckets is not None:
        args.num_buckets = int(args.num_buckets)
    if not all([a in get_models().keys() for a in args.learning_algorithms]):
        raise Exception('Invalid choice of learning algorithms')

    mode_data = args.mode_data if args.mode_data else args.mode
    plot_neural_training(args.learning_algorithms, mode_data, args.experiments, int(args.max_retained), args.only_components, args.only_parameters, float(args.test_split), args.short_term, args.short_terms,  float(args.classification_threshold) / 100, int(args.classification_top_n), args.num_buckets, args.confusion_matrix, args.save_dir)

