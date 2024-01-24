import collections as coll
import msutils as msu

MovieSection = coll.namedtuple("MovieSection", "start end comment")

FREEZE_FUDGE_FACTOR: float = 0.75


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
    new_comment = f"{sect_one.comment} - {sect_two.comment}"
    return MovieSection(new_start, new_end, new_comment)


class MovieSections:
    def __init__(self, movie_file_name: str, list_name: str = ""):
        self.section_list: list = []
        self.file_name = movie_file_name
        self.list_name = list_name

    def add_section(self, sect: MovieSection):
        new_sect: MovieSection = MovieSection(float(sect.start), float(sect.end), sect.comment)
        if new_sect.start > new_sect.end:
            raise MediaServerUtilityException(f"({new_sect.start},{new_sect.end}) is an invalid movie section.  "
                                              + "It Ends before it starts."
                                              )
        if len(self.section_list) == 0:
            self.section_list.append(new_sect)
        else:
            self._insert(new_sect)

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

    def ms_union(self, ms2):
        if self.file_name != ms2.file_name:
            raise MediaServerUtilityException(
                f"To union two MovieSections objects, the file_names must be the same. "
                f"{self.file_name} != {ms2.file_name}"
                )

        return_val = MovieSections(self.file_name)

        for ms in self.section_list:
            return_val.add_section(ms)

        for ms in ms2.section_list:
            return_val.add_section(ms)

        return return_val

    def __or__(self, ms2):
        return self.ms_union(ms2)

    def _single_intersect(self, list_name: str, section: MovieSection) -> [MovieSection]:
        return_val: [MovieSection] = []
        for my_section in self.section_list:
            if is_overlap(section, my_section):
                new_start: float = max(section.start, my_section.start)
                new_end: float = min(section.end, my_section.end)
                new_section: MovieSection = MovieSection(
                        new_start,
                        new_end,
                        f"{list_name}({section.start}-{section.end}) & " +
                        f"{self.list_name}({my_section.start}-{my_section.end})"
                        )
                return_val.append(new_section)

        return return_val

    def ms_intersection(self, ms2):
        if self.file_name != ms2.file_name:
            raise MediaServerUtilityException(f"To intersect two MovieSections objects, "
                                              f"the file_names must be the same. {self.file_name}"
                                              f" != {ms2.file_name}"
                                              )
        return_val = MovieSections(self.file_name)
        for section in ms2.section_list:
            matches: [MovieSection] = self._single_intersect(ms2.list_name, section)
            for m in matches:
                return_val.add_section(m)

        return return_val

    def __and__(self, ms2):
        return self.ms_intersection(ms2)

    def total_time(self) -> float:
        return_val: float = 0

        for sect in self.section_list:
            dur: float = sect.end - sect.start
            return_val += dur + FREEZE_FUDGE_FACTOR

        return return_val

    def create_input_file_for_video_gaps(self, inputs_file_name: str):
        with open(inputs_file_name, "w") as fd:
            first_gap: MovieSection = self.section_list[0]
            if first_gap.start > 0:
                self.section_header(fd)
                fd.write(f"inpoint 0.0\n")  # No fudging on start.
                self.outpoint(fd, first_gap.start)
                self.section_footer(fd, first_gap.comment)

            prev_gap = first_gap
            for gap in self.section_list:
                if gap == first_gap:
                    continue
                self.section_header(fd)
                self.inpoint(fd, prev_gap.end)
                self.outpoint(fd, gap.start)
                self.section_footer(fd, gap.comment)
                prev_gap = gap

            self.section_header(fd)
            self.inpoint(fd, prev_gap.end)

    def section_header(self, fd) -> None:
        fd.write(f"file '{self.file_name}'\n")

    def inpoint(self, fd, time) -> None:
        # find next i-frame (key-frame)
        key_frame_ts: float = msu.get_next_key_frame_after_timestamp(self.file_name, time)
        fd.write(f"inpoint {key_frame_ts}\n")

    @staticmethod
    def outpoint(fd, time) -> None:
        fd.write(f"outpoint {time - FREEZE_FUDGE_FACTOR}\n")

    @staticmethod
    def section_footer(fd, comment: str) -> None:
        fd.write(f"# {comment.strip().upper()} was removed.\n")
