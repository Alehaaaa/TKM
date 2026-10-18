from TheKeyMachine.tools.slider_blend import controller


def execute(mode, value, session=None):
    return controller.execute(mode, value, session=session)


def create_session(mode):
    return controller.create_session(mode)


def get_smooth_algorithm():
    return controller.get_smooth_algorithm()


def set_smooth_algorithm(value):
    return controller.set_smooth_algorithm(value)


def get_simplify_algorithm():
    return controller.get_simplify_algorithm()


def set_simplify_algorithm(value):
    return controller.set_simplify_algorithm(value)


def algorithm_choices():
    return [
        {
            "value": controller.ALGORITHM_CUSTOM,
            "label": "TKM Custom",
            "description": "Use TheKeyMachine's interactive curve algorithm.",
        },
        {
            "value": controller.ALGORITHM_MAYA_NATIVE,
            "label": "Maya Native",
            "description": "Use Maya's native curve filter implementation.",
        },
    ]
