import configparser
from pathlib import Path
from typing import List

import questionary as qy
import typer
from kinv.configs import DEFAULT_CONFIG_PATH, Settings
from kinv.modules import CSVBackend, Item, SQLiteBackend
from rapidfuzz.process import extract
from rich import print

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)


def _backend():
    """Instantiate the backend according to the current config."""
    cfg = Settings.from_config_file()
    data_dir = Path(cfg.data_dir)
    if cfg.backend == "CSV":
        data_file = data_dir / "data.csv"
        return CSVBackend.read_and_populate_data(data_dir, data_file)
    elif cfg.backend == "SQLite":
        data_file = data_dir / "data.db"
        data_file.touch()
        return SQLiteBackend(data_file=data_file)
    else:
        raise NotImplementedError(f"Backend {cfg.backend} not implemented yet.")


@app.command()
def config() -> None:
    """Interactively create/overwrite the kinv configuration file."""
    answers = qy.form(
        data_dir=qy.path("Enter your data path:", default="~/.config/kinv"),
        backend=qy.select(
            "Select your backend:",
            default="CSV",
            choices=["CSV", "YAML", "HUML", "SQLite"],
        ),
        currency_symbol=qy.select(
            "Select your currency symbol:", default="₹", choices=["₹", "$", "€", "¥"]
        ),
        currency_after=qy.select(
            "Show currency *after* the amount?",
            default="false",
            choices=["true", "false"],
        ),
        date_format=qy.text("Date format you want to use:", default="d/m/Y"),
    ).ask()

    parser = configparser.ConfigParser()
    parser["CLI"] = answers

    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CONFIG_PATH, "w") as fp:
        if qy.confirm("This will overwrite the existing config. Continue?").ask():
            parser.write(fp)
        else:
            print("[yellow]Config unchanged.[/yellow]")


@app.command()
def add() -> None:
    """Add a new inventory item."""
    item = Item.create_item_cli()
    backend = _backend()
    backend.new_entry(item)


@app.command()
def list() -> None:
    """Show the entire inventory table."""
    _backend().list_all()


@app.command()
def edit(
    item: str = typer.Argument(..., help="Item name or fuzzy search term"),
) -> None:
    """Edit an existing item."""
    backend = _backend()
    if isinstance(backend, CSVBackend):
        df = backend.data
        target = resolve_matches(item, df["name"].tolist(), "Select the item to edit.")
        row_idx = df.loc[df["name"] == target].index[0]

        print(df.loc[row_idx].to_dict())
        new_item = Item.create_item_cli()
        backend.del_item(target)
        backend.new_entry(new_item)
        print("[green]Database updated successfully.[/green]")

    if isinstance(backend, SQLiteBackend):
        conn = backend.conn
        cursor = conn.cursor()

        names_list = [
            names[0] for names in cursor.execute("SELECT name FROM items").fetchall()
        ]
        target = resolve_matches(item, names_list, "Select the item to edit.")
        item_info = conn.execute(
            f"SELECT * FROM items WHERE name = '{target}'"
        ).fetchone()
        print(dict(item_info))
        backend.edit_item(name=target)


@app.command()
def rm(item: str = typer.Argument(..., help="Item name or fuzzy search term")) -> None:
    """Remove an item from the inventory."""
    backend = _backend()
    if isinstance(backend, CSVBackend):
        df = backend.data
        target = resolve_matches(
            item, df["name"].tolist(), "Select the item to delete."
        )
        backend.del_item(target)
        print("[green]Item deleted successfully.[/green]")

    if isinstance(backend, SQLiteBackend):
        conn = backend.conn
        cursor = conn.cursor()

        names_list = [
            names[0] for names in cursor.execute("SELECT name FROM items").fetchall()
        ]
        target = resolve_matches(item, names_list, "Select the item to edit.")
        backend.del_item(target)


def resolve_matches(query: str, choices: List[str], message: str) -> str:
    matches = [m[0] for m in extract(query, choices=choices, score_cutoff=50)]
    if not matches:
        raise ValueError(f"No matches found for '{query}'.")
    if len(matches) == 1:
        return matches[0]
    return qy.select(message, choices=matches).ask()  # type: ignore


def main():
    app()


if __name__ == "__main__":
    main()
