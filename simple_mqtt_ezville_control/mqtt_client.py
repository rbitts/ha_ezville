import asyncio
import json
from queue import Queue

import paho.mqtt.client as mqtt

from constants import HA_TOPIC, EW11_TOPIC, STATE_TOPIC, DISCOVERY_DEVICE
from utils import log


class MQTTClientManager:
    """MQTT 통신 관리 클래스"""
    
    def __init__(self, config, device_manager):
        self.config = config
        self.device_manager = device_manager
        self.msg_queue = Queue()
        self.mqtt_online = False
        self.startup_delay = 0
        self.client = None
        
        # 로그 플래그
        self.mqtt_log = config['MQTT_LOG']
        self.reboot_control = config['reboot_control']
        self.reboot_delay = config['reboot_delay']
        self.comm_mode = config['mode']
        
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT 통신 연결 Callback"""
        if reason_code == 0:
            log('[INFO] MQTT Broker 연결 성공')
            # Socket인 경우 MQTT 장치의 명령 관련과 MQTT Status (Birth/Last Will Testament) Topic만 구독
            if self.comm_mode == 'socket':
                client.subscribe([(HA_TOPIC + '/#', 0), ('homeassistant/status', 0)])
            # Mixed인 경우 MQTT 장치 및 EW11의 명령/수신 관련 Topic 과 MQTT Status (Birth/Last Will Testament) Topic 만 구독
            elif self.comm_mode == 'mixed':
                client.subscribe([(HA_TOPIC + '/#', 0), (EW11_TOPIC + '/recv', 0), ('homeassistant/status', 0)])
            # MQTT 인 경우 모든 Topic 구독
            else:
                client.subscribe([(HA_TOPIC + '/#', 0), (EW11_TOPIC + '/recv', 0), (EW11_TOPIC + '/send', 1), ('homeassistant/status', 0)])
        else:
            errcode = {1: 'Connection refused - incorrect protocol version',
                       2: 'Connection refused - invalid client identifier',
                       3: 'Connection refused - server unavailable',
                       4: 'Connection refused - bad username or password',
                       5: 'Connection refused - not authorised'}
            log(errcode.get(reason_code.value, f'Connection refused - unknown reason: {reason_code}'))
         
    def _on_message(self, client, userdata, msg):
        """MQTT 메시지 Callback"""
        if msg.topic == 'homeassistant/status':
            # Reboot Control 사용 시 MQTT Integration의 Birth/Last Will Testament Topic은 바로 처리
            if self.reboot_control:
                status = msg.payload.decode('utf-8')
                
                if status == 'online':
                    log('[INFO] MQTT Integration 온라인')
                    self.mqtt_online = True
                    if not msg.retain:
                        log('[INFO] MQTT Birth Message가 Retain이 아니므로 정상화까지 Delay 부여')
                        self.startup_delay = self.reboot_delay
                elif status == 'offline':
                    log('[INFO] MQTT Integration 오프라인')
                    self.mqtt_online = False
        # 나머지 topic은 모두 Queue에 보관
        else:
            self.msg_queue.put(msg)
 
    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """MQTT 통신 연결 해제 Callback"""
        log('INFO: MQTT 연결 해제')
        
    def connect(self):
        """MQTT 클라이언트 연결"""
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 'mqtt-ezville')
        self.client.username_pw_set(self.config['mqtt_id'], self.config['mqtt_password'])
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.connect_async(self.config['mqtt_server'])
        
    def start(self):
        """MQTT 루프 시작"""
        if self.client:
            self.client.loop_start()
    
    def stop(self):
        """MQTT 루프 정지"""
        if self.client:
            self.client.loop_stop()
    
    def publish(self, topic, payload):
        """메시지 발행"""
        if self.client:
            self.client.publish(topic, payload)
    
    def get_message(self):
        """메시지 큐에서 가져오기"""
        if not self.msg_queue.empty():
            return self.msg_queue.get()
        return None
    
    def has_messages(self):
        """메시지 큐에 메시지가 있는지 확인"""
        return not self.msg_queue.empty()
    
    async def mqtt_discovery(self, payload):
        """MQTT Discovery로 장치 자동 등록"""
        intg = payload.pop('_intg')

        # MQTT 통합구성요소에 등록되기 위한 추가 내용
        payload['device'] = DISCOVERY_DEVICE
        payload['uniq_id'] = payload['name']

        # Discovery에 등록
        topic = 'homeassistant/{}/ezville_wallpad/{}/config'.format(intg, payload['name'])
        log('[INFO] 장치 등록:  {}'.format(topic))
        self.publish(topic, json.dumps(payload))
    
    async def update_state(self, device, state, id1, id2, value):
        """장치 State를 MQTT로 Publish"""
        deviceID = '{}_{:0>2d}_{:0>2d}'.format(device, id1, id2)
        key = deviceID + state
        
        if value != self.device_manager.get_state(key) or self.device_manager.force_update:
            self.device_manager.set_state(key, value)
            
            topic = STATE_TOPIC.format(deviceID, state)
            self.publish(topic, value.encode())
                    
            if self.mqtt_log:
                log('[LOG] ->> HA : {} >> {}'.format(topic, value))
        return
