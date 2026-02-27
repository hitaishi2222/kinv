import pandas as pd
from rapidfuzz.process import extract
import questionary as qy


def main():
    df = pd.read_csv("~/.config/kinv/data.csv")

    name_list = df["name"].to_list()
    matches = [
        match[0] for match in extract("bana", choices=name_list, score_cutoff=50)
    ]
    print(matches)
    if len(matches) != 1:
        pick_match = qy.select("Select the item to choose", choices=matches)  # type: ignore
    else:
        pick_match = matches[0]


if __name__ == "__main__":
    main()
