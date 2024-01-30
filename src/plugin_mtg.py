import requests
from pathlib import Path
import sys
import json
from enum import Enum
import colors as pycolors

from .plugin_base import PluginBase
from .bookshelf_errors import NoPriceFoundError, NoEntryFound

set_set = {"Urza's Saga": 'usg', "Urza's Destiny": 'uds', '7th Edition': '7ed', 'Exodus': 'exo', 'Classic 6th Edition': '6ed', 
           'Limited Edition Beta': 'leb', 'Fallen Empires': 'fem', 'Alliances': 'all', 'Planeshift': 'pls', 'Mirrodin': 'mrd',
           '9th Edition': '9ed', 'Champions of Kamigawa': 'chk', 'Ravnica: City of Guilds': 'rav', '5th Edition': '5ed',
           '8th Edition': '8ed', 'Invasion': 'inv', 'Ice Age': 'ice', 'Visions': 'vis', 'Homelands': 'hml', 'Legions': 'lgn',
           'The Dark': 'drk', 'Tempest': 'tmp', 'Fifth Dawn': '5dn', 'Dissension': 'dis', 'Mercadian Masques': 'mmq', 
           'Coldsnap': 'csp', 'Judgment': 'jud', 'Legends': 'leg', '4th Edition': '4ed', "Urza's Legacy": 'ulg', 'Prophecy': 'pcy', 
           'Portal': 'por', 'Portal Second Age': 'P02', 'Nemesis': 'nem', 'Antiquities': 'atq', 'Darksteel': 'dst', 'Gatecrash': 'gtc',
           'Unlimited Edition': '2ed', 'Chronicles': 'chr', 'Apocalypse': 'apc', 'Torment': 'tor', 'Planar Chaos': 'plc',
           'Stronghold': 'sth', 'Scourge': 'scg', 'Onslaught': 'ons', 'Weatherlight': 'wth', 'Mirage': 'mir', 'Arabian Nights': 'arn',
           'Time Spiral Timeshifted': 'tsb', 'Betrayers of Kamigawa': 'bok', 'Odyssey': 'ody', 'Revised Edition': '3ed', 'Time Spiral': 'tsp'}

class MTGCardFinish(str, Enum):
    FOIL = "foil"
    ETCHED = "etched"


class PluginMTG(PluginBase):
    def __init__(self, currency, foil_color=None, new_entry=None):
        self.currency = currency
        self.foil_color = foil_color
        self.version = '1.0'
        self.new_entry = new_entry

    def get_price(self, sf_card_data, finish=None):
        prices = sf_card_data.get('prices', {})

        # eur and eur_foil only available atm.
        if self.currency == 'eur' and finish == 'etched':
            finish = 'foil'

        price_finish = f'{self.currency}_{finish}' if finish else self.currency
        if found_price := prices.get(price_finish):
            return round(float(found_price), 2)
        else:
            return None

    def get_entry_info(self, entry=None, cardset=None, finish=None, price=None):
        card_info = None
        if entry:
            search_request_param = {
                'exact': entry
            }
            search_request = requests.get("https://api.scryfall.com/cards/named", search_request_param).json()

            if oracle_id := search_request.get('oracle_id'):
                card_info = self.__get_card_info(oracle_id, cardset, finish)
        elif cardset:
            setcode, cardnum = cardset.split("#")
            card_info = requests.get(f"https://api.scryfall.com/cards/{setcode}/{cardnum}/en").json()

        if card_info and not card_info.get('object') == "error":
            price_history = []

            if price or (price := self.get_price(card_info, finish)):
                price_history.append({'date': self.get_timestamp(), 'price': price, 'currency': 'eur'})
            else:
                raise NoPriceFoundError

            mtg_dict = {
                'bookshelf_type': 'mtg',
                'version': self.version,
                'name': card_info.get('name'),
                'oracle_id': card_info.get('oracle_id'),
                'scryfall_id': card_info.get('id'),
                'set': card_info.get('set'),
                'collector_number': card_info.get('collector_number'),
                'finish': finish,
                'price_history': price_history,
            }

            return mtg_dict
        else:
            raise NoEntryFound

    def __get_card_info(self, oracle_id, cardset, finish):
        card_info_params = {
            'order': 'released',
            'unique': 'prints',
            'q': f'oracle_id:{oracle_id}',
        }
        cards_info = requests.get("https://api.scryfall.com/cards/search", card_info_params).json()

        data_pos = None
        if cardset == '*':
            data_pos = 0
        else:
            card_sets = []
            found_pos = []
            for pos, card_data in enumerate(cards_info['data']):
                sf_card_set = f"{card_data['set']}#{card_data['collector_number']}"
                if cardset and cardset == sf_card_set:
                    return card_data
                elif cardset and sf_card_set.startswith(cardset):
                    found_pos.append(pos)
                card_sets.append(sf_card_set)

            # if no match or too many matches.
            if not found_pos or len(found_pos) > 1:
                print([card_sets[i] for i in found_pos] if found_pos else card_sets)
                sys.exit(0)

            data_pos = found_pos[0]
        return cards_info['data'][data_pos]

    def metadata_stringify(self, metadata_json, only_title=False, multiples=1):
        if only_title:
            return metadata_json['name']

        price = metadata_json['price_history'][-1]['price']
        metadata_str = ""
        if multiples is not None:
            metadata_str = f"{multiples}x "
        metadata_str += f"{metadata_json['name']} [{metadata_json['set']}#{metadata_json['collector_number']}]"
        if finish := metadata_json.get('finish'):
            if self.foil_color:
                metadata_str += f" [{self.__foil_color(finish)}]"
            else:
                metadata_str += f" [{finish}]"
        metadata_str += f" [€{price}]"
        return metadata_str

    def __foil_color(self, text):
        foil_color = getattr(pycolors, self.foil_color)
        return foil_color(text)

    def print_metadata(self, metadata_json, only_title=False, multiples=1):
        print(self.metadata_stringify(metadata_json, only_title, multiples))

    def get_unique_id(self, metadata_json, edition=True):
        if edition:
            if finish := metadata_json.get('finish'):
                return metadata_json['scryfall_id'] + f"#{finish}"
            else:
                return metadata_json['scryfall_id']
        else:
            return metadata_json['oracle_id']

    def get_title(self, metadata_json):
        return metadata_json.get('name')

    def price_update(self, collection):
        json_data_path = Path("resources/cards.json")
        print(f"Trying to load: {json_data_path.resolve()}")

        print("Load new prices...")
        with open(json_data_path, "r") as f:
            scryfall_data = json.load(f)

        print("Find updates")
        for sf_entry in scryfall_data:
            sf_id = sf_entry.get('id')

            if entries := collection.get(sf_id):
                for card_path, card_info in entries:
                    new_price = self.get_price(sf_entry, finish=card_info['finish'])
                    new_price_entry = {
                        'date': self.get_timestamp(),
                        'price': new_price,
                        'currency': self.currency
                    }
                    card_info['price_history'].append(new_price_entry)
