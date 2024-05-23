import datetime as dt
import logging as log
import optparse as op
import os
import shutil
import subprocess as proc
import sys
import typing as typ

import msutils as msu

WORK_FILE = "working"

FFMPEG_PROGRAM_LOCS = ["/home/jeff/bin/ffmpeg", "/usr/bin/ffmpeg"]
current_ffmpeg_index = 0

PROPER_VIDEO_CODECS: [str] = ["libx265", "hevc"]
OTHER_VIDEO_CODECS: [str] = ["h264", "mpeg2video", "mpeg4"]
PROPER_AUDIO_CODECS: [str] = ["ac3"]
OTHER_AUDIO_CODECS: [str] = ["aac", "vorbis", "pcm_s16le", "mp3"]
TEXT_SUBTITLE_CODECS: [str] = ["mov_text", "srt", "vobsub", "subrip", "ass"]
PROPER_SUBTITLE_CODECS: [str] = ["mov_text"]
GRAPHIC_SUBTITLE_CODECS: [str] = ["dvd_subtitle"]
CODECS_TO_IGNORE: [str] = ["bin_data", "png", ""]

TRANSCODED_ATTRIBUTE: str = "transcoded_to_hevc"

VIDEO_CODEC = PROPER_VIDEO_CODECS[0]
AUDIO_CODEC = PROPER_AUDIO_CODECS[0]
SUBTITLE_CODEC = PROPER_SUBTITLE_CODECS[0]
CORRECT_CODEC = "copy"

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
    """ Deprecated. """
    if has_transcoded_attribute(file_name):
        print(f"    {file_name} {msu.Color.BOLD}{msu.Color.DOUBLE_UNDERLINE}was previously "
              f"transcoded{msu.Color.END} and marked as such."
              )
        log.debug(f"{file_name} was previously transcoded and marked as such.")
        return True

    # CHECK IF PROPER CODECS ARE PRESENT IN THE VIDEO FILE.
    video_codec_ok: bool = False
    audio_codec_ok: bool = False
    subtitle_codec_ok: bool = True

    codecs: [str] = msu.all_codecs_for(file_name)
    for c in codecs:
        if not video_codec_ok:
            video_codec_ok = c in PROPER_VIDEO_CODECS
        if not audio_codec_ok:
            audio_codec_ok = c in PROPER_AUDIO_CODECS
        if subtitle_codec_ok:
            subtitle_codec_ok = c not in GRAPHIC_SUBTITLE_CODECS and c not in PROPER_SUBTITLE_CODECS

    return_val: bool = video_codec_ok and audio_codec_ok
    if return_val:
        set_transcoded_attribute(file_name)
        log.debug(f"{file_name} was previously transcoded and has NOW be marked as such.")
        print(f"{file_name} {msu.Color.BOLD}{msu.Color.DOUBLE_UNDERLINE}was previously transcoded{msu.Color.END} "
              f"and has {msu.Color.BOLD}{msu.Color.CYAN}NOW{msu.Color.END} be marked as such."
              )

    return return_val


def determine_new_codecs(file_name: str) -> (str, str, str):
    if has_transcoded_attribute(file_name):
        print(f"    {file_name} {msu.Color.BOLD}{msu.Color.DOUBLE_UNDERLINE}was previously "
              f"transcoded{msu.Color.END} and marked as such."
              )
        log.debug(f"{file_name} was previously transcoded and marked as such.")
        return CORRECT_CODEC, CORRECT_CODEC, CORRECT_CODEC

    # CHECK IF PROPER CODECS ARE PRESENT IN THE VIDEO FILE.
    video_codec: typ.Optional[str] = None
    audio_codec: typ.Optional[str] = None
    subtitle_codec: typ.Optional[str] = None

    codecs: [str] = msu.all_codecs_for(file_name)
    for c in codecs:
        c2: str = c.lower()
        if c2 not in PROPER_VIDEO_CODECS and \
           c2 not in OTHER_VIDEO_CODECS and \
           c2 not in PROPER_AUDIO_CODECS and \
           c2 not in OTHER_AUDIO_CODECS and \
           c2 not in GRAPHIC_SUBTITLE_CODECS and \
           c2 not in TEXT_SUBTITLE_CODECS and \
           c2 not in CODECS_TO_IGNORE:
            print(f"INVALID CODEC: {c}")
            log.error(f"INVALID CODEC: {c}")
            raise msu.MediaServerUtilityException(f"Invalid codec found transcoding " +
                                                  f"{file_name}. Codec: {c}"
                                                  )

        if video_codec is None:
            if c in PROPER_VIDEO_CODECS:
                video_codec = CORRECT_CODEC
            elif c in OTHER_VIDEO_CODECS:
                video_codec = VIDEO_CODEC

        if audio_codec is None:
            if c in PROPER_AUDIO_CODECS:
                audio_codec = CORRECT_CODEC
            elif c in OTHER_AUDIO_CODECS:
                audio_codec = AUDIO_CODEC

        if subtitle_codec is None:
            if c in GRAPHIC_SUBTITLE_CODECS:
                subtitle_codec = CORRECT_CODEC
            elif c in TEXT_SUBTITLE_CODECS:
                if c == subtitle_codec:
                    subtitle_codec = CORRECT_CODEC
                else:
                    subtitle_codec = SUBTITLE_CODEC

    prev_transcoded: bool = video_codec == CORRECT_CODEC and audio_codec == CORRECT_CODEC
    if prev_transcoded:
        set_transcoded_attribute(file_name)
        log.debug(f"{file_name} was previously transcoded and has NOW be marked as such.")
        print(f"{file_name} {msu.Color.BOLD}{msu.Color.DOUBLE_UNDERLINE}was previously transcoded{msu.Color.END} "
              f"and has {msu.Color.BOLD}{msu.Color.CYAN}NOW{msu.Color.END} be marked as such."
              )
        return CORRECT_CODEC, CORRECT_CODEC, CORRECT_CODEC

    # if video_codec is None:
    #     video_codec = VIDEO_CODEC
    # if audio_codec is None:
    #     audio_codec = AUDIO_CODEC

    return video_codec, audio_codec, subtitle_codec


def transcode(file_name: str) -> None:
    global current_ffmpeg_index

    assert file_name.endswith(".mp4") or file_name.endswith(".mkv")
    work_file_name: str = f"{WORK_FILE}{file_name[-4:]}"

    (vid_codec, aud_codec, sbt_codec) = determine_new_codecs(file_name)
    if vid_codec == CORRECT_CODEC and aud_codec == CORRECT_CODEC:
        return
    if vid_codec is None:
        log.error(f"No video found for {file_name}.  Skipping file.")

    if aud_codec is None:
        aud_codec = CORRECT_CODEC

    if sbt_codec is None:
        sbt_codec = CORRECT_CODEC

    print(f"{msu.Color.BOLD}{msu.Color.BLUE}Transcoding{msu.Color.END} {file_name} to "
          f"{vid_codec}/{aud_codec}/{sbt_codec} using "
          f"{msu.Color.CYAN}{FFMPEG_PROGRAM_LOCS[current_ffmpeg_index]}{msu.Color.END}."
          )
    log.debug(f"Transcoding {file_name} to hevc/ac3/{sbt_codec} using {FFMPEG_PROGRAM_LOCS[current_ffmpeg_index]}.")

    print(f"    Copying {work_file_name} to local disk for faster processing ... ", end="", flush=True)
    shutil.copy2(file_name, work_file_name)
    print("COMPLETE")
    ffmpeg_args: [str] = \
        [
            "nice",
            FFMPEG_PROGRAM_LOCS[current_ffmpeg_index],
            "-y",
            "-i", work_file_name,                # input file
            "-map", "0:v:0",                # Use 1st video stream
            "-map", "0:a?",                 # Keep all audio streams
            "-map", "0:s?",                 # Keep all subtitles
            "-c:v", vid_codec,              # video codec (hevc/h.265)
            "-c:a", aud_codec,              # audio codec (ac3)
            "-c:s", sbt_codec,              # subtitle codec (matches original)
            msu.temp_results_file_name(file_name),
        ]

    pre_transcode_text: [str] = []
    start_ts: dt.datetime = dt.datetime.now()
    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        try:
            pre_transcode_text = msu.ffmpeg_output_before_transcode(process.stderr)
            duration: float = msu.find_duration(pre_transcode_text)
        except msu.MediaServerUtilityException as msue:
            log.error(f"Error during startup of ffmpeg for {file_name}")
            log.exception(msue)

        for line in process.stderr:
            if msu.is_ffmpeg_update(line):
                current_loc = msu.ffmpeg_get_current_time(line)
                percent_progress = msu.pretty_progress_with_timer(start_ts, current_loc, duration)
                print(f"    Progress: {msu.Color.BOLD}{msu.Color.GREEN}{percent_progress}{msu.Color.END}    ",
                      end="\r"
                      )
            else:
                log.info(f"ffmpeg says: {line}")
                # print(f"*** ffmpeg says: {line}")

    if process.returncode != 0:
        current_ffmpeg_index += 1
        if current_ffmpeg_index >= len(FFMPEG_PROGRAM_LOCS):
            current_ffmpeg_index = 0

        for t in pre_transcode_text:
            log.debug(t)

        raise msu.MediaServerUtilityException(f"An error occurred while transcoding " +
                                              f"{file_name}. Return code: {process.returncode}"
                                              )

    percent_progress = msu.pretty_progress(duration, duration)
    print(f"    {msu.Color.GREEN}Complete: {msu.Color.BOLD}{percent_progress}{msu.Color.END}          ")
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
