import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
CONFUSION_MATRIX_FILE = 'confusion_matrix.csv'


def generate_plots(df, plot_all = False, save_dir = None):
    cms = {}
    cutoffs = sorted(df['cutoff'].unique()) if plot_all else [df['cutoff'].max()]
    for cutoff in cutoffs:
        df_cut = df[df['cutoff'] == cutoff].drop('cutoff', axis=1)
        cm = generate_plot(df_cut, f"cutoff = {cutoff}", f'{save_dir}/confusion_matrix_cutoff_{cutoff}.png' if save_dir else None)
        cms[cutoff] = cm
    if not save_dir:
        plt.show()

def generate_plot(df, title, save_path = None):
    classes = sorted(df['class'].unique())
    class_to_idx = {c: i for i, c in enumerate(classes)}
    true_labels = []
    pred_labels = []

    for _, row in df.iterrows():
        cls_idx = class_to_idx[row["class"]]
        TP = int(row["tp"])
        FP = int(row["fp"])

        for _ in range(TP):
            true_labels.append(cls_idx)
            pred_labels.append(cls_idx)
        other_classes = [c for c in classes if c != row["class"]]
        for i in range(FP):
            true_labels.append(class_to_idx[other_classes[i % len(other_classes)]])
            pred_labels.append(cls_idx)

    cm = confusion_matrix(true_labels, pred_labels, labels=list(range(len(classes))))
    disp = ConfusionMatrixDisplay(cm)
    disp.plot()
    plt.title(title)
    if save_path:
        plt.savefig(save_path)
    return cm

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='ConfusionMatrixSymbolic')
    data_source_group = parser.add_mutually_exclusive_group()
    data_source_group.add_argument('-m', '--mode', help='Mode for which to retrieve most recent confusion_matrix.csv')
    data_source_group.add_argument('-f', '--file', help='Path from which to read confusion matrix file')
    parser.add_argument('-a', '--all', action=argparse.BooleanOptionalAction, help='If set, generate a confusion matrix for each probability cutoff')
    parser.add_argument('-s', '--save-dir', help='If set, the directory to which to save the plot images; otherwise, display the plots')
    args = parser.parse_args()

    path = args.file if args.file else f'{DIR_PATH}/../logic/{args.mode}/{CONFUSION_MATRIX_FILE}'
    df = pd.read_csv(path)
    generate_plots(df, args.all, args.save_dir)

