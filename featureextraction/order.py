class Order:
    """
    Capsulates a dictionary the can be used as an order
    """
    def __init__(self, values):
        self.data = {}
        for idx, val in enumerate(values):
            self.data[str(val)] = idx

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __contains__(self, item):
        return item in self.data

    def __len__(self):
        return len(self.data)
