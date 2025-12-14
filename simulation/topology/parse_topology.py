import json
import sys
import re
import os
import subprocess


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
COMPONENT_ORDER_PATH = f'{BASE_PATH}/component_order.asp'


def read_topology(path):
    with open(path, 'r') as topology_file:
        return json.load(topology_file)

def gen_nodes_asp(topology):
    return [f'node({n["name"].lower()}, {n["templateId"]}).' for n in topology['nodes'].values()]

def rename_port_(port_name):
    return re.sub(r'^(.+)(In|Out)$', r'\2(\1)', port_name).lower()

def gen_connections_asp(topology):
    preds = []
    for c in topology['connectors'].values():
        if 'targetPort' not in c:
            continue
        pred_name = 'connector' if 'lineDashArray' in c else 'pipe'
        from_node, to_node = c['sourceNode'].lower(), c['targetNode'].lower()
        from_port, to_port = rename_port_(c['sourcePort']), rename_port_(c['targetPort'])
        preds.append(f'{pred_name}({from_node}, {from_port}, {to_node}, {to_port}).')
    return preds

def write_topology(topology, write_path):
    topology_asp = '\n'.join(gen_nodes_asp(topology)) + '\n\n' + '\n'.join(gen_connections_asp(topology))
    if write_path is None:
        print(topology)
        return
    with open(write_path, 'w') as topology_asp_file:
        return topology_asp_file.write(topology_asp)

def get_component_order(topology_filename):
    topology = read_topology(f'{BASE_PATH}/{topology_filename}')
    topology_asp_path = f'{BASE_PATH}/{topology_filename.replace(".json", ".asp")}'
    write_topology(topology, topology_asp_path)

    output = subprocess.run(['clingo', topology_asp_path, COMPONENT_ORDER_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    prev_line = None
    for line in output.stdout.split('\n'):
        if line == 'SATISFIABLE':
            succs = []
            paths = []
            for pred in prev_line.split(' '):
                pred_name, arg1, arg2 = tuple(re.split(r'\(|,|\)', pred)[:3])
                if pred_name == 'succ':
                    succs.append((arg1, arg2))
                elif pred_name == 'path':
                    paths.append((arg1, arg2))
            return succs, paths
        prev_line = line
    raise Exception('Could not read topology and generate node paths from it')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Please specify a path to the topology JSON file')
        exit(-1)
    topology_path = sys.argv[1]

    topology = read_topology(topology_path)
    write_topology(topology, None)

