from TheKeyMachine.core import toolWidgets
from TheKeyMachine.tools.slider_tangent import MODES, api


def create_section(section, section_data, *, namespace, object_prefix):
    return toolWidgets.build_slider_section(
        section, section_data, MODES, api.execute, api.create_session,
        namespace=namespace, object_prefix=object_prefix,
    )
