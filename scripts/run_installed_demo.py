from __future__ import annotations

import importlib
import json
import os
import re
from pathlib import Path

import bpy


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    contract_path = Path(
        os.environ.get(
            "RAC_RELEASE_CONTRACT",
            str(Path(__file__).resolve().parents[1] / "packaging" / "release_contract.json"),
        )
    )
    contract_spec = json.loads(contract_path.read_text(encoding="utf-8"))
    module_root = os.environ.get(
        "RAC_INSTALLED_MODULE", "bl_ext.user_default.camera_batch_renderer"
    )
    runtime = importlib.import_module(f"{module_root}.blender.runtime")
    auxiliary = importlib.import_module(f"{module_root}.blender.auxiliary")
    panel = importlib.import_module(f"{module_root}.presentation.panel")
    addon = importlib.import_module(module_root)
    scene_reader = importlib.import_module(f"{module_root}.blender.scene_reader")
    policy = importlib.import_module(f"{module_root}.presentation.host_policy")
    assert_true(
        policy.TARGET_ID == os.environ["RAC_EXPECTED_TARGET"],
        "Installed target policy does not match the selected Blender package",
    )
    assert_true(panel.RAC_PT_view3d_panel.is_registered, "Installed N-panel is not registered")
    assert_true(panel.RAC_PT_view3d_panel.bl_category == "Batch Render", "N-panel tab is wrong")
    manifest_path = Path(addon.__file__).resolve().with_name("blender_manifest.toml")
    if manifest_path.is_file():
        manifest_text = manifest_path.read_text(encoding="utf-8")
        match = re.search(r'^name = "([^"]+)"$', manifest_text, re.MULTILINE)
        assert_true(match is not None, "Installed Extension name is missing")
        installed_name = match.group(1)
    else:
        installed_name = addon.bl_info["name"]
    expected_name = (
        f"{contract_spec['display_name']} {runtime.VERSION_TEXT} "
        f"(Blender {policy.TARGET_LABEL})"
    )
    assert_true(installed_name == expected_name, "Installed add-on name differs")
    assert_true(
        panel.RAC_PT_panel.bl_label == expected_name, "Output panel name differs"
    )
    assert_true(
        panel.RAC_PT_view3d_panel.bl_label == expected_name, "N-panel name differs"
    )
    scene = bpy.context.scene
    settings = scene.rac_settings

    class LayoutRecorder:
        def __init__(self) -> None:
            self.properties: list[str] = []
            self.enabled = True

        def row(self, **_kwargs):
            return self

        def box(self):
            return self

        def column(self, **_kwargs):
            return self

        def prop(self, _data, property_name: str):
            self.properties.append(property_name)

        def template_list(self, *_args, **_kwargs):
            return None

        def label(self, **_kwargs):
            return None

        def operator(self, *_args, **_kwargs):
            return self

    drawn = LayoutRecorder()
    panel.draw_controls(drawn, bpy.context)
    for name, option in contract_spec["output_options"].items():
        definition = settings.bl_rna.properties.get(name)
        assert_true(definition is not None, f"Installed option is missing: {name}")
        assert_true(definition.name == option["label"], f"Installed option label is wrong: {name}")
        assert_true(
            definition.default == option["default"], f"Installed option default is wrong: {name}"
        )
        assert_true(
            getattr(settings, name) == option["default"], f"Initial option value is wrong: {name}"
        )
        assert_true(name in drawn.properties, f"Installed panel does not draw: {name}")
    original_camera = scene.camera
    original_filepath = scene.render.filepath
    session = runtime.run_batch_sync(
        scene,
        include_alpha=True,
        include_object_id=True,
        include_material_id=True,
    )
    progress = session.coordinator.snapshot()
    assert_true(progress.status.value == "completed", "Installed batch did not complete")
    assert_true(len(progress.results) == 8, "Installed batch did not produce eight results")
    assert_true(all(result.path.exists() for result in progress.results), "An output is missing")
    assert_true(scene.camera == original_camera, "Active camera was not restored")
    assert_true(scene.render.filepath == original_filepath, "Render filepath was not restored")
    assert_true(
        not any(item.name.startswith("RAC_") for item in bpy.data.scenes),
        "Temporary scene leaked",
    )

    id_manifest = next(session.allocation.directory.glob("*_ObjectID.json"))
    id_payload = json.loads(id_manifest.read_text(encoding="utf-8"))
    allowed = {(0, 0, 0), *(tuple(item["rgb"]) for item in id_payload["objects"])}
    for result in progress.results:
        if result.channel.value == "ObjectID":
            colors = auxiliary.read_png_colors(result.path)
            assert_true(colors <= allowed, f"Object ID contains undeclared colors: {colors}")
            assert_true(colors - {(0, 0, 0)}, "Object ID contains no object label")
        elif result.channel.value == "Alpha" and result.camera_name == "Camera_01_Front":
            image = bpy.data.images.load(str(result.path), check_existing=False)
            try:
                width, height = image.size[:]
                pixels = list(image.pixels)
                bottom_center = pixels[(width // 2) * 4]
                top_center = pixels[((height - 1) * width + width // 2) * 4]
                assert_true(bottom_center > 0.95, "Alpha ground is not opaque")
                assert_true(top_center < 0.05, "Alpha world is not transparent")
            finally:
                bpy.data.images.remove(image)

    material_manifest = next(session.allocation.directory.glob("*_MaterialID.json"))
    material_payload = json.loads(material_manifest.read_text(encoding="utf-8"))
    material_allowed = {
        (0, 0, 0),
        *(tuple(item["rgb"]) for item in material_payload["materials"]),
    }
    for result in progress.results:
        if result.channel.value == "MaterialID":
            colors = auxiliary.read_png_colors(result.path)
            assert_true(
                colors <= material_allowed,
                f"Material ID contains undeclared colors: {colors}",
            )
            assert_true(colors - {(0, 0, 0)}, "Material ID contains no material label")

    render_info = next(session.allocation.directory.glob("*_RenderInfo.json"))
    payload = json.loads(render_info.read_text(encoding="utf-8"))
    assert_true(payload["status"] == "completed", "RenderInfo is not completed")
    assert_true(
        payload["blender_version"] == bpy.app.version_string,
        "RenderInfo Blender version does not match the running host",
    )
    contract = {
        "schema_version": 1,
        "cameras": sorted({result.camera_name for result in progress.results}),
        "channels": sorted({result.channel.value for result in progress.results}),
        "result_matrix": sorted(
            [result.camera_name, result.channel.value] for result in progress.results
        ),
        "result_count": len(progress.results),
        "render_info_schema": payload["schema_version"],
        "render_info_status": payload["status"],
        "object_palette": sorted([list(color) for color in allowed]),
        "material_palette": sorted([list(color) for color in material_allowed]),
        "display_name": contract_spec["display_name"],
        "output_options": {
            name: {
                "label": settings.bl_rna.properties[name].name,
                "default": settings.bl_rna.properties[name].default,
                "drawn": name in drawn.properties,
            }
            for name in contract_spec["output_options"]
        },
    }
    single_channel_results = {}
    for selected_name, option in contract_spec["output_options"].items():
        selected = {name: name == selected_name for name in contract_spec["output_options"]}
        single_session = runtime.run_batch_sync(scene, **selected)
        single_progress = single_session.coordinator.snapshot()
        actual_channels = sorted({result.channel.value for result in single_progress.results})
        assert_true(single_progress.status.value == "completed", f"{selected_name} batch failed")
        assert_true(
            actual_channels == [option["channel"]],
            f"{selected_name} rendered an unselected channel",
        )
        assert_true(len(single_progress.results) == 2, f"{selected_name} result count is wrong")
        assert_true(
            all(result.path.exists() for result in single_progress.results),
            f"{selected_name} output missing",
        )
        assert_true(scene.camera == original_camera, f"{selected_name} did not restore camera")
        assert_true(
            scene.render.filepath == original_filepath, f"{selected_name} did not restore filepath"
        )
        assert_true(
            not single_session.allocation.working_directory.exists(),
            f"{selected_name} left a work directory",
        )
        single_channel_results[selected_name] = actual_channels
    try:
        scene_reader.validate_scene(
            scene, **{name: False for name in contract_spec["output_options"]}
        )
    except ValueError as exc:
        assert_true("Select at least one output" in str(exc), "Empty selection error is wrong")
    else:
        raise AssertionError("Empty output selection was accepted")
    contract["single_channel_results"] = single_channel_results
    contract["empty_selection_rejected"] = True
    contract_output = os.environ.get("RAC_CONTRACT_OUTPUT")
    if contract_output:
        contract_path = os.path.abspath(contract_output)
        os.makedirs(os.path.dirname(contract_path), exist_ok=True)
        with open(contract_path, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(contract, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    print(
        "INSTALLED_DEMO_OK",
        json.dumps(
            {
                "directory": str(session.allocation.directory),
                "results": len(progress.results),
                "render_info": render_info.name,
                "object_id_info": id_manifest.name,
                "material_id_info": material_manifest.name,
            },
            ensure_ascii=False,
        ),
    )


if __name__ == "__main__":
    main()
