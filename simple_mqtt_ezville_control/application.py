import asyncio
import time
from queue import Queue

from device_manager import DeviceManager
from mqtt_client import MQTTClientManager
from ew11_client import EW11Client
from packet_processor import PacketProcessor
from command_handler import CommandHandler
from constants import HA_TOPIC, EW11_TOPIC
from utils import log


class EzvilleApplication:
    """Ezville 애플리케이션 메인 클래스"""
    
    def __init__(self, config):
        self.config = config
        
        # 컴포넌트 초기화
        self.device_manager = DeviceManager()
        self.mqtt_client = MQTTClientManager(config, self.device_manager)
        
        # 통신 모드에 따라 EW11 클라이언트 초기화
        self.comm_mode = config['mode']
        if self.comm_mode in ['socket', 'mixed']:
            self.ew11_client = EW11Client(config)
        else:
            self.ew11_client = None
        
        self.packet_processor = PacketProcessor(config, self.device_manager, self.mqtt_client)
        self.command_handler = CommandHandler(config, self.device_manager, self.mqtt_client, self.ew11_client)
        
        # 설정값
        self.state_loop_delay = config['state_loop_delay']
        self.restart_check_delay = config['restart_check_delay']
        self.reboot_control = config['reboot_control']
        
        # 강제 업데이트 설정
        self.force_mode = config['force_update_mode']
        self.force_period = config['force_update_period']
        self.force_duration = config['force_update_duration']
        
        # 상태 플래그
        self.restart_flag = False
        self.addon_started = False
        self.last_received_time = time.time()
        
        # 시간 변수
        self.force_target_time = time.time() + self.force_period
        self.force_stop_time = self.force_target_time + self.force_duration
        
    async def process_message(self):
        """MQTT message를 분류하여 처리"""
        while self.mqtt_client.has_messages():
            msg = self.mqtt_client.get_message()
            if not msg:
                break
                
            topics = msg.topic.split('/')

            if topics[0] == HA_TOPIC and topics[-1] == 'command':
                await self.command_handler.process_ha_command(topics, msg.payload.decode('utf-8'))
            elif topics[0] == EW11_TOPIC and topics[-1] == 'recv':
                # Que에서 확인된 시간 기준으로 EW11 Health Check함.
                self.last_received_time = time.time()
                if self.ew11_client:
                    self.ew11_client.update_receive_time()

                await self.packet_processor.process_packet(msg.payload.hex().upper())
    
    async def state_update_loop(self):
        """상태 업데이트 루프"""
        while True:
            # 메시지가 있는 동안 계속 처리
            has_messages = self.mqtt_client.has_messages()
            
            if has_messages:
                # 메시지가 있으면 모두 처리
                await self.process_message()
            
            timestamp = time.time()
            
            # 정해진 시간이 지나면 FORCE 모드 발동
            if timestamp > self.force_target_time and not self.device_manager.force_update and self.force_mode:
                self.force_stop_time = timestamp + self.force_duration
                self.device_manager.force_update = True
                log('[INFO] 상태 강제 업데이트 실시')
                
            # 정해진 시간이 지나면 FORCE 모드 종료    
            if timestamp > self.force_stop_time and self.device_manager.force_update and self.force_mode:
                self.force_target_time = timestamp + self.force_period
                self.device_manager.force_update = False
                log('[INFO] 상태 강제 업데이트 종료')
            
            # 메시지가 있을 때는 짧은 시간(0.001초)만 대기하여 빠르게 처리
            # 메시지가 없을 때만 STATE_LOOP_DELAY 대기
            if has_messages:
                await asyncio.sleep(0.001)  # 1ms 대기로 CPU 과부하 방지
            else:
                await asyncio.sleep(self.state_loop_delay)
    
    async def restart_control(self):
        """EW11 재실행 시 리스타트 실시"""
        while True:
            if self.restart_flag or (not self.mqtt_client.mqtt_online and self.addon_started and self.reboot_control):
                if self.restart_flag:
                    log('[WARNING] EW11 재시작 확인')
                elif not self.mqtt_client.mqtt_online and self.addon_started and self.reboot_control:
                    log('[WARNING] 동작 중 MQTT Integration Offline 변경')
                
                # Asyncio Loop 획득
                loop = asyncio.get_event_loop()
                
                # MTTQ 및 socket 연결 종료
                log('[WARNING] 모든 통신 종료')
                self.mqtt_client.stop()
                if self.ew11_client:
                    self.ew11_client.close()
                       
                # flag 원복
                self.restart_flag = False
                self.mqtt_client.mqtt_online = False

                # asyncio loop 종료
                log('[WARNING] asyncio loop 종료')
                loop.stop()
            
            # RESTART_CHECK_DELAY초 마다 실행
            await asyncio.sleep(self.restart_check_delay)
    
    def set_restart_flag(self, value):
        """재시작 플래그 설정"""
        self.restart_flag = value
    
    def run(self):
        """애플리케이션 실행"""
        # MQTT 클라이언트 연결
        self.mqtt_client.connect()
        
        # asyncio loop 획득 및 EW11 오류시 재시작 task 등록
        loop = asyncio.get_event_loop()
        loop.create_task(self.restart_control())
        
        # Discovery 및 강제 업데이트 시간 설정
        self.force_target_time = time.time() + self.force_period
        self.force_stop_time = self.force_target_time + self.force_duration
        
        while True:
            # MQTT 통신 시작
            self.mqtt_client.start()
            
            # MQTT Integration의 Birth/Last Will Testament를 기다림 (1초 단위)
            while not self.mqtt_client.mqtt_online and self.reboot_control:
                log('[INFO] Waiting for MQTT connection')
                time.sleep(1)
            
            # socket 통신 시작       
            if self.comm_mode in ['mixed', 'socket']:
                self.ew11_client.initiate_socket()

            log('[INFO] 장치 등록 및 상태 업데이트를 시작합니다')

            tasklist = []
     
            # 필요시 Discovery 등의 지연을 위해 Delay 부여 
            time.sleep(self.mqtt_client.startup_delay)      
      
            # socket 데이터 수신 loop 실행
            if self.comm_mode == 'socket':
                tasklist.append(loop.create_task(self.ew11_client.serial_recv_loop(self.mqtt_client.msg_queue)))
            
            # EW11 패킷 기반 state 업데이트 loop 실행
            tasklist.append(loop.create_task(self.state_update_loop()))
            
            # Home Assistant 명령 실행 loop 실행
            tasklist.append(loop.create_task(self.command_handler.command_loop()))
            
            # EW11 상태 체크 loop 실행
            if self.ew11_client:
                tasklist.append(loop.create_task(self.ew11_client.health_check_loop(self.set_restart_flag)))
            
            # ADDON 정상 시작 Flag 설정
            self.addon_started = True
            loop.run_forever()
            
            # 이전 task는 취소
            log('[INFO] 이전 실행 Task 종료')
            for task in tasklist:
                task.cancel()

            self.addon_started = False
            
            # 주요 변수 초기화
            self.mqtt_client.msg_queue = Queue()
            self.command_handler.cmd_queue = asyncio.Queue()
            self.device_manager.reset()
