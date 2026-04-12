import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import json
import pandas as pd
import re

# 1. 모델 및 경로 설정
MODEL_PATH = "models/v1_r8_docent_competition_opt" 

print(f"📦 모델 로딩 중... (넉넉한 VRAM 환경 권장)")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH, 
    torch_dtype=torch.bfloat16, 
    device_map="auto", 
    trust_remote_code=True
)
model.eval()

# 2. 질문 리스트
questions = [
    "TSMC의 CoWoS 패키징 기술이 왜 HBM에 필수적인가요?",
    "HBM4에서 로직 다이(Logic Die)가 도입되는 이유를 비유로 설명해줘.",
    "식각(Etching) 공정은 반도체에서 어떤 역할을 하나요?"
]

# 3. 테스트할 하이퍼파라미터 세트 (10가지 세분화)
configs = [
    # --- 저온 영역: 정밀도와 논리 위주 (Conservative) ---
    {"name": "01_Logic-Pure", "temp": 0.1, "top_p": 0.70, "top_k": 20},    # 가장 보수적, 교과서적인 답변
    {"name": "02_Ultra-Stable", "temp": 0.2, "top_p": 0.80, "top_k": 30},  # 실수가 거의 없는 안정적인 답변
    {"name": "03_Engineer-Standard", "temp": 0.3, "top_p": 0.85, "top_k": 40}, # 현장 엔지니어의 말투

    # --- 중온 영역: 균형 잡힌 설명 (Balanced) ---
    {"name": "04_Stable-Docent", "temp": 0.4, "top_p": 0.90, "top_k": 50}, # (추천) 가장 대중적인 도슨트 느낌
    {"name": "05_Balanced-Expert", "temp": 0.5, "top_p": 0.92, "top_k": 50}, # 전문성과 유연함의 결합
    {"name": "06_Natural-Flow", "temp": 0.6, "top_p": 0.94, "top_k": 60},   # 문장의 연결이 매끄러운 상태

    # --- 고온 영역: 풍부한 비유와 창의성 (Creative) ---
    {"name": "07_Rich-Analogy", "temp": 0.7, "top_p": 0.95, "top_k": 70},   # 비유가 더 다채로워짐
    {"name": "08_Creative-Talker", "temp": 0.8, "top_p": 0.96, "top_k": 80}, # 일상적인 예시를 더 많이 사용
    {"name": "09_High-Diversity", "temp": 0.9, "top_p": 0.98, "top_k": 100}, # 답변마다 개성이 뚜렷함
    {"name": "10_Genius-Wild", "temp": 1.1, "top_p": 1.0, "top_k": 150}      # (위험/흥미) 매우 창의적이나 환각 가능성 있음
]

def clean_content(text):
    """리스트 형태나 탭 문자가 섞인 답변을 깨끗하게 정제합니다."""
    # 1. 만약 모델이 리스트 ["용어1", "용어2"] 형태로 답변했다면 문자열로 합쳐줌 (TypeError 방지 핵심)
    if isinstance(text, list):
        text = "\n".join([str(i) for i in text])
    
    if not isinstance(text, str):
        return ""

    # 2. 무한 탭(\t) 및 과도한 공백 제거
    text = text.replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text) # 모든 연속된 공백(탭 포함)을 단일 공백으로
    
    # 3. 머리말 및 불필요한 기호 제거
    text = re.sub(r'^[1-4]단계\s*(\(.*?\))?\s*[:\-]\s*', '', text)
    text = re.sub(r'^(비유|설명|상세설명|용어설명|핵심용어|질문|유도질문|답변)\s*[:\-]\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^([1-4]\.|Step\s*[1-4][: ]|#\d)', '', text)
    text = re.sub(r'^[QA][\.:]\s*', '', text)
    
    return text.strip()

def ask_docent(question, config):
    # [시스템 메시지 및 프롬프트 - 기존과 동일]
    sys_msg = (
        "당신은 삼성전자나 SK하이닉스의 기술 엔지니어 출신 도슨트입니다. "
        "반드시 아래의 JSON 포맷으로만 답변하고, 내부 속성은 '단일 문자열(String)'로 작성하세요.\n\n"
        "포맷: {\"step1\": \"비유\", \"step2\": \"상세설명\", \"step3\": \"용어설명\", \"step4\": \"유도질문\"}"
    )
    prompt = f"[|system|]{sys_msg}[|endofturn|]\n[|user|]{question}[|endofturn|]\n[|assistant|]\n{{\n  \"step1\": \"이것은 마치 "
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=2048,
            do_sample=True,
            temperature=config['temp'],
            top_p=config['top_p'],
            top_k=config['top_k'],
            repetition_penalty=1.1,
            eos_token_id=tokenizer.eos_token_id
        )
    
    raw_res = tokenizer.decode(outputs[0], skip_special_tokens=False).split("[|assistant|]")[-1].strip()
    
    # [핵심] 파싱 전처리: 무한 탭(\t) 발생 시 즉시 제거
    raw_res = raw_res.replace('\t', '')

    # JSON 시작점 강제 보정
    if not raw_res.startswith("{"):
        raw_res = "{\n  \"step1\": \"이것은 마치 " + raw_res

    # 1. JSON 영역 추출
    json_match = re.search(r'(\{.*\})', raw_res, re.DOTALL)
    json_str = json_match.group(1) if json_match else raw_res

    # 2. JSON 닫기 보정
    if not json_str.strip().endswith("}"):
        if json_str.count('"') % 2 != 0: json_str += '"'
        json_str += "\n}"

    parsed_json = {}
    
    # 3. 정석 파싱 시도 (성공 시 리스트 타입 등도 모두 가져옴)
    try:
        clean_json_str = re.sub(r'"\s*\n\s*"step', '",\n"step', json_str)
        parsed_json = json.loads(clean_json_str)
    except:
        # 4. Fallback 파싱 (정규표현식) - 리스트 형태([])도 잡을 수 있도록 개선
        for i in range(1, 5):
            key = f"step{i}"
            # 패턴: 문자열(") 또는 리스트([)로 시작해서 다음 step이 나오기 전까지 매칭
            p = rf'"{key}"\s*:\s*(["\[].*?["\]])(?=\s*,\s*"step|\s*\}})'
            m = re.search(p, json_str, re.DOTALL)
            if m:
                val = m.group(1).strip()
                # 리스트인 경우 내부 내용만 추출
                if val.startswith('['):
                    val = val.strip('[]').replace('"', '')
                elif val.startswith('"'):
                    val = val.strip('"')
                parsed_json[key] = val
            elif i == 4: # 마지막 step 처리
                m_last = re.search(rf'"{key}"\s*:\s*(["\[].*?["\]]?)\s*\}}', json_str, re.DOTALL)
                if m_last: parsed_json[key] = m_last.group(1).strip('[]" ')

    # 5. UI용 최종 정제 (TypeError 방지 로직 적용됨)
    final_parsed = {}
    if parsed_json:
        for k, v in parsed_json.items():
            cleaned_v = clean_content(v)
            if cleaned_v: final_parsed[k] = cleaned_v
    
    return raw_res, (final_parsed if final_parsed else None)

# 4. 비교 테스트 실행
print("\n" + "=".center(100, "="))
print("🚀 풍부한 도슨트 최적 파라미터 탐색 (A/B Test)".center(100))
print("=".center(100, "="))

results_summary = []

for i, q in enumerate(questions):
    print(f"\n\n[ TEST CASE {i+1} ] ❓ {q}")
    print("─" * 100)
    
    for cfg in configs:
        raw_text, parsed_data = ask_docent(q, cfg)
        
        status = "✅ PASS" if parsed_data else "❌ FAIL"
        print(f"\n▶ SETTING: 【 {cfg['name']} 】 (T:{cfg['temp']} / P:{cfg['top_p']} / K:{cfg['top_k']}) | JSON: {status}")
        print(f"{'─' * 15} [ PARSED ANSWER ] {'─' * 15}")
        
        if parsed_data:
            for k, v in parsed_data.items():
                print(f"[{k.upper()}]")
                print(f"{v}\n")
        else:
            print("[RAW DATA]\n" + raw_text[:500] + "...(파싱 실패)")
        
        results_summary.append({
            "Q": i+1,
            "Setting": cfg['name'],
            "Status": status,
            "Length(Chars)": len(raw_text)
        })

# 5. 최종 리포트 출력
print("\n\n" + "=".center(100, "="))
print("📊 최종 비교 결과 리포트".center(100))
print("=".center(100, "="))
summary_df = pd.DataFrame(results_summary)
print(summary_df.to_string(index=False))