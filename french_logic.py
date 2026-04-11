import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util
from openai import OpenAI
import os

# 1. 모델 및 데이터 로드
print("임베딩 모델 및 데이터 로딩 중...")
embedder = SentenceTransformer('jhgan/ko-sroberta-multitask')

def load_data(file_path):
    try:
        return pd.read_csv(file_path, encoding='utf-8')
    except:
        return pd.read_csv(file_path, encoding='cp949')

df = load_data('french.csv')
df['korean'] = df['korean'].fillna("") 
df['french'] = df['french'].fillna("")

# 코퍼스 벡터화
df['combined'] = df['korean'] + " " + df['french']
corpus_embeddings = embedder.encode(df['combined'].tolist(), convert_to_tensor=True)
print("데이터베이스 벡터화 완료!")

# 2. 하이브리드 검색 로직
def search_hybrid(query):
    query_clean = str(query).lower().strip()
    
    for i, row in df.iterrows():
        f_val = str(row['french']).lower()
        k_val = str(row['korean']).lower()
        if query_clean in f_val or query_clean in k_val:
            return row

    q_emb = embedder.encode(query, convert_to_tensor=True)
    scores = util.cos_sim(q_emb, corpus_embeddings)[0]
    best_idx = torch.argmax(scores).item()
    
    if scores[best_idx].item() > 0.65: 
        return df.iloc[best_idx]
    
    return None

# 3. LLM 연동 및 결과 반환 함수
def get_french_bot_result(user_query):
    # 클라우드 서버(DigitalOcean)의 환경 변수에서 안전하게 키를 꺼내오는 방식
    MY_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "") 
    
    # 만약 서버에 키가 세팅 안 되어 있으면 에러 방지용 안내문 출력
    if not MY_OPENAI_KEY:
        return "시스템 오류: 서버에 OpenAI API 키가 설정되지 않았습니다. 관리자에게 문의하세요.", None
    ...

    matched = search_hybrid(user_query)
    
    # [핵심 수정] 숫자(1. 2.)를 절대 쓰지 못하게 억제하고 템플릿을 고정함
    system_prompt = """당신은 'NEW LEARN' 플랫폼의 왕초보 전용 프랑스어 선생님입니다.
    사용자에게 다음 형식에 맞춰 '초개인화 해설'을 제공하세요.
    
    [문법 조립 블록]
    - 문장을 단어별로 쪼개고 뜻 설명 (예: Je(나) - 주어)
    
    [입문자 눈높이 해설]
    - 발음 팁과 파리 여행에서의 실제 쓰임새 설명
    
    주의사항: 
    - 절대 대괄호 앞에 숫자(1. 2. 등)를 붙이지 마세요.
    - 불필요한 줄바꿈을 남발하지 말고 촘촘하게 작성하세요."""

    if matched is not None:
        french_text = matched['french']
        korean_text = matched['korean']
        pronunciation = matched['pronunciation']
        ans_image = matched['image_url'] if 'image_url' in matched and pd.notna(matched['image_url']) else None
        
        user_prompt = f"""
        [데이터베이스 정보]
        - 문장: {french_text}
        - 뜻: {korean_text}
        - 발음: {pronunciation}
        """
        prefix = f"프랑스어 문장: {french_text}\n"
        
    else:
        ans_image = None
        user_prompt = f"""
        데이터베이스에 없는 내용입니다. 사용자의 질문: '{user_query}'
        가장 먼저 이 질문에 해당하는 번역된 문장을 제시하고 해설해주세요.
        반드시 답변의 첫 줄을 '프랑스어 문장: [번역된 프랑스어]' 형식으로 시작하세요.
        """
        prefix = "" 

    try:
        client = OpenAI(api_key=MY_OPENAI_KEY)
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o", 
            temperature=0.5, 
            top_p=0.8,       
            max_tokens=1000,
        )
        llm_explanation = response.choices[0].message.content.strip()
        
    except Exception as e:
        llm_explanation = f"LLM 답변 생성 중 오류가 발생했습니다: {e}"
        prefix = f"프랑스어 문장: {user_query}\n"

    final_text = f"{prefix}\n{llm_explanation}" if prefix else llm_explanation
    return final_text, ans_image