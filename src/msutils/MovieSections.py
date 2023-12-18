import collections as coll
from msutils.MediaServerUtilityException import MediaServerUtilityException

MovieSection = coll.namedtuple("MovieSection", "start end")


def is_overlap(sect_one: MovieSection, sect_two: MovieSection) -> bool:
    # Partial overlaps.  One section starts within the other's timeframe
    if sect_two.start <= sect_one.start <= sect_two.end:
        return True
    if sect_one.start <= sect_two.start <= sect_one.end:
        return True

    # Complete overlap. One section starts before and ends after the other.
    if sect_one.start <= sect_two.start and sect_one.end >= sect_two.end:
        return True
    if sect_two.start <= sect_one.start and sect_two.end >= sect_one.end:
        return True

    return False


def combine(sect_one: MovieSection, sect_two: MovieSection) -> MovieSection:
    # Verify an overlap
    high_start = max(sect_one.start, sect_two.start)
    low_end = min(sect_one.end, sect_two.end)
    if high_start > low_end:
        raise MediaServerUtilityException(f"Cannot combine {sect_one} and {sect_two}.  No overlapping time.")

    new_start = min(sect_one.start, sect_two.start)
    new_end = max(sect_one.end, sect_two.end)
    return MovieSection(new_start, new_end)


class MovieSections:
    def __init__(self, movie_file_name: str):
        self.section_list: list = []
        self.file_name = movie_file_name

    def add_section(self, sect: MovieSection):
        if sect.start > sect.end:
            raise MediaServerUtilityException(f"({sect.start},{sect.end}) is an invalid movie section.  "
                                              + "It Ends before it starts."
                                              )
        if len(self.section_list) == 0:
            self.section_list.append(sect)
        else:
            self._insert(sect)

    def _consolidate_sections(self) -> None:
        consolidated_list = []

        self.section_list.sort()
        prev_sect: MovieSection = self.section_list[0]
        for idx in range(1, len(self.section_list)):
            curr_sect: MovieSection = self.section_list[idx]
            if is_overlap(prev_sect, curr_sect):
                prev_sect = combine(prev_sect, curr_sect)
            else:
                consolidated_list.append(prev_sect)
                prev_sect = curr_sect

        consolidated_list.append(prev_sect)
        consolidated_list.sort()
        self._section_list = consolidated_list

    def _insert(self, new_sect: MovieSection):
        made_update: bool = False

        # Look for overlap with any existing
        list_size: int = len(self.section_list)
        for idx in range(list_size):
            sect = self.section_list[idx]
            if is_overlap(new_sect, sect):
                self.section_list[idx] = combine(new_sect, sect)
                made_update = True

        if made_update:
            self._consolidate_sections()
        else:
            # SIMPLE ADD WITH NO OVERLAPS AT ALL
            self.section_list.append(new_sect)
            self.section_list.sort()

    def create_input_file_for_video_gaps(self, inputs_file_name: str):
        with open(inputs_file_name, "w") as fd:
            first_gap: MovieSection = self.section_list[0]
            if first_gap.start > 0:
                fd.write(f"file '{self.file_name}'\ninpoint 0.0\noutpoint {first_gap.start}\n")

            prev_gap = first_gap
            for gap in self.section_list:
                if (gap == first_gap):
                    continue
                fd.write(f"file '{self.file_name}'\ninpoint {prev_gap.end}\noutpoint {gap.start}\n")
                prev_gap = gap
            fd.write(f"file '{self.file_name}'\ninpoint {prev_gap.end}\n")
