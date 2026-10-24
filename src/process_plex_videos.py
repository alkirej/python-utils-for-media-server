import datetime as dt
import logging as log
import optparse as op
import os
import shutil
import sys

import msutils as msu
from remove_gaps import video_gap_removal
from transcode_to_hevc import transcode, get_ffmpeg_version, EXTENSIONS_TO_PROCESS

MAX_RETRIES: int = 1 # 0

if "__main__" == __name__:
    # SETUP LOGGER BEFORE IMPORTS SO THEY CAN USE THESE SETTINGS
    log.basicConfig(filename="process-plex-videos.log",
                    filemode="a",
                    format="%(asctime)s %(filename)15.15s %(funcName)15.15s %(levelname)5.5s %(lineno)4.4s %(message)s",
                    datefmt="%Y%m%d-%H:%M:%S"
                    )
    log.getLogger().setLevel(log.DEBUG)


def process_single_file(file_name: str, ffmpeg_version: str, copy_file: bool = True) -> None:
    current_timestamp: dt.datetime = dt.datetime.now()
    print(f"{msu.Color.OVERLINE}{msu.Color.UNDERLINE}{msu.Color.BOLD}{current_timestamp.strftime('%m/%d/%Y')} "
          f"{msu.Color.BOLD}{msu.Color.PURPLE}{current_timestamp.strftime('%H:%M:%S')} "
          f"{msu.Color.YELLOW}{msu.Color.BOLD}{file_name}{msu.Color.END}"
          )

    retry_count: int = 0
    success: bool = False

    clean_file_name: str = msu.clean_file_name(file_name)
    shutil.move(file_name, clean_file_name)
    while not success and retry_count <= MAX_RETRIES:
        try:
            transcode(clean_file_name, ffmpeg_version, copy_file)
            video_gap_removal(clean_file_name)
            success = True

        except msu.MediaServerUtilityException as msue:
            retry_count += 1
            log.error(msue)
            log.exception(msue)

            if retry_count >= MAX_RETRIES:
                log.warning(f"Received exception processing {clean_file_name}. " +
                            f"Skipping to next.  This file will need to be reprocessed."
                            )
                print(f"Error processing {clean_file_name}. {msu.Color.RED}GIVING UP{msu.Color.END}")
            else:
                log.info(f"Received exception processing {clean_file_name}.  RETRY # {retry_count}")
                print(f"\n    Error processing {file_name}.  " +
                      f"RETRY {msu.Color.BOLD}{msu.Color.PURPLE}#{retry_count}{msu.Color.END}"
                      )


def process_dir_tree(dir_name: str, ffmpeg_version: str, file_copy: bool = True) -> None:
    for (current_dir, dirs, files) in os.walk(dir_name):
        dirs.sort()
        for f in sorted(files):
            if f.endswith( EXTENSIONS_TO_PROCESS ):
                full_path = os.path.join(current_dir, f)
                process_single_file(full_path, ffmpeg_version, file_copy)


def main():
    parser = op.OptionParser()
    parser.add_option("-v", "--ffmpeg_version", help="supported versions are 6 and 8", default="8")
    parser.add_option("-c", "--combine", help="Combine all arguments into single file name", default=False, action="store_true", dest="combine")
    parser.add_option("-n", "--no_file_copy", help="skip speed up copy locally", default=True, action="store_false", dest="file_copy")

    opts, vals = parser.parse_args()
    ffmpeg_version = get_ffmpeg_version(opts)
    combine = opts.combine

    try:
        if combine:
            vals = [" ".join(vals)]
        path_to_process: str = vals[0]
    except IndexError:
        pass

    if len(vals) != 1:
        print("Exactly one argument (file-name/directory) expected.")
        sys.exit(1)
    else:
        if path_to_process.endswith(".mp4") or path_to_process.endswith(".mkv"):
            process_single_file(path_to_process, ffmpeg_version, opts.file_copy)
        else:
            if os.path.isdir(path_to_process):
                process_dir_tree(path_to_process, ffmpeg_version, opts.file_copy)
            else:
                log.error(f"{path_to_process} is not a valid video file or directory.")
                print(f"{path_to_process} is not a valid video file or directory.")
                sys.exit(1)


if "__main__" == __name__:
    main()
