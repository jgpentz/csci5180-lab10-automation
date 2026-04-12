"""Pydantic models for topology.yaml (Phase 1 validation)."""

from __future__ import annotations

import ipaddress
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def parse_cidr(value: str) -> ipaddress.IPv4Interface:
    try:
        return ipaddress.IPv4Interface(value)
    except ValueError as e:
        raise ValueError(f"Invalid IPv4 CIDR: {value!r}") from e


class GlobalSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ospf_process_id: int = Field(ge=1, le=65535)
    ospf_area: int | str = 0


class LoopbackSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface: str = "Loopback0"
    cidr: str

    @property
    def ipv4_interface(self) -> ipaddress.IPv4Interface:
        return parse_cidr(self.cidr)


class ManagementSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["svi", "routed"] = "svi"
    vlan: int | None = Field(default=None, ge=1, le=4094)
    interface: str | None = None
    cidr: str

    @model_validator(mode="after")
    def check_type_fields(self) -> ManagementSpec:
        if self.type == "svi" and self.vlan is None:
            raise ValueError("management.type=svi requires management.vlan")
        if self.type == "routed" and not self.interface:
            raise ValueError("management.type=routed requires management.interface")
        return self

    @property
    def ipv4_interface(self) -> ipaddress.IPv4Interface:
        return parse_cidr(self.cidr)


class DeviceInterface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    cidr: str
    ospf_network: Literal["point-to-point", "broadcast"] = "point-to-point"

    @property
    def ipv4_interface(self) -> ipaddress.IPv4Interface:
        return parse_cidr(self.cidr)


class Device(BaseModel):
    """Per-node topology entry (gateway = L3 router, routed mgmt)."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["leaf", "spine", "gateway"]
    loopback: LoopbackSpec
    management: ManagementSpec
    interfaces: list[DeviceInterface] = Field(default_factory=list)
    router_id: str | None = None

    @model_validator(mode="after")
    def gateway_uses_routed_management(self) -> Device:
        if self.role == "gateway" and self.management.type != "routed":
            raise ValueError("gateway devices require management.type=routed (no SVI)")
        return self

    @field_validator("router_id")
    @classmethod
    def validate_router_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            ipaddress.IPv4Address(v)
        except ValueError as e:
            raise ValueError(f"router_id must be a dotted IPv4: {v!r}") from e
        return v


class Topology(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version: int = 1
    global_settings: GlobalSettings = Field(alias="global")
    devices: dict[str, Device]

    @model_validator(mode="after")
    def validate_hostnames(self) -> Topology:
        for hostname in self.devices:
            if not hostname or len(hostname) > 63:
                raise ValueError(f"Invalid hostname: {hostname!r}")
        return self

    def router_id_for(self, device: Device) -> str:
        if device.router_id:
            return device.router_id
        return str(device.loopback.ipv4_interface.ip)


def ios_ipv4_with_mask(cidr: str) -> tuple[str, str]:
    """Return (address, dotted_decimal_mask) for Cisco IOS."""
    iface = parse_cidr(cidr)
    host = str(iface.ip)
    mask = str(iface.network.netmask)
    return host, mask
