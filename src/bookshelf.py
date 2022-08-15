import os
import json
import uuid

from pathlib import Path

from pyclicommander import Commander

from .bookshelf_config import config

commander = Commander()

ACCEPTABLE_METHODS = ['alpha', 'price']
def main():
    return commander.call_with_help()

def dirs_n_entries(path):
    dirs = []
    bse = []
    for f in path.iterdir():
        if is_bookshelf_entry(f):
            bse.append(f)
        elif f.is_dir() and not f.name == ".git":
            dirs.append(f)
    return dirs, bse

def is_bookshelf_entry(e):
    if e.is_dir():
        for f in e.iterdir():
            if '.bookshelf.metadata' == f.name:
                return True
    return False

def entries(path, sort_by='alpha'):
    yield path
    dirs, bse = dirs_n_entries(path)
    if sort_by == 'alpha':
        bse.sort()
    elif sort_by == 'price':
        bse.sort(key=sort_by_price)
    yield from bse
    dirs.sort()
    for d in dirs:
        yield from entries(d, sort_by)

def sort_by_price(bse):
    with open(os.path.join(bse, '.bookshelf.metadata'), 'r') as metadata:
        metadata_json = json.load(metadata)
        return metadata_json['price_history'][-1]['price']
 
@commander.cli("ls [SHELF] [-q] [-r] [--sort-by=METHOD]")
def list_entries(shelf=None, q=False, r=False, sort_by='alpha'):
    home_path = str(Path(config.home).absolute()) + "/"
    price_total = 0.0
    multiples = 1
    prev_entry = None
    sort_by = 'alpha' if sort_by not in ACCEPTABLE_METHODS else sort_by
    second_folder = False
    for e in entries(Path(os.path.join(config.home, shelf or '')), sort_by):
        if is_bookshelf_entry(e):
            with open(os.path.join(e, '.bookshelf.metadata'), 'r') as metadata:
                metadata_json = json.load(metadata)
                price = metadata_json['price_history'][-1]['price']
                price_total += price
                if prev_entry and prev_entry['oracle_id'] == metadata_json['oracle_id']:
                    multiples += 1
                else:
                    if prev_entry and not q:
                        print_metadata(prev_entry, multiples=multiples)
                    prev_entry = metadata_json
                    multiples = 1
        else:
            if prev_entry:
                if not q:
                    print_metadata(prev_entry, multiples=multiples)
                prev_entry = None
            if second_folder and not r:
                break
            print(f"==> {str(e).removeprefix(home_path)}")
            second_folder = True
    if prev_entry and not q:
        print_metadata(prev_entry, multiples=multiples)
    print(f"Total price: {price_total}")


def print_metadata(metadata_json, multiples=1):       
    price = metadata_json['price_history'][-1]['price']
    metadata_str = f"{multiples}x "
    metadata_str += f"{metadata_json['name']} [{metadata_json['set']}#{metadata_json['collector_number']}]"
    if finish := metadata_json.get('finish'):
        metadata_str += f" [{finish}]"
    metadata_str += f" [{price}]"
    print(metadata_str)


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
    for plugin_shelfs, plugin in config.shelfs.items():
        if shelf.startswith(plugin_shelfs):
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

