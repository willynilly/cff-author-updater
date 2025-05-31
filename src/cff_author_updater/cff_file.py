from copy import deepcopy
from pathlib import Path

import yaml

from cff_author_updater.ordered_yaml_loader import OrderedYamlLoader


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
            self.original_cff = yaml.load(f, Loader=OrderedYamlLoader)

        self.cff = deepcopy(self.original_cff)

    def save(self):

        # save to a temp file first to make sure it works
        import tempfile

        is_valid_cff: bool = False
        with tempfile.NamedTemporaryFile(mode="w+", delete=True) as temp_file:
            yaml.dump(self.cff, temp_file, sort_keys=False)
            is_valid_cff, validation_errors = self.validate(
                cff_path=Path(temp_file.name)
            )

        if not is_valid_cff:
            error_message = (
                f"Invalid CFF dictionary before saving {self.cff}\n"
                + "\n".join(f"[cffconvert] {line}" for line in validation_errors)
            )
            raise ValueError(error_message)

        # now save to the original CFF file
        with open(self.cff_path, "w") as f:
            yaml.dump(self.cff, f, sort_keys=False)

        is_valid_cff, validation_errors = self.validate()
        if not is_valid_cff:
            error_message = (
                f"Invalid CFF dictionary after saving {self.cff}\n"
                + "\n".join(f"[cffconvert] {line}" for line in validation_errors)
            )
            raise ValueError(error_message)

    def validate(self, cff_path: Path | None = None) -> tuple[bool, list[str]]:
        if cff_path is None:
            cff_path = self.cff_path

        import subprocess

        try:
            result = subprocess.run(
                ["cffconvert", "--validate", "--infile", cff_path],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, []
        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr.splitlines() if e.stderr else []
            return False, stderr_output
