import logging as log
import optparse as op
import os
import subprocess as proc
import sys

import msutils as msu

FFMPEG_PROC_NAME = "ffmpeg"
PROPER_VIDEO_CODECS: [str] = ["hevc", "libx265"]
PROPER_AUDIO_CODECS: [str] = ["ac3"]

TRANSCODED_ATTRIBUTE: str = "transcoded_to_hevc"
MP4_SUBTITLE_CODEC = "mov_text"
MKV_SUBTITLE_CODEC = "srt"

VIDEO_CODEC = PROPER_VIDEO_CODECS[0]
AUDIO_CODEC = PROPER_AUDIO_CODECS[0]

if "__main__" == __name__:
    # SETUP LOGGER BEFORE IMPORTS SO THEY CAN USE THESE SETTINGS
    log.basicConfig(filename="transcoding-to-hevc.log",
                    filemode="w",
                    format="%(asctime)s %(filename)15.15s %(funcName)15.15s %(levelname)5.5s %(lineno)4.4s %(message)s",
                    datefmt="%Y%m%d-%H:%M:%S"
                    )
    log.getLogger().setLevel(log.DEBUG)


def has_transcoded_attribute(file_name: str) -> bool:
    return msu.is_user_attribute_set_to_yes(file_name, TRANSCODED_ATTRIBUTE)


def set_transcoded_attribute(file_name: str) -> None:
    msu.set_user_attribute_to_yes(file_name, TRANSCODED_ATTRIBUTE)


def already_transcoded(file_name: str) -> bool:
    if has_transcoded_attribute(file_name):
        print(f"{file_name} was previously transcoded and marked as such.")
        log.debug(f"{file_name} was previously transcoded and marked as such.")
        return True

    # CHECK IF PROPER CODECS ARE PRESENT IN THE VIDEO FILE.
    video_codec_ok: bool = False
    audio_codec_ok: bool = False

    codecs: [str] = msu.all_codecs_for(file_name)
    for c in codecs:
        if not video_codec_ok:
            video_codec_ok = c in PROPER_VIDEO_CODECS
        if not audio_codec_ok:
            audio_codec_ok = c in PROPER_AUDIO_CODECS

    return_val: bool = video_codec_ok and audio_codec_ok
    if return_val:
        set_transcoded_attribute(file_name)
        log.debug(f"{file_name} was previously transcoded and has NOW be marked as such.")
        print(f"{file_name} was previously transcoded and has " +
              f"{msu.Color.BOLD}{msu.Color.CYAN}NOW{msu.Color.END} be marked as such."
              )

    return return_val


def transcode(file_name: str) -> None:
    if file_name.endswith(".mp4"):
        sub_codec: str = MP4_SUBTITLE_CODEC
    elif file_name.endswith(".mkv"):
        sub_codec: str = MKV_SUBTITLE_CODEC
    else:
        assert file_name.endswith(".mp4") or file_name.endswith(".mkv")
        return

    if already_transcoded(file_name):
        return

    print(f"Transcoding {file_name} to hevc/ac3.")
    log.debug(f"Transcoding {file_name} to hevc/ac3.")

    ffmpeg_args: [str] = \
        [
            FFMPEG_PROC_NAME,
            "-y",
            # "-ss", "00:00:00",
            "-threads", "3",                # use as few threads as possible
            "-i", file_name,                # input file
            "-map", "0:v:0",                # Use 1st video stream
            "-map", "0:a?",                 # Keep all audio streams
            "-map", "0:s?",                 # Keep all subtitles
            "-c:s", sub_codec,              # subtitle codec (matches original)
            "-c:v", VIDEO_CODEC,            # video codec (hevc/h.265)
            "-c:a", AUDIO_CODEC,            # audio codec (ac3)
            "-threads", "3",                # use as few threads as possible
            msu.temp_results_file_name(file_name),
        ]

    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        try:
            pre_transcode_text: [str] = msu.ffmpeg_output_before_transcode(process.stderr)
            duration: float = msu.find_duration(pre_transcode_text)
        except msu.MediaServerUtilityException as msue:
            log.error(f"Error during startup of ffmpeg for {file_name}")
            log.exception(msue)

        for line in process.stderr:
            if msu.is_ffmpeg_update(line):
                current_loc = msu.ffmpeg_get_current_time(line)
                percent_progress = msu.pretty_progress(current_loc, duration)
                print(f"Transcode Progress: {msu.Color.BOLD}{msu.Color.GREEN}{percent_progress}{msu.Color.END}",
                      end="\r"
                      )

    if process.returncode != 0:
        print("====================")
        for t in pre_transcode_text:
            print(t)
        print("====================")

        raise msu.MediaServerUtilityException(f"An error occurred while transcoding " +
                                              f"{file_name}. Return code: {process.returncode}"
                                              )

    percent_progress = msu.pretty_progress(duration, duration)
    print(f"Transcode Progress: {msu.Color.BOLD}{msu.Color.GREEN}{percent_progress}{msu.Color.END}")
    log.info(f"... Transcode of {file_name} complete.  Rename file.")

    msu.replace_file(file_name,
                     msu.temp_results_file_name(file_name),
                     [TRANSCODED_ATTRIBUTE]
                     )
    set_transcoded_attribute(file_name)
    log.info(f"... Rename complete.")


def walk_dir_transcoding(dir_name: str) -> None:
    for (current_dir, dirs, files) in os.walk(dir_name):
        dirs.sort()
        for f in sorted(files):
            if f.endswith(".mp4") or f.endswith(".mkv"):
                full_path = os.path.join(current_dir, f)
                transcode(full_path)


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
            transcode(path_to_process)
        else:
            if os.path.isdir(path_to_process):
                walk_dir_transcoding(path_to_process)
            else:
                log.error(f"{path_to_process} is not a valid video file or directory.")
                print(f"{path_to_process} is not a valid video file or directory.")
                sys.exit(1)


if "__main__" == __name__:
    main()
