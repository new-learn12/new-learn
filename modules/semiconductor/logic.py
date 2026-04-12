import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import re
import json

# 1. 모델 설정 (이미지 폴더 구조 반영: modules/semiconductor/models/...)
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
    if isinstance(text, list):
        text = "\n".join([str(i) for i in text])
    if not isinstance(text, str):
        return ""

    text = text.replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    # 각종 머리말(1단계:, 비유:, Step 1 등) 제거
    text = re.sub(r'^[1-4]단계\s*(\(.*?\))?\s*[:\-]\s*', '', text)
    text = re.sub(r'^(비유|설명|상세설명|용어|용어설명|핵심용어|질문|유도질문|답변)\s*[:\-]\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^([1-4]\.|Step\s*[1-4][: ]|#\d)', '', text)
    text = re.sub(r'^[QA][\.:]\s*', '', text)
    
    return text.strip()

def call_semi_llm(question):
    # [핵심 수정] 사용자 데이터셋 기반 Few-Shot 예시 (app.py에 맞게 포맷팅)
    few_shot_examples = """
[예시 1]
질문: PVD 공정에 대해서 설명해주세요.
답변:
{
  "1단계": "PVD는 마치 태양이 지구에 빛을 비추는 것처럼, 원자들이 막을 만들기 위해 서로 충돌하면서 에너지를 주고받는 방법이에요.",
  "2단계": "PVD는 '물리적 증착'이라는 뜻으로, 원자들이 높은 에너지를 가지고 움직여서 막을 만드는 방식입니다. CVD처럼 화학 반응을 이용하지 않고 원자들이 그냥 부딪혀서 막을 만들기에 깨끗하고 안전합니다. 하지만 낮은 압력에서 작업하여 원자들이 멀리까지 이동하므로 복잡한 형태에는 잘 붙지 않을 수 있습니다.",
  "3단계": "PVD (물리적 증착): 원자들이 에너지를 주고받아 물리적으로 막을 만드는 방법. / CVD (화학 기상 증착): 화학 반응을 통해 막을 형성하는 방법.",
  "4단계": "PVD 공정으로 만들어진 얇은 막은 반도체 내부에서 주로 어떤 역할을 하게 될까요?"
}


[예시 2]
질문: 시스템반도체의 정의가 무엇인가요?
답변:
{
  "1단계": "시스템반도체는 마치 요리사를 도와주는 다양한 '주방 도구'와 같아요. 요리사가 요리를 잘하기 위해 칼, 믹서기, 오븐 등 용도에 맞는 도구를 사용하는 것처럼, 전자기기가 각자의 일을 잘하도록 돕는 특화된 부품들이죠.",
  "2단계": "시스템반도체는 정보를 저장하는 메모리반도체와 달리, 데이터를 계산하고 제어하는 역할을 수행합니다. 대표적으로 컴퓨터의 두뇌인 CPU(중앙처리장치)가 있으며, 이 외에도 스마트폰의 두뇌인 AP, 전력을 관리하는 PMIC, 이미지 센서 등 그 종류가 매우 다양합니다. 정보의 흐름을 지휘하고 처리한다는 점에서 전자기기의 '핵심 지능'이라고 할 수 있습니다.",
  "3단계": "시스템반도체: 정보를 처리하고 제어하는 기능을 하는 반도체로, 메모리반도체와는 대조되는 개념입니다. / CPU: 중앙처리장치(Central Processing Unit)의 줄임말로, 컴퓨터 시스템의 모든 연산과 제어를 담당하는 핵심 반도체입니다.",
  "4단계": "우리가 매일 사용하는 스마트폰 안에는 어떤 종류의 시스템반도체들이 각자의 역할을 하고 있을까요?"
}

[예시 3]
질문: 고대역폭 메모리(HBM)란 무엇인가요?
답변:
{
  "1단계": "HBM은 데이터를 나르는 길을 아주 넓게 만든 '초거대 고속도로'와 같아요. 기존 메모리가 좁은 1차선 도로로 데이터를 조금씩 보냈다면, HBM은 수많은 차선을 한꺼번에 열어 엄청난 양의 데이터를 순식간에 전달하는 방식입니다.",
  "2단계": "고대역폭 메모리(HBM)는 여러 개의 DRAM 다이를 수직으로 적층하여 데이터 처리량(대역폭)을 혁신적으로 높인 기술입니다. DRAM을 쌓아 올린 후 TSV(실리콘 관통 전극) 기술로 수천 개의 구멍을 뚫어 연결하기 때문에, 기존 패키징 방식보다 훨씬 빠른 속도로 대량의 데이터를 처리할 수 있습니다. 특히 AI 연산처럼 막대한 데이터를 실시간으로 주고받아야 하는 환경에서 필수적입니다.",
  "3단계": "HBM (High Bandwidth Memory): 여러 개의 DRAM을 수직으로 쌓아 데이터 전송 속도를 극대화한 고성능 메모리입니다. / TSV (Through Silicon Via): 칩에 미세한 구멍을 뚫어 상하 칩을 전극으로 직접 연결하는 고난도 패키징 기술입니다.",
  "4단계": "HBM 기술이 발전할수록 인공지능(AI)의 학습 속도는 어떻게 달라지게 될까요?"
}
"""

# [최적화된 시스템 메시지] 
    # 입문자용 설명 지침과 JSON 포맷 법을 명시
    sys_msg = (
        "당신은 반도체 기술을 일반인에게 친절하게 들려주는 전문 도슨트입니다.\n"
        "반드시 아래의 '출력 형식'과 '작성 가이드'를 엄수하여 답변하세요.\n\n"
        "### 출력 형식 (JSON 전용)\n"
        "{\n"
        "  \"1단계\": \"비유 내용\",\n"
        "  \"2단계\": \"상세설명 내용\",\n"
        "  \"3단계\": \"용어설명 내용\",\n"
        "  \"4단계\": \"추가질문 내용\"\n"
        "}\n\n"
        "### [절대 규칙]\n"
        "1. [1단계 - 비유]: 반도체 용어를 '전혀' 모르는 사람에게 설명하듯 하세요. '웨이퍼', '소자', '공정' 같은 단어 대신 '도화지', '부품', '과정' 같은 일상 단어만 쓰세요.\n"
        "2. [2단계 - 상세설명]: 1단계 내용을 반복하지 마세요. 곧바로 기술적인 '원리'와 '목적'을 깊이 있게 설명하세요.\n"
        "3. [3단계 - 용어설명]: 가장 중요한 용어 1~2개의 핵심 뜻을 적으세요.\n"
        "4. [4단계 - 추가질문]: 반드시 사용자에게 궁금증을 던지는 '질문(? )' 형태로 마무리하세요.\n\n"    
        f"### 참고 예시\n{few_shot_examples}"
    )
    
    # 모델 호출을 위한 프롬프트 구성
    prompt = f"[|system|]{sys_msg}[|endofturn|]\n[|user|]{question}[|endofturn|]\n[|assistant|]\n{{\n  \"1단계\": \""
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=1024,
            do_sample=True,
            temperature=0.35,          
            top_p=0.9,
            repetition_penalty=1.15,   # 반복 억제 강화
            eos_token_id=tokenizer.eos_token_id
        )
    
    raw_res = tokenizer.decode(outputs[0], skip_special_tokens=False).split("[|assistant|]")[-1].strip()
    raw_res = raw_res.replace('\t', '')
    
    if not raw_res.startswith("{"):
        raw_res = "{\n  \"1단계\": \"" + raw_res

    # 1. JSON 영역 추출
    json_match = re.search(r'(\{.*\})', raw_res, re.DOTALL)
    json_str = json_match.group(1) if json_match else raw_res

    if not json_str.strip().endswith("}"):
        if json_str.count('"') % 2 != 0: json_str += '"'
        json_str += "\n}"

    parsed_json = {}
    
    # 2. 정석 파싱
    try:
        clean_json_str = re.sub(r'"\s*\n\s*"[1-4]단계', '",\n"1단계', json_str)
        # 키 이름에 (비유), (본문) 등 찌꺼기가 붙어있으면 강제 제거
        clean_json_str = re.sub(r'"[1-4]단계\s*\([^)]+\)"\s*:', lambda m: f'"{m.group()[1:4]}" :', clean_json_str)
        parsed_json = json.loads(clean_json_str)
    except:
        # 3. 강력한 Fallback 파싱
        for i in range(1, 5):
            # "1단계 (비유)": 또는 "1단계": 모두 호환되도록 정규식 수정
            key_pattern = rf'"{i}단계(\s*\(.*?\))?"\s*:'
            p = rf'{key_pattern}\s*(["\[].*?["\]])(?=\s*,\s*"[1-4]단계|\s*\}})'
            m = re.search(p, json_str, re.DOTALL)
            key_name = f"{i}단계"
            
            if m:
                val = m.group(2).strip() # group(2)가 실제 값
                if val.startswith('['): val = val.strip('[]').replace('"', '')
                elif val.startswith('"'): val = val.strip('"')
                parsed_json[key_name] = val
            elif i == 4:
                m_last = re.search(rf'{key_pattern}\s*(["\[].*?["\]]?)\s*\}}', json_str, re.DOTALL)
                if m_last: parsed_json[key_name] = m_last.group(2).strip('[]" ')

    # 4. 최종 정제 로직
    final_parsed = {}
    if parsed_json:
        # 혹시 모델이 "1단계 (비유)" 등으로 저장했다면 "1단계"로 강제 변환
        for k, v in parsed_json.items():
            clean_k = k[:3] if "단계" in k else k # "1단계" 부분만 추출
            cleaned_v = clean_content(v)
            if cleaned_v: final_parsed[clean_k] = cleaned_v
            
    return raw_res, final_parsed

if __name__ == "__main__":
    # 1. 테스트할 질문 리스트 (입문자용 + 핵심 기술 + 트렌드 골고루 구성)
    test_questions = [
        "반도체 웨이퍼가 정확히 뭔가요?",
        "메모리 반도체와 시스템 반도체의 차이가 궁금해요.",
        "HBM이 요즘 왜 이렇게 인기인가요?",
        "반도체 칩을 보호하는 '패키징' 공정은 왜 필요한가요?",
        "공정 중에서 '포토 공정'이 무엇인지 쉽게 설명해주세요."
    ]

    print(f"🔍 총 {len(test_questions)}개의 질문으로 AI 도슨트 성능 테스트를 시작합니다.")
    print("=" * 60)

    for i, q in enumerate(test_questions, 1):
        print(f"\n🚀 [테스트 {i}/{len(test_questions)}] 질문: {q}")
        print("💡 답변 생성 및 파싱 중...")
        
        try:
            raw, parsed = call_semi_llm(q)
            
            if parsed:
                print(f"✅ {i}번 테스트 성공! (JSON 파싱 완료)")
                # UI에서 보게 될 최종 형태 출력
                print("-" * 30)
                for key, value in parsed.items():
                    print(f"[{key}]: {value}...") # 너무 길면 잘라서 출력
                print("-" * 30)
            else:
                print(f"❌ {i}번 테스트 파싱 실패.")
                print("--- [Raw Output] ---")
                print(raw)
                print("--------------------")
        
        except Exception as e:
            print(f"⚠️ {i}번 테스트 중 에러 발생: {e}")

        print("\n" + "=" * 60)

    print("\n✨ 모든 테스트가 완료되었습니다.")