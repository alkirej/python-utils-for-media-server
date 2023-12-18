import logging as log
import optparse as op
import pathlib as path
import shutil as sh
import subprocess as proc
import sys

import msutils as msu
# from msutils import MovieSections

FFMPEG_FILE = "ffmpeg"
INPUTS_FILE_NAME = "ffmpeg_inputs_file.txt"
TEMP_FILE = "temp_output.mkv"

if "__main__" == __name__:
    # SETUP LOGGER BEFORE IMPORTS SO THEY CAN USE THESE SETTINGS
    log.basicConfig(filename="remove-freezes-and-commercials.log",
                    filemode="w",
                    format="%(asctime)s %(filename)15.15s %(funcName)15.15s %(levelname)5.5s %(lineno)4.4s %(message)s",
                    datefmt="%Y%m%d-%H:%M:%S"
                    )
    log.getLogger().setLevel(log.DEBUG)


def temp_results_file_name(file_name: str) -> str:
    extension: str = file_name[-4:]
    if extension != ".mp4" and extension != ".mkv":
        raise msu.MediaServerUtilityException(f"{extension} is not a valid file type to transcode. (.mp4 or .mkv only)")

    return f"temp-output{extension}"


# def remove_commercials(inputs_file_name: str, temp_results_file_name: str):
def remove_gaps(gaps: msu.MovieSections):
    gaps.create_input_file_for_video_gaps(INPUTS_FILE_NAME)

    ffmpeg_args = [FFMPEG_FILE,
                   "-y",
                   "-safe", "0",
                   "-f", "concat",
                   "-i", INPUTS_FILE_NAME,
                   "-c", "copy",
                   "-c:s", "copy",
                   temp_results_file_name(gaps.file_name)
                   ]
    print()
    print("... REMOVING COMMERCIALS AND FREEZES ...")
    print()
    print(ffmpeg_args)
    log.debug(f"Removing gaps (commercials and freezes) from latest video file.")
    proc.run(ffmpeg_args)
    log.debug(f"Gap removal complete.")

    path.Path.unlink(path.Path(INPUTS_FILE_NAME))


def find_duration(text: [str]) -> float:
    for line in text:
        if msu.is_ffmpeg_duration_line(line):
            return_val: float = msu.get_ffmpeg_duration(line)
            log.debug(f"Movie length: {return_val} seconds.")
            return return_val

    return 0


def find_movie_chapters(text: [str]) -> [msu.MovieChapter]:
    chapters: [msu.MovieChapter] = []
    i = 0

    for i, line in enumerate(text):
        if msu.is_ffmpeg_chapter_header(line):
            break

    for j in range(i+1, len(text), 3):
        if msu.is_ffmpeg_chapter(text[j]):
            curr_chapter: msu.MovieChapter = msu.MovieChapter([text[j], text[j+1], text[j+2]])
            chapters.append(curr_chapter)
            log.debug(f"Movie chapter found: {curr_chapter.title}")
        else:
            break

    return chapters


def is_freeze_data(output) -> bool:
    idx = output.find("lavfi.freezedetect.freeze_")
    return idx >= 0


def get_freeze_location(output: str) -> float:
    broken_line: [str] = output.split(":")
    if len(broken_line) < 2:
        raise msu.MediaServerUtilityException(f"Invalid freeze line supplied to get_freeze_location. {output}")
    return float(broken_line[1].strip())


def process_freeze_output(output) -> (float | None, float | None):
    start_info: bool = output.find("lavfi.freezedetect.freeze_start") > 0
    end_info: bool = output.find("lavfi.freezedetect.freeze_end") > 0

    if start_info:
        # FOUND FREEZE START TIME
        return get_freeze_location(output), None
    elif end_info:
        # FOUND FREEZE END TIME
        return None, get_freeze_location(output)

    # FREEZE DURATION OR OTHER FREEZE INFO THAT WE DON'T NEED.
    return None, None


def look_for_freezes_and_progress(output, duration: float = 0.0) -> [msu.MovieSection]:
    found_freezes: [msu.MovieSection] = []
    current_freeze_start: float | None = None

    for ffmpeg_output in output:
        # MONITOR FOR A FREEZE
        if is_freeze_data(ffmpeg_output):
            (start, end) = process_freeze_output(ffmpeg_output)

            # CHECK FOR EXCEPTIONS
            if start is not None and end is not None:
                raise msu.MediaServerUtilityException(f"Freeze start and stop received simultaneously.")
            if start is not None:
                if current_freeze_start is not None:
                    raise msu.MediaServerUtilityException(f"Two consecutive freeze starts encountered. End expected.")
                # FREEZE START DATA RECEIVED
                current_freeze_start = start

            elif end is not None:
                # FREEZE END DATA RECEIVED
                freeze_info: msu.MovieSection = msu.MovieSection(current_freeze_start, end)
                found_freezes.append(freeze_info)
                log.debug(f"Freeze found from {current_freeze_start} to {end}")
                current_freeze_start = None

        # MONITOR FOR PROGRESS UPDATES
        elif msu.is_ffmpeg_update(ffmpeg_output):
            current_loc = msu.ffmpeg_get_current_time(ffmpeg_output)
            percent_progress = msu.pretty_progress(current_loc, duration)
            print(f"Progress: {percent_progress}", end="\r")

    print(f"Progress: 100.0%")
    return found_freezes


def ffmpeg_output_before_transcode(output) -> [str]:
    pre_transcode_text: [str] = []
    started_transcoding: bool = False
    while not started_transcoding:
        ffmpeg_output = output.readline()
        pre_transcode_text.append(ffmpeg_output)
        started_transcoding = msu.is_ffmpeg_update(ffmpeg_output)

    return pre_transcode_text


def find_commercials_and_freezes(file_name: str) -> msu.MovieSections:
    sections_to_remove: msu.MovieSections = msu.MovieSections(file_name)

    ffmpeg_args = [FFMPEG_FILE,
                   "-i", file_name,
                   "-vf", "freezedetect",
                   "-map", "0:v:0",
                   "-f", "null",
                   "-"
                   ]

    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        try:
            pre_transcode_text: [str] = ffmpeg_output_before_transcode(process.stderr)
            duration: float = find_duration(pre_transcode_text)
            chapters: [msu.MovieChapter] = find_movie_chapters(pre_transcode_text)
            for movie_ch in filter(lambda ch: ch.title == "Advertisement", chapters):
                sections_to_remove.add_section(movie_ch.section)

            freezes: [msu.MovieSection] = look_for_freezes_and_progress(process.stderr, duration)
            for f in freezes:
                sections_to_remove.add_section(f)

            print(sections_to_remove.section_list)

        except msu.MediaServerUtilityException as exc:
            print(exc)
            log.exception(exc)

    return sections_to_remove


def replace_file(orig_file_name: str, replace_with_file_name: str) -> None:
    backup_file_name: str = f"{orig_file_name}.backup"

    # REPLACE ORIGINAL FILE WITH NEW, BETTER ONE
    # 1 -> move original to .backup
    sh.move(orig_file_name, backup_file_name)
    # 2 -> move temp to original
    sh.move(replace_with_file_name, orig_file_name)
    # 3 -> remove backup file
    path.Path.unlink(path.Path(backup_file_name))


def video_gap_removal(file_name: str) -> None:
    gaps: msu.MovieSections = find_commercials_and_freezes(file_name)
    print(gaps)
    print(len(gaps.section_list))
    if len(gaps.section_list) > 0:
        gaps.create_input_file_for_video_gaps(INPUTS_FILE_NAME)
        remove_gaps(gaps)
        replace_file(file_name, temp_results_file_name(gaps.file_name))


def main():
    parser = op.OptionParser()
    _, vals = parser.parse_args()
    file_to_process = vals[0]

    if len(vals) != 1:
        print("Exactly one argument (file-name) expected.")
        sys.exit(1)
    else:
        video_gap_removal(file_to_process)


if "__main__" == __name__:
    main()
