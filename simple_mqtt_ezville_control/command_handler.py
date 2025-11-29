import asyncio
import random

from constants import RS485_DEVICE, EW11_SEND_TOPIC
from utils import log, checksum


class CommandHandler:
    """HA 명령 처리 클래스"""
    
    def __init__(self, config, device_manager, mqtt_client, ew11_client=None):
        self.config = config
        self.device_manager = device_manager
        self.mqtt_client = mqtt_client
        self.ew11_client = ew11_client
        self.cmd_queue = asyncio.Queue()
        
        # 설정값
        self.debug = config['DEBUG_LOG']
        self.mqtt_log = config['MQTT_LOG']
        self.ew11_log = config['EW11_LOG']
        self.comm_mode = config['mode']
        self.cmd_interval = config['command_interval']
        self.cmd_retry_count = config['command_retry_count']
        self.first_waittime = config['first_waittime']
        self.random_backoff = config['random_backoff']
        self.command_loop_delay = config['command_loop_delay']
        
    async def process_ha_command(self, topics, value):
        """HA에서 전달된 메시지 처리"""
        device_info = topics[1].split('_')
        device = device_info[0]
        
        if self.mqtt_log:
            log('[LOG] HA ->> : {} -> {}'.format('/'.join(topics), value))

        if device in RS485_DEVICE:
            key = topics[1] + topics[2]
            idx = int(device_info[1])
            sid = int(device_info[2])
            cur_state = self.device_manager.get_state(key)
            
            if value == cur_state:
                return
            else:
                if device == 'thermostat':
                    await self._handle_thermostat_command(topics, value, idx, sid, key)
                elif device == 'light':
                    await self._handle_light_command(value, idx, sid, key)
                elif device == 'plug':
                    await self._handle_plug_command(value, idx, sid, key)
                elif device == 'gasvalve':
                    await self._handle_gasvalve_command(value, idx, key)
                elif device == 'batch':
                    await self._handle_batch_command(topics, idx, key)
    
    async def _handle_thermostat_command(self, topics, value, idx, sid, key):
        """온도조절기 명령 처리"""
        device = 'thermostat'
        
        if topics[2] == 'power':
            if value == 'heat':
                sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + '01010000')
                recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
                statcmd = [key, value]
               
                await self.cmd_queue.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
            
            # Thermostat는 외출 모드를 Off 모드로 연결
            elif value == 'off':
                sendcmd = checksum('F7' + RS485_DEVICE[device]['away']['id'] + '1' + str(idx) + RS485_DEVICE[device]['away']['cmd'] + '01010000')
                recvcmd = 'F7' + RS485_DEVICE[device]['away']['id'] + '1' + str(idx) + RS485_DEVICE[device]['away']['ack']
                statcmd = [key, value]
               
                await self.cmd_queue.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
                                        
            if self.debug:
                log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))
                            
        elif topics[2] == 'setTemp':
            value = int(float(value))
            
            # BCD encoding for temperature (e.g., 14 -> "14")
            bcd_value = "{:02d}".format(value)

            # Payload: 03 (Len) + 01 (Fixed) + Temp + 00
            sendcmd = checksum('F7' + RS485_DEVICE[device]['target']['id'] + '1' + str(idx) + RS485_DEVICE[device]['target']['cmd'] + '0301' + bcd_value + '000000')
            recvcmd = 'F7' + RS485_DEVICE[device]['target']['id'] + '1' + str(idx) + RS485_DEVICE[device]['target']['ack']
            statcmd = [key, str(value)]

            await self.cmd_queue.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
                   
            if self.debug:
                log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))
    
    async def _handle_light_command(self, value, idx, sid, key):
        """조명 명령 처리"""
        device = 'light'
        pwr = '01' if value == 'ON' else '00'
            
        sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + '030' + str(sid) + pwr + '000000')
        recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
        statcmd = [key, value]
        
        await self.cmd_queue.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
                   
        if self.debug:
            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))
    
    async def _handle_plug_command(self, value, idx, sid, key):
        """플러그 명령 처리"""
        device = 'plug'
        pwr = '01' if value == 'ON' else '00'

        sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + '020' + str(sid) + pwr + '0000')
        recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
        statcmd = [key, value]
            
        await self.cmd_queue.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
                   
        if self.debug:
            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))
    
    async def _handle_gasvalve_command(self, value, idx, key):
        """가스밸브 명령 처리"""
        device = 'gasvalve'
        # 가스 밸브는 ON 제어를 받지 않음
        if value == 'OFF':
            sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '0' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + '0100' + '0000')
            recvcmd = ['F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']]
            statcmd = [key, value]

            await self.cmd_queue.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
                   
            if self.debug:
                log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))
    
    async def _handle_batch_command(self, topics, idx, key):
        """일괄차단기 명령 처리"""
        device = 'batch'
        # Batch는 Elevator 및 외출/그룹 조명 버튼 상태 고려 
        elup_state = '1' if self.device_manager.get_state(topics[1] + 'elevator-up') == 'ON' else '0'
        eldown_state = '1' if self.device_manager.get_state(topics[1] + 'elevator-down') == 'ON' else '0'
        out_state = '1' if self.device_manager.get_state(topics[1] + 'outing') == 'ON' else '0'
        group_state = '1' if self.device_manager.get_state(topics[1] + 'group') == 'ON' else '0'

        # 일괄 차단기는 4가지 모드로 조절               
        if topics[2] == 'elevator-up':
            elup_state = '1'
        elif topics[2] == 'elevator-down':
            eldown_state = '1'
# 그룹 조명과 외출 모드 설정은 테스트 후에 추가 구현                                                
#                    elif topics[2] == 'group':
#                        group_state = '1'
#                    elif topics[2] == 'outing':
#                        out_state = '1'
                    
        CMD = '{:0>2X}'.format(int('00' + eldown_state + elup_state + '0' + group_state + out_state + '0', 2))
        
        # 일괄 차단기는 state를 변경하여 제공해서 월패드에서 조작하도록 해야함
        # 월패드의 ACK는 무시
        sendcmd = checksum('F7' + RS485_DEVICE[device]['state']['id'] + '0' + str(idx) + RS485_DEVICE[device]['state']['cmd'] + '0300' + CMD + '000000')
        recvcmd = 'NULL'
        statcmd = [key, 'NULL']
        
        await self.cmd_queue.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
        
        if self.debug:
            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))
    
    async def send_to_ew11(self, send_data):
        """HA에서 전달된 명령을 EW11 패킷으로 전송"""
        # 0.05초 간격으로 상태 확인 (20Hz polling)
        # 수신 패킷 처리에 더 많은 시간을 할애
        POLLING_INTERVAL = 0.05
        
        for i in range(self.cmd_retry_count):
            if self.ew11_log:
                log('[SIGNAL] 신호 전송: {}'.format(send_data))
                        
            if self.comm_mode == 'mqtt':
                self.mqtt_client.publish(EW11_SEND_TOPIC, bytes.fromhex(send_data['sendcmd']))
            else:
                if self.ew11_client:
                    self.ew11_client.send(send_data['sendcmd'])
            
            if self.debug:
                log('[DEBUG] Iter. No.: ' + str(i + 1) + ', Target: ' + send_data['statcmd'][1] + ', Current: ' + str(self.device_manager.get_state(send_data['statcmd'][0])))
              
            # Ack나 State 업데이트가 불가한 경우 한번만 명령 전송 후 Return
            if send_data['statcmd'][1] == 'NULL':
                return
      
            # 대기 시간 계산
            if i == 0:
                wait_time = self.first_waittime
            else:
                if self.random_backoff:
                    wait_time = random.randint(0, int(self.cmd_interval * 1000))/1000
                else:
                    wait_time = self.cmd_interval
            
            # 짧은 간격으로 폴링하면서 상태 확인
            # 이렇게 하면 ACK 대기 중에도 수신 패킷이 처리됨
            elapsed_time = 0
            poll_count = 0
            while elapsed_time < wait_time:
                await asyncio.sleep(POLLING_INTERVAL)
                elapsed_time += POLLING_INTERVAL
                poll_count += 1
                
                # 상태가 변경되었는지 확인
                current_state = self.device_manager.get_state(send_data['statcmd'][0])
                if send_data['statcmd'][1] == current_state:
                    if self.debug:
                        log('[DEBUG] ACK received after {:.2f}s ({} polls)'.format(elapsed_time, poll_count))
                    return
                
                # 5번 폴링마다 현재 상태 로그
                if self.debug and poll_count % 5 == 0:
                    log('[DEBUG] Polling... Target: {}, Current: {}, Elapsed: {:.2f}s'.format(
                        send_data['statcmd'][1], current_state, elapsed_time))

        if self.ew11_log:
            log('[SIGNAL] {}회 명령을 재전송하였으나 수행에 실패했습니다.. 다음의 Queue 삭제: {}'.format(str(self.cmd_retry_count), send_data))
            return
    
    async def command_loop(self):
        """명령 처리 루프"""
        while True:
            if not self.cmd_queue.empty():
                send_data = await self.cmd_queue.get()
                await self.send_to_ew11(send_data)               
            
            # COMMAND_LOOP_DELAY 초 대기 후 루프 진행
            await asyncio.sleep(self.command_loop_delay)
