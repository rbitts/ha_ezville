import asyncio
import socket
import telnetlib
import time

from utils import log
from constants import EW11_TOPIC


class EW11Client:
    """EW11 소켓 통신 관리 클래스"""
    
    def __init__(self, config):
        self.config = config
        self.soc = None
        self.last_received_time = time.time()
        
        # 설정값
        self.address = config['ew11_server']
        self.port = config['ew11_port']
        self.buffer_size = config['ew11_buffer_size']
        self.timeout = config['ew11_timeout']
        self.ew11_id = config['ew11_id']
        self.ew11_password = config['ew11_password']
        self.ew11_log = config['EW11_LOG']
        self.serial_recv_delay = config['serial_recv_delay']
        
    def initiate_socket(self):
        """SOCKET 통신 시작"""
        log('[INFO] Socket 연결을 시작합니다')
            
        retry_count = 0
        while True:
            try:
                self.soc = socket.socket()
                self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self._connect_socket()
                return self.soc
            except ConnectionRefusedError as e:
                log('[ERROR] Server에서 연결을 거부합니다. 재시도 예정 (' + str(retry_count) + '회 재시도)')
                time.sleep(1)
                retry_count += 1
                continue
              
    def _connect_socket(self):
        """소켓 연결"""
        self.soc.connect((self.address, self.port))
    
    def send(self, data):
        """데이터 전송"""
        try:
            if self.ew11_log:
                log('[SIGNAL] 신호 전송: {}'.format(data))
            self.soc.sendall(bytes.fromhex(data))
        except OSError:
            self.close()
            self.initiate_socket()
            self.soc.sendall(bytes.fromhex(data))
    
    def receive(self):
        """데이터 수신"""
        try:
            return self.soc.recv(self.buffer_size)
        except OSError:
            self.close()
            self.initiate_socket()
            return None
    
    def close(self):
        """소켓 닫기"""
        if self.soc:
            self.soc.close()
    
    async def reset(self):
        """Telnet 접속하여 EW11 리셋"""
        ew11 = telnetlib.Telnet(self.address)

        ew11.read_until(b'login:')
        ew11.write(self.ew11_id.encode('utf-8') + b'\n')
        ew11.read_until(b'password:')
        ew11.write(self.ew11_password.encode('utf-8') + b'\n')
        ew11.write('Restart'.encode('utf-8') + b'\n')
        ew11.read_until(b'Restart..')
        
        log('[INFO] EW11 리셋 완료')
        
        # 리셋 후 60초간 Delay
        await asyncio.sleep(60)
    
    def update_receive_time(self):
        """수신 시간 업데이트"""
        self.last_received_time = time.time()
    
    def is_timeout(self):
        """타임아웃 확인"""
        return time.time() - self.last_received_time > self.timeout
    
    async def serial_recv_loop(self, msg_queue):
        """시리얼 수신 루프"""
        class MSG:
            topic = ''
            payload = bytearray()
        
        while True:
            try:
                # EW11 버퍼 크기만큼 데이터 받기
                data = self.receive()
                if data:
                    msg = MSG()
                    msg.topic = EW11_TOPIC + '/recv'
                    msg.payload = data   
                    msg_queue.put(msg)
                    self.update_receive_time()
                
            except Exception as e:
                log(f'[ERROR] 수신 오류: {e}')
         
            await asyncio.sleep(self.serial_recv_delay)
    
    async def health_check_loop(self, restart_flag_callback):
        """EW11 동작 상태 체크"""
        while True:
            # TIMEOUT 시간 동안 새로 받은 EW11 패킷이 없으면 재시작
            if self.is_timeout():
                timestamp = time.time()
                log('[WARNING] {} {} {}초간 신호를 받지 못했습니다. ew11 기기를 재시작합니다.'.format(
                    timestamp, self.last_received_time, self.timeout))
                try:
                    await self.reset()
                    restart_flag_callback(True)
                except:
                    log('[ERROR] 기기 재시작 오류! 기기 상태를 확인하세요.')
            else:
                log('[INFO] EW11 연결 상태 문제 없음')
            
            await asyncio.sleep(self.timeout)
