import json
import os

with open("config.json", "r") as f:
    config = json.load(f)

for fp_ref in config["create_on_init_fps"]:
    fp = config[fp_ref]
    if not os.path.exists(fp):
        os.makedirs(fp)