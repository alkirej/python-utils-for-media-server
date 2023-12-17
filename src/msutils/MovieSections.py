import collections as coll

MovieSection = coll.namedtuple("MovieSection", "start end")


class MovieSections:
    def __init__(self):
        self._section_list: list = []

    def add_section(self, sect: MovieSection):
        if len(self._section_list) == 0:
            self._section_list.append(sect)

        else:
            self._insert(sect)

    def _insert(self, new_sect: MovieSection):
        self._section_list.append(new_sect)
        self._section_list.sort()


test: MovieSections = MovieSections()

one: MovieSection = MovieSection(290.01, 292.64)
two: MovieSection = MovieSection(300.00, 450.61)
thr: MovieSection = MovieSection(1000.98, 1242.00)
print("---- add #1 ----")
test.add_section(one)
print(test._section_list)

print("---- add #2 ----")
test.add_section(two)
print(test._section_list)

print("---- add #3 ----")
test.add_section(thr)
print(test._section_list)
