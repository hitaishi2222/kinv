import sys
from pathlib import Path
from typing import Literal
from rich import print

from pydantic import BaseModel, DirectoryPath

import configparser

if sys.platform == "windows":
    DEFAULT_CONFIG_PATH = Path("~\\AppData\\Local\\kinv\\config.ini").expanduser()
else:
    DEFAULT_CONFIG_PATH = Path("~/.config/kinv/config.ini").expanduser()


class Settings(BaseModel):
    data_dir: DirectoryPath
    backend: Literal["CSV", "YAML", "HUML", "SQLite"]
    currency_symbol: str
    currency_after: bool
    date_format: str

    @classmethod
    def from_config_file(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Settings":
        if not path.exists():
            raise ValueError(f"config file is not found at : {path}. Run `kinv config`")
        config = configparser.ConfigParser()
        config.read(path)
        opt = {section: dict(config.items(section)) for section in config.sections()}

        cli = opt.get("CLI", None)
        if not cli:
            raise ValueError(
                "Key [/bold red]'CLI'[/bold red] not found in config file!"
            )

        # data_dir
        data_dir = cli.get("data_dir", DEFAULT_CONFIG_PATH.parent)

        # currency_symbol
        if cli.get("backend", "CSV") not in ["CSV", "YAML", "HUML", "SQLite"]:
            raise ValueError(
                "backend must be one of ['CSV', 'YAML', 'HUML', 'SQLite'] "
            )
        else:
            backend = "CSV"

        # currency_symbol
        sym: str = cli.get("currency_symbol", "₹")

        # currency_position (After: True, Before:False default) ex:[ 15$ or $15 ]
        currency_after: bool = (
            True if cli.get("currency_after", False) in ["True", "true"] else False
        )

        # date format
        def set_date_format(format: str) -> str:
            result = ""
            for char in format:
                if char.isalpha():
                    result += "%" + char
                else:
                    result += char
            return result

        date_format: str = set_date_format(cli.get("date_format", "d/m/Y"))

        return cls(
            data_dir=Path(data_dir).expanduser(),
            backend=backend,
            currency_symbol=sym,
            currency_after=currency_after,
            date_format=date_format,
        )


if __name__ == "__main__":
    sec = Settings.from_config_file(DEFAULT_CONFIG_PATH)
    print(sec)
