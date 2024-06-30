import random
import os
import datetime
import numpy
from scipy.stats import burr

C = 11.652
D = 0.221
SCALE = 107.083
NUMBER_OF_DATAPOINTS = 250 
possible_values = list(range(100000, 1100001, 100000))
operators = ["+", "-", "*", "/"]

def generate_configs():
    path_to_file = "temp/temp_file.npy"
    config = {"writeFile": {}, "disc": {}, "function_input": {}, "memory": {}, "workload": {}, "network": {}}
    config["writeFile"]["path_to_file"] = path_to_file
    config["disc"]["path_to_file"] = path_to_file

    memory_use = int(burr.rvs(C, D, SCALE, size=2)[0] / 5)
    network_use = random.choice([True, False])
    workload_iterations = random.choice(possible_values)
    workload_operator  = random.choice(operators)

    config["disc"]["block_size"] = memory_use 
    config["function_input"]["output_size"] = memory_use
    config["memory"]["size_in_bytes"] = memory_use
    config["workload"]["array_size"] = memory_use 
    config["writeFile"]["block_size"] = memory_use
    config["workload"]["type"] = "float32"
    config["network"]["use"] = False 
    config["workload"]["iterations"] = workload_iterations
    config["workload"]["operator"] = workload_operator
                
    return config


size_generators = {
    'test' : 10,
    'small' : 10000,
    'large': 100000
}

def buckets_count():
    return (0, 0)

def generate_input(data_dir, size, benchmarks_bucket, input_paths, output_paths, upload_func):
    return [generate_configs() for i in range(size)]

