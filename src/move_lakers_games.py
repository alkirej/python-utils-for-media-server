import glob
import os
import shutil

GAMES_RECORDED_DIR: str = "/home/jeff/Videos/recordings/Lakers"
PLEX_DIR_FOR_GAMES: dict = {"1962": "/nfs/Media-01/media-store/Video/Sports Games/Lakers/1961-62",
                            "1964": "/nfs/Media-01/media-store/Video/Sports Games/Lakers/1963-64",
                            "1973": "/nfs/Media-01/media-store/Video/Sports Games/Lakers/1972-73",
                            "1984": "/nfs/Media-01/media-store/Video/Sports Games/Lakers/1983-84",
                            "1990": "/nfs/Media-01/media-store/Video/Sports Games/Lakers/1989-90",
                            "2013": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2012-13",
                            "2014": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2013-14",
                            "2015": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2014-15",
                            "2016": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2015-16",
                            "2017": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2016-17",
                            "2018": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2017-18",
                            "2019": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2018-19",
                            "2020": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2019-20",
                            "2021": "/nfs/Media-04/media-store/Video/Sports Games/Lakers/2020-21"
                            }
GAME_POSTERS: dict = {"1962": "game-poster.webp",
                      "1964": "game-poster.webp",
                      "1973": "game-poster.webp",
                      "1984": "game-poster.webp",
                      "1990": "game-poster.webp",
                      "2013": "game-poster.webp",
                      "2014": "Season2014a.jpg",
                      "2015": "game-poster.webp",
                      "2016": "game-poster.webp",
                      "2017": "game-poster.webp",
                      "2018": "game-poster.webp",
                      "2019": "game-poster.jpg",
                      "2020": "game-poster.webp",
                      "2021": "game-poster.webp"
                      }


def get_year_from_game_filename(fn: str) -> str:
    yr_start_idx: int = fn.find("-s") + 2
    yr: str = fn[yr_start_idx:yr_start_idx+4]

    return yr


def get_plex_dir_for_year(yr: str) -> str:
    return PLEX_DIR_FOR_GAMES[yr]


def find_extension(fn: str) -> str:
    fn_parts: [str] = fn.split(".")
    return fn_parts[-1]


def create_game_poster_for(file_name: str) -> None:
    year = get_year_from_game_filename(file_name)
    plex_dir: str = get_plex_dir_for_year(year)
    poster_file: str = GAME_POSTERS[year]
    poster_file_ext: str = find_extension(poster_file)

    poster_original_path: str = os.path.join(plex_dir, poster_file)
    final_poster_path: str = os.path.join(plex_dir, f"{file_name[:-4]}.{poster_file_ext}")

    shutil.copyfile(poster_original_path, final_poster_path)


def move_game_video(file_name: str) -> None:
    year = get_year_from_game_filename(file_name)
    plex_dir: str = get_plex_dir_for_year(year)
    final_game_video_path: str = os.path.join(plex_dir, file_name)
    shutil.move(file_name, final_game_video_path)


def main() -> None:
    print("Upload and newly recorded Lakers games to plex ...")
    os.chdir(GAMES_RECORDED_DIR)
    mkv_files: [str] = glob.glob("*.mkv")

    for fn in mkv_files:
        fn_wo_ext: str = fn[:-4]
        file_count: int = len(glob.glob(f"{fn_wo_ext}.*"))
        if file_count == 1:
            print(f"Moving {fn} to plex ... ", end="", flush=True)
            create_game_poster_for(fn)
            move_game_video(fn)
            print("COMPLETE")


if "__main__" == __name__:
    main()
