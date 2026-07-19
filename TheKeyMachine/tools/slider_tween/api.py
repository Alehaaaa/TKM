from TheKeyMachine.tools.slider_tween import controller


def execute(mode, value, session=None):
    return controller.execute(mode, value, session=session)


def create_session(mode):
    return controller.create_session(mode)
