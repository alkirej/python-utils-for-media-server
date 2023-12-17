import logging as log
import optparse as op
import pathlib as path
import shutil as sh
import subprocess as proc
import sys

import msutils as msu

FFMPEG_FILE = "ffmpeg"
INPUTS_FILE_NAME = "ffmpeg_inputs_file.txt"
TEMP_FILE = "temp_output.mkv"

if "__main__" == __name__:
    # SETUP LOGGER BEFORE IMPORTS SO THEY CAN USE THESE SETTINGS
    log.basicConfig(filename="remove-commercials.log",
                    filemode="w",
                    format="%(asctime)s %(filename)15.15s %(funcName)15.15s %(levelname)5.5s %(lineno)4.4s %(message)s",
                    datefmt="%Y%m%d-%H:%M:%S"
                    )
    log.getLogger().setLevel(log.DEBUG)


def add_chapter_to_inputs(filename: str, chapter_text: [str]) -> str:
    time_line = chapter_text[0]
    start_idx = time_line.find(" start ")
    end_idx = time_line.find(" end ")

    if start_idx < 0 or end_idx < 0:
        raise RuntimeError(f"Cannot find start/end times in: {time_line}")

    start_time = time_line[start_idx+7:].split(",")[0]
    end_time = time_line[end_idx+5:]

    result = f"file '{filename}'\ninpoint {start_time}\noutpoint {end_time}"
    return result


def remove_commercials(inputs_file_name: str, temp_results_file_name: str):
    ffmpeg_args = [FFMPEG_FILE,
                   "-y",
                   "-safe", "0",
                   "-f", "concat",
                   "-i", inputs_file_name,
                   "-c", "copy",
                   "-c:s", "text",
                   temp_results_file_name
                   ]
    print()
    print("REMOVING COMMERCIALS ...")
    print()
    log.debug(f"Remove commercials from latest video file.")
    proc.run(ffmpeg_args)


def examine_file(file_name: str, inputs_file_name: str) -> [(float, float)]:
    duration: float = -1
    chapters_sect: bool = False
    chapters_done: bool = False
    current_chapter_text: [str] = []
    delete_some_video = False

    ffmpeg_args = [FFMPEG_FILE,
                   "-i", file_name,
                   "-vf", "freezedetect",
                   "-map", "0:v:0",
                   "-f", "null",
                   "-"
                   ]

    with open(inputs_file_name, "w") as inputs_file:
        with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
            try:
                for output_line in process.stderr:
                    to_log = output_line.strip()
                    log.debug(to_log)

                    if msu.is_ffmpeg_update(output_line):
                        current_loc = msu.ffmpeg_get_current_time(output_line)
                        percent_progress = msu.pretty_progress(current_loc, duration)
                        print(f"Progress: {percent_progress}", end="\r")
                        log.debug(f"Progress: {percent_progress}")

                    elif duration < 0:
                        if msu.is_ffmpeg_duration_line(output_line):
                            duration = msu.get_ffmpeg_duration(output_line)

                    elif not chapters_done:
                        if not chapters_sect:
                            chapters_sect = msu.is_ffmpeg_chapter_header(output_line)

                        else:
                            current_chapter_text.append(output_line)
                            current_line_count = len(current_chapter_text)
                            if 1 == current_line_count:
                                chapters_done = not msu.is_ffmpeg_chapter(output_line)
                            elif 3 == current_line_count:
                                if msu.is_ffmpeg_chapter_a_commercial(current_chapter_text):
                                    delete_some_video = True
                                else:
                                    input_text = add_chapter_to_inputs(file_name, current_chapter_text)
                                    inputs_file.write(input_text)
                                # look for next chapter
                                current_chapter_text = []

            except msu.MediaServerUtilityException as exc:
                print(exc)
                log.exception(exc)
                process.kill()
                process.wait()
                sys.exit(1)

    return delete_some_video


def main():
    parser = op.OptionParser()
    _, vals = parser.parse_args()
    file_to_process = vals[0]

    if len(vals) != 1:
        print("Exactly one argument (file-name) expected.")
        sys.exit(1)

    found_commercials = examine_file(file_to_process, INPUTS_FILE_NAME)
    if found_commercials:
        remove_commercials(INPUTS_FILE_NAME, TEMP_FILE)

        backup_file_name: str = f"{file_to_process}.backup"

        # RENAME FILES
        # 1 -> move original to .bak
        sh.move(file_to_process, backup_file_name)
        # 2 -> move temp to original
        sh.move(TEMP_FILE, file_to_process)

        # 3 -> remove backup file
        path.Path.unlink(path.Path(backup_file_name))

    # remove inputs file
    path.Path.unlink(path.Path(INPUTS_FILE_NAME))


if "__main__" == __name__:
    main()
