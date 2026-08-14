from TheKeyMachine.ui.widgets import toolbar_widgets
from TheKeyMachine.tools.slider_tween import MODES, api


def create_section(section, section_data, *, namespace, object_prefix):
    return toolbar_widgets.build_slider_section(
        section, section_data, MODES, api.execute, api.create_session,
        namespace=namespace, object_prefix=object_prefix,
    )
