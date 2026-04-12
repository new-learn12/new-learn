import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import re

# 1. 모델 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models", "v1_r8_docent_competition_opt")

print(f"📦 반도체 도슨트 모델 로딩 중...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR, 
    torch_dtype=torch.bfloat16, 
    device_map="auto", 
    trust_remote_code=True
)
model.eval()

def call_semi_llm(question):
    """
    JSON 강제 없이 compare_model.py의 고성능 서술형 답변을 생성하고,
    app.py 호환을 위해 텍스트를 단계별로 자릅니다.
    """
    # 1. 시스템 프롬프트: compare_model.py 스타일 (JSON 언급 삭제)
    messages = [
        {
            "role": "system", 
            "content": (
                "당신은 반도체 전문 도슨트입니다. 반드시 초보자를 위해 아래 4단계 구조로 상세히 답변하세요.\n\n"
                "### 구조 ###\n"
                "1단계(비유): 일상적인 비유로 쉽게 설명\n"
                "2단계(본문): 기술적 원리와 중요성을 깊이 있게 설명\n"
                "3단계(용어사전): 핵심 용어들을 친절하게 풀이\n"
                "4단계(유도질문): 사용자가 더 궁금해할 만한 질문"
            )
        },
        {"role": "user", "content": question}
    ]
    
    # 2. Chat Template 적용 및 답변 시작 가이드
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    prompt += "1단계(비유):" # 모델이 서론 없이 바로 답변을 시작하도록 유도
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=1536, # 풍부한 내용을 위해 충분한 토큰 할당
            temperature=0.45, 
            top_p=0.9,
            do_sample=True,
            repetition_penalty=1.1,
            eos_token_id=tokenizer.eos_token_id
        )
    
    # 3. 전체 텍스트 추출
    generated_text = tokenizer.decode(outputs[0][len(inputs["input_ids"][0]):], skip_special_tokens=True).strip()
    full_content = "1단계(비유): " + generated_text
    
    # 4. app.py UI를 위한 섹션 분리 (정규표현식 활용)
    parsed_data = {
        "1단계": "",
        "2단계": "",
        "3단계": "",
        "4단계": ""
    }
    
    # 섹션별 텍스트를 나누기 위한 패턴 (숫자만 맞으면 괄호나 이름이 달라도 캡처)
    sections = {
        "1단계": r"1단계.*?:(.*?)(?=2단계|$)",
        "2단계": r"2단계.*?:(.*?)(?=3단계|$)",
        "3단계": r"3단계.*?:(.*?)(?=4단계|$)",
        "4단계": r"4단계.*?:(.*?)(?=$)"
    }
    
    for key, pattern in sections.items():
        match = re.search(pattern, full_content, re.DOTALL)
        if match:
            # 추출된 텍스트에서 불필요한 공백이나 특수문자 정제
            content = match.group(1).strip()
            # 마크다운 태그가 섞여있을 경우 제거 (선택 사항)
            content = re.sub(r'^###\s*.*?\n', '', content) 
            parsed_data[key] = content
        else:
            parsed_data[key] = "내용을 생성 중입니다."

    return full_content, parsed_data

if __name__ == "__main__":
    # 테스트 실행
    raw, parsed = call_semi_llm("TSMC의 CoWoS 패키징에 대해 설명해줘.")
    import json
    print(json.dumps(parsed, indent=2, ensure_ascii=False))