class MailExtractor:
    """
    Can be inherited from to create an iterable
    mail object base
    """
    def __init__(self, data):
        self.base = []

    def __getitem__(self, key):
        return self.base[key]

    def __setitem__(self, key, value):
        self.base[key] = value

    def __len__(self):
        return len(self.base)

    def extract():
        return
