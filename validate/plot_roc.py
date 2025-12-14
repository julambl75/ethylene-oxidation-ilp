import csv
import sys
import warnings
import matplotlib.pyplot as plt
from sklearn import metrics
from collections import defaultdict


warnings.filterwarnings("ignore", category=UserWarning)


# Sort items in each list according to how the first should be sorted
def together_sort(*lists):
    return tuple([list(z) for z in zip(*sorted(list(zip(*lists))))])

def compute_tpr_fpr(matrix_path, print_f=None):
    with open(matrix_path, 'r') as matrix_file:
        csv_rows = list(csv.DictReader(matrix_file))

    tps = defaultdict(lambda: defaultdict(int))
    tns = defaultdict(lambda: defaultdict(int))
    fps = defaultdict(lambda: defaultdict(int))
    fns = defaultdict(lambda: defaultdict(int))
    for row in csv_rows:
        if row['tp'] == '':
            print(f'Warning: found UNSAT for class "{row["class"]}" and cutoff {row["cutoff"]}')
            continue
        tps[row['class']][float(row['cutoff'])] += int(row['tp'])
        tns[row['class']][float(row['cutoff'])] += int(row['tn'])
        fps[row['class']][float(row['cutoff'])] += int(row['fp'])
        fns[row['class']][float(row['cutoff'])] += int(row['fn'])

    tprs = defaultdict(list)
    fprs = defaultdict(list)
    for cl in tps.keys():
        if 1 in tps[cl]:
            accuracy = (tps[cl][1] + tns[cl][1]) / (tps[cl][1] + tns[cl][1] + fps[cl][1] + fns[cl][1])
            precision = tps[cl][1] / (tps[cl][1] + fps[cl][1]) if (tps[cl][1] + fps[cl][1]) > 0 else 0
            recall = tps[cl][1] / (tps[cl][1] + fns[cl][1]) if (tps[cl][1] + fns[cl][1]) > 0 else 0
            f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
            msg = f' --> Accuracy ignoring probabilities for class "{cl}": {accuracy}'
            msg += f'\n     Precision ignoring probabilities for class "{cl}": {precision}'
            msg += f'\n     Recall ignoring probabilities for class "{cl}": {recall}'
            msg += f'\n     F1-score ignoring probabilities for class "{cl}": {f1_score}'
            print(msg)
            if print_f is not None:
                print_f.write(msg + '\n')

        for ctf in tps[cl].keys():
            if tps[cl][ctf] + fns[cl][ctf] == 0:
                print(f'Warning: skipped ctf for class "{cl}"')
                continue
            tprs[cl].append(tps[cl][ctf] / (tps[cl][ctf] + fns[cl][ctf]))
            fprs[cl].append(fps[cl][ctf] / (fps[cl][ctf] + tns[cl][ctf]))
    return tprs, fprs

def plot(tprs, fprs, save_dir=None, print_f=None):
    for cl in tprs.keys():
        auc = 1-metrics.auc(fprs[cl], tprs[cl])
        msg = f' --> AUC for class "{cl}": {auc}'
        print(msg)
        if print_f is not None:
            print_f.write(msg + '\n')

        display = metrics.RocCurveDisplay(fpr=[0] + fprs[cl] + [1], tpr=[0] + tprs[cl] + [1], roc_auc=auc, estimator_name=cl)
        display.plot()
        plt.plot([0, 1], [0, 1], 'k--', label='Random guess', color='red')
        plt.title(f'ROC Curve for "{cl}"')
        display.ax_.legend()
        if save_dir:
            plt.savefig(f'{save_dir}/{cl}.png')

    if not save_dir:
        plt.show()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Please specify a path to the confusion matrix CSV file')
        exit(-1)
    matrix_path = sys.argv[1]
    save_dir = sys.argv[2] if len(sys.argv) > 2 else None

    if len(sys.argv) > 3:
        print_dir = sys.argv[3]
        print_f = open(print_dir, 'a')
    else:
        print_f = None

    tprs, fprs = compute_tpr_fpr(matrix_path, print_f)
    plot(tprs, fprs, save_dir, print_f)

    if print_f is not None:
        print_f.close()

