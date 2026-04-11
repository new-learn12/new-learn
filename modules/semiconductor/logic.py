import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import re
import json

# 1. 모델 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models", "v1_r8_docent_competition_opt")

print(f"📦 모델 로딩 중...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR, 
    torch_dtype=torch.bfloat16, 
    device_map="auto", 
    trust_remote_code=True
)
model.eval()

def clean_content(text):
    """
    리스트/탭 문자 에러를 방지하고, 불필요한 머리말을 완벽히 제거합니다.
    """
    # 1. 모델이 리스트 형태로 뱉었을 경우 문자열로 병합 (TypeError 방지)
    if isinstance(text, list):
        text = "\n".join([str(i) for i in text])
    if not isinstance(text, str):
        return ""

    # 2. 무한 탭(\t) 및 과도한 공백 정규화
    text = text.replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    # 3. 각종 머리말(1단계:, 비유:, Step 1 등) 제거
    text = re.sub(r'^[1-4]단계\s*(\(.*?\))?\s*[:\-]\s*', '', text)
    text = re.sub(r'^(비유|설명|상세설명|용어|용어설명|핵심용어|질문|유도질문|답변)\s*[:\-]\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^([1-4]\.|Step\s*[1-4][: ]|#\d)', '', text)
    text = re.sub(r'^[QA][\.:]\s*', '', text)
    
    return text.strip()

def call_semi_llm(question):
    # [프롬프트 최적화] 반복을 막고 각 단계의 역할을 명확히 분리
    sys_msg = (
        "당신은 삼성전자나 SK하이닉스의 기술 엔지니어 출신 도슨트입니다. "
        "사용자가 반도체 개념을 깊이 있게 이해할 수 있도록 매우 상세하고 친절하게 설명하세요.\n"
        "반드시 아래의 JSON 포맷으로만 답변하고, 내부 속성은 절대 객체나 배열이 아닌 '단일 문자열(String)'로 길게 작성하세요.\n"
        "[중요] 각 단계는 서로 다른 정보를 담아야 합니다. 이전 단계의 문장을 그대로 복사해서 사용하지 마세요.\n\n"
        "포맷: {\"1단계\": \"비유\", \"2단계\": \"상세설명\", \"3단계\": \"용어설명\", \"4단계\": \"유도질문\"}\n\n"
        "[작성 가이드]\n"
        "- 1단계: 오직 일상적이고 기발한 비유에만 집중하여 2~3문장 이상 구체적으로 묘사하세요.\n"
        "- 2단계: 비유를 배제하고 기술적 사양, 원리, 공정의 목적 등을 전공자 수준으로 깊이 있게 작성하세요.\n"
        "- 3단계: 답변과 관련된 핵심 전공 용어 및 약어를 최소 1개 이상 고르고, 각각의 뜻풀이를 자세히 적어주세요.\n"
        "- 4단계: 사용자의 지적 호기심을 자극하는 날카로운 후속 질문을 1개 던지세요."
    )
    
    prompt = f"[|system|]{sys_msg}[|endofturn|]\n[|user|]{question}[|endofturn|]\n[|assistant|]\n{{\n  \"1단계\": \""
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        # [파라미터 최적화] Stable-Docent 기반 + 반복 패널티 강화
        outputs = model.generate(
            **inputs,
            max_new_tokens=2048,      # 상세한 답변을 위해 길이 증가
            do_sample=True,
            temperature=0.4,          # 안정적이면서 자연스러운 흐름 유지
            top_p=0.9,
            top_k=50,
            repetition_penalty=1.15,  # [핵심] 1.1 -> 1.15로 올려 반복 복붙 현상 억제
            eos_token_id=tokenizer.eos_token_id
        )
    
    raw_res = tokenizer.decode(outputs[0], skip_special_tokens=False).split("[|assistant|]")[-1].strip()
    
    # 탭 문자 사전 제거
    raw_res = raw_res.replace('\t', '')
    
    if not raw_res.startswith("{"):
        raw_res = "{\n  \"1단계\": \"" + raw_res

    # 1. JSON 영역 추출 및 닫기 보정
    json_match = re.search(r'(\{.*\})', raw_res, re.DOTALL)
    json_str = json_match.group(1) if json_match else raw_res

    if not json_str.strip().endswith("}"):
        if json_str.count('"') % 2 != 0: json_str += '"'
        json_str += "\n}"

    parsed_json = {}
    # 2. 정석 파싱 시도
    try:
        clean_json_str = re.sub(r'"\s*\n\s*"[1-4]단계', '",\n"1단계', json_str)
        parsed_json = json.loads(clean_json_str)
    except:
        # 3. 강력한 Fallback 파싱 (정규표현식) - 키가 "1단계" 형식일 때 대응
        for i in range(1, 5):
            key = f"{i}단계"
            # 큰따옴표나 대괄호 안의 내용을 모두 잡아냄
            p = rf'"{key}"\s*:\s*(["\[].*?["\]])(?=\s*,\s*"[1-4]단계|\s*\}})'
            m = re.search(p, json_str, re.DOTALL)
            if m:
                val = m.group(1).strip()
                if val.startswith('['): val = val.strip('[]').replace('"', '')
                elif val.startswith('"'): val = val.strip('"')
                parsed_json[key] = val
            elif i == 4: # 마지막 4단계는 뒤에 콤마가 없을 수 있음
                m_last = re.search(rf'"{key}"\s*:\s*(["\[].*?["\]]?)\s*\}}', json_str, re.DOTALL)
                if m_last: parsed_json[key] = m_last.group(1).strip('[]" ')

    # 4. 최종 정제 로직 거치기
    final_parsed = {}
    if parsed_json:
        for k, v in parsed_json.items():
            cleaned_v = clean_content(v)
            if cleaned_v: final_parsed[k] = cleaned_v
            
    return raw_res, final_parsed

if __name__ == "__main__":
    test_q = "반도체 공정에서 '식각'이 무엇인지 설명해줘."
    print("\n💡 AI 도슨트 답변 생성 중...\n")
    
    raw, parsed = call_semi_llm(test_q)
    
    if parsed:
        print("[ 최종 UI용 데이터 ]")
        print(json.dumps(parsed, indent=4, ensure_ascii=False))
    else:
        print("❌ 파싱 실패. Raw Data를 확인하세요.")
        print(raw)