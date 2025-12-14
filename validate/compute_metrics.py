import sys
import re
from collections import defaultdict
from statistics import mean, median


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Please specify probabilistic rules')
        exit(-1)
    rules = [line.strip() for line in sys.argv[1].splitlines() if line.strip()]
    body_lens = [len(r.split(':-')[1].split(', ')) for r in rules]
    probabilities = [float(r.split(':')[0]) if ':failure' in r else 1 for r in rules]
    grouped_rules = defaultdict(list)
    for r in rules:
        grouped_rules[re.search(r'failure\(([^,]+),([^\)]+)', r).groups()].append(r)
    num_rules_per_class = {cl: len(rs) for cl, rs in grouped_rules.items()}
    print(f' --> Number of rules: {len(rules)}')
    print(f' --> Average length of body: {mean(body_lens)}')
    print(f' --> Average rule probability: {mean(probabilities)}')
    print(f' --> Median rule probability: {median(probabilities)}')
    print(f' --> Average number of rules per class: {mean(num_rules_per_class.values())}')

