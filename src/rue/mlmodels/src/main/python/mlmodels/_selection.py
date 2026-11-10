from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Selection:
    ws: Any
    run: int
    name: str
    rows: tuple

    @property
    def frame(self):
        return self.ws.runs[(self.run, self.name)].frame[list(self.rows)]

    @property
    def path(self):
        return self.ws.runs[(self.run, self.name)].path

    def between(self, start, end):
        times = self.ws.runs[(self.run, self.name)].frame["time"]
        return self._keep(lambda index: start <= str(times[index]).replace(" ", "T") < end)

    def head(self, count):
        return Selection(self.ws, self.run, self.name, self.rows[:count])

    def tail(self, count):
        return Selection(self.ws, self.run, self.name, self.rows[-count:] if count else ())

    def slice(self, start, stop=None):
        return Selection(self.ws, self.run, self.name, self.rows[start:stop])

    def filter(self, expression):
        frame = self.ws.runs[(self.run, self.name)].frame.with_row_index("__row").filter(expression)
        kept = set(frame["__row"].to_list())
        return self._keep(lambda index: index in kept)

    def __getitem__(self, key):
        if not isinstance(key, slice):
            raise TypeError(f"a selection is sliced with [start:stop] [{key}]")
        return self.slice(key.start, key.stop)

    def _keep(self, test):
        return Selection(self.ws, self.run, self.name, tuple(index for index in self.rows if test(index)))
