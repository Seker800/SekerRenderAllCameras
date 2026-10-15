from __future__ import annotations

import sys
import unittest
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from unittest.mock import patch


class EnvironmentVisibilityTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(sys.modules, {"bpy": SimpleNamespace()}):
            self.api = run_path(
                str(Path(__file__).parents[2] / "camera_batch_renderer/blender/environment.py")
            )

        def collection(name, children=()):
            return SimpleNamespace(
                name_full=name,
                library=None,
                children=list(children),
                hide_render=True,
                hide_viewport=True,
            )

        self.child = collection("Manual child")
        self.selected = collection("Selected", [self.child])
        self.other = collection("Other")
        self.unrelated = collection("Manual unrelated")
        self.parent = collection("Manual parent", [self.selected, self.other, self.unrelated])
        self.root = collection("Scene", [self.parent])

        def layer(item):
            return SimpleNamespace(
                collection=item,
                exclude=True,
                hide_viewport=True,
                children=[layer(child) for child in item.children],
            )

        self.scene = SimpleNamespace(collection=self.root, camera=None, world=None)
        self.view_layer = SimpleNamespace(layer_collection=layer(self.root))

    def test_preview_only_changes_registered_roots(self):
        self.api["preview_environment"](
            self.scene,
            self.view_layer,
            camera="Camera",
            world="World",
            light_collection=self.selected,
            other_light_collections=(self.other,),
        )
        self.assertFalse(self.selected.hide_render)
        self.assertFalse(self.selected.hide_viewport)
        for item in (self.child, self.unrelated, self.parent, self.root, self.other):
            self.assertTrue(item.hide_render, item.name_full)
            self.assertTrue(item.hide_viewport, item.name_full)
        self.assertEqual(self.scene.camera, "Camera")
        self.assertEqual(self.scene.world, "World")
        layers = self.api["layer_collections"](self.view_layer)
        for item in layers:
            self.assertEqual(item.exclude, item.collection is not self.selected)

    def test_render_switch_preserves_all_viewport_flags(self):
        self.api["switch_light_collections"](
            self.scene,
            self.view_layer,
            "local|Selected",
            ("local|Other",),
            viewport=False,
        )
        self.assertFalse(self.selected.hide_render)
        self.assertTrue(self.selected.hide_viewport)
        self.assertTrue(self.child.hide_render)
        self.assertTrue(self.unrelated.hide_render)

    def test_registered_ancestor_is_not_hidden_when_selecting_child(self):
        self.parent.hide_render = False
        self.api["switch_light_collections"](
            self.scene,
            self.view_layer,
            "local|Selected",
            ("local|Manual parent",),
            viewport=False,
        )
        self.assertFalse(self.parent.hide_render)
