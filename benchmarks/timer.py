from collections import deque
from math import ceil, sqrt
from time import time
from timeit import Timer


class SimpleTimer(Timer):
    """A simpler timer which allows to automatically measure time taken to get
    stable results based on coefficient of variation (sigma to mean ratio)"""

    REL_PRECISION = 0.015

    def auto_measure(
        self,
        max_time=20,
        min_time=0.02,
        rel_precision=REL_PRECISION,
        expected_num_of_checks=40,
    ):
        """Automatically measures time to get stable results based on
        coefficient of variation (sigma to mean ratio)

        Args:
          max_time: max time in seconds the test should finish
          min_time: min time in seconds a single set (number of iterations
            varies) should take
          rel_precision: coefficient of variation (sigma to mean ratio)
          expected_num_of_checks: number of results to calculate variation for
        """
        ts = time()
        ts_finish_by = ts + max_time
        std_deviation_to_mean_ratio = rel_precision / 2
        i = 1
        while True:
            time_taken = self.timeit(ceil(i))
            if time_taken >= min_time:
                number_of_iterations = ceil(i)
                break

            if min_time / time_taken > 100:
                i *= 16.18
            else:
                i *= 1.618

        left_time = max(0.0, ts_finish_by - time())

        checks = min(ceil(left_time / time_taken), expected_num_of_checks)
        if checks < 4:
            raise Exception(
                f"one run for {number_of_iterations} takes {time_taken}, "
                f"max_time should allow for at least 5 runs"
            )

        times = deque((time_taken,), maxlen=checks)
        for i in range(checks - 1):
            times.append(self.timeit(number_of_iterations))

        while True:
            mean = sum(times) / checks
            std_deviation = sqrt(
                sum(d * d for d in (mean - t for t in times)) / checks
            )
            ratio = std_deviation / mean
            if ratio < std_deviation_to_mean_ratio:
                return number_of_iterations, mean

            if time() > ts_finish_by:
                print(
                    "failed to achieve expected precision, "
                    f"last rel_precision={ratio * 2}"
                )
                return number_of_iterations, mean

            for i in range(ceil(checks / 4)):
                times.append(self.timeit(number_of_iterations))

    @classmethod
    def get_base_time(cls):
        N = 1000000

        def f():
            for i in range(N):
                pass

        number, time_taken = cls(f).auto_measure()
        return time_taken / number / (N * 1.0)
