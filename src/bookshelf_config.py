from .plugin_mtg import PluginMTG

class BookshelfConfig:
    home = "/home/trez/lekplats/billy"
    shelfs = {
        "mtg/": PluginMTG(currency='eur')
    }


config = BookshelfConfig()
