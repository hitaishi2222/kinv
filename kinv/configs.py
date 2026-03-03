import configparser
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, DirectoryPath
from rich import print

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
        parser = configparser.ConfigParser()
        parser.read(path)
        # opt = {section: dict(parser.items(section)) for section in parser.sections()}

        cli = parser["CLI"] if "CLI" in parser else None
        if cli is None:
            raise ValueError("Section [CLI] missing in config file!")

        # data_dir
        data_dir = Path(
            cli.get("data_dir", str(DEFAULT_CONFIG_PATH.parent))
        ).expanduser()

        # backend
        if cli["backend"] in ["CSV", "YAML", "HUML", "SQLite"]:
            backend = cli.get("backend", "CSV")
        else:
            raise ValueError("backend must be one of ['CSV', 'YAML', 'HUML', 'SQLite']")

        # currency_symbol
        sym: str = cli.get("currency_symbol", "₹")

        # currency_position (After: True, Before:False default) ex:[ 15$ or $15 ]
        currency_after = cli.get("currency_after", "false").lower() == "true"

        # date format
        def _expand_date(fmt: str) -> str:
            # Convert shortcuts like d/m/Y → %d/%m/%Y
            result = ""
            for ch in fmt:
                result += f"%{ch}" if ch.isalpha() else ch
            return result

        date_format = _expand_date(cli.get("date_format", "d/m/Y"))

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
