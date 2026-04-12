import os
# 모든 라이브러리 로드 전 최상단 배치
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

import json
import torch
import gc
import matplotlib.pyplot as plt  # 📈 시각화를 위한 라이브러리 추가
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainerCallback
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig

# ==========================================
# 🎛️ [파라미터 설정 구역] - 12시간 내 완주 세팅
# ==========================================
EXP_NAME = "v1_r8_docent_competition_opt"
MODEL_ID = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
DATA_DIR = "data"
OUTPUT_DIR = f"models/{EXP_NAME}"

# 폴더가 없으면 미리 생성 (그래프 저장을 위해)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ⏱️ 1단계: 지식 학습
S1_EPOCHS = 2       
S1_LR = 2e-4
S1_MAX_DATA = 800   

# 🎯 2단계: 구조화 학습 
S2_EPOCHS = 5       
S2_LR = 5e-5
DOCENT_REPEAT = 5   

# 🧠 메모리 안정화 세팅 (12시간 완주를 위한 타협점)
LORA_R = 8           
LORA_ALPHA = 16
BATCH_SIZE = 1
GRAD_ACC = 16       # 32에서 16으로 복구 (메모리 스왑 현상 방지로 속도 안정화)
MAX_SEQ = 192       

# ==========================================
# 📈 [그래프 저장용 도우미 함수]
# ==========================================
def save_loss_plot(log_history, title, filename):
    try:
        steps = []
        losses = []
        for log in log_history:
            if 'loss' in log and 'step' in log:
                steps.append(log['step'])
                losses.append(log['loss'])
        
        if steps and losses:
            plt.figure(figsize=(10, 5))
            plt.plot(steps, losses, marker='o', linestyle='-', color='b', label='Training Loss')
            plt.title(title)
            plt.xlabel('Steps')
            plt.ylabel('Loss')
            plt.legend()
            plt.grid(True)
            plt.savefig(filename)  # 화면에 띄우지 않고 파일로 얌전히 저장
            plt.close()
            print(f"📈 그래프 저장 완료: {filename}")
    except Exception as e:
        print(f"⚠️ 그래프 저장 중 에러 발생 (학습에는 지장 없음): {e}")

# ==========================================
# 🛡️ [무적의 모니터링 콜백] - 에러 발생 시 무시함
# ==========================================
class ProgressLogCallback(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        try: # 💡 여기서 에러가 나도 절대 멈추지 않도록 try-except 적용
            if logs:
                loss = logs.get("loss", "N/A")
                learning_rate = logs.get("learning_rate", "N/A")
                
                # 안전한 문자열 변환
                loss_str = f"{loss:.4f}" if isinstance(loss, (int, float)) else str(loss)
                lr_str = f"{learning_rate:.6f}" if isinstance(learning_rate, (int, float)) else str(learning_rate)
                
                print(f"🚩 [Step {state.global_step}] Loss: {loss_str} | LR: {lr_str}")
        except:
            pass # 출력하다 에러 나면 그냥 조용히 넘어가고 학습 속행

# ==========================================
# ⚙️ 0. 데이터 로드 및 전처리
# ==========================================
def format_prompt(sys, user, assistant):
    return f"[|system|]{sys}[|endofturn|]\n[|user|]{user}[|endofturn|]\n[|assistant|]{assistant}[|endofturn|]"

def load_stage1():
    texts = []
    if os.path.exists(os.path.join(DATA_DIR, "semiconductor_interview_qa.jsonl")):
        with open(os.path.join(DATA_DIR, "semiconductor_interview_qa.jsonl"), "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d.get("input") and d.get("output"):
                    texts.append(format_prompt("당신은 반도체 전문가입니다.", d["input"], d["output"]))
                    
    for f_name in ["semiconductor_final_dataset.jsonl", "exaone_knowledge_base.jsonl"]:
        file_path = os.path.join(DATA_DIR, f_name)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    d = json.loads(line)
                    txt = d.get("text") or d.get("content")
                    if txt:
                        texts.append(format_prompt("당신은 반도체 전문가입니다.", "반도체 기술 정보를 설명하세요.", txt))
    
    ds = Dataset.from_dict({"text": texts}).train_test_split(test_size=0.1, seed=42)
    train_size = min(len(ds["train"]), S1_MAX_DATA)
    print(f"💡 1단계 데이터 {train_size}개 세팅 완료.")
    ds["train"] = ds["train"].select(range(train_size))
    return ds["train"], ds["test"]

def load_stage2():
    texts = []
    with open(os.path.join(DATA_DIR, "processed_final_dataset.jsonl"), "r", encoding="utf-8") as f:
        lines = f.readlines()
        for _ in range(DOCENT_REPEAT):
            for line in lines:
                d = json.loads(line)
                out = json.dumps(d['output'], ensure_ascii=False, indent=2) if isinstance(d['output'], dict) else d['output']
                sys_msg = "당신은 반도체 전문 도슨트입니다. 반드시 '1단계 비유, 2단계 전문설명, 3단계 용어, 4단계 유도질문'의 JSON 형식으로만 대답하세요."
                texts.append(format_prompt(sys_msg, d['instruction'], out))
    
    ds = Dataset.from_dict({"text": texts}).train_test_split(test_size=0.1, seed=42)
    print(f"💡 2단계 데이터 전체 {len(ds['train'])}개 세팅 완료.")
    return ds["train"], ds["test"]

# ==========================================
# 🚀 1. 모델 준비
# ==========================================
print(f"\n📦 모델 로딩: {MODEL_ID}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, device_map="auto", torch_dtype=torch.bfloat16, trust_remote_code=True
)

def force_get_input_embeddings():
    if hasattr(model, "transformer") and hasattr(model.transformer, "wte"): return model.transformer.wte
    elif hasattr(model, "model") and hasattr(model.model, "embed_tokens"): return model.model.embed_tokens
    return model.get_submodule("transformer.wte")

model.get_input_embeddings = force_get_input_embeddings
print("✅ 임베딩 레이어 연결 완료")

model = prepare_model_for_kbit_training(model)
lora_config = LoraConfig(
    r=LORA_R, lora_alpha=LORA_ALPHA, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05, bias="none", task_type="CAUSAL_LM"
)
model = get_peft_model(model, lora_config)
model.gradient_checkpointing_enable() 

# ==========================================
# 🛡️ 2. Stage 1: 지식 학습 (무정지 설계)
# ==========================================
print("\n📊 [Stage 1] 반도체 도메인 지식 학습 시작")
s1_train, s1_eval = load_stage1()

trainer1 = SFTTrainer(
    model=model, 
    train_dataset=s1_train, 
    eval_dataset=s1_eval,
    processing_class=tokenizer, 
    args=SFTConfig(
        output_dir="./checkpoints_s1",
        num_train_epochs=S1_EPOCHS,
        learning_rate=S1_LR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACC,
        logging_steps=5, 
        eval_strategy="no", # 평가 단계 생략 (시간 단축 및 에러 방지)
        save_strategy="no",
        report_to="none",
        max_length=MAX_SEQ,      
        dataset_text_field="text",
    ),
    callbacks=[ProgressLogCallback()]
)

try:
    trainer1.train()
    # 📈 학습 완료 직후 그래프 저장
    save_loss_plot(trainer1.state.log_history, "Stage 1: Knowledge Training Loss", os.path.join(OUTPUT_DIR, "stage1_loss.png"))
except Exception as e:
    print(f"\n⚠️ Stage 1에서 에러가 발생했지만 강제로 Stage 2로 넘어갑니다: {e}")
finally:
    # 에러가 나든 안 나든 메모리는 무조건 비움
    del trainer1
    gc.collect()
    torch.cuda.empty_cache()

# ==========================================
# 🛡️ 3. Stage 2: 4단계 구조 학습 (무정지 설계)
# ==========================================
print("\n🎯 [Stage 2] 4단계 도슨트 구조 집중 학습 시작")
s2_train, s2_eval = load_stage2()

trainer2 = SFTTrainer(
    model=model, 
    train_dataset=s2_train, 
    eval_dataset=s2_eval,
    processing_class=tokenizer, 
    args=SFTConfig(
        output_dir="./checkpoints_s2",
        num_train_epochs=S2_EPOCHS,
        learning_rate=S2_LR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACC,
        logging_steps=5,
        eval_strategy="no", # 평가 단계 생략 (시간 단축 및 에러 방지)
        save_strategy="no",
        report_to="none",
        max_length=MAX_SEQ,      
        dataset_text_field="text",
    ),
    callbacks=[ProgressLogCallback()]
)

try:
    trainer2.train()
    # 📈 학습 완료 직후 그래프 저장
    save_loss_plot(trainer2.state.log_history, "Stage 2: Docent Structure Training Loss", os.path.join(OUTPUT_DIR, "stage2_loss.png"))
except Exception as e:
    print(f"\n⚠️ Stage 2에서 에러가 발생했지만, 지금까지 학습된 상태로 저장을 시도합니다: {e}")

# ==========================================
# 🛡️ 4. 최종 모델 저장 (최후의 보루 설계)
# ==========================================
print("\n💾 모델 병합 및 최종 저장 시도 중...")
try:
    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("-" * 50)
    print(f"✅ 완벽하게 모델 저장이 완료되었습니다: {OUTPUT_DIR}")
    print("-" * 50)
except Exception as e:
    print(f"\n🚨 [긴급] 병합 중 에러 발생! 모델의 가중치(LoRA)만이라도 안전하게 백업합니다: {e}")
    # 병합에 실패하더라도 학습된 껍데기는 무조건 남김
    emergency_dir = OUTPUT_DIR + "_lora_backup"
    model.save_pretrained(emergency_dir)
    tokenizer.save_pretrained(emergency_dir)
    print(f"✅ 긴급 백업 완료: {emergency_dir}")