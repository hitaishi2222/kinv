from datetime import datetime
from typing import Dict, List, Literal

import pandas as pd
import questionary as qy
import sqlite3
from kinv.configs import Settings
from pydantic import BaseModel, ConfigDict, DirectoryPath, FilePath, PrivateAttr
from rich.console import Console
from rich.table import Table

console = Console()


class Item(BaseModel):
    name: str
    price: float
    quantity: float
    quantity_unit: Literal["Kg", "g", "nos", "L", "ml"]
    expiry_date: datetime
    expiry_duration: int

    @classmethod
    def create_item_cli(cls) -> "Item":
        config = Settings.from_config_file()
        conf = config.model_dump()  # better caching
        item_info = qy.form(
            name=qy.text("Enter Item Name: "),
            price=qy.text(f"Enter its Price: {conf['currency_symbol']} "),
            quantity=qy.text("Enter the quantity (in numbers)"),
            quantity_unit=qy.text(
                "Enter the unit which of quantity (`Kg`, `g`, `nos`, `L`, `ml`)",
                default="nos",
            ),
            expiry_date=qy.text(f"Expiry date: format-`{conf['date_format']}`"),
        ).ask()

        return cls(
            name=item_info["name"],
            price=float(item_info["price"]),
            quantity=float(item_info["quantity"]),
            quantity_unit=item_info["quantity_unit"],
            expiry_date=datetime.strptime(
                item_info["expiry_date"], conf["date_format"]
            ),
            expiry_duration=(
                datetime.strptime(item_info["expiry_date"], conf["date_format"])
                - datetime.now()
            ).days,
        )

    @property
    def value(self) -> float:
        return self.quantity * self.price

    @property
    def price_str(self) -> str:
        conf = Settings.from_config_file().model_dump()
        if conf["currency_after"]:
            return f"{self.price}{conf['currency_symbol']}"
        else:
            return f"{conf['currency_symbol']}{self.price}"

    def csv_entry(self) -> Dict:
        return self.model_dump()

    def edit_entry(self, new_entry: "Item"):
        if not isinstance(new_entry, Item):
            raise AttributeError("`new_entry` is not an instance of `Item`")
        self.name = new_entry.name
        self.price = new_entry.price
        self.quantity = new_entry.quantity
        self.quantity_unit = new_entry.quantity_unit
        self.expiry_date = new_entry.expiry_date
        self.expiry_duration = new_entry.expiry_duration


class CSVBackend(BaseModel):
    data_dir: DirectoryPath
    data_file: FilePath
    data: pd.DataFrame

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def read_and_populate_data(
        cls, data_dir: DirectoryPath, data_file: FilePath
    ) -> "CSVBackend":
        conf = Settings.from_config_file().model_dump()

        if data_dir != conf["data_dir"]:
            raise ValueError("data_dir and backend directory are not matching.")
        if not data_dir.exists():
            data_dir.mkdir()
        if not data_file.exists():
            data_file.touch()
            data_file.write_text(
                "name,price,quantity,quantity_unit,expiry_date,expiry_duration\n"
            )

        df = pd.read_csv(
            data_file,
            dtype={
                "name": str,
                "price": float,
                "quantity": float,
                "quantity_unit": str,
                "expiry_duration": int,
            },
            parse_dates=["expiry_date"],
        ).sort_values(by="expiry_duration")

        return cls(data_dir=data_dir, data_file=data_file, data=df)

    @property
    def no_of_entries(self) -> int:
        return len(self.data)

    def item_list(self) -> List[Item]:
        items = []
        for item in self.data.itertuples():
            items.append(
                Item(
                    name=item.name,  # type: ignore
                    price=item.price,  # type: ignore
                    quantity=item.quantity,  # type: ignore
                    quantity_unit=item.quantity_unit,  # type: ignore
                    expiry_date=item.expiry_date,  # type: ignore
                    expiry_duration=item.expiry_duration,  # type: ignore
                )
            )
        return items

    def new_entry(self, item: Item):
        if item.name in self.data["name"].values:
            raise ValueError(f"Item `{item.name}`already Exists. Try editing it...")
        pd.DataFrame([item.csv_entry()]).to_csv(
            self.data_file, mode="a", index=False, header=False
        )
        # Also update the in‑memory DataFrame so the current session sees the change
        self.data = pd.concat(
            [self.data, pd.DataFrame([item.csv_entry()])], ignore_index=True
        )

    def del_item(self, item_name: str):
        self.data = self.data[self.data["name"] != item_name]  # type: ignore
        self.data.to_csv(self.data_file, index=False)

    def list_all(self):
        conf = Settings.from_config_file().model_dump()

        table = Table(title="Kitchen Inventory")
        table.add_column("name", justify="left", style="cyan")
        table.add_column("price", justify="right")
        table.add_column("quantity", justify="right", style="red")
        table.add_column("unit", justify="right", style="red")
        table.add_column("expiry date", justify="right", style="blue")
        table.add_column("expiry in", justify="right", style="blue")

        for item in self.item_list():
            table.add_row(
                f"{item.name}",
                f"{item.price_str}",
                f"{item.quantity}",
                f"{item.quantity_unit}",
                f"{item.expiry_date.strftime(conf['date_format'])}",
                f"{item.expiry_duration}",
            )
        console.print(table)


class SQLiteBackend(BaseModel):
    data_file: FilePath
    _conn: sqlite3.Connection = PrivateAttr()

    def model_post_init(self, __context):
        self._conn = sqlite3.connect(self.data_file)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    @property
    def conn(self):
        return self._conn

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL,
                quantity REAL,
                quantity_unit TEXT,
                expiry_date TEXT,
                expiry_duration INTEGER
            )
        """)
        self._conn.commit()

    def item_list(self) -> list[Item]:
        rows = self.conn.execute("SELECT * FROM items").fetchall()

        items = []
        for row in rows:
            data = dict(row)

            # convert ISO string → datetime
            data["expiry_date"] = datetime.fromisoformat(data["expiry_date"])

            items.append(Item(**data))

        return items

    def new_entry(self, item: Item):
        data = item.model_dump()

        # convert datetime to ISO string
        data["expiry_date"] = data["expiry_date"].isoformat()

        self.conn.execute(
            """
            INSERT INTO items
            (name, price, quantity, quantity_unit, expiry_date, expiry_duration)
            VALUES (:name, :price, :quantity, :quantity_unit, :expiry_date, :expiry_duration)
            """,
            data,
        )
        self.conn.commit()

    def del_item(self, item_name: str):
        self.conn.execute(
            "DELETE FROM items WHERE name = ?",
            (item_name,),
        )
        self.conn.commit()

    def list_all(self):
        conf = Settings.from_config_file().model_dump()

        table = Table(title="Kitchen Inventory")
        table.add_column("name", justify="left", style="cyan")
        table.add_column("price", justify="right")
        table.add_column("quantity", justify="right", style="red")
        table.add_column("unit", justify="right", style="red")
        table.add_column("expiry date", justify="right", style="blue")
        table.add_column("expiry in", justify="right", style="blue")

        for item in self.item_list():
            table.add_row(
                f"{item.name}",
                f"{item.price_str}",
                f"{item.quantity}",
                f"{item.quantity_unit}",
                f"{item.expiry_date.strftime(conf['date_format'])}",
                f"{item.expiry_duration}",
            )
        console.print(table)

    def edit_item(self, name: str):
        data = Item.create_item_cli().model_dump()
        data["expiry_date"] = data["expiry_date"].isoformat()
        data["search_name"] = name

        self.conn.execute(
            """
            UPDATE items
            SET name = :name,
                price = :price,
                quantity = :quantity,
                quantity_unit = :quantity_unit,
                expiry_date = :expiry_date,
                expiry_duration = :expiry_duration
            WHERE name = :search_name
            """,
            data,
        )
        self.conn.commit()
