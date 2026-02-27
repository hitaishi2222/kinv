from typing import List
import typer
import questionary as qy
import configparser
from pathlib import Path
from rapidfuzz.process import extract
from rich import print

from configs import Settings, DEFAULT_CONFIG_PATH
from modules import CSVBackend, Item

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)
conf_parser = configparser.ConfigParser()


@app.command()
def config():
    """
    Initialize `KInv` for some general configuration
    """
    init_answers = qy.form(
        data_dir=qy.path(
            "Enter your data path:",
            default="~/.config/kinv",
        ),
        backend=qy.select(
            "Select your backend:",
            default="CSV",
            choices=["CSV", "YAML", "HUML", "SQLite"],
        ),
        currency_symbol=qy.select(
            "Select your Currency symbol:",
            default="₹",
            choices=["₹", "$", "€", "¥"],
        ),
        currency_after=qy.select(
            "Select your Currency symbol:",
            default="false",
            choices=["true", "false"],
        ),
        date_format=qy.text("Date format you want to use:", default="d/m/Y"),
    ).ask()

    conf_parser["CLI"] = {
        "data_dir": init_answers["data_dir"],
        "backend": init_answers["backend"],
        "currency_symbol": init_answers["currency_symbol"],
        "currency_after": init_answers["currency_after"],
        "date_format": init_answers["date_format"],
    }

    DEFAULT_CONFIG_PATH.parent.mkdir(exist_ok=True)
    DEFAULT_CONFIG_PATH.touch()
    with open(DEFAULT_CONFIG_PATH, "w") as conf_file:
        flag: bool = qy.confirm(
            "This will wipe the current config (if there any) and write new config to it."
        ).ask()
        if flag:
            conf_parser.write(conf_file)
        else:
            print("Nothing changed in your config or config not saved.")


@app.command()
def add():
    """
    Add item to the database.
    """
    item = Item.create_item_cli()
    # print(item.model_dump())
    # print(f"{item.expiry_duration} days")

    conf = Settings.from_config_file().model_dump()
    if conf["backend"] == "CSV":
        csv_backend = CSVBackend.read_and_populate_data(
            Path(conf["data_dir"]), Path(conf["data_dir"]).joinpath("data.csv")
        )
        csv_backend.new_entry(item)


@app.command()
def list():
    """
    List table
    """
    conf = Settings.from_config_file().model_dump()
    if conf["backend"] == "CSV":
        csv_backend = CSVBackend.read_and_populate_data(
            Path(conf["data_dir"]), Path(conf["data_dir"]).joinpath("data.csv")
        )
        csv_backend.list_all()


@app.command()
def edit(item):
    """
    Edit an item.
    """
    conf = Settings.from_config_file().model_dump()
    if conf["backend"] == "CSV":
        csv_backend = CSVBackend.read_and_populate_data(
            Path(conf["data_dir"]), Path(conf["data_dir"]).joinpath("data.csv")
        )
        df = csv_backend.data
        edit_item = resolve_matches(
            item, df["name"].to_list(), "Select the item to edit."
        )
        item_index = df[df["name"] == edit_item].index[0]
        print(df.loc[item_index].to_dict())
        new_item = Item.create_item_cli()
        csv_backend.del_item(edit_item)
        csv_backend.new_entry(new_item)

    print("[red] Database updated succesfully...[/red]")


@app.command()
def rm(item):
    """
    Remove an item...
    """
    conf = Settings.from_config_file().model_dump()
    if conf["backend"] == "CSV":
        csv_backend = CSVBackend.read_and_populate_data(
            Path(conf["data_dir"]), Path(conf["data_dir"]).joinpath("data.csv")
        )
        df = csv_backend.data
        edit_item = resolve_matches(
            item, df["name"].to_list(), "Select the item to edit."
        )
        csv_backend.del_item(edit_item)

    print("[red] Item deleted succesfully...[/red]")


def resolve_matches(query: str, choices: List[str], message: str) -> str:
    matches = [match[0] for match in extract(query, choices=choices, score_cutoff=50)]
    if len(matches) != 1:
        pick_match = qy.select(message, choices=matches).ask()  # type: ignore
    else:
        pick_match = matches[0]
    return pick_match


if __name__ == "__main__":
    app()
