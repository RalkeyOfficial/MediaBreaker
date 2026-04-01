import logging
from nicegui import ui


def main(args):
    log = logging.getLogger(__name__)

    ui.label('Hello NiceGUI!')
    ui.label('Hello')

    log.debug('UI enabled')

    ui.run(
        reload=False,
        title="Media Breaker",
        dark=True,
        language="en-US"
    )

    return None
