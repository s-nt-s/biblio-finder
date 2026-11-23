from ebiblio import EbiblioClient, SearchQuery, SearchResult


class Ebiblio:
    def __init__(self, *urls):
        self.__clients = tuple(map(EbiblioClient, urls))

    def search(self, query: SearchQuery):
        result: list[SearchResult] = []
        for c in self.__clients:
            for r in c.search_all(query):
                if r not in result:
                    result.append(r)
        return tuple(result)