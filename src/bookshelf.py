import os
import json
import uuid
import sys
from typing import List, Dict
import itertools as it

from dataclasses import dataclass
from pathlib import Path

from pyclicommander import Commander

from .bookshelf_config import config

commander = Commander()

home_path = str(Path(config.home).absolute())
IGNORED_FOLDERS = ['.git']
ACCEPTABLE_METHODS = ['name', 'price']


def main():
    return commander.call_with_help()


@dataclass
class Bookshelf:
    current_path: Path
    sub_shelfs: List[Path]
    books: List[Dict[str, str]]


@commander.cli("ls [SHELF] [-q] [-r] [--sort-by=METHOD]")
def cmd_ls(shelf=None, q=False, r=False, sort_by='name'):
    shelf_path = Path(config.home) / (shelf or '')
    sort_by = 'name' if sort_by not in ACCEPTABLE_METHODS else sort_by
    bookshelf = create_bookshelf(shelf_path, sort_by)
    lister(bookshelf, q, r, sort_by)


def lister(bookshelf, q=False, r=False, sort_by='name'):
    current_shelf = fix_shelf_prefix(bookshelf.current_path)
    plugin = find_plugin(current_shelf)
    total_price = 0.0

    print(f"==> {current_shelf} ({len(bookshelf.books)})")
    for k, g in it.groupby(bookshelf.books, key=lambda r: r['oracle_id']):
        cards = list(g)
        total_price += sum([latest_price(c) for c in cards])
        if not q:
            plugin.print_metadata(cards[0], len(cards))
    print(f"Total price: {total_price}")

    for sub_shelf in bookshelf.sub_shelfs:
        if r:
            lister(create_bookshelf(sub_shelf, sort_by), q, r)
        else:
            print(f"==> {fix_shelf_prefix(sub_shelf)}")


def fix_shelf_prefix(shelf):
    fixed_shelf = str(shelf).removeprefix(home_path).removeprefix('/')
    return fixed_shelf or '~root~'


def create_bookshelf(shelf_path, sort_by='name'):
    books = []
    shelfs = []

    for f in shelf_path.iterdir():
        if f.is_dir() and f.name not in IGNORED_FOLDERS:
            possible_book = f / '.bookshelf.metadata'
            if possible_book.exists():
                with open(possible_book, 'r') as book_data:
                    book = json.load(book_data)
                books.append(book)
            else:
                shelfs.append(f)

    if sort_by == 'name':
        books.sort(key=lambda b: b['name'])
    elif sort_by == 'price':
        books.sort(key=latest_price)

    return Bookshelf(shelf_path, shelfs, books)


def latest_price(book):
    return book['price_history'][-1]['price']


@commander.cli("add SHELF ENTRY [--times=N] [--foil] [--etched] [--cardset=SET]")
def add_entry(shelf, entry, times=1, foil=False, etched=False, cardset=None):

    finish = None
    if foil and etched:
        print('Choose either foil or etched or none')
        sys.exit(1)
    elif foil:
        finish = "foil"
    elif etched:
        finish = "etched"

    # Find card on scryfall
    entry_info = None
    if plugin := find_plugin(shelf):
        entry_info = plugin.get_entry_info(entry, cardset, finish)

    # Put into bookshelf.
    if entry_info:
        price = entry_info['price_history'][-1]['price']
        print(f"Adding {entry}[{entry_info['set']}#{entry_info['collector_number']}] [{price}] @ {shelf}")
        for n in range(int(times)):
            entry_id = f"{entry}-{str(uuid.uuid4())}"
            path = os.path.join(config.home, shelf, entry_id)
            Path(path).mkdir(parents=True)
            path_metadata = os.path.join(path, '.bookshelf.metadata')
            with open(path_metadata, 'w') as f:
                f.write(json.dumps(entry_info))
            print(path)
    else:
        print("Nothing found.")


def find_plugin(shelf):
    for plugin_shelfs, plugin in config.shelfs.items():
        if shelf.startswith(plugin_shelfs):
            return plugin


@commander.cli("price-update SHELF [ENTRY] [-r]")
def scryfall_price_update(shelf, entry=None, r=False):
    pass
