import pandas as pd
import re

# 1. 파일 로드: 전역 변수(df)로 CSV 파일을 한 번만 읽어옵니다.
try:
    df = pd.read_csv('french.csv')
except Exception as e:
    print(f"CSV 파일 로드 실패. 파일 이름과 위치를 확인하세요: {e}")
    df = None

def find_french_phrase(user_query, df):
    # 데이터가 정상적으로 로드되지 않았을 경우를 대비한 방어 코드
    if df is None:
        return None
        
    # 사용자 입력값 전처리 (특수문자 및 공백 제거, 소문자 강제 변환)
    query = re.sub(r'[?.!, ]', '', str(user_query)).lower()
    
    # 데이터프레임을 순회하며 비교
    for index, row in df.iterrows():
        # A. 프랑스어('french' 열)로 입력했을 때의 검색
        if 'french' in row and pd.notna(row['french']):
            db_french = re.sub(r'[?.!, ]', '', str(row['french'])).lower()
            if query == db_french:
                return row
        
        # B. 한국어('korean' 열) 뜻으로 입력했을 때의 검색
        if 'korean' in row and pd.notna(row['korean']):
            db_korean = re.sub(r'[?.!, ]', '', str(row['korean'])).lower()
            if query == db_korean:
                return row
                
    return None # 일치하는 항목이 없을 경우

def get_french_bot_result(user_query, github_token):
    # 전역 변수 df를 사용하여 검색 함수 호출
    matched = find_french_phrase(user_query, df)
    
    if matched is not None: # 검색 결과가 있다면
        # 실제 존재하는 열의 데이터를 변수에 저장
        french_text = matched['french']
        korean_text = matched['korean']
        pronunciation = matched['pronunciation']
        
        # 이미지가 없는 경우를 대비한 처리 (NaN 값 방지)
        if 'image_url' in matched and pd.notna(matched['image_url']):
            ans_image = matched['image_url']
        else:
            ans_image = None
            
        # UI(app.py)에서 '프랑스어 문장:' 이라는 키워드로 TTS 음성을 추출하므로, 반드시 해당 텍스트를 포함해야 함
        ans_text = f"프랑스어 문장: {french_text}\n<br>뜻: {korean_text}\n<br>발음: {pronunciation}"
        
        return ans_text, ans_image
        
    else: # 검색 결과가 없다면
        return "죄송합니다. 해당 표현은 아직 제 데이터베이스에 없습니다. 기초적인 인사나 식당 관련 질문을 해주세요"