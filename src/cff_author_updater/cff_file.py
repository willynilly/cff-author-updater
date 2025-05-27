from copy import deepcopy
from pathlib import Path

import yaml


class CffFile:

    def __init__(self, cff_path: Path):
        self.cff_path = cff_path
        self.load()

    def load(self, cff_path: Path | None = None):
        if cff_path is None:
            cff_path = self.cff_path

        # Check if the CFF file exists
        if not cff_path.exists():
            raise ValueError(f"{cff_path} not found.")

        # make sure the CFF file is valid
        if not self.validate():
            raise ValueError(f"Validation failed for input CFF file: {cff_path}")

        # create a dictionary from the CFF file
        with open(cff_path, "r") as f:
            self.original_cff = yaml.safe_load(f)

        self.cff = deepcopy(self.original_cff)

    @property
    def cff(self):
        return self._cff

    @cff.setter
    def cff(self, cff: dict):
        import tempfile

        is_valid_cff: bool = False
        with tempfile.NamedTemporaryFile(mode="w+", delete=True) as temp_file:
            yaml.dump(cff, temp_file, sort_keys=False)
            is_valid_cff = self.validate(cff_path=Path(temp_file.name))

        if not is_valid_cff:
            raise ValueError(f"Invalid CFF dictionary {cff}")

        self._cff = cff

    def save(self):
        with open(self.cff_path, "w") as f:
            yaml.dump(self.cff, f, sort_keys=False)

        self.validate()

    def validate(self, cff_path: Path | None = None):
        if cff_path is None:
            cff_path = self.cff_path

        import subprocess

        try:
            subprocess.run(
                ["cffconvert", "--validate", "--infile", cff_path], check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
