"""Patch 1 GPT: Objective -> Portal -> BuiltDoor."""

import unittest

from svenmap.mechanics import add_objective
from svenmap.planning import (
    BlueprintConfig, blueprint_to_aligned_spec, build_blueprint_map,
    generate_blueprint, portal_to_legacy_door, resolve_all_portals,
    resolve_portal, validate_portal_geometry,
)
from svenmap.validator_portals import validate_portal_binding


class TestPortalBinding(unittest.TestCase):
    def test_registry_matches_blueprint(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=42, floors=1))
        ids = {c["id"] for c in blueprint["spatial"]["connections"]}
        portals = resolve_all_portals(blueprint)
        self.assertEqual(set(portals), ids)
        for portal in portals.values():
            self.assertEqual(validate_portal_geometry(portal, blueprint), [])
            self.assertIsNotNone(portal.door_bounds)

    def test_unknown_portal(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=42, floors=1))
        with self.assertRaises(KeyError):
            resolve_portal(blueprint, "portal_missing")

    def test_binding(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=7, floors=1))
        spec = blueprint_to_aligned_spec(blueprint)
        m = build_blueprint_map(blueprint, [], None)
        portals = resolve_all_portals(blueprint)
        goal_conn = next(
            c for c in blueprint["spatial"]["connections"]
            if c["b"] == spec.goal
        )
        portal = portals[goal_conn["id"]]
        add_objective(
            m, spec, None, script_name=spec.name,
            mode="collect", item_count=5,
            door_bounds=portal_to_legacy_door(portal),
            portal_id=portal.id,
        )
        binding = validate_portal_binding(blueprint, portals, m)
        self.assertTrue(binding["passed"], binding["errors"])
        self.assertEqual(binding["objective_portal"], portal.id)

    def test_items_use_portal_points(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=42, floors=1))
        spec = blueprint_to_aligned_spec(blueprint)
        m = build_blueprint_map(blueprint, [], None)
        portals = resolve_all_portals(blueprint)
        goal_conn = next(
            c for c in blueprint["spatial"]["connections"]
            if c["b"] == spec.goal
        )
        portal = portals[goal_conn["id"]]
        points = []
        for key in sorted(portals)[:5]:
            x, y, z = portals[key].item_point
            points.append((x, y, z, portals[key].area_a))
        add_objective(
            m, spec, None, script_name=spec.name,
            mode="collect", item_count=5,
            door_bounds=portal_to_legacy_door(portal),
            portal_id=portal.id, item_points=points,
        )
        item_centers = {i["center"] for i in m.meta["mechanics"]["items"]}
        expected = {(x, y) for x, y, _z, _a in points}
        self.assertEqual(len(item_centers & expected), 5)

    def test_determinism(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=1, floors=1))
        a = resolve_all_portals(blueprint)
        b = resolve_all_portals(blueprint)
        def key_map(registry):
            return {
                k: (v.door_bounds.x0, v.door_bounds.y0, v.door_bounds.z0,
                    v.door_bounds.x1, v.door_bounds.y1, v.door_bounds.z1)
                for k, v in registry.items()
            }
        self.assertEqual(key_map(a), key_map(b))


if __name__ == "__main__":
    unittest.main()
