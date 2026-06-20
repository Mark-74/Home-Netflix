class Film:
    def __init__(self, title : str, cover : str, slug : str, id : int):
        self.title =  title
        self.cover = cover
        self.slug = slug
        self.id = id
        
class Stored:
    def __init__(self, id : int, title : str, path : str, cover : str, status : str):
        self.id = id
        self.title = title
        self.path = path
        self.cover = cover
        self.status = status
