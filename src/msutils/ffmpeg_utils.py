import datetime as dt
import logging as log
import subprocess as proc

from .MediaServerUtilityException import MediaServerUtilityException
import msutils as msu

FFMPEG_PROGRAM_LOCS = ["/home/jeff/bin/ffmpeg", "/usr/bin/ffmpeg"]
current_ffmpeg_index: int = 0


def run_ffmpeg(ffmpeg_args: [str]) -> None:
    global current_ffmpeg_index

    pre_transcode_text: [str] = []
    start_ts: dt.datetime = dt.datetime.now()
    with proc.Popen(ffmpeg_args, text=True, stderr=proc.PIPE) as process:
        try:
            pre_transcode_text = msu.ffmpeg_output_before_transcode(process.stderr)
            duration: float = msu.find_duration(pre_transcode_text)
        except MediaServerUtilityException as msue:
            log.error(f"Error during startup of ffmpeg. {ffmpeg_args}")
            log.exception(msue)

        for line in process.stderr:
            if msu.is_ffmpeg_update(line):
                current_loc = msu.ffmpeg_get_current_time(line)
                percent_progress = msu.pretty_progress_with_timer(start_ts, current_loc, duration)
                print(f"    Progress: {msu.Color.BOLD}{msu.Color.GREEN}{percent_progress}{msu.Color.END}",
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

        raise MediaServerUtilityException(f"An error occurred while transcoding {ffmpeg_args}" +
                                          f"Return code: {process.returncode}"
                                          )

    percent_progress = msu.pretty_progress(duration, duration)
    print(f"    {msu.Color.GREEN}Complete: {msu.Color.BOLD}{percent_progress}{msu.Color.END}          ")
