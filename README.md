# NEW LEARN: 통합형 AI 교육 챗봇 서비스

## 📖 프로젝트 소개
도메인별 특성에 맞는 LLM 및 NLP 모델을 조합하여 서로 다른 5개 전문 분야의 지식을 단일 UI에서 제공하는 통합형 AI 교육 챗봇 서비스

### 기획 의도
이공계, 인문학, 사회과학, 어학 등 성격이 다른 5개의 전문 분야 지식을 통합하여, 사용자의 폭넓은 학습 요구를 한 곳에서 충족시키는 맞춤형 AI 튜터 시스템을 구축

### 주요 인사이트
- 수치적 데이터(반도체), 심리/역사적 맥락, 언어적 규칙(일본어/프랑스어)이 LLM과 NLP 모델을 통해 어떻게 다르게 처리되고 최적화되는지 분석
- 학문 간 지식 연결을 지원하는 멀티 도메인 학습 시스템으로 확장 가능

## 📂 리포지토리 구조
공통 UI 레이아웃과 분야별 비즈니스 로직을 분리하여 관리

```text
new-learn/
├── .github/               # GitHub Actions 워크플로우 (CI/CD)
│   └── workflows
│       └── merge-main-pull-request.yml
├── app.py                 # [Main]
├── requirements.txt       # 프로젝트 전체 패키지 의존성 (통합 관리)
│
├── layouts/               # app.py에서 분리된 분야별 UI 렌더링 함수 모음
│   └── __init__.py        
│
└── modules/               # [Logic] 5개 분야별 독립 비즈니스 로직 패키지
    ├── semiconductor/     # 반도체 모듈
    ├── psychology/        # 심리 모듈
    ├── history/           # 역사 모듈
    ├── japanese/          # 일본어 모듈 
    └── french/            # 프랑스어 모듈
```

## 🛠 기술 스택 및 파이프라인
본 프로젝트는 단일 통합 환경 위에서 구동되나, 각 모듈 담당자가 도메인 특성에 최적화된 AI 모델을 개별적으로 선택하여 구현

- **UI/UX:** Streamlit (사용자 인터페이스 설계 및 프레임워크 구축)
- **Language:** Python 3.11
- **CI/CD:** GitHub Actions (Linting 및 코드 품질 관리)

### 분야별 NLP/LLM 모델 파이프라인
각 모듈의 데이터 특성(수치, 문맥, 언어 규칙 등)에 따라 최적의 모델을 매칭하여 독립적인 파이프라인을 구축

| 분야 | 사용 모델 |
| :--- | :--- |
| 프랑스어 | [TODO: 모델 확인 필요] |
| 일본어 | Google Gemini 1.5 Flash, Helsinki-NLP (Asymmetric Pipeline) |
| 심리 | [TODO: 모델 확인 필요] |
| 역사 | [TODO: 모델 확인 필요] |
| 반도체 | LG EXAONE 3.5 2.4B |

## ⚙️ CI/CD 및 코드 품질 (GitHub Actions)
`main` 브랜치의 안정성을 유지하기 위해 자동화된 워크플로우를 운영

- **트리거:** `main` 브랜치로의 Pull Request 및 Push 발생 시 자동 실행
- **Linting (Flake8):** - Ubuntu 환경 / Python 3.11 
  - 한 줄 최대 길이 120자 허용 및 불필요한 공백 에러(E302, E305 등) 무시 등 커스텀 룰 적용
- **Testing:** TODO 추후 단위 테스트(Pytest) 자동화 파이프라인 도입 예정

## 🔗 Service Demo
- [NEW LEARN 바로가기](https://your-app-name.ondigitalocean.app)

## 🚀 Deployment
효율적인 배포 관리를 위해 클라우드 네이티브 환경 구축

- **Infrastructure:** DigitalOcean App Platform
- **Deployment Flow:**
  - `main` 브랜치 병합 시 GitHub Actions 연동을 통한 자동 빌드 및 배포(CD) 수행
  - TODO 환경 변수(API Keys)의 안전한 관리를 위한 App Platform 내 보안 설정 적용

## 💻 시작하기
1. 저장소 클론
   ```bash
   https://github.com/new-learn12/new-learn.git
   cd new-learn
   ```
2. 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```
3. 환경 변수 설정
   - `.env` 파일에 필요한 API Key 등을 세팅합니다. (상세 변수명 추후 업데이트 예정)
4. 애플리케이션 실행
   ```bash
   streamlit run app.py
   ```

## 🤝 팀원 및 역할
본 프로젝트는 5개 분야별 1인 담당 체제로 개발

| 구분 | 이름 | 담당 역할 | GitHub |
| :--- | :--- | :--- | :--- |
| Leader | 장윤진 | 프로젝트 총괄 및 프랑스어 모듈 개발 | [@spring-winter1213](https://github.com/spring-winter1213) |
| Technical | 박영현 | • 주요 아키텍처 설계 및 시스템 통합<br>• 일본어 교육 모듈 개발 | [@PARKYOUNGHYUN](https://github.com/PARKYOUNGHYUN) |
| Member | 정근우 | • UI/UX 디자인 및 인터페이스 설계<br>• 심리 교육 모듈 개발 | [@studentJung99](https://github.com/studentJung99) |
| Member | 박성훈 | • UI/UX 디자인 및 인터페이스 설계<br>• 역사 교육 모듈 개발 | [@s0undup](https://github.com/s0undup) |
| Member | 권효중 | 반도체 교육 모듈 개발 | [@maxwell779](https://github.com/maxwell779) |