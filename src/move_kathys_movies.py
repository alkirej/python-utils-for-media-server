import os
import shutil

RECORDINGS_DIR: str = "/home/jeff/Videos/recordings/movies"
PLEX_DIR_FOR_MOVIES: str = "/nfs/Media-01/media-store/Video/Movies"


def main() -> None:
    print("Upload and newly recorded movies games to plex ...")
    os.chdir(RECORDINGS_DIR)

    for (current_dir, dirs, files) in os.walk(RECORDINGS_DIR):
        dirs.sort()
        if len(files) == 1 and files[0].endswith(".mkv"):
            print(f"Moving {current_dir} to {PLEX_DIR_FOR_MOVIES} ... ", end="", flush=True)
            shutil.copytree(current_dir, os.path.join(PLEX_DIR_FOR_MOVIES, current_dir))
            shutil.rmtree(current_dir)
            print("Complete")


if "__main__" == __name__:
    main()
