import logging as log
import optparse as op
import os
import shutil

if "__main__" == __name__:
    # SETUP LOGGER BEFORE IMPORTS SO THEY CAN USE THESE SETTINGS
    log.basicConfig(filename="poster-to-season.log",
                    filemode="w",
                    format="%(asctime)s %(filename)15.15s %(funcName)15.15s %(levelname)5.5s %(lineno)4.4s %(message)s",
                    datefmt="%Y%m%d %H%M%S"
                    )
    log.getLogger().setLevel(log.DEBUG)


def parse_command_line() -> op.Values:
    parser = op.OptionParser()
    parser.add_option("-p", "--poster",
                      dest="poster_file",
                      help="File to use as poster for the season."
                      )
    parser.add_option("-s", "--season",
                      dest="season_dir",
                      help="Directory the videos for the season are located."
                      )
    options, _ = parser.parse_args()

    if not options.poster_file:
        parser.error("Filename of poster is missing.")
    if not options.season_dir:
        parser.error("Season directory is missing.")

    if not os.path.isfile(options.poster_file):
        parser.error(f"Cannot find image file {options.poster_file}.")
    if not os.path.isdir(options.season_dir):
        parser.error(f"Cannot find directory {options.season_dir}.")

    return options


def main() -> None:
    options: op.Values = parse_command_line()
    dot_idx: int = options.poster_file.rfind(".")
    # FILE EXTENSION OF POSTER (INCLUDING THE PERIOD)
    poster_ext: str = options.poster_file[dot_idx:]

    for file_name in sorted(os.listdir(options.season_dir)):
        if file_name.endswith(".mp4") or file_name.endswith(".mkv"):
            print(f"Copying poster for {file_name}")
            # build poster filename
            poster_file_name: str = f"{file_name[:-4]}{poster_ext}"
            poster_full_path: str = os.path.join(options.season_dir, poster_file_name)
            log.debug(f"Copying {options.poster_file} to {poster_full_path}.")
            shutil.copyfile(options.poster_file, poster_full_path)


if __name__ == "__main__":
    main()
