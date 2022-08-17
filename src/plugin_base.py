from datetime import datetime


class PluginBase:

    def __init__(self):
        pass

    def get_timestamp(self):                                             
        my_date = datetime.now()                                         
        return my_date.isoformat() + 'Z'                                 
