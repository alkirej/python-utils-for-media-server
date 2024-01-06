import datetime as dt
import logging as log
import optparse as op
import os
import shutil
import sys

import msutils as msu
from remove_gaps import video_gap_removal
from transcode_to_hevc import transcode

MAX_RETRIES: int = 5

if "__main__" == __name__:
    # SETUP LOGGER BEFORE IMPORTS SO THEY CAN USE THESE SETTINGS
    log.basicConfig(filename="process-plex-videos.log",
                    filemode="w",
                    format="%(asctime)s %(filename)15.15s %(funcName)15.15s %(levelname)5.5s %(lineno)4.4s %(message)s",
                    datefmt="%Y%m%d-%H:%M:%S"
                    )
    log.getLogger().setLevel(log.DEBUG)


def process_single_file(file_name: str) -> None:
    current_timestamp: dt.datetime = dt.datetime.now()
    print(f"{msu.Color.OVERLINE}{msu.Color.UNDERLINE}{msu.Color.BOLD}{current_timestamp.strftime('%m/%d/%Y')} "
          f"{msu.Color.BOLD}{msu.Color.PURPLE}{current_timestamp.strftime('%H:%M:%S')} "
          f"{msu.Color.YELLOW}{msu.Color.BOLD}{file_name}{msu.Color.END}"
          )

    retry_count: int = 0
    success: bool = False

    clean_file_name: str = msu.clean_file_name(file_name)
    shutil.move(file_name, clean_file_name)
    while not success and retry_count < MAX_RETRIES:
        try:
            transcode(clean_file_name)
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
                print(f"Error processing {file_name}.  " +
                      f"RETRY {msu.Color.BOLD}{msu.Color.PURPLE}#{retry_count}{msu.Color.END}"
                      )


def process_dir_tree(dir_name: str) -> None:
    for (current_dir, dirs, files) in os.walk(dir_name):
        dirs.sort()
        for f in sorted(files):
            if f.endswith(".mp4") or f.endswith(".mkv"):
                full_path = os.path.join(current_dir, f)
                process_single_file(full_path)


def main():
    parser = op.OptionParser()
    _, vals = parser.parse_args()
    path_to_process: str = vals[0]

    if len(vals) != 1:
        print(vals)
        print("Exactly one argument (file-name/directory) expected.")
        sys.exit(1)
    else:
        if path_to_process.endswith(".mp4") or path_to_process.endswith(".mkv"):
            process_single_file(path_to_process)
        else:
            if os.path.isdir(path_to_process):
                process_dir_tree(path_to_process)
            else:
                log.error(f"{path_to_process} is not a valid video file or directory.")
                print(f"{path_to_process} is not a valid video file or directory.")
                sys.exit(1)


if "__main__" == __name__:
    main()
