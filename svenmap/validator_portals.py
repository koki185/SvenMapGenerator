"""QA связи Objective -> Portal -> BuiltDoor (Patch 1)."""

from typing import Dict


def validate_portal_binding(blueprint: dict, portals: Dict, m) -> dict:
    """Проверить, что механика ссылается на реальный портал Blueprint."""
    ids = {c.get("id") for c in blueprint["spatial"]["connections"]}
    registry_ids = set(portals)
    built = m.meta.get("built_doors", {})
    mech = m.meta.get("mechanics", {})
    objective_portal = mech.get("portal_id")
    secret_portals = [
        b.get("portal_id")
        for b in m.meta.get("secrets", {}).get("secrets", [])
        if b.get("portal_id")
    ]

    errors = []
    if ids != registry_ids:
        errors.append(
            "registry не совпадает с Blueprint: {} / {}".format(
                sorted(ids - registry_ids), sorted(registry_ids - ids)
            )
        )
    if not built:
        errors.append("нет построенных дверей")
    if objective_portal and objective_portal not in built:
        errors.append("objective.portal_id не найден среди built_doors")
    if objective_portal and objective_portal not in registry_ids:
        errors.append("objective.portal_id нет в registry")
    for portal_id in secret_portals:
        if portal_id not in registry_ids:
            errors.append("secret portal_id нет в registry: " + str(portal_id))

    return {
        "blueprint_portals": len(ids),
        "resolved": len(registry_ids),
        "built_doors": len(built),
        "objective_portal": objective_portal,
        "secret_portals": secret_portals,
        "errors": errors,
        "passed": not errors,
    }
