"""PR-5: совместимость нового pipeline с legacy builder и QA."""

import unittest

from svenmap.builders import build_level
from svenmap.mechanics import add_objective, validate_objective
from svenmap.planning import (
    BlueprintConfig, blueprint_to_level_spec, generate_blueprint,
)
from svenmap.validator import unreachable_areas


class TestPipelineV2(unittest.TestCase):
    def test_adapter_30_seeds(self):
        for seed in range(1, 31):
            blueprint = generate_blueprint(
                BlueprintConfig(seed=seed, floors=1)
            )
            spec = blueprint_to_level_spec(blueprint)
            self.assertEqual(spec.start, "spawn")
            self.assertEqual(spec.goal, "goal")
            self.assertGreater(len(spec.connections), 0)

    def test_build_and_objective(self):
        for seed in (1, 7, 42):
            blueprint = generate_blueprint(
                BlueprintConfig(seed=seed, floors=1)
            )
            spec = blueprint_to_level_spec(blueprint)
            m = build_level(spec, [], seed=seed)
            self.assertEqual(unreachable_areas(m.solids, spec), [])
            add_objective(m, spec, None, script_name=spec.name,
                          mode="collect", item_count=5)
            checks = validate_objective(spec, m)
            self.assertTrue(checks.get("objective"),
                            "seed {}: {}".format(seed, checks))


if __name__ == "__main__":
    unittest.main()
