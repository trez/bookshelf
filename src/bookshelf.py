import os
import json
import uuid
import sys
import json
import itertools
import functools
from typing import List, Dict
import itertools as it

from dataclasses import dataclass
from pathlib import Path

from git import Repo
from pyclicommander import Commander

from .bookshelf_config import config, find_plugin
from .bookshelf_errors import NoPriceFoundError, NoEntryFound

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

    def __iter__(self):
        books, sub_shelfs = self.__get_books_and_shelfs()
        if self.flatten and (self.depth is None or self.depth > 0):
            for sub_shelf in sub_shelfs:
                sub_bookshelf = Bookshelf(sub_shelf, depth=(self.depth and self.depth-1), flatten=True, filters=self.filters)
                books.extend(list(sub_bookshelf)[0][1])  # take second part of tuple from first element of list.
                
        if self.sort_by == 'name':
            books.sort(key=lambda b: b[1]['name'])
        elif self.sort_by == 'price':
            books.sort(key=lambda b: latest_price(b[1]))

        yield (self.current_path, books)

        if not self.flatten and (self.depth is None or self.depth > 0):
            for sub_shelf in sub_shelfs:
                sub_bookshelf = Bookshelf(sub_shelf, sort_by=self.sort_by, depth=(self.depth and self.depth-1), filters=self.filters)
                yield from sub_bookshelf

    def __get_books_and_shelfs(self):
        books = []
        sub_shelfs = []
        for f in self.current_path.iterdir():
            if f.is_dir() and f.name not in IGNORED_FOLDERS:
                possible_book = f / '.bookshelf.metadata'
                if possible_book.exists():
                    with open(possible_book, 'r') as book_data:
                        book = json.load(book_data)
                    if not self.filters or all(filter_fun(book) for filter_fun in self.filters):
                        books.append((f, book))
                else:
                    sub_shelfs.append(f)
        return books, sub_shelfs

    def __init__(self, shelf, depth=None, sort_by='name', filters=None, flatten=False):
        """ List books and sub-bookshelfs """
        shelf_path = Path(config.home) / (shelf or '')
        # plugin = find_plugin(fix_shelf_prefix(shelf_path))

        if not str(shelf_path.resolve()).startswith(home_path):
            print("No peeking outside of ~root~")
            sys.exit(1)

        if not shelf_path.exists():
            print("Shelf does not exist.")
            sys.exit(1)

        self.current_path = shelf_path
        self.depth = depth
        self.sort_by = 'name' if sort_by not in ACCEPTABLE_SORTS else sort_by
        self.filters = filters if filters else []
        self.flatten = flatten

    def get_sub_shelfs(self):
        _, sub_shelfs = self.__get_books_and_shelfs()
        return sub_shelfs

    def add_filter(self, b):
        self.filters.append(b)


def try_float(f):
    if f is not None:
        return float(f)


def try_int(i):
    if i is not None:
        return int(i)


def fix_shelf_prefix(shelf):
    fixed_shelf = str(shelf).removeprefix(home_path).removeprefix('/').removesuffix('/')
    return fixed_shelf or '~root~'


def latest_price(book):
    return get_prices(book)[-1]


def get_prices(book):
    return [b['price'] for b in book['price_history']]


@commander.cli("ls [SHELF] [-q] [-qq] [-r] [-t] [--no-group] [--sort-by=METHOD] [--price-sum] [--price-min=X] [--price-max=X] [--foil] [--flatten] [--reprint-group]")
def cmd_ls(shelf=None, q=False, qq=False, r=False, t=False, no_group=False, sort_by='name', price_sum=False, price_min=None, price_max=None, foil=False, flatten=False, reprint_group=False):
    """ Browse your bookshelf.

Flags
--------
    -r                  Recursivly browse the shelfs.
    -q                  Quiet, don't list entries.
    -qq                 QUIET! don't list shelfs.
    -t                  Print only title not any extra metadata.
    --no-group          Don't group multiples of entries, row by row instead.
    --reprint-group     Reprints gets grouped into one entry.
    --sort-by=METHOD    Where METHOD = 'name' | 'price'
    --price-sum         Sum up prices from shelfs listed.
    --flatten           Treat all bookshelfs as if it was one big shelf.

Filter flags
--------
    --price-min=X       Filter entries with its latest price being over X.
    --price-max=X       Filter entries with its latest price being under X.
    --foil              Filter entries that are foil.
    """
 
    total_price = 0.0

    bookshelf = Bookshelf(shelf, sort_by=sort_by, depth=(None if r else 0), flatten=flatten)

    if price_min := try_float(price_min): bookshelf.add_filter(lambda b: latest_price(b) > price_min)
    if price_max := try_float(price_max): bookshelf.add_filter(lambda b: latest_price(b) < price_max)
    if foil: bookshelf.add_filter(lambda b: b.get('finish') is not None)

    for current_path, books in bookshelf:
        plugin = find_plugin(fix_shelf_prefix(current_path))

        shelf_price = 0.0
        grouped_books = []
        prev_title = None
        current_groups = {}
        for book_path, book in books:
            shelf_price += latest_price(book)
            book_title = plugin.get_title(book)
            book_id = plugin.get_unique_id(book, edition=not reprint_group)
            if prev_title != book_title or no_group:
                prev_title = book_title
                grouped_books.extend(current_groups.values())
                current_groups = {}
            current_groups.setdefault(book_id, []).append((book_path, book))
        grouped_books.extend(current_groups.values())
        total_price += shelf_price

        if not qq:
            print(f"=> {fix_shelf_prefix(current_path)} ({len(books)}) [{round(shelf_price, 2)}]")

        if not q:
            for group in grouped_books:
                plugin.print_metadata(group[0][1], only_title=t, multiples=None if no_group else len(group))

        if not qq and not r:
            for sub_shelf in bookshelf.get_sub_shelfs():
                print(f"==> {fix_shelf_prefix(sub_shelf)}")

        if not qq and not q:
            print("")

    if price_sum:
        print(f"Total price: {round(total_price, 2)}")



@commander.cli("add SHELF [ENTRY] [--times=N] [--foil] [--etched] [--cardset=SET] [--price=M] [--find-old]")
def add_entry(shelf, entry=None, times=1, foil=False, etched=False, cardset=None, price=None, find_old=False):
    """ Add stuff to your bookshelf.

Flags
--------
    --times=N           Add N copies.
    --price=M           Use price given instead of looking it up.
    """

    def entrify(entry_name):
        entry_split = entry_name.split("/")
        if len(entry_split) > 1:
            name = entry_split[0]
        else:
            name = entry_name
        return name.replace('\'', '').replace(',', '').strip().lower()

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

    if price:
        price = float(price)

    # FIXME: PluginMTGify
    # Find card on scryfall
    try:
        entry_info = plugin.get_entry_info(entry, cardset, finish, price) if plugin else None
    except NoPriceFoundError:
        print("No price information available for entry")
        return -1
    except NoEntryFound:
        print("Lookup failed for entry")
        return -1

#    if find_old:
#        for shelf_path, books in Bookshelf(shelf, depth=recursive):
#            for book_path, book in:

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


@commander.cli("price-update SHELF [ENTRY] [PRICE] [-r] [--dry] [--min-change=X]")
def price_update(shelf, entry=None, price=None, r=False, dry=False, min_change=None):
    """ Update shelf with prices either by lookup or by given price. 

Flags
--------
    -r                  Recursivly browse the shelfs.
    --dry               Get a preview of how update would look like by doing a dry run.
    --min-change=X      Only update if change difference is larger than X.
    """
    recursive = None if r else 0
    min_change = try_float(min_change)

    bookshelf = Bookshelf(shelf, depth=recursive, flatten=True)

    collection = {}
    for shelf_path, books in bookshelf:
        plugin = find_plugin(fix_shelf_prefix(shelf_path))
        for book_path, book in books:
            book_id = plugin.get_unique_id(book)
            book_collection = collection.setdefault(book_id, [])
            book_collection.append((book_path, book))

    plugin.price_update(collection)

    price_fluctuation = 0.0
    for book_id, books in collection.items():
        for book_path, book_info in books:
            p = fix_shelf_prefix(book_path.parents[0])
            prices = get_prices(book_info)
            price_change_text = "~"
            if len(prices) > 1:
                a, b = prices[-2:]  # last two entries.
                price_change = round(b - a, 2)
            else:
                price_change = round(prices[-1], 2)

            if min_change is None or abs(price_change) >= min_change:
                price_fluctuation += price_change
                price_change_text = f"+{price_change}" if price_change >= 0 else f"{price_change}"

                print(f"{p} => {plugin.metadata_stringify(book_info, None)} [{price_change_text}]")

                if not dry:
                    with open(book_path / '.bookshelf.metadata', 'w') as f:
                        f.write(json.dumps(book_info, indent=2))

    print(f"Price fluctuation: {price_fluctuation}")


@commander.cli("search [SHELF] [--title=NAME] [--cardset=SET] [--depth=N] [-q] [-t] [--price-sum] [--full-path] [--price-min=X] [--price-max=X]")
def cmd_search(shelf=None, title=None, cardset=None, depth=None, q=False, t=False, price_sum=False, full_path=False, price_min=None, price_max=None):
    """ Search through your bookshelfs with different filters.

Flags
--------
    -q                  Quiet, don't list entries.
    -t                  Print only title not any extra metadata.
    --depth=N           Limit how deep into the shelfs one looks, default is indefinitly.
    --price-sum         Sum up prices from shelfs listed.
    --full-path         Show the real name of entries.

Filter flags
--------
    --price-min=X       Filter entries with its latest price being over X.
    --price-max=X       Filter entries with its latest price being under X.
    --cardset=SET       Filter entries that matches, eg. SET, SET#CollectorNumber.
    """

    # Any filters specified?
    filters = []
    if price_min := try_float(price_min):
        filters.append(lambda b: latest_price(b) > price_min)
    if price_max := try_float(price_max):
        filters.append(lambda b: latest_price(b) < price_max)
    if title is not None:
        filters.append(lambda b: b['name'].lower() == title.lower())
    if cardset is not None: 
        filters.append(lambda b: b['set'] == cardset or f"{b['set']}#{b['collector_number']}" == cardset)

    if not filters:
        print("No filters specied.")
        return

    bookshelf = Bookshelf(shelf, depth=try_int(depth), flatten=True, filters=filters)

    summed_price = 0.0
    for book_path, book in list(bookshelf)[0][1]:
        p = fix_shelf_prefix(book_path)
        plugin = find_plugin(p)
        summed_price += latest_price(book)
        if not q:
            if full_path:
                print(f"{p} => ", end='')
            else:
                print(f"{fix_shelf_prefix(book_path.parents[0])} => ", end='')
            plugin.print_metadata(book, only_title=t, multiples=None)

    if price_sum:
        print(f"Summed up price: {round(summed_price, 2)}")


@commander.cli("generate-www [SHELF]")
def generate_www(shelf):
    shelf_path = Path(config.home) / (shelf or '')
    bookshelf = create_bookshelf(shelf_path)
    current_shelf = fix_shelf_prefix(bookshelf.current_path)
    plugin = find_plugin(current_shelf)
    cards = get_all_entries(bookshelf, {})
    cards_json, paths_json = make_cards_json(cards)
    with open('www/cards.js', 'w') as f:
        f.write("var card_paths =")
        f.write(json.dumps(paths_json, indent=1))
        f.write(";\n")
        f.write("\n")
        f.write("var cards =")
        f.write(json.dumps(cards_json, indent=1))
        f.write(";")

#    for c in cards.keys():
#        print(c)
   # for book_path, book_info in cards['Windswept Heath'].items():
   #     print(f"{fix_shelf_prefix(book_path.parents[0])} => ", end='')
   #     plugin.print_metadata(book_info, only_title=False, multiples=1)
        

def get_all_entries(bookshelf, entry_dict=None):
    if not entry_dict:
        entry_dict = {}

    for book_path, book in bookshelf.books:
        r = entry_dict.setdefault(book['name'], {})
        r[book_path] = book

    for sub_shelf in bookshelf.sub_shelfs:
        entry_dict = get_all_entries(create_bookshelf(sub_shelf), entry_dict)

    return entry_dict


def make_cards_json(cards):
    cards_json = {}
    paths_json = {}
    path_id = 0
    for cardname, cards_info in cards.items():
        card_json = {}
        for card_path, card_info in cards_info.items():
            card_set = f"{card_info['set']}#{card_info['collector_number']}"
            if card_finish := card_info.get('finish'):
                card_set += f"#{card_finish}"

            card_path = fix_shelf_prefix(card_path.parents[0])
            card_path_id = paths_json.get(card_path)
            if not card_path_id:
                paths_json[card_path] = path_id
                card_path_id = path_id
                path_id += 1

            card_key = f"{card_set}@{card_path_id}"
            card_json[card_key] = card_json.get(card_key, 0) + 1
        cards_json[cardname] = card_json
    inv_paths_json = {v: k for k, v in paths_json.items()}
    return cards_json, inv_paths_json

@commander.cli("price-added [SHELF]")
def price_added(shelf=None):
    shelf_path = fix_shelf_prefix(Path(config.home) / (shelf or ''))
    plugin = find_plugin(shelf_path)
    repo = Repo(Path(config.home))
    books = []
    for f in repo.untracked_files:
        if f.startswith(shelf_path) and f.endswith('.bookshelf.metadata'):
                with open(config.home + "/" + f, 'r') as book_data:
                    book = json.load(book_data)
                    book_path = Path(f).parents[0]
                    books.append((book_path, book))

    price_sum = 0
    for book_path, book_info in books:
        price_sum += latest_price(book_info)
        plugin.print_metadata(book_info, only_title=False, multiples=1)

    print(f"Price total: {round(price_sum, 2)}")
