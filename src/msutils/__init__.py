import datetime as dt
import logging as log
import os
import pathlib as path
import shutil as sh
import subprocess as proc
import time

from .ffmpeg_utils import run_ffmpeg
from .MediaServerUtilityException import MediaServerUtilityException
from .MovieSections import MovieSection, MovieSections
from .MovieChapter import MovieChapter

FFMPEG_FILE = "ffmpeg"
KEY_FRAME_SCAN_DURATION: float = 15.0
TOO_MANY_LINES_BEFORE_PROGRESS: int = 100000


class Color:
    BOLD = '\033[1m'
    FAINT = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    DOUBLE_UNDERLINE = '\033[21m'
    OVERLINE = '\033[53m'
    BLINK = '\033[5m'

    END = '\033[0;37;0m'
    OFF = END

    BLACK = '\033[30;48m'
    BLUE = '\033[34;48m'
    CYAN = '\033[36;48m'
    GRAY = f"{BOLD}{BLACK}"
    GREEN = '\033[32;48m'
    PINK = '\033[38;5;206m'
    PURPLE = '\033[35;48m'
    RED = '\033[31;48m'
    YELLOW = '\033[33;48m'
    WHITE = '\033[37;48m'


YES: str = "Yes"


def round_to(value: int, base: int) -> int:
    return base * round(value/base)


def how_accurate(percent_complete: float) -> int:
    if percent_complete < 20.0:
        return 60
    if percent_complete < 40.0:
        return 30
    if percent_complete < 60.0:
        return 15
    if percent_complete < 80.0:
        return 5
    return 1


def is_user_attribute_set_to_yes(file_name: str, attr_name: str) -> bool:
    attr_names = (attr for attr in os.listxattr(file_name) if attr.startswith("user."))
    for n in attr_names:
        if n == f"user.{attr_name}" and YES == str(os.getxattr(file_name, n), "UTF-8"):
            return True
    return False


def set_user_attribute_to_yes(file_name: str, attr_name: str) -> None:
    os.setxattr(file_name, f"user.{attr_name}", bytes(YES, "UTF-8"))


def duplicate_xattrs(from_fn: str, to_fn: str, strip_attrs: [str] = None) -> None:
    strip: [str] = []
    if strip_attrs is not None:
        for attr in strip_attrs:
            strip.append(f"user.{attr}")

    attr_names = (attr for attr in os.listxattr(from_fn) if attr.startswith("user."))
    for n in attr_names:
        if n not in strip:
            os.setxattr(to_fn, n, os.getxattr(from_fn, n))


def clean_file_name(orig_file_name: str) -> str:
    file_name_idx: int = orig_file_name.rfind("/")
    if file_name_idx < 0:
        dir_loc: str = ""
        file: str = orig_file_name
    else:
        dir_loc: str = orig_file_name[0:file_name_idx]
        file: str = orig_file_name[file_name_idx+1:]

    chars_to_remove: set = {'"', "'"}
    new_file_name: str = ''.join(ch for ch in file if ch not in chars_to_remove)

    if file_name_idx < 0:
        return new_file_name
    else:
        return os.path.join(dir_loc, new_file_name)


def replace_file(orig_file_name: str, replace_with_file_name: str, strip_attrs: [str] = None) -> None:
    print(f"    {Color.BOLD}{Color.BLUE}Replacing{Color.END} video file.")
    log.info(f"Replace {orig_file_name} with the new, updated version.")
    backup_file_name: str = f"{orig_file_name}.backup"
    # REPLACE ORIGINAL FILE WITH NEW, BETTER ONE
    # 1 -> move original to .backup
    sh.move(orig_file_name, backup_file_name)
    # 2 -> move temp to original
    while True:
        try:
            sh.copyfile(replace_with_file_name, orig_file_name)
            break
        except PermissionError:
            print("Permission error ... retry one time after 1 minute.")
            time.sleep(65)
        except Exception as e:
            log.exception(e)
            print(f"Exception: {type(e)} --> {e}")
            raise e

    # 3 -> copy file attributes provided by the user
    duplicate_xattrs(backup_file_name, orig_file_name, strip_attrs)
    # 4 -> remove backup file
    path.Path.unlink(path.Path(backup_file_name))
    path.Path.unlink(path.Path(replace_with_file_name))
    log.info(f"Completed update of {orig_file_name}.")


def ffmpeg_output_before_transcode(output) -> [str]:
    line_count: int = 0
    pre_transcode_text: [str] = []
    started_transcoding: bool = False
    while not started_transcoding:
        ffmpeg_output = output.readline()
        if len(ffmpeg_output) > 3:
            pre_transcode_text.append(ffmpeg_output)
        started_transcoding = is_ffmpeg_update(ffmpeg_output)

        line_count += 1
        if line_count > TOO_MANY_LINES_BEFORE_PROGRESS:
            log.error("Cannot find beginning of ffmpeg processing.")
            log.error(pre_transcode_text)
            raise MediaServerUtilityException("Cannot find beginning of ffmpeg processing.")

    return pre_transcode_text


def temp_results_file_name(file_name: str) -> str:
    extension: str = file_name[-4:]
    if extension != ".mp4" and extension != ".mkv":
        raise MediaServerUtilityException(f"{extension} is not a valid file type to transcode. (.mp4 or .mkv only)")

    return f"temp-output{extension}"


def find_duration(text: [str]) -> float:
    for line in text:
        if is_ffmpeg_duration_line(line):
            return_val: float = get_ffmpeg_duration(line)

            log.debug(f"Movie length: {return_val:.1f} seconds.")
            return return_val

    return 0


def text_to_secs(text: str) -> float:
    """ Convert string such as 01:14:30.54 (hh:mm:ss.xx) into 4470.54 """
    if len(text) < 11 or text[2] != ":" or text[5] != ":":
        log.warning(f"{text} is an invalid time duration. Using 0.")
        return 0.0

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


def pretty_progress_with_timer(start_ts: dt.datetime, current: float, total: float) -> str:
    current_ts: dt.datetime = dt.datetime.now()
    elapsed_time: dt.timedelta = current_ts - start_ts
    progress: float = 100 * current / total

    time_worked: int = elapsed_time.seconds
    time_left: int = int(time_worked * (100.0 - progress) / progress)
    accuracy: int = how_accurate(progress)
    approximate_time: int = round_to(time_left, accuracy) + accuracy

    mins: int = approximate_time // 60
    secs: int = approximate_time % 60

    return f"{Color.GREEN}{progress:5.1f}%{Color.END} ({current:,.1f} of " \
           f"{Color.CYAN}{total:,.1f}{Color.END})" \
           f"  {Color.BOLD}{mins:02}:{secs:02}{Color.END}    "


def is_ffmpeg_update(text: str) -> bool:
    idx = text.find(" time=")
    return idx > 0


def ffmpeg_get_current_time(text: str) -> float:
    idx = text.find(" time=")
    if idx < 0:
        raise MediaServerUtilityException(f"{text} is not a valid ffmpeg progress update.")
    time_in_text = text[idx+6:idx+6+12]
    return text_to_secs(time_in_text)


def all_codecs_for(file_name: str) -> [str]:
    result: proc.CompletedProcess = proc.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries",
            "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_name,
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        raise MediaServerUtilityException(f"An error occurred while probing {file_name}. " +
                                          f"Return code: {result.returncode}"
                                          )

    return_val: [str] = []

    for codec in str(result.stdout, 'UTF-8').split("\n"):
        return_val.append(codec)

    return return_val


def get_next_key_frame_after_timestamp(video_file: str, loc_in_video: float) -> float:
    start: float = loc_in_video
    stop: float = loc_in_video + KEY_FRAME_SCAN_DURATION
    key_frames: [float] = []

    ffmpeg_args: [str] = [FFMPEG_FILE,
                          "-hide_banner",
                          "-ss", f"{start}",
                          "-to", f"{stop}",
                          "-skip_frame", "nokey",
                          "-i", video_file,
                          "-an",
                          "-vf", "showinfo",
                          "-f", "null",
                          "-",
                          ]

    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        for line in process.stderr:
            start_idx: int = line.find("pts_time:")
            if start_idx >= 0:
                end_idx: int = line.find(" ", start_idx + 9)
                timestamp: float = float(line[start_idx+9: end_idx])
                key_frames.append(timestamp)

    if len(key_frames) == 0:
        return loc_in_video

    return loc_in_video + key_frames[0] - 0.25
