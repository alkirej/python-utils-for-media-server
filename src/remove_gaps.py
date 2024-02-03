import datetime as dt
import logging as log
import optparse as op
import os
import pathlib as path
import subprocess as proc
import sys

import msutils as msu

FFMPEG_FILE = "ffmpeg"
INPUTS_FILE_NAME = "ffmpeg_inputs_file.txt"
TEMP_FILE = "temp_output.mkv"

NO_GAPS_FIELD = "checked-for-gaps"
NO_GAPS_VALUE = "Yes"

if "__main__" == __name__:
    # SETUP LOGGER BEFORE IMPORTS SO THEY CAN USE THESE SETTINGS
    log.basicConfig(filename="remove-freezes-and-commercials.log",
                    filemode="w",
                    format="%(asctime)s %(filename)15.15s %(funcName)15.15s %(levelname)5.5s %(lineno)4.4s %(message)s",
                    datefmt="%Y%m%d-%H:%M:%S"
                    )
    log.getLogger().setLevel(log.INFO)


def remove_gaps(gaps: msu.MovieSections):
    gaps.create_input_file_for_video_gaps(INPUTS_FILE_NAME)
    output_file_name: str = msu.temp_results_file_name(gaps.file_name)

    ffmpeg_args = ["nice",
                   FFMPEG_FILE,
                   "-y",
                   "-safe", "0",
                   "-f", "concat",
                   "-i", INPUTS_FILE_NAME,
                   "-c", "copy",
                   "-c:s", "copy",
                   output_file_name
                   ]
    print(f"    {msu.Color.BLUE}{msu.Color.BOLD}Removing{msu.Color.END} "
          f"{msu.Color.BOLD}{msu.Color.GREEN}{gaps.total_time():.1f}{msu.Color.END} seconds from movie."
          )
    log.info(f"Removing {gaps.total_time():.1f} seconds of gaps (commercials and freezes) from {gaps.file_name}.")
    if gaps.total_time() > 15:
        for x in gaps.section_list:
            print(f"        ...   {msu.Color.BOLD}{msu.Color.CYAN}{x.start:>8,.1f}{msu.Color.END}-{x.end:>8,.1f}: " +
                  f"{msu.Color.BOLD}{msu.Color.YELLOW}{x.comment}{msu.Color.END}"
                  )

    current: float = 0.0
    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        for line in process.stderr:
            if msu.is_ffmpeg_update(line):
                current = msu.ffmpeg_get_current_time(line)
                print(f"        Removing: {msu.Color.BOLD}{msu.Color.CYAN}{current:,.1f}{msu.Color.END}", end="\r")

    print(f"        Removing: {msu.Color.BOLD}{msu.Color.CYAN}{current:,.1f}{msu.Color.END}")
    log.info(f"Gap removal complete for {gaps.file_name}.")
    path.Path.unlink(path.Path(INPUTS_FILE_NAME))


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
            log.info(f"Movie chapter found: {curr_chapter.title} ({curr_chapter.section.start:.1f}-" +
                     f"{curr_chapter.section.end:.1f})"
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
    start_ts: dt.datetime = dt.datetime.now()
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
            percent_progress = msu.pretty_progress_with_timer(start_ts, current_loc, duration)
            print(f"    Searching: {msu.Color.BOLD}{msu.Color.GREEN}{percent_progress}{msu.Color.END}", end="\r")

    percent_progress = msu.pretty_progress(duration, duration)
    print(f"    {msu.Color.GREEN}Complete: {msu.Color.BOLD}{percent_progress}{msu.Color.END}          ")
    return found_video_freezes & found_silences


def find_commercials_and_freezes(file_name: str) -> msu.MovieSections:
    commercials: msu.MovieSections = msu.MovieSections(file_name)

    ffmpeg_args = ["nice",
                   FFMPEG_FILE,
                   "-i", file_name,
                   "-vf", "freezedetect=n=0.001",
                   "-map", "0:v:0",
                   "-af", "silencedetect",
                   "-map", "0:a:0?",
                   "-f", "null",
                   "-",
                   ]

    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        try:
            pre_transcode_text: [str] = msu.ffmpeg_output_before_transcode(process.stderr)
            duration: float = msu.find_duration(pre_transcode_text)
            chapters: [msu.MovieChapter] = find_movie_chapters(pre_transcode_text)
            for movie_ch in filter(lambda ch: ch.title == "Advertisement", chapters):
                commercials.add_section(movie_ch.section)

            vid_freezes: msu.MovieSections = look_for_freezes_and_progress(file_name, process.stderr, duration)

        except msu.MediaServerUtilityException as exc:
            print(exc)
            log.exception(exc)
            process.kill()
            process.wait()
            raise exc

    all_gaps: msu.MovieSections = commercials | vid_freezes
    return all_gaps


def gaps_already_removed(file_name: str) -> bool:
    attr_names = (attr for attr in os.listxattr(file_name) if attr.startswith("user."))
    for n in attr_names:
        if n == f"user.{NO_GAPS_FIELD}" and NO_GAPS_VALUE == str(os.getxattr(file_name, n), "UTF-8"):
            log.info(f"{file_name} has already been processed by gap remover.")
            print(f"    {file_name} {msu.Color.BOLD}{msu.Color.DOUBLE_UNDERLINE}has already been processed "
                  f"{msu.Color.END}by the gap remover."
                  )
            return True
    return False


def video_gap_removal(file_name: str) -> None:
    if gaps_already_removed(file_name):
        return

    log.info(f"Finding gaps in: {file_name}")
    print(f"{msu.Color.BOLD}{msu.Color.BLUE}Finding gaps{msu.Color.END} in: {file_name}")

    try:
        gaps: msu.MovieSections = find_commercials_and_freezes(file_name)
    except msu.MediaServerUtilityException:
        # Exception should have been logged already.
        return

    if len(gaps.section_list) > 0:
        remove_gaps(gaps)
        msu.replace_file(file_name,
                         msu.temp_results_file_name(file_name),
                         [NO_GAPS_FIELD]
                         )
    else:
        log.info("Found no gaps to remove.")
        print(f"    Found no gaps to remove in {file_name}.")

    # Mark file as processed.
    os.setxattr(file_name, f"user.{NO_GAPS_FIELD}", bytes(NO_GAPS_VALUE, "UTF-8"))


def walk_dir_removing_gaps(dir_name: str) -> None:
    for (current_dir, dirs, files) in os.walk(dir_name):
        dirs.sort()
        for f in sorted(files):
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
