import json
import os
import time
from enum import Enum
from multiprocessing.pool import ThreadPool
from typing import List, TYPE_CHECKING

from sebs.faas.system import System as FaaSSystem
from sebs.faas.function import Trigger
from sebs.experiments.experiment import Experiment
from sebs.experiments.result import Result as ExperimentResult
from sebs.experiments.config import Config as ExperimentConfig
from sebs.utils import serialize
from sebs.statistics import basic_stats, ci_tstudents, ci_le_boudec

# import cycle
if TYPE_CHECKING:
    from sebs import SeBS


class PapiExperiment(Experiment):
    def __init__(self, config: ExperimentConfig):
        super().__init__(config)

    @staticmethod
    def name() -> str:
        return "papi-experiment"

    @staticmethod
    def typename() -> str:
        return "Experiment.PapiExperiment"

    class RunType(Enum):
        WARM = 0
        COLD = 1
        BURST = 2
        SEQUENTIAL = 3

        def str(self) -> str:
            return self.name.lower()

    def prepare(self, sebs_client: "SeBS", deployment_client: FaaSSystem):

        # create benchmark instance
        settings = self.config.experiment_settings(self.name())
        self._benchmark = sebs_client.get_benchmark(
            settings["benchmark"], deployment_client, self.config
        )
        self._function = deployment_client.get_function(self._benchmark)
        # prepare benchmark input
        self._storage = deployment_client.get_storage(replace_existing=self.config.update_storage)
        self._benchmark_input = self._benchmark.prepare_input(
            storage=self._storage, size=settings["input-size"]
        )

        # add HTTP trigger
        triggers = self._function.triggers(Trigger.TriggerType.HTTP)
        if len(triggers) == 0:
            self._trigger = deployment_client.create_trigger(
                self._function, Trigger.TriggerType.HTTP
            )
        else:
            self._trigger = triggers[0]

        self._out_dir = os.path.join(sebs_client.output_dir, "papi-experiment")
        if not os.path.exists(self._out_dir):
            os.mkdir(self._out_dir)
        self._deployment_client = deployment_client
        self._sebs_client = sebs_client

    def run(self):

        settings = self.config.experiment_settings(self.name())

        # Execution on systems where memory configuration is not provided
        memory_sizes = settings["memory-sizes"]
        if len(memory_sizes) == 0:
            self.logging.info("Begin experiment")
            self.run_configuration(settings, settings["repetitions"])
        for memory in memory_sizes:
            self.logging.info(f"Begin experiment on memory size {memory}")
            self._function.config.memory = memory
            self._deployment_client.update_function(self._function, self._benchmark)
            self._sebs_client.cache_client.update_function(self._function)
            self.run_configuration(settings, settings["repetitions"], suffix=str(memory))

    def run_configuration(self, settings: dict, repetitions: int, suffix: str = ""):

        for experiment_type in settings["experiments"]:
            if experiment_type == "cold":
                self._run_configuration(
                    PapiExperiment.RunType.COLD,
                    settings,
                    settings["concurrent-invocations"],
                    repetitions,
                    suffix,
                )
            elif experiment_type == "warm":
                self._run_configuration(
                    PapiExperiment.RunType.WARM,
                    settings,
                    settings["concurrent-invocations"],
                    repetitions,
                    suffix,
                )
            elif experiment_type == "burst":
                self._run_configuration(
                    PapiExperiment.RunType.BURST,
                    settings,
                    settings["concurrent-invocations"],
                    repetitions,
                    suffix,
                )
            elif experiment_type == "sequential":
                self._run_configuration(
                    PapiExperiment.RunType.SEQUENTIAL, settings, 1, repetitions, suffix
                )
            else:
                raise RuntimeError(f"Unknown experiment type {experiment_type} for PapiExperiment!")

    def _run_configuration(
        self,
        run_type: "PapiExperiment.RunType",
        settings: dict,
        invocations: int,
        repetitions: int,
        suffix: str = "",
    ):

        # Randomize starting value to ensure that it's not the same
        # as in the previous run.
        # Otherwise we could not change anything and containers won't be killed.
        from random import randrange

        self._deployment_client.cold_start_counter = randrange(100)

        """
            Cold experiment: schedule all invocations in parallel.
        """
        file_name = (
            f"{run_type.str()}_results_{suffix}.json"
            if suffix
            else f"{run_type.str()}_results.json"
        )
        self.logging.info(f"Begin {run_type.str()} experiments")
        incorrect_executions = []
        error_executions = []
        error_count = 0
        incorrect_count = 0
        colds_count = 0
        with open(os.path.join(self._out_dir, file_name), "w") as out_f:
            samples_gathered = 0
            client_times = []
            with ThreadPool(invocations) as pool:
                result = ExperimentResult(self.config, self._deployment_client.config)
                result.begin()
                samples_generated = 0

                # Warm up container
                # For "warm" runs, we do it automatically by pruning cold results
                if run_type == PapiExperiment.RunType.SEQUENTIAL:
                    self._trigger.sync_invoke(self._benchmark_input)

                first_iteration = True
                while samples_gathered < repetitions:

                    if run_type == PapiExperiment.RunType.COLD or run_type == PapiExperiment.RunType.BURST:
                        self._deployment_client.enforce_cold_start(
                            [self._function], self._benchmark
                        )

                    time.sleep(5)

                    results = []
                    for i in range(0, invocations):
                        results.append(
                            pool.apply_async(
                                self._trigger.sync_invoke, args=(self._benchmark_input,)
                            )
                        )

                    incorrect = []
                    for res in results:
                        try:
                            ret = res.get()
                            if first_iteration:
                                continue
                            if run_type == PapiExperiment.RunType.COLD and not ret.stats.cold_start:
                                self.logging.info(f"Invocation {ret.request_id} is not cold!")
                                incorrect.append(ret)
                            elif run_type == PapiExperiment.RunType.WARM and ret.stats.cold_start:
                                self.logging.info(f"Invocation {ret.request_id} is cold!")
                            else:
                                result.add_invocation(self._function, ret)
                                colds_count += ret.stats.cold_start
                                client_times.append(ret.times.client / 1000.0)
                                samples_gathered += 1
                        except Exception as e:
                            error_count += 1
                            error_executions.append(str(e))
                    samples_generated += invocations
                    if first_iteration:
                        self.logging.info(
                            f"Processed {samples_gathered} warm-up samples, ignoring these results."
                        )
                    else:
                        self.logging.info(
                            f"Processed {samples_gathered} samples out of {repetitions},"
                            f" {error_count} errors"
                        )

                    first_iteration = False

                    if len(incorrect) > 0:
                        incorrect_executions.extend(incorrect)
                        incorrect_count += len(incorrect)

                    time.sleep(5)

                result.end()
                out_f.write(
                    serialize(
                        {
                            **json.loads(serialize(result)),
                            "statistics": {
                                "samples_generated": samples_gathered,
                                "failures": error_executions,
                                "failures_count": error_count,
                                "incorrect": incorrect_executions,
                                "incorrect_count": incorrect_count,
                                "cold_count": colds_count,
                            },
                        }
                    )
                )

    
