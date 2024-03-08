import os
import shutil

RECORDINGS_DIR: str = "/home/jeff/Videos/recordings/movies"
PLEX_DIR_FOR_MOVIES: str = "/nfs/Media-01/media-store/Video/Movies"


def process_movie(movie_dir_name: str) -> None:
    movie_files: [str] = os.listdir(movie_dir_name)

    if len(movie_files) == 1 and movie_files[0][-4:].lower() == ".mkv":
        print("            Moving movie ... ", end="", flush=True)
        ensure_dir_exists(os.path.join(PLEX_DIR_FOR_MOVIES, movie_dir_name))
        shutil.move(movie_dir_name, PLEX_DIR_FOR_MOVIES)
        print("Complete.")


def ensure_dir_exists(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main() -> None:
    print("Upload newly recorded movies to plex ...")
    os.chdir(RECORDINGS_DIR)
    movie_list: [str] = os.listdir(os.getcwd())
    movie_list.sort()

    for movie in movie_list:
        if os.path.isdir(movie):
            print(f"    Found dir for movie: {movie}.")
            process_movie(movie)
    print(f"    Complete")


if "__main__" == __name__:
    main()
