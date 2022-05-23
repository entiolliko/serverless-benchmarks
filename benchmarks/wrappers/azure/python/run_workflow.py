import json
import sys
import os
import operator

import azure.durable_functions as df

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(dir_path, os.path.pardir))

from .fsm import *


def get_var(obj, path: str):
    names = path.split(".")
    assert(len(names) > 0)

    for n in names:
        obj = obj[n]

    return obj


def set_var(obj, val, path: str):
    names = path.split(".")
    assert(len(names) > 0)

    for n in names[:-1]:
        obj = obj[n]
    obj[names[-1]] = val


def run_workflow(context: df.DurableOrchestrationContext):
    with open("definition.json") as f:
        definition = json.load(f)

    states = {n: State.deserialize(n, s)
                   for n, s in definition["states"].items()}
    current = states[definition["root"]]
    res = context.get_input()

    while current:
        if isinstance(current, Task):
            res = yield context.call_activity(current.func_name, res)
            current = states.get(current.next, None)
        elif isinstance(current, Switch):
            ops = {
                "<": operator.lt,
                "<=": operator.le,
                "==": operator.eq,
                ">=": operator.ge,
                ">": operator.gt
            }

            next = None
            for case in current.cases:
                var = get_var(res, case.var)
                op = ops[case.op]
                if op(var, case.val):
                    next = states[case.next]
                    break

            if not next and current.default:
                next = states[current.default]
            current = next
        elif isinstance(current, Map):
            array = get_var(res, current.array)
            tasks = [context.call_activity(current.func_name, e) for e in array]
            map_res = yield context.task_all(tasks)

            set_var(res, map_res, current.array)
            current = states.get(current.next, None)
        elif isinstance(current, Repeat):
            for i in range(current.count):
                res = yield context.call_activity(current.func_name, res)
            current = states.get(current.next, None)
        elif isinstance(current, Loop):
            array = get_var(res, current.array)
            for elem in array:
                yield context.call_activity(current.func_name, elem)
            current = states.get(current.next, None)
        else:
            raise ValueError(f"Undefined state: {current}")

    return res


main = df.Orchestrator.create(run_workflow)