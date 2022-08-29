from pathlib import Path

from .plugin_mtg import PluginMTG
# from .plugin_vg import PluginVG


class BookshelfConfig:
    home = "/home/trez/lekplats/billy"
    shelfs = {
        "mtg/": PluginMTG(currency='eur')
    }


config = BookshelfConfig()

home_path = str(Path(config.home).absolute())


def fix_shelf_prefix(shelf):
    fixed_shelf = str(shelf).removeprefix(config.home).removeprefix('/').removesuffix('/')
    return fixed_shelf or '~root~'


def find_plugin(shelf):
    for plugin_shelfs, plugin in config.shelfs.items():
        if shelf.startswith(fix_shelf_prefix(plugin_shelfs)):
            return plugin
