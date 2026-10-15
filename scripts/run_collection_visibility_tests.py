"""Real-host regressions for preset scope and collection-only visibility changes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blender_test_safety import require_isolated_profile  # noqa: E402

require_isolated_profile()
sys.path.insert(0, os.environ.get("RAC_PACKAGE_PARENT", str(ROOT)))

from camera_batch_renderer.blender.environment import (  # noqa: E402
    id_key,
    layer_collections,
    preview_environment,
)
from camera_batch_renderer.blender.state_transaction import BlenderStateTransaction  # noqa: E402
from camera_batch_renderer.domain import CameraEnvironmentSpec  # noqa: E402


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    def collection(name, parent):
        item = bpy.data.collections.new(name)
        parent.children.link(item)
        return item

    parent = collection("Manual Parent", scene.collection)
    selected = collection("Selected Preset", parent)
    other = collection("Other Preset", parent)
    child = collection("Manual Hidden Child", selected)
    unrelated = collection("Manual Unrelated", parent)
    scene.view_layers.new("Second View Layer")
    layers = [layer for view in scene.view_layers for layer in layer_collections(view)]
    light = bpy.data.objects.new("Manually Hidden Light", bpy.data.lights.new("Light", "POINT"))
    selected.objects.link(light)
    scene.view_layers[0].update()
    light.hide_render = True
    light.hide_viewport = True
    light.hide_set(True, view_layer=scene.view_layers[0])
    other_light = bpy.data.objects.new(
        "Other Hidden Eye", bpy.data.lights.new("Other Light", "POINT")
    )
    other.objects.link(other_light)
    scene.view_layers[0].update()
    other_light.hide_set(True, view_layer=scene.view_layers[0])
    for item in (selected, child, unrelated):
        item.hide_render = item.hide_viewport = True
    for layer in layers:
        if layer.collection in (selected, child, unrelated):
            layer.exclude = layer.hide_viewport = True
    initial_objects = (light.hide_render, light.hide_viewport)
    initial_eye = light.hide_get(view_layer=scene.view_layers[0])

    preview_environment(
        scene,
        scene.view_layers[0],
        camera=None,
        world=None,
        light_collection=selected,
        other_light_collections=(other,),
    )
    assert not selected.hide_render and not selected.hide_viewport
    assert other.hide_render and other.hide_viewport
    assert child.hide_render and child.hide_viewport
    assert unrelated.hide_render and unrelated.hide_viewport
    assert (light.hide_render, light.hide_viewport) == initial_objects
    assert light.hide_get(view_layer=scene.view_layers[0]) == initial_eye
    assert all(layer.exclude for layer in layers if layer.collection in (child, unrelated))
    assert other_light.hide_get(view_layer=scene.view_layers[0])
    preview_environment(
        scene,
        scene.view_layers[0],
        camera=None,
        world=None,
        light_collection=other,
        other_light_collections=(selected,),
    )
    assert other_light.hide_get(view_layer=scene.view_layers[0])
    preview_environment(
        scene,
        scene.view_layers[0],
        camera=None,
        world=None,
        light_collection=selected,
        other_light_collections=(other,),
    )
    # A manually hidden ancestor must stay hidden, even when a preset is selected.
    parent.hide_render = parent.hide_viewport = True
    preview_environment(
        scene,
        scene.view_layers[0],
        camera=None,
        world=None,
        light_collection=selected,
        other_light_collections=(other,),
    )
    assert parent.hide_render and parent.hide_viewport
    parent.hide_render = parent.hide_viewport = False

    before = [(item, item.hide_render) for item in (selected, other, child, unrelated)]
    before_layers = [(layer, layer.exclude) for layer in layers]
    spec = CameraEnvironmentSpec(
        light_collection_key=id_key(selected),
        light_collection_name=selected.name,
        light_object_keys=(id_key(light),),
    )
    transaction = BlenderStateTransaction(scene).capture()
    try:
        transaction.apply_environment(spec, (id_key(selected), id_key(other)))
        assert (light.hide_render, light.hide_viewport) == initial_objects
        assert child.hide_render and unrelated.hide_render
        assert all(not layer.exclude for layer in layers if layer.collection == selected)
        # A user's unrelated edit during a batch is not owned by the transaction.
        unrelated.hide_render = False
        transaction.apply_environment(None)
        assert not unrelated.hide_render
        raise RuntimeError("Injected failure")
    except RuntimeError as exc:
        assert str(exc) == "Injected failure"
    finally:
        transaction.restore()
    for item, hidden in before:
        if item != unrelated:
            assert item.hide_render == hidden
    assert all(layer.exclude == excluded for layer, excluded in before_layers)
    assert (light.hide_render, light.hide_viewport) == initial_objects
    print("COLLECTION_VISIBILITY_TESTS_OK", bpy.app.version_string, flush=True)


main()
