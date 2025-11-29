#!/usr/bin/env python3
"""
Ezville Wallpad MQTT Control
리팩토링된 버전 - 클래스 기반 모듈 구조
"""
import json

from constants import CONFIG_DIR
from application import EzvilleApplication


if __name__ == '__main__':
    # 설정 파일 로드
    with open(CONFIG_DIR + '/options.json') as file:
        config = json.load(file)
    
    # 애플리케이션 실행
    app = EzvilleApplication(config)
    app.run()
