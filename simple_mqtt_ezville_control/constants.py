# DEVICE 별 패킷 정보
RS485_DEVICE = {
    'light': {
        'state':    { 'id': '0E', 'cmd': '81' },

        'power':    { 'id': '0E', 'cmd': '41', 'ack': 'C1' }
    },
    'thermostat': {
        'state':    { 'id': '35', 'cmd': '81' },
        
        'power':    { 'id': '35', 'cmd': '43', 'ack': 'C3' },
        'away':    { 'id': '35', 'cmd': '45', 'ack': 'C5' },
        'target':   { 'id': '35', 'cmd': '43', 'ack': 'C3' }
    },
    'plug': {
        'state':    { 'id': '50', 'cmd': '81' },

        'power':    { 'id': '50', 'cmd': '43', 'ack': 'C3' }
    },
    'gasvalve': {
        'state':    { 'id': '12', 'cmd': '81' },

        'power':    { 'id': '12', 'cmd': '41', 'ack': 'C1' } # 잠그기만 가능
    },
    'batch': {
        'state':    { 'id': '33', 'cmd': '81' },

        'press':    { 'id': '33', 'cmd': '41', 'ack': 'C1' }
    }
}

# MQTT Discovery를 위한 Preset 정보
DISCOVERY_DEVICE = {
    'ids': ['ezville_wallpad',],
    'name': 'ezville_wallpad',
    'mf': 'EzVille',
    'mdl': 'EzVille Wallpad',
    'sw': 'ktdo79/addons/ezville_wallpad',
}

# MQTT Discovery를 위한 Payload 정보
DISCOVERY_PAYLOAD = {
    'light': [ {
        '_intg': 'light',
        '~': 'ezville/light_{:0>2d}_{:0>2d}',
        'name': 'ezville_light_{:0>2d}_{:0>2d}',
        'opt': True,
        'stat_t': '~/power/state',
        'cmd_t': '~/power/command'
    } ],
    'thermostat': [ {
        '_intg': 'climate',
        '~': 'ezville/thermostat_{:0>2d}_{:0>2d}',
        'name': 'ezville_thermostat_{:0>2d}_{:0>2d}',
        'mode_cmd_t': '~/power/command',
        'mode_stat_t': '~/power/state',
        'temp_stat_t': '~/setTemp/state',
        'temp_cmd_t': '~/setTemp/command',
        'curr_temp_t': '~/curTemp/state',
#        "modes": [ "off", "heat", "fan_only" ],     # 외출 모드는 fan_only로 매핑
        'modes': [ 'heat', 'off' ],     # 외출 모드는 off로 매핑
        'min_temp': '5',
        'max_temp': '40'
    } ],
    'plug': [ {
        '_intg': 'switch',
        '~': 'ezville/plug_{:0>2d}_{:0>2d}',
        'name': 'ezville_plug_{:0>2d}_{:0>2d}',
        'stat_t': '~/power/state',
        'cmd_t': '~/power/command',
        'icon': 'mdi:leaf'
    },
    {
        '_intg': 'binary_sensor',
        '~': 'ezville/plug_{:0>2d}_{:0>2d}',
        'name': 'ezville_plug-automode_{:0>2d}_{:0>2d}',
        'stat_t': '~/auto/state',
        'icon': 'mdi:leaf'
    },
    {
        '_intg': 'sensor',
        '~': 'ezville/plug_{:0>2d}_{:0>2d}',
        'name': 'ezville_plug_{:0>2d}_{:0>2d}_powermeter',
        'stat_t': '~/current/state',
        'unit_of_meas': 'W'
    } ],
    'gasvalve': [ {
        '_intg': 'switch',
        '~': 'ezville/gasvalve_{:0>2d}_{:0>2d}',
        'name': 'ezville_gasvalve_{:0>2d}_{:0>2d}',
        'stat_t': '~/power/state',
        'cmd_t': '~/power/command',
        'icon': 'mdi:valve'
    } ],
    'batch': [ {
        '_intg': 'button',
        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
        'name': 'ezville_batch-elevator-up_{:0>2d}_{:0>2d}',
        'cmd_t': '~/elevator-up/command',
        'icon': 'mdi:elevator-up'
    },
    {
        '_intg': 'button',
        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
        'name': 'ezville_batch-elevator-down_{:0>2d}_{:0>2d}',
        'cmd_t': '~/elevator-down/command',
        'icon': 'mdi:elevator-down'
    },
    {
        '_intg': 'binary_sensor',
        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
        'name': 'ezville_batch-groupcontrol_{:0>2d}_{:0>2d}',
        'stat_t': '~/group/state',
        'icon': 'mdi:lightbulb-group'
    },
    {
        '_intg': 'binary_sensor',
        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
        'name': 'ezville_batch-outing_{:0>2d}_{:0>2d}',
        'stat_t': '~/outing/state',
        'icon': 'mdi:home-circle'
    } ]
}

# STATE 확인용 Dictionary
STATE_HEADER = {
    prop['state']['id']: (device, prop['state']['cmd'])
    for device, prop in RS485_DEVICE.items()
    if 'state' in prop
}

# ACK 확인용 Dictionary
ACK_HEADER = {
    prop[cmd]['id']: (device, prop[cmd]['ack'])
    for device, prop in RS485_DEVICE.items()
        for cmd, code in prop.items()
            if 'ack' in code
}

# MQTT Topics
HA_TOPIC = 'ezville'
STATE_TOPIC = HA_TOPIC + '/{}/{}/state'
EW11_TOPIC = 'ew11'
EW11_SEND_TOPIC = EW11_TOPIC + '/send'

# Configuration directory
CONFIG_DIR = '/data'
