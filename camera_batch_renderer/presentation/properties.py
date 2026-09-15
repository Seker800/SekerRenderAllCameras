import bpy


class RAC_Settings(bpy.types.PropertyGroup):
    include_alpha: bpy.props.BoolProperty(name="Render Alpha", default=False)
    include_object_id: bpy.props.BoolProperty(name="Render Object ID", default=False)
    status_text: bpy.props.StringProperty(name="Status", default="Ready")
    progress: bpy.props.FloatProperty(name="Progress", default=0.0, min=0.0, max=1.0)
