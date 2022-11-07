import os
import json
import uuid
import sys
from typing import List, Dict
import itertools as it

from dataclasses import dataclass
from pathlib import Path

from pyclicommander import Commander

from .bookshelf_config import config, find_plugin

commander = Commander('bookshelf')

home_path = str(Path(config.home).absolute())
IGNORED_FOLDERS = ['.git']
ACCEPTABLE_SORTS = ['name', 'price']


def main():
    return commander.call_with_help()


@commander.cli("")
def main_cli():
    """ Let's get help """
    commander.help_all_commands()


@dataclass
class Bookshelf:
    current_path: Path
    sub_shelfs: List[Path]
    books: List[Dict[str, str]]


def try_float(f):
    if f is not None:
        return float(f)

def try_int(i):
    if i is not None:
        return int(i)

@commander.cli("ls [SHELF] [-q] [-qq] [-r] [-t] [--no-group] [--sort-by=METHOD] [--price-sum] [--price-min=X] [--price-max=X] [--foil]")
def cmd_ls(shelf=None, q=False, qq=False, r=False, t=False, no_group=False, sort_by='name', price_sum=False, price_min=None, price_max=None, foil=False):
    """ Browse your bookshelfs.

Flags
--------
    -r                  Recursivly browse the shelfs.
    -q                  Quiet, don't list entries.
    -qq                 QUIET! don't list shelfs.
    -t                  Print only title not any extra metadata.
    --no-group          Don't group multiples of entries, row by row instead.
    --sort-by=METHOD    Where METHOD = 'name' | 'price'
    --price-min=X       Filter entries with its latest price being over X.
    --price-max=X       Filter entries with its latest price being under X.
    --foil              Filter entries that are foil.
    --price-sum         Sum up prices from shelfs listed.
    """
    shelf_path = Path(config.home) / (shelf or '')
    sort_by = 'name' if sort_by not in ACCEPTABLE_SORTS else sort_by
    bookshelf = create_bookshelf(shelf_path, sort_by)
    summed_price = lister(bookshelf, q, qq, r, t, no_group, sort_by, price_sum, try_float(price_min), try_float(price_max), foil)
    if price_sum and r:
        print(f"Summed up price: {round(summed_price, 2)}")


def lister(bookshelf, q=False, qq=False, r=False, t=False, no_group=False, sort_by='name', price_sum=False, price_min=None,
           price_max=None, foil=False):
    current_shelf = fix_shelf_prefix(bookshelf.current_path)
    plugin = find_plugin(current_shelf)
    total_price = 0.0

    if not qq:
        print(f"=> {current_shelf} ({len(bookshelf.books)})")

    for k, g in it.groupby(bookshelf.books, key=lambda r: r[1]['oracle_id']):
        num_books = 0
        book = None
        for book_path, book_info in g:
            price = latest_price(book_info)
            if price_min is not None and price < price_min:
                continue

            if price_max is not None and price > price_max:
                continue

            if foil and not book_info.get('finish'):
                continue

            total_price += price

            if no_group and not q:
                plugin.print_metadata(book_info, only_title=t, multiples=None)
            else:
                num_books += 1
                if book is None:
                    book = book_info

        if not no_group and book and not q:
            plugin.print_metadata(book, only_title=t, multiples=num_books)

    if price_sum:
        print(f"Total price: {round(total_price, 2)}")

    for sub_shelf in bookshelf.sub_shelfs:
        if r:
            if not qq:
                print("")

            sub_price = lister(create_bookshelf(sub_shelf, sort_by), q, qq, r, t, no_group, sort_by, price_sum, price_min, price_max, foil)
            if price_sum:
                total_price += sub_price
        else:
            if not qq:
                print(f"==> {fix_shelf_prefix(sub_shelf)}")
    return total_price


def fix_shelf_prefix(shelf):
    fixed_shelf = str(shelf).removeprefix(home_path).removeprefix('/').removesuffix('/')
    return fixed_shelf or '~root~'


def create_bookshelf(shelf_path, sort_by='name'):
    books = []
    shelfs = []

    if not str(shelf_path.resolve()).startswith(home_path):
        print("No peeking outside of ~root~")
        sys.exit(1)

    if not shelf_path.exists():
        print("Shelf does not exist.")
        sys.exit(1)

    for f in shelf_path.iterdir():
        if f.is_dir() and f.name not in IGNORED_FOLDERS:
            possible_book = f / '.bookshelf.metadata'
            if possible_book.exists():
                with open(possible_book, 'r') as book_data:
                    book = json.load(book_data)
                books.append((f, book))
            else:
                shelfs.append(f)

    if sort_by == 'name':
        books.sort(key=lambda b: b[1]['name'])
    elif sort_by == 'price':
        books.sort(key=lambda b: latest_price(b[1]))

    return Bookshelf(shelf_path, shelfs, books)


def latest_price(book):
    return get_prices(book)[-1]


def get_prices(book):
    return [b['price'] for b in book['price_history']]


@commander.cli("add SHELF [ENTRY] [--times=N] [--foil] [--etched] [--cardset=SET]")
def add_entry(shelf, entry=None, times=1, foil=False, etched=False, cardset=None):
    """ Add stuff to your bookshelf.
    """
    plugin = find_plugin(shelf)

    # FIXME: (MTG) Determine 'finish' for card entry
    finish = None
    if foil and etched:
        print('Choose either foil or etched or none')
        sys.exit(1)
    elif foil:
        finish = "foil"
    elif etched:
        finish = "etched"

    # FIXME: PluginMTGify
    # Find card on scryfall
    entry_info = plugin.get_entry_info(entry, cardset, finish) if plugin else None

    # Put into bookshelf.
    if entry_info:
        for n in range(int(times)):
            entry_name = entry if entry else entrify(entry_info.get('name'))
            entry_id = f"{entry_name}-{str(uuid.uuid4())}"
            path = os.path.join(config.home, shelf, entry_id)
            Path(path).mkdir(parents=True)
            path_metadata = os.path.join(path, '.bookshelf.metadata')
            with open(path_metadata, 'w') as f:
                f.write(json.dumps(entry_info, indent=2))
            print(f"{fix_shelf_prefix(shelf)} => {plugin.metadata_stringify(entry_info, multiples=None)}")
    else:
        print("Nothing found.")

def entrify(entry_name):
    entry_split = entry_name.split("/")
    if len(entry_split) > 1:
        name = entry_split[0]
    else:
        name = entry_name

    return name.replace('\'', '').replace(',', '').strip().lower()


@commander.cli("price-update SHELF [ENTRY] [PRICE] [-r] [--dry]")
def price_update(shelf, entry=None, price=None, r=False, dry=False):
    """ Update shelf with prices either by lookup or by given price. """
    shelf_path = Path(config.home) / (shelf or '')
    plugin = find_plugin(fix_shelf_prefix(shelf_path))
    bookshelf = create_bookshelf(shelf_path)

    collection = {}
    pricer(bookshelf, collection, r)
    plugin.price_update(collection)

    price_fluctuation = 0.0
    for book_id, books in collection.items():
        for book_path, book_info in books:
            p = fix_shelf_prefix(book_path.parents[0])
            prices = get_prices(book_info)
            price_change_text = "~"
            if len(prices) > 1:
                a, b = prices[-2:]
                price_change = round(b - a, 2)
                price_fluctuation += price_change
                price_change_text = f"+{price_change}" if price_change >= 0 else f"{price_change}"

            print(f"{p} => {plugin.metadata_stringify(book_info, None)} [{price_change_text}]")

            if not dry:
                with open(book_path / '.bookshelf.metadata', 'w') as f:
                    f.write(json.dumps(book_info, indent=2))
    print(f"Price fluctuation: {price_fluctuation}")


def pricer(bookshelf, collection, r=False):
    current_shelf = fix_shelf_prefix(bookshelf.current_path)
    plugin = find_plugin(current_shelf)

    for book_path, book in bookshelf.books:
        book_id = plugin.get_unique_id(book)
        book_collection = collection.setdefault(book_id, [])
        book_collection.append((book_path, book))

    if r:
        for sub_shelf in bookshelf.sub_shelfs:
            pricer(create_bookshelf(sub_shelf), collection, r)


@commander.cli("search [SHELF] [--title=NAME] [--cardset=SET] [--depth=N] [-q] [-t] [--price-sum] [--full-path] [--price-min=X] [--price-max=X]")
def cmd_search(shelf=None, title=None, cardset=None, depth=None, q=False, t=False, price_sum=False, full_path=False, price_min=None, price_max=None):
    """ Look through your bookshelfs for a specific title.

Flags
--------
    -q                  Quiet, don't list entries.
    -t                  Print only title not any extra metadata.
    --depth=N           Limit how deep into the shelfs one looks, default is indefinitly.
    --price-min=X       Filter entries with its latest price being over X.
    --price-max=X       Filter entries with its latest price being under X.
    --price-sum         Sum up prices from shelfs listed.
    --full-path         Show the real name of entries.
    """
    def filter_fun(book):
        # print(f"{title=}")
        price = latest_price(book)
        match = True
        match &= title is None or book['name'].lower() == title.lower()
        match &= cardset is None or book['set'] == cardset
        match &= price_min is None or price >= price_min
        match &= price_max is None or price <= price_max
        return match

    shelf_path = Path(config.home) / (shelf or '')
    bookshelf = create_bookshelf(shelf_path)
    price_min = try_float(price_min)
    price_max = try_float(price_max)

    # Any filters specified?
    filters = [title, cardset, price_min, price_max]
    if not any((f is not None for f in filters)):
        print("No filters specied.")
        return

    matches = searcher(bookshelf, filter_fun, try_int(depth))
    summed_price = 0.0

    for match_path, match_info in matches:
        p = fix_shelf_prefix(match_path)
        plugin = find_plugin(p)
        summed_price += latest_price(match_info)
        if not q:
            if full_path:
                print(f"{p} => ", end='')
            else:
                print(f"{fix_shelf_prefix(match_path.parents[0])} => ", end='')
            plugin.print_metadata(match_info, only_title=t, multiples=None)

    if price_sum:
        print(f"Summed up price: {round(summed_price, 2)}")


def searcher(bookshelf, filter_fun, depth=None):
    matches = []
    for book_path, book in bookshelf.books:
        if filter_fun(book):
            matches.append((book_path, book))

    if depth is None or depth > 0:
        for sub_shelf in bookshelf.sub_shelfs:
            matches.extend(searcher(create_bookshelf(sub_shelf), filter_fun, depth and depth-1))

    return matches
