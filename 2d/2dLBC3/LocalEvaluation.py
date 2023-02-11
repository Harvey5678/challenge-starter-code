import sys

sys.path.insert(0, '/build/service')
from IOU_precision_recall import main

import os.path
import glob
import argparse
import subprocess
import os
import json
from zipfile import ZipFile
import statistics
import tempfile

def evaluate(reference_manifest, user_manifest, exeRoot='/build'):
    results = {
        'reference': os.path.basename(reference_manifest),
        'user': os.path.basename(user_manifest),
        'warping_error': 10e10,
    }

    # Compute warping error evaluation
    args = [ os.path.join(exeRoot, 'warping_error'), reference_manifest, user_manifest ]
    output = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if 0 == output.returncode:
        results['warping_error'] = float(output.stdout)
    #else:
        #raise Exception(f'Error: got return code { output.returncode } from warping_error.\nstderr: { output.stderr }')
    
    # Compute Precision/Recall/IO
    priou = main.compute_all(reference_manifest, user_manifest)
    for key in priou:
        results[key] = priou[key]

    # ...other evaluation metrics
    # ...
    return results


def evaluate_files(ref, user, tmp, exeRoot='/build'):
    ref_tmp = os.path.join(tmp, 'ref')
    if not os.path.exists(ref_tmp):
        os.mkdir(ref_tmp)
    
    user_tmp = os.path.join(tmp, 'user')
    if not os.path.exists(user_tmp):
        os.mkdir(user_tmp)
    
    ref_files = parse_input_files(ref, ref_tmp)
    user_files = parse_input_files(user, user_tmp)
    print("ref_files: ", ref_files)
    print("user_files: ", user_files)

    # Make a dummy file in user_tmp
    dummy_json = {
        "header": {
            "layer number": 0
        }
    }
    dummy_file = os.path.join(user_tmp, 'Empty or Missing File')
    json.dump(dummy_json, open(dummy_file, 'w'), indent=2)

    results = []
    for ref_file in ref_files:
        eval_data = {}
        try:
            user_file = next((u for u in user_files if os.path.basename(u) == os.path.basename(ref_file)), dummy_file)
            if not user_file:
                eval_data = { 'status': f'ERROR: user result for test dataset { os.path.basename(ref_file) } not found!'}
            else:
                eval_data = evaluate(ref_file, user_file, exeRoot)
        except Exception as e:
            #eval_data = { 'status': f'ERROR: an exception occurred evaluating { os.path.basename(ref_file) }.', 'error_msg': str(e) }
            #eval_data = {'status': f'from {os.path.basename(ref_file)}moving to the next file.',
            #             'ignore this msg': str(e)}
            eval_data = {'status': f'from {os.path.basename(ref_file)}moving to the next file.',
                         'action': 'processing...'}

        results.append(eval_data)
    
    key_agg = {}
    def add_key_agg(key, value):
        if not key in key_agg:
            key_agg[key] = []
        
        key_agg[key].append(value)

    good_results = 0
    for record in results:
        if 'status' in record:
            continue

        good_results += 1
        for key in record:            
            if key == 'status':
                continue

            if key == "reference":
                add_key_agg(key, record[key])

            obj = record[key]
            if isinstance(obj, str):
                continue

            if isinstance(obj, list):
                for index, item in enumerate(obj):
                    add_key_agg(f'{ key }_{ index }', item)
            else:
                add_key_agg(key, obj)

    summary_dict = {}
    keys = ['reference']

    for key in key_agg:
        if key=='reference':
            continue
        keys.append(key)
        summary_dict[key] = statistics.mean(key_agg[key])
    
    csvdata = '\t'.join(keys) + '\n'

    record_ct = good_results
    for ir in range(0, record_ct):
        csvdata += f'{ key_agg["reference"][ir] }'

        for key in key_agg:
            if key == 'reference':
                continue

            csvdata += f'\t{ key_agg[key][ir] }'
        csvdata += '\n'
    outlist = []
    csvdata += 'averages'
    for key in summary_dict:
        csvdata += f'\t{ summary_dict[key] }'
        outlist.append(f'{summary_dict[key]}')
    
    return results, csvdata, outlist


def parse_input_files(base_file, root_dir):
    #thepath = "%s*.txt" % (base_file)
    thepath = os.path.join(base_file, '*')
    if not '.zip' in base_file:
        files = glob.glob(thepath)
        return files
    
    dirname = f'{ os.path.basename(base_file) }_files'
    
    tmp = os.path.join(root_dir, dirname)
    os.mkdir(tmp)

    files = []

    with ZipFile(base_file, 'r') as inzip:
        for item in inzip.namelist():
            inzip.extract(item, tmp)
            files.append(os.path.join(tmp, item))
    
    return files


def test_cli():
    #parser = argparse.ArgumentParser(description="Execute evaluation service")
    #parser.add_argument('--ref-data', dest='refData', type=str, required=True, help='Local path to reference ZIP or JSON')
    #parser.add_argument('--user-data', dest='userData', type=str, required=True, help='Local path to user ZIP or JSON')
    #parser.add_argument('--exe-root', dest='exeRoot', type=str, default='/build', help='Path to local exes')
    #parser.add_argument('--out', type=str, required=True, help='Path to JSON output report')

    #args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tempdir:
        results, summary, outlist = evaluate_files(sys.argv[1], sys.argv[2], tempdir, '/build')
        print(f'Local Test output:\n{ json.dumps(results, indent=2) }\nSummary:\n{ summary }')

        output_dir = sys.argv[3]
        output_result = os.path.join(output_dir, 'report.json')
        output_score = os.path.join(output_dir, 'scores.txt')

        json.dump(results, open(output_result, 'w'), indent=2)
        #print(f'Results written to |{ args.out }|')
        #print(sys.argv[1], " ", sys.argv[2], " ",sys.argv[3])
        output_scorefile = open(output_score, 'w')
        output_scorefile.write("submitted: 1\n")
        output_scorefile.write("warping_error: ")
        output_scorefile.write(outlist[0])
        output_scorefile.write("\nprecision_0: ")
        output_scorefile.write(outlist[1])
        output_scorefile.write("\nprecision_1: ")
        output_scorefile.write(outlist[2])
        output_scorefile.write("\nprecision_2: ")

        output_scorefile.write(outlist[3])
        output_scorefile.write("\nrecall_0: ")

        output_scorefile.write(outlist[4])
        output_scorefile.write("\nrecall_1: ")

        output_scorefile.write(outlist[5])
        output_scorefile.write("\nrecall_2: ")

        output_scorefile.write(outlist[6])
        output_scorefile.write("\niou: ")

        output_scorefile.write(outlist[7])
        output_scorefile.write("\nbetti_error: ")

        output_scorefile.write(outlist[8])
        output_scorefile.close()

if __name__ == "__main__":
    test_cli()
