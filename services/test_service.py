def do_nothing(seconds, app_logger):
    while iterations > 0:
        app_logger.info("Doing NOTHING, {} left...".format(iterations)
        time.sleep(1)
    app_logger.info("Job NOTHING done")

def do_stuff(seconds, app_logger):
    while iterations > 0:
        app_logger.info("Doing STUFF, {} left...".format(iterations)
        time.sleep(1)
    app_logger.info("Job STUFF done")
