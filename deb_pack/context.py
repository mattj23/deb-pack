import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class Target:
    source_path: str
    target_path: str


@dataclass
class ServiceUnit:
    source_path: str


@dataclass
class Context:
    control: Dict[str, str]
    targets: List[Target]
    services: List[ServiceUnit]

    def populate(self, path: str):
        for root, folders, files in os.walk(path):
            for file in files:
                absolute = os.path.abspath(os.path.join(root, file))
                if file == "control" and os.path.split(root)[-1] == "DEBIAN":
                    with open(absolute, "r") as handle:
                        items = [x.split(":", 1) for x in handle.read().split("\n") if ":" in x]
                        values = {key.strip(): value.strip() for key, value in items}
                        self.control.update(values)

                    print("control file", absolute)
                else:
                    relative = os.path.relpath(absolute, path)
                    self.targets.append(Target(absolute, relative))

    def save(self, path: str):
        with open(path, "w") as handle:
            json.dump(asdict(self), handle, indent=2)

    def add_target(self, source, dest):
        self.targets.append(Target(source, dest))

    def add_service(self, source):
        self.services.append(ServiceUnit(source))

    def built_name(self) -> str:
        errors = []
        values = {}
        for key in ("Package", "Version", "Architecture"):
            if key not in self.control:
                errors.append(key)
            else:
                values[key] = self.control[key]
        if errors:
            raise KeyError(f"Missing the following control keys: {', '.join(errors)}")

        return "{Package}_{Version}_{Architecture}.deb".format(**values)


def create_context() -> Context:
    return Context({}, [], [])


def load_context(path: str) -> Context:
    if not os.path.exists(path):
        raise FileNotFoundError()

    with open(path, "r") as handle:
        raw = json.load(handle)

    targets = [Target(**x) for x in raw["targets"]]
    services = [ServiceUnit(**x) for x in raw["services"]]

    return Context(raw["control"], targets, services)
