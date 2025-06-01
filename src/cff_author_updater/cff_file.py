from copy import deepcopy
from pathlib import Path

import yaml

from cff_author_updater.ordered_yaml_loader import OrderedYamlLoader


class CffFileValidationError(ValueError):
    def __init__(self, message: str, validation_errors: list[str]):
        super().__init__(message)

        CFFCONVERT_VALIDATION_DUPLICATE_AUTHOR_TEXT: str = (
            "Failed validating 'uniqueItems' in schema['properties']['authors']"
        )

        self.cffconvert_validation_errors = validation_errors
        self.cffconvert_validation_duplicate_errors = [
            error
            for error in self.cffconvert_validation_errors
            if CFFCONVERT_VALIDATION_DUPLICATE_AUTHOR_TEXT in error
        ]
        self.cffconvert_validation_other_errors = [
            error
            for error in self.cffconvert_validation_errors
            if CFFCONVERT_VALIDATION_DUPLICATE_AUTHOR_TEXT not in error
        ]


class CffFile:

    def __init__(self, cff_path: Path, validate: bool = True):
        self.cff_path = cff_path

        # Check if the CFF file exists
        if not self.cff_path.exists():
            raise ValueError(f"{self.cff_path} not found.")

        # create a dictionary from the CFF file
        with open(self.cff_path, "r") as f:
            self.original_cff = yaml.load(f, Loader=OrderedYamlLoader)

        self.cff = deepcopy(self.original_cff)

        if validate:
            # make sure the CFF file is valid
            is_valid_cff, validation_errors = self.validate()
            if not is_valid_cff:
                error_message = (
                    f"Invalid CFF file while loading {self.cff}\n"
                    + "\n".join(f"[cffconvert] {error}" for error in validation_errors)
                )
                raise CffFileValidationError(
                    message=error_message, validation_errors=validation_errors
                )

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
                + "\n".join(f"[cffconvert] {error}" for error in validation_errors)
            )
            raise CffFileValidationError(
                message=error_message, validation_errors=validation_errors
            )

        # now save to the original CFF file
        with open(self.cff_path, "w") as f:
            yaml.dump(self.cff, f, sort_keys=False)

        is_valid_cff, validation_errors = self.validate()
        if not is_valid_cff:
            error_message = (
                f"Invalid CFF dictionary after saving {self.cff}\n"
                + "\n".join(f"[cffconvert] {error}" for error in validation_errors)
            )
            raise CffFileValidationError(
                message=error_message, validation_errors=validation_errors
            )

    def validate(self, cff_path: Path | None = None) -> tuple[bool, list[str]]:
        if cff_path is None:
            cff_path = self.cff_path

        import subprocess

        try:
            subprocess.run(
                ["cffconvert", "--validate", "--infile", cff_path],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, []
        except subprocess.CalledProcessError as e:
            stderr_output = [e.stderr] if e.stderr else []
            return False, stderr_output
