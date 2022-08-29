import requests
from pathlib import Path
import sys
import json
from enum import Enum

from .plugin_base import PluginBase


class MTGCardFinish(str, Enum):
    FOIL = "foil"
    ETCHED = "etched"


class PluginMTG(PluginBase):
    def __init__(self, currency):
        self.currency = currency
        self.version = '1.0'

    def get_price(self, sf_card_data, finish=None):
        prices = sf_card_data.get('prices', {})

        # eur and eur_foil only available atm.
        if self.currency == 'eur' and finish == 'etched':
            finish = 'foil'

        price_finish = f'{self.currency}_{finish}' if finish else self.currency
        return round(float(prices.get(price_finish, '0.0')), 2)

    def get_entry_info(self, entry, cardset=None, finish=None):
        search_request_param = {
            'exact': entry
        }
        search_request = requests.get("https://api.scryfall.com/cards/named", search_request_param).json()
        if oracle_id := search_request.get('oracle_id'):
            card_info = self.__get_card_info(oracle_id, cardset, finish)
            price_history = []
            if price := self.get_price(card_info, finish):
                price_history.append({'date': self.get_timestamp(), 'price': price, 'currency': 'eur'})
            mtg_dict = {
                'bookshelf_type': 'mtg',
                'version': self.version,
                'name': card_info.get('name'),
                'oracle_id': oracle_id,
                'scryfall_id': card_info.get('id'),
                'set': card_info.get('set'),
                'collector_number': card_info.get('collector_number'),
                'finish': finish,
                'price_history': price_history,
            }

            return mtg_dict

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

    def metadata_stringify(self, metadata_json, multiples=1):
        price = metadata_json['price_history'][-1]['price']
        metadata_str = ""
        if multiples is not None:
            metadata_str = f"{multiples}x "
        metadata_str += f"{metadata_json['name']} [{metadata_json['set']}#{metadata_json['collector_number']}]"
        if finish := metadata_json.get('finish'):
            metadata_str += f" [{finish}]"
        metadata_str += f" [{price}]"
        return metadata_str

    def print_metadata(self, metadata_json, multiples=1):
        print(self.metadata_stringify(metadata_json, multiples))

    def get_unique_id(self, metadata_json):
        return metadata_json['scryfall_id']

    def price_update(self, collection):
        json_data_path = Path("resources/default-cards-20220819090518.json")

        print("Load new prices...")
        with open(json_data_path, "r") as f:
            json_data = json.load(f)

        print("Find updates")
        for jd in json_data:
            sf_id = jd.get('id')
            if entries := collection.get(sf_id):
                for card_path, card_info in entries:
                    new_price = self.get_price(jd, finish=card_info['finish'])
                    new_price_entry = {
                        'date': self.get_timestamp(),
                        'price': new_price,
                        'currency': self.currency
                    }
                    card_info['price_history'].append(new_price_entry)
