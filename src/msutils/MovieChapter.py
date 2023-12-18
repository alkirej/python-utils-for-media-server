import msutils as msu

class MovieChapter:
    def __init__(self, ffmpeg_text: [str]):
        self.title: str = MovieChapter.find_chapter_title(ffmpeg_text)
        self.section: msu.MovieSection = MovieChapter.make_into_movie_section(ffmpeg_text[0])

    @staticmethod
    def make_into_movie_section(time_line: str) -> msu.MovieSection:
        start_idx = time_line.find(" start ")
        end_idx = time_line.find(" end ")

        if start_idx < 0 or end_idx < 0:
            raise RuntimeError(f"Cannot find start/end times in: {time_line}")

        start_time = float(time_line[start_idx+7:].split(",")[0])
        end_time = float(time_line[end_idx+5:])

        return msu.MovieSection(start_time, end_time)

    @staticmethod
    def find_chapter_title(chapter_text: [str]) -> str:
        if len(chapter_text) != 3:
            raise msu.MediaServerUtilityException(f"{chapter_text} is an invalid chapter from ffmpeg.")

        title_line = chapter_text[2].strip()
        title = title_line.split(":")
        return title[1].strip()
