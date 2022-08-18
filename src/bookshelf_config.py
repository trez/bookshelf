from .plugin_mtg import PluginMTG
# from .plugin_vg import PluginVG


class BookshelfConfig:
    home = "/home/trez/lekplats/billy"
    shelfs = {
        "mtg/": PluginMTG(currency='eur')
    }


config = BookshelfConfig()


def find_plugin(shelf):
    for plugin_shelfs, plugin in config.shelfs.items():
        if shelf.startswith(plugin_shelfs):
            return plugin
