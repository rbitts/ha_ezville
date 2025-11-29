class DeviceManager:
    """디바이스 상태 및 캐시 관리 클래스"""
    
    def __init__(self):
        # State 저장용 공간
        self.device_state = {}
        
        # 이전에 전달된 패킷인지 판단을 위한 캐시
        self.msg_cache = {}
        
        # MQTT Discovery List
        self.discovery_list = []
        
        # EW11 전달 패킷 중 처리 후 남은 짜투리 패킷 저장
        self.residue = ''
        
        # 강제 업데이트 플래그
        self.force_update = False
        
    def get_state(self, key):
        """디바이스 상태 조회"""
        return self.device_state.get(key)
    
    def set_state(self, key, value):
        """디바이스 상태 설정"""
        self.device_state[key] = value
    
    def is_cached(self, packet_key, packet_data):
        """패킷이 캐시되어 있는지 확인"""
        return self.msg_cache.get(packet_key) == packet_data
    
    def cache_packet(self, packet_key, packet_data):
        """패킷을 캐시에 저장"""
        self.msg_cache[packet_key] = packet_data
    
    def is_discovered(self, discovery_name):
        """디바이스가 discovery 되었는지 확인"""
        return discovery_name in self.discovery_list
    
    def add_discovery(self, discovery_name):
        """디바이스를 discovery 목록에 추가"""
        if discovery_name not in self.discovery_list:
            self.discovery_list.append(discovery_name)
    
    def get_residue(self):
        """남은 패킷 데이터 조회"""
        return self.residue
    
    def set_residue(self, data):
        """남은 패킷 데이터 설정"""
        self.residue = data
    
    def clear_residue(self):
        """남은 패킷 데이터 초기화"""
        self.residue = ''
        
    def reset(self):
        """모든 상태 초기화"""
        self.device_state = {}
        self.msg_cache = {}
        self.discovery_list = []
        self.residue = ''
        self.force_update = False
