import json
import time
from openai import OpenAI
import os

# ==========================================
# 1. API 설정
# ==========================================
GITHUB_TOKEN = "" 
ENDPOINT = "https://models.inference.ai.azure.com"
MODEL_NAME = "Mistral-large-2407"

client = OpenAI(base_url=ENDPOINT, api_key=GITHUB_TOKEN)

def transform_to_4step(instruction, output_text, max_retries=3):
    prompt = f"""
    당신은 반도체 전문 도슨트입니다. 아래 기존의 질문과 답변을 
    초보자를 위한 '4단계 도슨트 스타일'로 리모델링하세요.
    
    [원본 데이터]
    질문: {instruction}
    답변: {output_text}

    [조건]
    1. 답변은 반드시 아래 4단계 구조를 명확히 나누어 작성하세요.
       - 1단계 (비유): 일상적인 사물에 빗대어 핵심 요약
       - 2단계 (본문): 원본의 수치와 팩트를 보존하며 초등학생 수준으로 쉽게 설명
       - 3단계 (미니 사전): 답변에 나온 전문 용어 1~2개 뜻풀이
       - 4단계 (유도): 이와 관련된 호기심을 자극하는 짧은 질문
    2. 출력은 반드시 아래 형태의 JSON 형식으로만 응답하세요.
       {{"instruction": "원본 질문과 동일하게 유지", "output": "4단계로 재구성된 답변"}}
    """
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                messages=[
                    # 시스템 메시지로 한 번 더 강조 (오픈소스 모델용)
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=MODEL_NAME,
                temperature=0.7,
                response_format={ "type": "json_object" } 
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            time.sleep(5)
    return None

# ==========================================
# 2. 실행 및 모니터링 로직
# ==========================================
data_configs = [
    ('data/semiconductor_interview_qa.jsonl', 'qa', None),  
    ('data/exaone_knowledge_base.jsonl', 'news', 250),     
    ('data/semiconductor_final_dataset.jsonl', 'report', 250) 
]

output_file = 'data/processed_final_dataset.jsonl'
total_success = 0

print("\n" + "="*50)
print("🚀 반도체 도슨트 데이터 생성 공장 가동 시작")
print("="*50)

with open(output_file, 'a', encoding='utf-8') as f_out:
    for file_path, file_type, limit in data_configs:
        if not os.path.exists(file_path):
            print(f"❌ 파일 없음: {file_path}")
            continue

        with open(file_path, 'r', encoding='utf-8') as f_temp:
            all_lines = f_temp.readlines()
            target_count = len(all_lines) if limit is None else min(len(all_lines), limit)

        print(f"\n📂 파일 처리 중: [{file_path}]")
        print(f"🎯 목표 개수: {target_count}개")
        print("-" * 30)

        count = 0
        for line in all_lines:
            if limit is not None and count >= limit:
                break
            
            try:
                raw = json.loads(line)
                
                # --- 데이터 타입별 파싱 로직 수정 ---
                if file_type == 'qa':
                    # 'input'이 있으면 질문으로 쓰고, 없으면 'instruction' 사용
                    inst = raw.get('input') if raw.get('input') else raw.get('instruction')
                    out = raw.get('output')
                else: 
                    # news, report 파일: 'text' 필드를 가져오고 질문은 자동으로 생성
                    out = raw.get('text')
                    # 첫 문장을 가져와서 "~에 대해 설명해줘" 식의 질문으로 만듦
                    summary = out.split('.')[0][:20] if out else "반도체 기술"
                    inst = f"{summary} 관련 기술에 대해 자세히 설명해줘."
                
                if not inst or not out: continue
                
                # 변환 요청
                new_data = transform_to_4step(inst, out[:2000]) 
                
                if new_data:
                    # 최종 저장 (수정된 질문과 4단계 답변 저장)
                    final_data = {
                        "instruction": inst.strip(),
                        "output": new_data.get('output')
                    }
                    f_out.write(json.dumps(final_data, ensure_ascii=False) + "\n")
                    
                    count += 1
                    total_success += 1
                    
                    # --- 모니터링 출력 수정 (preview_text와 변수명 통일) ---
                    if isinstance(new_data.get('output'), str):
                        preview_text = new_data['output'][:50].replace('\n', ' ')
                    else:
                        preview_text = "데이터 형식 오류"
                        
                    print(f"✅ [{count}/{target_count}] 변환 성공!")
                    print(f"   🔹 질문 요약: {inst[:30]}...")
                    print(f"   🔹 비유 맛보기: {preview_text}...")
                    print(f"   🕒 누적 성공: {total_success}개")
                    print("-" * 20)
                    
                    time.sleep(1.5) 
                else:
                    print(f"⚠️ [{count+1}] 변환 실패 (데이터를 건너뜁니다)")

            except Exception as e:
                print(f"❌ 에러 발생: {e}")
                continue

print("\n" + "="*50)
print(f"🎉 모든 작업 완료! 총 생성된 데이터: {total_success}개")
print(f"📁 결과 파일: {output_file}")
print("="*50)