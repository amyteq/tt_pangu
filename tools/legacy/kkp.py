#!/usr/bin/env python

# this script is a wrapper to kaggle kernels push command, because:
# 1. Kaggle doesn't support yaml or alternative metadata json file yet,
# 2. JSON has no native support for comments!

# solution - use this python script to automate:
# 1. search kernel-metadata.yaml file in the folder to push ($1)
# 2. merge sections (base + $2), and save (override) the result to kernel-metadata.json
# 3. run original kaggle command to push the code

# syntax:
# for command: kaggle kernels push -p /path/to/your/kernel
# now use: kkp.py /path/to/your/kernel petals-to-the-metal

# references:
# https://github.com/Kaggle/kaggle-api
# https://github.com/Kaggle/kaggle-api/blob/main/docs/README.md#kernels
# https://github.com/Kaggle/kaggle-api/blob/main/docs/KernelPushRequest.md
# kaggle kernels push will update the version as long as the id is unchanged
# the slug part of the id (kernel-id) should match the title's slug (https://slugify.online/)

import yaml
import json
import os
import sys
import subprocess

def remove_keys(data, condition):
    return {k: v for k, v in data.items() if not condition(k)}

if len(sys.argv) != 3:
    print(f'''Usage: {sys.argv[0]} <folder> <key>!
folder: the folder where kernel-metadata.yaml and .ipynb files are saved, e.g. ./, kaggle/petals
   key: the key in kernel-metadata.yaml file used to generate kernel-metadata.json, e.g. model1''')
    sys.exit(1)

_, folder, key = sys.argv
name = 'kernel-metadata'
yaml_file = f'{folder}/kernel-metadata.yaml'
json_file = f'{folder}/kernel-metadata.json'

with open(yaml_file, 'r') as yaml_file:
    yaml_content = yaml.safe_load(yaml_file)
    # print(type(yaml_content), yaml_content)

if key not in yaml_content:
    raise ValueError(f'Invalid Key: ({key}) dose NOT exist in {yaml_file}!')

content = {**yaml_content['base'], **yaml_content[key]}
condition = lambda k: k.startswith('_')
json_content = remove_keys(content, condition)
# print(json_content)

with open(json_file, 'w') as kmj:
    json.dump(json_content, kmj, indent=2)

# run command: kaggle kernels push -p /path/to/your/kernel
result = subprocess.run(["kaggle", "kernels", "push", "-p", folder], capture_output=True, text=True)
if result.returncode != 0:
    print('ERROR: ', result.returncode, result.stderr)
else:
    print('SUCCESS: ', result.stdout)

if os.path.exists(json_file): os.remove(json_file)

# kaggle kernels list --user harrysun2006 --page-size 50 --sort-by dateCreated
# kaggle kernels delete (N/A)