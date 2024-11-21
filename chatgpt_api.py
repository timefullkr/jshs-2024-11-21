# chatgpt_api.py 
import os
from openai import AsyncOpenAI

class GPT_Client:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_menu_review(self, menu: str):
        """메뉴 리뷰 생성"""
        # 급식 정보가 없는 경우 처리
        if not menu or menu == "급식 정보 없음":
            return "급식 정보가 없습니다.", 0.0, 0.0

        try:
            # AI에 보낼 메시지 만들기
            prompt = f"""
            다음 학교 급식 메뉴에 대해 영양학적 관점과 학생 선호도 관점에서 각각 분석하고 평가하는 리뷰를 작성해주세요:
           
            다음을 준수해주세요.
            리뷰는 450자 이내로 작성해주세요.
            '이번 학교 급식 메뉴는...' , '이번 학교 급식은...' 등 사용하지 마십시고 다양한 시작어를 사용해야 합니다.
            시작없이 바로 리뷰를 하는 방법도 가끔 사용하시도록 합니다.
            반듯이 존칭어를 사용해야 합니다.
            학교 점심 메뉴: {menu}

            반드시 마지막에 줄바꿈을 하고 5점 만점으로 각각의 평가 점수를 다음처럼 추가해주세요.
            #NUTRI_RATE:영양학적 평가점수
            #PREF_RATE:학생 선호도 평가점수
            """

            # AI에 요청 보내기
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 학교 급식을 평가하는 영양 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            # AI 응답 처리하기
            review_text = response.choices[0].message.content.strip()
            review_text = review_text.replace('\n\n', '\n')
            lines = review_text.split('\n')

            # 기본 평가 점수
            nutri_score = 3.0
            pref_score = 3.0
            review_lines = []

            # 응답 분석
            for line in lines:
                if line.startswith('#NUTRI_RATE:'):
                    try:
                        nutri_score = float(line.replace('#NUTRI_RATE:', '').strip())
                        nutri_score = min(max(nutri_score, 1.0), 5.0)  # 1~5 사이로 제한
                    except:
                        pass
                elif line.startswith('#PREF_RATE:'):
                    try:
                        pref_score = float(line.replace('#PREF_RATE:', '').strip())
                        pref_score = min(max(pref_score, 1.0), 5.0)  # 1~5 사이로 제한
                    except:
                        pass
                elif line.strip():
                    review_lines.append(line.strip())

            # 최종 리뷰 텍스트 만들기
            final_review = '\n'.join(review_lines)
            if not final_review:
                return "메뉴 분석 결과를 생성하지 못했습니다.", 3.0, 3.0

            return final_review, nutri_score, pref_score

        except Exception as e:
            print(f"메뉴 분석 중 오류 발생: {str(e)}")
            return "메뉴 분석 중 오류가 발생했습니다.", 3.0, 3.0

    def check_api_key(self):
        """API 키 확인"""
        if not self.client.api_key:
            return False
        return True

class GPT_Client_API:
    """
    AI 서비스 생성을 도와주는 클래스
    - AI 서비스 생성에 필요한 설정을 처리합니다.
    """
    def create(self):
        """AI 서비스 만들기"""
        # 환경 변수에서 API 키 가져오기
        api_key = os.getenv('OPENAI_API_KEY')
        
        # API 키가 없으면 None 반환
        if not api_key:
            print("OpenAI API key를 찾을 수 없습니다.")
            return None
            
        # API 키가 있으면 AIService 인스턴스 생성
        return GPT_Client(api_key)
