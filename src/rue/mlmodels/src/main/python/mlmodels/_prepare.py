from dataclasses import dataclass
from typing import Any


@dataclass
class Split:
    name: str
    frame: object
    members: list

    @property
    def paths(self):
        return [(member.path, len(member.rows)) for member in self.members]


@dataclass
class Fold:
    ws: Any
    index: int

    @property
    def training(self):
        return self.ws.splits["training"].frame

    @property
    def validation(self):
        return self.ws.splits["validation"].frame

    def record(self, **metrics):
        self.ws.folds[self.index].update(metrics)
