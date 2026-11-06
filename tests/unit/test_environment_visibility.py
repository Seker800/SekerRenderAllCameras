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

    def test_preview_only_sets_camera_and_world(self):
        self.other.hide_render = False
        self.other.hide_viewport = False
        collections = (
            self.selected,
            self.other,
            self.child,
            self.unrelated,
            self.parent,
            self.root,
        )
        before = {
            item.name_full: (item.hide_render, item.hide_viewport)
            for item in collections
        }
        before_layers = {
            item.collection.name_full: item.exclude
            for item in self.api["layer_collections"](self.view_layer)
        }
        self.api["preview_environment"](
            self.scene,
            camera="Camera",
            world="World",
        )
        after = {
            item.name_full: (item.hide_render, item.hide_viewport)
            for item in collections
        }
        self.assertEqual(after, before)
        self.assertEqual(
            {
                item.collection.name_full: item.exclude
                for item in self.api["layer_collections"](self.view_layer)
            },
            before_layers,
        )
        self.assertEqual(self.scene.camera, "Camera")
        self.assertEqual(self.scene.world, "World")

    def test_render_switch_preserves_all_viewport_flags(self):
        self.other.hide_render = False
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
        self.assertTrue(self.other.hide_render)

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
