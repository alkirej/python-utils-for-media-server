from .MediaServerUtilityException import MediaServerUtilityException
from .MovieSections import MovieSection, MovieSections
from .MovieChapter import MovieChapter


class Color:
    PURPLE = '\033[1;35;48m'
    CYAN = '\033[1;36;48m'
    BOLD = '\033[1;37;48m'
    BLUE = '\033[1;34;48m'
    GREEN = '\033[1;32;48m'
    YELLOW = '\033[1;33;48m'
    RED = '\033[1;31;48m'
    BLACK = '\033[1;30;48m'
    UNDERLINE = '\033[4;37;48m'
    END = '\033[1;37;0m'


def text_to_secs(text: str) -> float:
    """ Convert string such as 01:14:30.54 (hh:mm:ss.xx) into 4470.54 """
    if len(text) < 11 or text[2] != ":" or text[5] != ":":
        raise MediaServerUtilityException(f"{text} is an invalid time duration.")

    hrs = int(text[0:2])
    mins = int(text[3:5])
    secs = float(text[6:])

    return (hrs * 60 * 60) + (mins * 60) + secs


def is_ffmpeg_chapter_header(text: str) -> bool:
    """ Is the supplied output TEXT from ffmpeg indicate a list of
        chapters is forthcoming?
    """
    return text.strip() == "Chapters:"


def is_ffmpeg_duration_line(text: str) -> bool:
    idx = text.find("Duration: ")
    return idx == 2


def get_ffmpeg_duration(text: str) -> float:
    dur_in_text = text[12:23]
    return text_to_secs(dur_in_text)


def is_ffmpeg_chapter(text: str) -> bool:
    idx = text.find("Chapter #")
    return idx >= 0


def pretty_progress(current: float, total: float) -> str:
    progress: float = 100 * current / total
    return f"{Color.GREEN}{progress:5.1f}%{Color.END} ({current:,.1f} of {Color.CYAN}{total:,.1f}{Color.END})"


def is_ffmpeg_update(text: str) -> bool:
    idx = text.find(" time=")
    return idx > 0


def ffmpeg_get_current_time(text: str) -> float:
    idx = text.find(" time=")
    if idx < 0:
        raise MediaServerUtilityException(f"{text} is not a valid ffmpeg progress update.")
    time_in_text = text[idx+6:idx+6+12]
    return text_to_secs(time_in_text)
