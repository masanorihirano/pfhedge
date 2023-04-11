import dataclasses
import pathlib
from typing import List
from typing import Optional
from typing import Sequence
from typing import cast

import pysen
from pysen import Flake8Setting
from pysen import IsortSetting
from pysen import Source
from pysen.component import ComponentBase
from pysen.manifest import Manifest
from pysen.manifest import ManifestBase


@dataclasses.dataclass
class Flake8SettingExtended(Flake8Setting):
    excludes: Optional[List[str]] = None

    @staticmethod
    def default() -> "Flake8SettingExtended":
        return cast(
            Flake8SettingExtended,
            Flake8SettingExtended(
                select=["B", "C", "E", "F", "W", "B950"],
            ).to_black_compatible(),
        )


def build(
    components: Sequence[ComponentBase], src_path: Optional[pathlib.Path]
) -> ManifestBase:
    isort_setting: IsortSetting = pysen.IsortSetting.default()
    isort_setting.force_single_line = True
    isort_setting.known_first_party = {"pfhedge"}

    isort = pysen.Isort(setting=isort_setting.to_black_compatible())

    flake8_setting = Flake8SettingExtended.default()
    flake8_setting.excludes = [
        "examples/",
        "docs/",
        ".git",
        "__pycache__",
        "build",
        "dist",
        ".venv",
    ]

    flake8 = pysen.Flake8(
        setting=flake8_setting.to_black_compatible(),
        source=Source(
            includes=["."],
            excludes=[
                "examples/",
                "docs/",
                ".git",
                "__pycache__",
                "build",
                "dist",
                ".venv",
            ],
        ),
    )

    others = [
        component
        for component in components
        if not isinstance(component, pysen.Isort)
        and not isinstance(component, pysen.Flake8)
    ]

    return Manifest([isort, flake8, *others])
