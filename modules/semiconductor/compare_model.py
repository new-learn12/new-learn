import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import os

# 1. 경로 설정
BASE_MODEL_ID = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
# 사용자가 직접 학습하고 튜닝한 모델 경로 (v1_r8_docent_competition_opt)
CUSTOM_MODEL_PATH = "./models/v1_r8_docent_competition_opt" 

def load_model_and_tokenizer(path, is_custom=False):
    print(f"📦 {'사용자 정의' if is_custom else '기본'} 모델 로딩 중: {path}")
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )
    model.eval()
    return model, tokenizer

def generate_answer(model, tokenizer, question):
    # 도슨트 시스템 프롬프트 (기본 모델에는 주입, 커스텀 모델은 학습되어 있음)
    messages = [
        {"role": "system", "content": "당신은 반도체 전문 도슨트입니다. 초보자를 위해 4단계(비유, 본문, 용어사전, 유도질문) 구조로 답변하세요."},
        {"role": "user", "content": question}
    ]
    
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=1024,
            temperature=0.4, # 테스트에서 확인된 최적 온도 적용
            top_p=0.9,
            do_sample=True,
            repetition_penalty=1.1
        )
    
    return tokenizer.decode(outputs[0][len(inputs["input_ids"][0]):], skip_special_tokens=True)

# 2. 비교 실행
test_questions = [
    "HBM4가 기존 HBM3와 구조적으로 다른 점이 뭐야?",
    "반도체 8대 공정 중에서 '포토 공정'을 비유로 설명해줘.",
    "TSMC의 CoWoS 패키징이 왜 AI 칩에서 중요한가요?"
]

# 모델 로드 (메모리 확보를 위해 순차적으로 로드하거나 고사양 GPU 권장)
base_model, base_tok = load_model_and_tokenizer(BASE_MODEL_ID)
custom_model, custom_tok = load_model_and_tokenizer(CUSTOM_MODEL_PATH, is_custom=True)

print("\n" + "="*80)
print("🤖 AI 도슨트 성능 비교 테스트 리포트")
print("="*80)

for i, q in enumerate(test_questions):
    print(f"\n❓ 질문 {i+1}: {q}")
    
    print("\n[1. 기본 EXAONE-3.5 모델 답변]")
    print("-" * 40)
    print(generate_answer(base_model, base_tok, q))
    
    print("\n[2. 튜닝된 AI 도슨트 모델 답변]")
    print("-" * 40)
    print(generate_answer(custom_model, custom_tok, q))
    print("\n" + "="*80)