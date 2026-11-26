"""Midea Cloud models."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class MideaCloudAppliance:
    """An appliance registered on a Midea cloud account."""

    appliance_code: int
    name: str
    appliance_type: int
    sn: str
    sn8: str
    model: str
    model_number: str
    manufacturer_code: str
    smart_product_id: str | None
    category: str | None
    online: bool
