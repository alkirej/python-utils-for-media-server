import logging as log

import plexapi.exceptions as pexc
import plexapi.video as pvid
import plexapi.server as psvr
import plexapi.library as plib


def analyze_video(movie: pvid.Movie) -> None:
    log.info(f"Analyzing {movie.title}")
    try:
        # Does not seem to work, but scanning from web app does refresh things.
        movie.analyze()

    except pexc.NotFound as nfe:
        log.error(f"Error received analyzing movie. {nfe}.  It will need to be done manually.")
        log.exception(nfe)
