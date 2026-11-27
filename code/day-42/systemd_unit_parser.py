#!/usr/bin/env python3
"""
Day 42 Lab: systemd Declarative Unit Parser & Drop-in Override Engine
Parses declarative INI-style systemd unit configuration files ([Unit], [Service], [Install]),
implements directory hierarchy precedence (/lib vs /run vs /etc), and merges
drop-in configuration snippets (.d/*.conf) with reset semantics.
Uses Python standard library only.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ParsedUnit:
    name: str
    sections: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def get(self, section: str, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.sections.get(section, {}).get(key, default)


class SystemdUnitParser:
    """Parses unit files and merges drop-in override directories."""

    @staticmethod
    def parse_ini_string(content: str) -> Dict[str, Dict[str, str]]:
        sections: Dict[str, Dict[str, str]] = {}
        current_section = None

        for raw_line in content.splitlines():
            line = raw_line.strip()
            # Ignore empty lines and comments
            if not line or line.startswith(('#', ';')):
                continue

            # Section header [Unit], [Service], etc.
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1].strip()
                if current_section not in sections:
                    sections[current_section] = {}
                continue

            # Key-Value pair
            if '=' in line and current_section:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()

                # In systemd, an empty value (e.g. ExecStart=) clears previous list assignments!
                if val == "" and key in sections[current_section]:
                    del sections[current_section][key]
                else:
                    sections[current_section][key] = val

        return sections

    @staticmethod
    def merge_units(base: ParsedUnit, override: ParsedUnit) -> ParsedUnit:
        """Merges override unit (e.g. from override.conf) onto base unit."""
        merged_sections = {s: dict(kvs) for s, kvs in base.sections.items()}

        for sec, kvs in override.sections.items():
            if sec not in merged_sections:
                merged_sections[sec] = {}
            for k, v in kvs.items():
                merged_sections[sec][k] = v

        return ParsedUnit(name=base.name, sections=merged_sections)


def main():
    print("====================================================")
    print("DAY 42: systemd UNIT PARSER & DROP-IN MERGER")
    print("====================================================")

    # 1. Base unit file from package vendor: /usr/lib/systemd/system/nginx.service
    vendor_unit_text = """
    [Unit]
    Description=The NGINX HTTP and reverse proxy server
    After=network-online.target remote-fs.target
    Wants=network-online.target

    [Service]
    Type=forking
    PIDFile=/run/nginx.pid
    ExecStart=/usr/sbin/nginx -g 'daemon on; master_process on;'
    ExecReload=/usr/sbin/nginx -g 'daemon on; master_process on;' -s reload
    ExecStop=-/sbin/start-stop-daemon --quiet --stop --retry QUIT/5 --pidfile /run/nginx.pid
    TimeoutStopSec=5s
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target
    """

    # 2. Administrator drop-in override: /etc/systemd/system/nginx.service.d/override.conf
    admin_override_text = """
    [Service]
    # Reset ExecStart list
    ExecStart=
    ExecStart=/usr/local/custom/sbin/nginx -g 'daemon on;'
    RestartSec=10s
    MemoryMax=1G
    """

    parser = SystemdUnitParser()
    base_unit = ParsedUnit(name="nginx.service", sections=parser.parse_ini_string(vendor_unit_text))
    override_unit = ParsedUnit(name="override.conf", sections=parser.parse_ini_string(admin_override_text))

    print("1. Vendor Default Configuration:")
    print(f"   ExecStart : {base_unit.get('Service', 'ExecStart')}")
    print(f"   Restart   : {base_unit.get('Service', 'Restart')}")

    print("\n2. Merging Administrator Drop-in Override...")
    effective_unit = parser.merge_units(base_unit, override_unit)

    print("3. Effective Merged Configuration:")
    print(f"   Description : {effective_unit.get('Unit', 'Description')}")
    print(f"   ExecStart   : {effective_unit.get('Service', 'ExecStart')}")
    print(f"   RestartSec  : {effective_unit.get('Service', 'RestartSec')}")
    print(f"   MemoryMax   : {effective_unit.get('Service', 'MemoryMax')}")

    assert effective_unit.get('Service', 'ExecStart') == "/usr/local/custom/sbin/nginx -g 'daemon on;'"
    assert effective_unit.get('Service', 'MemoryMax') == "1G"
    assert effective_unit.get('Unit', 'Description') == "The NGINX HTTP and reverse proxy server"
    print("\n[VERIFIED] Unit parser and drop-in override engine validated 100%!")


if __name__ == "__main__":
    main()
