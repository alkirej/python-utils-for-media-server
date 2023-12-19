import datetime as dt
import logging as log
import optparse as op
import os
import pathlib as path
import shutil as sh
import subprocess as proc
import sys

import msutils as msu

FFMPEG_FILE = "ffmpeg-local-copy-2"
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
    print(f"{msu.Color.RED}... REMOVE COMMERCIALS AND FREEZES ...{msu.Color.END}")
    print(f"{msu.Color.RED}--------------------------------------{msu.Color.END}")
    print(f"Removing {msu.Color.GREEN}{gaps.total_time():.1f}{msu.Color.END} seconds from movie.")
    log.debug(f"Removing {gaps.total_time():.1f} seconds of gaps (commercials and freezes) from {gaps.file_name}.")

    current: float = 0.0
    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        for line in process.stderr:
            if msu.is_ffmpeg_update(line):
                current = msu.ffmpeg_get_current_time(line)
                print(f"Removal Progress: {msu.Color.CYAN}{current:,.1f}{msu.Color.END}", end="\r")

    print(f"Removal Progress: {msu.Color.CYAN}{current:,.1f}{msu.Color.END}")
    log.debug(f"Gap removal complete for {gaps.file_name}.")
    path.Path.unlink(path.Path(INPUTS_FILE_NAME))


def find_duration(text: [str]) -> float:
    for line in text:
        if msu.is_ffmpeg_duration_line(line):
            return_val: float = msu.get_ffmpeg_duration(line)
            log.debug(f"Movie length: {return_val:.1f} seconds.")
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
            log.debug(
                f"Movie chapter found: {curr_chapter.title} ({curr_chapter.section.start:.1f}-{curr_chapter.section.end:.1f})"
                      )
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


def process_silence_output(output: str) -> (float | None, float | None):
    start_info: bool = output.find("silence_start: ") >= 0
    end_info: bool = output.find("silence_end: ") >= 0

    time: float = float(output.split(" ")[4].strip())
    if start_info:
        return time, None
    elif end_info:
        return None, time

    return None, None


def is_silence_data(output: str) -> bool:
    idx = output.find("[silencedetect")
    return idx >= 0


def look_for_freezes_and_progress(file_name: str, output, duration: float = 0.0) -> [msu.MovieSection]:
    found_video_freezes: msu.MovieSections = msu.MovieSections(file_name, "video")
    found_silences: msu.MovieSections = msu.MovieSections(file_name, "audio")

    current_freeze_start: float | None = None
    current_silence_start: float | None = None

    for ffmpeg_output in output:
        # MONITOR FOR A FREEZE
        if is_freeze_data(ffmpeg_output):
            (start_f, end_f) = process_freeze_output(ffmpeg_output)

            # CHECK FOR EXCEPTIONS
            if start_f is not None and end_f is not None:
                raise msu.MediaServerUtilityException(f"Freeze start and stop received simultaneously.")
            if start_f is not None:
                if current_freeze_start is not None:
                    raise msu.MediaServerUtilityException(f"Two consecutive freeze starts encountered. End expected.")
                # FREEZE START DATA RECEIVED
                current_freeze_start = start_f
            elif end_f is not None:
                if current_freeze_start is None:
                    raise msu.MediaServerUtilityException(f"Freeze end without a start.")

                # FREEZE END DATA RECEIVED
                freeze_info: msu.MovieSection = msu.MovieSection(current_freeze_start,
                                                                 end_f,
                                                                 f"{current_freeze_start}-{end_f}"
                                                                 )
                found_video_freezes.add_section(freeze_info)
                log.debug(f"Freeze found from {current_freeze_start} to {end_f}")
                current_freeze_start = None

        elif is_silence_data(ffmpeg_output):
            (start_s, end_s) = process_silence_output(ffmpeg_output)

            # CHECK FOR EXCEPTIONS
            if start_s is not None and end_s is not None:
                raise msu.MediaServerUtilityException(f"Silence start and stop received simultaneously.")
            if start_s is not None:
                if current_silence_start is not None:
                    raise msu.MediaServerUtilityException(f"Two consecutive silence starts encountered. End expected.")
                # FREEZE START DATA RECEIVED
                current_silence_start = start_s
            elif end_s is not None:
                if current_silence_start is None:
                    raise msu.MediaServerUtilityException(f"Silence end without a start.")
                silence_info: msu.MovieSection = msu.MovieSection(current_silence_start,
                                                                  end_s,
                                                                  f"{current_silence_start}-{end_s}"
                                                                  )
                found_silences.add_section(silence_info)
                log.debug(f"Silence found from {current_silence_start:.1f} to {end_s:.1f} secs")
                current_silence_start = None

        # MONITOR FOR PROGRESS UPDATES
        elif msu.is_ffmpeg_update(ffmpeg_output):
            current_loc = msu.ffmpeg_get_current_time(ffmpeg_output)
            percent_progress = msu.pretty_progress(current_loc, duration)
            print(f"Search Progress: {msu.Color.GREEN}{percent_progress}{msu.Color.END}", end="\r")

    percent_progress = msu.pretty_progress(duration, duration)
    print(f"Search Progress: {msu.Color.GREEN}{percent_progress}{msu.Color.END}")
    return found_video_freezes & found_silences


def ffmpeg_output_before_transcode(output) -> [str]:
    pre_transcode_text: [str] = []
    started_transcoding: bool = False
    while not started_transcoding:
        ffmpeg_output = output.readline()
        pre_transcode_text.append(ffmpeg_output)
        started_transcoding = msu.is_ffmpeg_update(ffmpeg_output)

    return pre_transcode_text


def find_commercials_and_freezes(file_name: str) -> msu.MovieSections:
    commercials: msu.MovieSections = msu.MovieSections(file_name)

    ffmpeg_args = [FFMPEG_FILE,
                   "-i", file_name,
                   "-vf", "freezedetect=n=0.001",
                   "-map", "0:v:0",
                   "-af", "silencedetect",
                   "-map", "0:a:0",
                   "-f", "null",
                   "-"
                   ]

    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        try:
            pre_transcode_text: [str] = ffmpeg_output_before_transcode(process.stderr)
            duration: float = find_duration(pre_transcode_text)
            chapters: [msu.MovieChapter] = find_movie_chapters(pre_transcode_text)
            for movie_ch in filter(lambda ch: ch.title == "Advertisement", chapters):
                commercials.add_section(movie_ch.section)

            vid_freezes: msu.MovieSections = look_for_freezes_and_progress(file_name, process.stderr, duration)

        except msu.MediaServerUtilityException as exc:
            print(exc)
            log.exception(exc)

    log.debug("COMMERCIALS")
    for x in commercials.section_list:
        log.debug(x)
    log.debug("FREEZES")
    for x in vid_freezes.section_list:
        log.debug(x)

    log.debug("FINAL RESULTS")
    all_gaps: msu.MovieSections = commercials | vid_freezes
    for x in all_gaps.section_list:
        log.debug(x)

    return all_gaps


def replace_file(orig_file_name: str, replace_with_file_name: str) -> None:
    print(f"{msu.Color.BLUE}Replace{msu.Color.END} {orig_file_name} with the new, updated version.")
    log.debug(f"Replace {orig_file_name} with the new, updated version.")
    backup_file_name: str = f"{orig_file_name}.backup"
    log.debug(f"Replace {orig_file_name} with the new, updated version.")
    # REPLACE ORIGINAL FILE WITH NEW, BETTER ONE
    # 1 -> move original to .backup
    sh.move(orig_file_name, backup_file_name)
    # 2 -> move temp to original
    sh.move(replace_with_file_name, orig_file_name)
    # 3 -> remove backup file
    path.Path.unlink(path.Path(backup_file_name))
    log.debug(f"Completed update of {orig_file_name}.")


def video_gap_removal(file_name: str) -> None:
    current_timestamp: dt.datetime = dt.datetime.now()
    print(f"\n{current_timestamp.strftime('%m/%d/%Y')} {msu.Color.PURPLE}{current_timestamp.strftime('%H:%M:%S')}{msu.Color.END}")

    log.info(f"Removing gaps in: {file_name}")
    print(f"Removing gaps in: {msu.Color.YELLOW}{file_name}{msu.Color.END}")

    gaps: msu.MovieSections = find_commercials_and_freezes(file_name)

    if len(gaps.section_list) > 0:
        remove_gaps(gaps)
        replace_file(file_name, temp_results_file_name(gaps.file_name))
    else:
        log.debug(f"Found no gaps to remove in {file_name}.")
        print(f"Found no gaps to remove in {file_name}.")


def walk_dir_removing_gaps(dir_name: str) -> None:
    for (current_dir, _, files) in os.walk(dir_name):
        for f in files:
            if f.endswith(".mp4") or f.endswith(".mkv"):
                full_path = os.path.join(current_dir, f)
                video_gap_removal(full_path)


def main():
    parser = op.OptionParser()
    _, vals = parser.parse_args()
    path_to_process: str = vals[0]

    if len(vals) != 1:
        print("Exactly one argument (file-name) expected.")
        sys.exit(1)
    else:
        if path_to_process.endswith(".mp4") or path_to_process.endswith(".mkv"):
            video_gap_removal(path_to_process)
        else:
            if os.path.isdir(path_to_process):
                walk_dir_removing_gaps(path_to_process)
            else:
                log.error(f"{path_to_process} is not a valid video file or directory.")
                print(f"{path_to_process} is not a valid video file or directory.")
                sys.exit(1)


if "__main__" == __name__:
    main()
    # test()
