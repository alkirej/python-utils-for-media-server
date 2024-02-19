import glob
import os
import shutil

RECORDINGS_DIR: str = "/media/jeff/ToolsDisk/recordings/episodes"
PLEX_DIR_FOR_TV: str = "/nfs/Media-01/media-store/Video/Television Shows"


def process_episode(tv_show_dir_name: str, season_dir_name: str, file_name: str) -> None:
    # file name should not include the extension.  (Mkv will be added automatically)
    season_path: str = os.path.join(tv_show_dir_name, season_dir_name)
    episode_path: str = os.path.join(season_path, f"{file_name}.mkv")
    episode_files: [str] = glob.glob(f"{episode_path}.*")

    if len(episode_files) == 1:
        print("            Moving episode file ... ", end="", flush=True)
        ensure_dir_exists(os.path.join(PLEX_DIR_FOR_TV, season_path))
        dest_path: str = os.path.join(PLEX_DIR_FOR_TV, season_path, f"{file_name}.mkv")
        shutil.move(episode_path, dest_path)
        print("Complete.")


def process_season(tv_show_dir_name: str, season_dir_name: str) -> None:
    season_dir: str = os.path.join(tv_show_dir_name, season_dir_name)
    episode_list: [str] = os.listdir(season_dir)
    episode_list.sort()

    for episode in episode_list:
        print(f"        Found episode {episode}")
        if episode.endswith(".mkv"):
            process_episode(tv_show_dir_name, season_dir_name, episode[:-4])


def process_tv_show(tv_show_dir_name: str) -> None:
    season_list: [str] = os.listdir(tv_show_dir_name)
    season_list.sort()

    for season in season_list:
        print(f"    Found dir for {season}.")
        process_season(tv_show_dir_name, season)


def ensure_dir_exists(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main() -> None:
    print("Upload newly recorded television show episodes to plex ...")
    os.chdir(RECORDINGS_DIR)
    show_list: [str] = os.listdir(os.getcwd())
    show_list.sort()

    for tv_show in show_list:
        print(f"Found dir for show {tv_show}.")
        process_tv_show(tv_show)


if "__main__" == __name__:
    main()
