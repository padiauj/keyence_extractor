import PIL

class Tile:
    def __init__(self, path, corner):
        self.path = path
        self.corner = corner
    def __get_size(self):
        self.path = 