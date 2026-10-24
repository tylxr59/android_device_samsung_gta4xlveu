#!/usr/bin/env python3
"""Check the SM-P613 reporting-only thermal configuration's safety contract."""
import json
from pathlib import Path
import sys


def check(config):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(config.get('CoolingDevices') == [], 'Cooling control must remain with kernel/vendor')
    expected = {
        'cpu-0-max-step': ('CPU', None, 120),
        'cpu-1-max-step': ('CPU', None, 120),
        'gpuss-max-step': ('GPU', None, 95),
        'battery': ('BATTERY', 42, 50),
    }
    rows = config['Sensors']
    names = [r['Name'] for r in rows]
    require(len(names) == len(set(names)) == 8, 'Expected four unique physical/virtual pairs')
    by_name = {r['Name']: r for r in rows}
    require(set(names) == set(expected) | {'reported-' + n for n in expected}, 'Unknown sensor')
    for name, (kind, moderate, severe) in expected.items():
        raw, reported = by_name[name], by_name['reported-' + name]
        require(raw.get('Monitor') is False and raw.get('Hidden') is True,
                name + ': physical sensors must never be monitored or exposed')
        require(not raw.get('SendCallback') and not raw.get('SendPowerHint') and
                not raw.get('BindedCdevInfo') and not raw.get('VirtualSensor'),
                name + ': physical control/virtualization is forbidden')
        require(reported.get('VirtualSensor') is True and reported.get('Monitor') is True,
                name + ': only virtual pass-through sensors may be monitored')
        require(reported.get('Combination') == [name] and
                reported.get('Formula') == 'MAXIMUM' and
                reported.get('Coefficient') == ['1.0'], name + ': altered temperature formula')
        require(not reported.get('SendPowerHint') and not reported.get('BindedCdevInfo') and
                not reported.get('TempPath') and not reported.get('TriggerSensor'),
                name + ': unexpected control or file override')
        require(reported.get('Type') == raw.get('Type') == kind and
                reported.get('Multiplier') == raw.get('Multiplier') == 0.001,
                name + ': type/units mismatch')
        thresholds = ['NAN'] * 7
        if moderate is not None:
            thresholds[2] = moderate
        thresholds[3] = severe
        require(reported.get('HotThreshold') == thresholds,
                name + ': thresholds differ from observed kernel/battery policy')
        require(not reported.get('ColdThreshold'), name + ': unreviewed cold policy')
        require(reported.get('PollingDelay', 0) >= 5000 and
                reported.get('PassiveDelay', 0) >= 1000, name + ': excessive polling')
    return True


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('thermal_info_config.json')
    check(json.loads(path.read_text()))
    print('Reporting-only thermal configuration safety checks passed')
