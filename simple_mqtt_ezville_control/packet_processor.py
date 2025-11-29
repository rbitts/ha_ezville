import asyncio

from constants import STATE_HEADER, ACK_HEADER, DISCOVERY_PAYLOAD
from utils import log, checksum


class PacketProcessor:
    """패킷 파싱 및 처리 클래스"""
    
    def __init__(self, config, device_manager, mqtt_client):
        self.config = config
        self.device_manager = device_manager
        self.mqtt_client = mqtt_client
        
        # 로그 플래그
        self.ew11_log = config['EW11_LOG']
        self.discovery_delay = config['discovery_delay']
        
    async def process_packet(self, raw_data):
        """EW11 전달된 메시지 처리"""
        raw_data = self.device_manager.get_residue() + raw_data
        
        if self.ew11_log:
            log('[SIGNAL] receved: {}'.format(raw_data))
        
        # 유효한 device ID 목록
        VALID_DEVICE_IDS = {'0E', '35', '50', '12', '33'}
        
        k = 0
        msg_length = len(raw_data)
        
        while k < msg_length:
            # F7로 시작하는 패턴을 패킷으로 분리
            if raw_data[k:k + 2] == 'F7':
                # 최소 4바이트(F7 + Device ID) 확인
                if k + 4 > msg_length:
                    self.device_manager.set_residue(raw_data[k:])
                    break
                
                # Device ID 확인 (노이즈 필터링)
                device_id = raw_data[k + 2:k + 4]
                if device_id not in VALID_DEVICE_IDS:
                    # 노이즈 패킷 - 1바이트씩 진행
                    if self.ew11_log:
                        log('[WARNING] Invalid device ID detected: {}, skipping noise'.format(device_id))
                    k += 1
                    continue
                
                # 남은 데이터가 최소 패킷 길이를 만족하지 못하면 RESIDUE에 저장 후 종료
                if k + 10 > msg_length:
                    self.device_manager.set_residue(raw_data[k:])
                    break
                else:
                    try:
                        data_length = int(raw_data[k + 8:k + 10], 16)
                        packet_length = 10 + data_length * 2 + 4
                    except ValueError:
                        # 데이터 길이 파싱 실패 - 노이즈로 판단
                        if self.ew11_log:
                            log('[WARNING] Invalid data length at position {}, skipping'.format(k))
                        k += 1
                        continue
                    
                    # 남은 데이터가 예상되는 패킷 길이보다 짧으면 RESIDUE에 저장 후 종료
                    if k + packet_length > msg_length:
                        self.device_manager.set_residue(raw_data[k:])
                        break
                    else:
                        packet = raw_data[k:k + packet_length]
                        
                # 분리된 패킷이 Valid한 패킷인지 Checksum 확인                
                if packet != checksum(packet):
                    k += 1
                    continue
                else:
                    await self._process_valid_packet(packet)
                    
                self.device_manager.clear_residue()
                k = k + packet_length
            else:
                k += 1
    
    async def _process_valid_packet(self, packet):
        """유효한 패킷 처리"""
        STATE_PACKET = False
        ACK_PACKET = False
        
        # STATE 패킷인지 확인
        if packet[2:4] in STATE_HEADER and packet[6:8] in STATE_HEADER[packet[2:4]][1]:
            STATE_PACKET = True
        # ACK 패킷인지 확인
        elif packet[2:4] in ACK_HEADER and packet[6:8] in ACK_HEADER[packet[2:4]][1]:
            ACK_PACKET = True
        
        if STATE_PACKET or ACK_PACKET:
            # MSG_CACHE에 없는 새로운 패킷이거나 FORCE_UPDATE 실행된 경우만 실행
            if not self.device_manager.is_cached(packet[0:10], packet[10:]) or self.device_manager.force_update:
                name = STATE_HEADER[packet[2:4]][0]
                
                if name == 'light':
                    await self._process_light_packet(packet, STATE_PACKET)
                elif name == 'thermostat':
                    await self._process_thermostat_packet(packet, STATE_PACKET)
                elif name == 'plug':
                    await self._process_plug_packet(packet, STATE_PACKET)
                elif name == 'gasvalve':
                    await self._process_gasvalve_packet(packet, STATE_PACKET)
                elif name == 'batch':
                    await self._process_batch_packet(packet, STATE_PACKET)
    
    async def _process_light_packet(self, packet, is_state_packet):
        """조명 패킷 처리"""
        name = 'light'
        # ROOM ID
        rid = int(packet[5], 16)
        # ROOM의 light 갯수 + 1
        slc = int(packet[8:10], 16) 
        
        for id in range(1, slc):
            discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, id)
            
            if not self.device_manager.is_discovered(discovery_name):
                self.device_manager.add_discovery(discovery_name)
            
                payload = DISCOVERY_PAYLOAD[name][0].copy()
                payload['~'] = payload['~'].format(rid, id)
                payload['name'] = payload['name'].format(rid, id)
           
                # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
                await self.mqtt_client.mqtt_discovery(payload)
                await asyncio.sleep(self.discovery_delay)
            
            # State 업데이트까지 진행
            onoff = 'ON' if int(packet[10 + 2 * id: 12 + 2 * id], 16) > 0 else 'OFF'
                
            await self.mqtt_client.update_state(name, 'power', rid, id, onoff)
            
            # 직전 처리 State 패킷은 저장
            if is_state_packet:
                self.device_manager.cache_packet(packet[0:10], packet[10:])
    
    async def _process_thermostat_packet(self, packet, is_state_packet):
        """온도조절기 패킷 처리"""
        name = 'thermostat'
        # Room ID (3번째 바이트의 하위 니블)
        rid = int(packet[4:6], 16) & 0x0F
        src = 1
        
        discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, src)
        
        if not self.device_manager.is_discovered(discovery_name):
            self.device_manager.add_discovery(discovery_name)
        
            payload = DISCOVERY_PAYLOAD[name][0].copy()
            payload['~'] = payload['~'].format(rid, src)
            payload['name'] = payload['name'].format(rid, src)
       
            # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
            await self.mqtt_client.mqtt_discovery(payload)
            await asyncio.sleep(self.discovery_delay)
        
        # 데이터 파싱
        # Byte 1 (Index 12:14): 상태 (01: Heat, 02: Off/Away?)
        # Byte 2 (Index 14:16): 설정 온도
        # Byte 4 (Index 18:20): 현재 온도
        
        state_byte = int(packet[12:14], 16)
        
        # 상태 판단 (로그 분석 기반 임시 로직)
        # 01: Heat
        # 그 외: Off (추후 로그 더 분석 필요)
        if state_byte == 1:
            onoff = 'heat'
        else:
            onoff = 'off'

        # 온도는 BCD 코드로 추정됨 (Hex 문자열을 그대로 10진수로 인식)
        # 예: 0x23 -> 35(X), 23(O)
        try:
            setT = str(int(packet[14:16]))
            curT = str(int(packet[18:20]))
        except ValueError:
            # BCD가 아닌 경우(A-F 포함)에 대한 예외 처리 (기존 방식 유지)
            setT = str(int(packet[14:16], 16))
            curT = str(int(packet[18:20], 16))

        await self.mqtt_client.update_state(name, 'power', rid, src, onoff)
        await self.mqtt_client.update_state(name, 'curTemp', rid, src, curT)
        await self.mqtt_client.update_state(name, 'setTemp', rid, src, setT)
        
        # 직전 처리 State 패킷은 저장
        if is_state_packet:
            self.device_manager.cache_packet(packet[0:10], packet[10:])
        else:
            # Ack 패킷도 해당 방의 State 패킷으로 간주하여 저장 (중복 처리 방지)
            # Header(F7) + ID(35) + RID + CMD(81) + Len
            state_header = packet[0:6] + '81' + packet[8:10]
            self.device_manager.cache_packet(state_header, packet[10:])
    
    async def _process_plug_packet(self, packet, is_state_packet):
        """플러그 패킷 처리"""
        name = 'plug'
        
        # plug는 ACK PACKET에 상태 정보가 없으므로 STATE_PACKET만 처리
        if not is_state_packet:
            return
        
        # ROOM ID
        rid = int(packet[5], 16)
        # ROOM의 plug 갯수
        spc = int(packet[10:12], 16) 
    
        for id in range(1, spc + 1):
            discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, id)

            if not self.device_manager.is_discovered(discovery_name):
                self.device_manager.add_discovery(discovery_name)
        
                for payload_template in DISCOVERY_PAYLOAD[name]:
                    payload = payload_template.copy()
                    payload['~'] = payload['~'].format(rid, id)
                    payload['name'] = payload['name'].format(rid, id)
           
                    # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
                    await self.mqtt_client.mqtt_discovery(payload)
                    await asyncio.sleep(self.discovery_delay)  
        
            # BIT0: 대기전력 On/Off, BIT1: 자동모드 On/Off
            # 위와 같지만 일단 on-off 여부만 판단
            onoff = 'ON' if int(packet[7 + 6 * id], 16) > 0 else 'OFF'
            autoonoff = 'ON' if int(packet[6 + 6 * id], 16) > 0 else 'OFF'
            power_num = '{:.2f}'.format(int(packet[8 + 6 * id: 12 + 6 * id], 16) / 100)
            
            await self.mqtt_client.update_state(name, 'power', rid, id, onoff)
            await self.mqtt_client.update_state(name, 'auto', rid, id, onoff)
            await self.mqtt_client.update_state(name, 'current', rid, id, power_num)
        
            # 직전 처리 State 패킷은 저장
            self.device_manager.cache_packet(packet[0:10], packet[10:])
    
    async def _process_gasvalve_packet(self, packet, is_state_packet):
        """가스밸브 패킷 처리"""
        name = 'gasvalve'
        # Gas Value는 하나라서 강제 설정
        rid = 1
        # Gas Value는 하나라서 강제 설정
        spc = 1 
        
        discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, spc)
            
        if not self.device_manager.is_discovered(discovery_name):
            self.device_manager.add_discovery(discovery_name)
            
            payload = DISCOVERY_PAYLOAD[name][0].copy()
            payload['~'] = payload['~'].format(rid, spc)
            payload['name'] = payload['name'].format(rid, spc)
           
            # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
            await self.mqtt_client.mqtt_discovery(payload)
            await asyncio.sleep(self.discovery_delay)                                

        onoff = 'ON' if int(packet[12:14], 16) == 1 else 'OFF'
                
        await self.mqtt_client.update_state(name, 'power', rid, spc, onoff)
        
        # 직전 처리 State 패킷은 저장
        if is_state_packet:
            self.device_manager.cache_packet(packet[0:10], packet[10:])
    
    async def _process_batch_packet(self, packet, is_state_packet):
        """일괄차단기 패킷 처리"""
        name = 'batch'
        
        # 일괄차단기 ACK PACKET은 상태 업데이트에 반영하지 않음
        if not is_state_packet:
            return
        
        # 일괄차단기는 하나라서 강제 설정
        rid = 1
        # 일괄차단기는 하나라서 강제 설정
        sbc = 1
        
        discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, sbc)
        
        if not self.device_manager.is_discovered(discovery_name):
            self.device_manager.add_discovery(discovery_name)
            
            for payload_template in DISCOVERY_PAYLOAD[name]:
                payload = payload_template.copy()
                payload['~'] = payload['~'].format(rid, sbc)
                payload['name'] = payload['name'].format(rid, sbc)
           
                # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
                await self.mqtt_client.mqtt_discovery(payload)
                await asyncio.sleep(self.discovery_delay)           

        # 일괄 차단기는 버튼 상태 변수 업데이트
        states = bin(int(packet[12:14], 16))[2:].zfill(8)
                
        ELEVDOWN = states[2]                                        
        ELEVUP = states[3]
        GROUPON = states[5]
        OUTING = states[6]
                                            
        grouponoff = 'ON' if GROUPON == '1' else 'OFF'
        outingonoff = 'ON' if OUTING == '1' else 'OFF'
        
        #ELEVDOWN과 ELEVUP은 직접 DEVICE_STATE에 저장
        elevdownonoff = 'ON' if ELEVDOWN == '1' else 'OFF'
        elevuponoff = 'ON' if ELEVUP == '1' else 'OFF'
        self.device_manager.set_state('batch_01_01elevator-up', elevuponoff)
        self.device_manager.set_state('batch_01_01elevator-down', elevdownonoff)
            
        # 일괄 조명 및 외출 모드는 상태 업데이트
        await self.mqtt_client.update_state(name, 'group', rid, sbc, grouponoff)
        await self.mqtt_client.update_state(name, 'outing', rid, sbc, outingonoff)
        
        self.device_manager.cache_packet(packet[0:10], packet[10:])
