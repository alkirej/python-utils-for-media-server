import glob
import os
import shutil

TEAM_NAME = "Dodgers"
FILEMATCH_GLOB = f"*{TEAM_NAME}*"

# GAMES_RECORDED_DIR: str = "/home/jeff/Videos/recordings/Dodgers"
GAMES_RECORDED_DIR: str = "/home/jeff/Downloads"
PLEX_DIR_FOR_GAMES: dict = {"2024": "/nfs/Media-01/media-store/Video/Sports Games/Dodgers/2024",
                            "2025": "/nfs/Media-04/media-store/Video/Sports Games/Dodgers/2025",
                            }
GAME_POSTERS: dict = {"2024": "game-poster.jpg",
                      "2025": "game-poster.jpg",
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


def move_game_video(file_name: str, new_file_name: str) -> None:
    print(f"file name: {file_name}");

    year = get_year_from_game_filename(new_file_name)
    print(f"year: {year}")
    plex_dir: str = get_plex_dir_for_year(year)
    print(f"plex dir: {plex_dir}")
    final_game_video_path: str = os.path.join(plex_dir, new_file_name)
    shutil.move(file_name, final_game_video_path)


def standardize_filename(orig_fn: str) -> str:
    word: [str] = orig_fn.split()
    ext: str = word[8][-4:]
    date: str = word[8][0:-4]
    year: str = date[-4:]
    day: str = date[:-4] 

    home_away: str
    opponent: str
    if TEAM_NAME == word[2]:
        home_away = "at"
        opponent = word[4]
    else:
        home_away = "vs"
        opponent = word[2]

    return f"{year}{day}{home_away}{opponent}-s{year}e{day}{ext}"

def main() -> None:
    print("Upload and newly recorded DODGERS games to plex ...")
    os.chdir(GAMES_RECORDED_DIR)
    files_to_update: [str] = glob.glob(FILEMATCH_GLOB)

    for fn in files_to_update:
        new_fn: str = standardize_filename(fn)
        fn_wo_ext: str = new_fn[:-4]
        print(f"Moving {fn} to plex ... ", end="", flush=True)
        create_game_poster_for(new_fn)
        move_game_video(fn, new_fn)
        print("COMPLETE")


if "__main__" == __name__:
    main()
