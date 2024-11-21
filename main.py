# main.py

import os
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
from database import Database
from neis_api import NeisService
from chatgpt_api import GPT_Client_API
from websocket_manager import ConnectionManager
import json
import logging
from logging.handlers import RotatingFileHandler
from typing import AsyncGenerator

# 환경 변수 로드
load_dotenv()

# 기본 설정
BASE_DIR = Path(__file__).resolve().parent

# 로그 디렉토리 설정
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)  # 디렉토리가 없으면 생성

# 로그 파일 경로 설정
LOG_FILE = LOG_DIR / "app.log"

# 로깅 설정
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)

# 로테이팅 파일 핸들러 설정 (파일 크기 5MB, 최대 5개 파일)
rotating_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5*1024*1024,  # 5MB
    backupCount=5,
    encoding='utf-8'
)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
rotating_handler.setFormatter(formatter)
logger.addHandler(rotating_handler)

# 콘솔 핸들러 추가 (선택 사항)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 데이터베이스 초기화
db = Database(str(BASE_DIR / "data" / "school_meals.db"))

# NEIS 서비스 초기화
neis_api = NeisService(api_key=os.getenv('NEIS_API_KEY'))

# AI 서비스 초기화
ai_client = GPT_Client_API().create()

if not ai_client:
    logger.critical("AI 서비스 초기화에 실패했습니다.")
    raise RuntimeError("Failed to initialize AI service")

# WebSocket 매니저 초기화
ws_manager = ConnectionManager()

async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan 이벤트 핸들러
    - 애플리케이션 시작 시 데이터베이스 초기화
    - 애플리케이션 종료 시 데이터베이스 연결 종료
    """
    try:
        # 애플리케이션 시작 시 데이터베이스 초기화
        await db.init_db()
        # logger.info("애플리케이션이 시작되었습니다.")
        yield
    finally:
        # 애플리케이션 종료 시 데이터베이스 연결 종료
        await db.close()
        # logger.info("애플리케이션이 종료되었습니다.")

# FastAPI 앱 초기화 (Lifespan 이벤트 핸들러 사용)
app = FastAPI(lifespan=lifespan)

# 정적 파일 마운트
app.mount("/templates", StaticFiles(directory=str(BASE_DIR / "templates")), name="templates")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/js", StaticFiles(directory=str(BASE_DIR / "templates" / "js")), name="js")
app.mount("/css", StaticFiles(directory=str(BASE_DIR / "static" / "css")), name="css")
app.mount("/help", StaticFiles(directory=str(BASE_DIR / "static" / "help")), name="help")

# WebSocket 엔드포인트 추가
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = websocket.query_params.get("client_id")
    if not client_id:
        await websocket.close(code=1008, reason="Client ID is required")
        logger.warning("클라이언트 ID가 제공되지 않아 WebSocket 연결이 종료되었습니다.")
        return

    await ws_manager.connect(websocket, client_id)
    # logger.info(f"클라이언트 {client_id}가 WebSocket에 연결되었습니다.")
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"클라이언트 {client_id}로부터 받은 데이터: {data}")
            # 클라이언트로부터의 메시지 처리 로직이 필요한 경우 여기에 추가
    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
        # logger.info(f"클라이언트 {client_id}의 WebSocket 연결이 종료되었습니다.")
    except Exception as e:
        await ws_manager.disconnect(client_id)
        logger.error(f"WebSocket 연결 중 오류 발생: {e}")

# API 라우트
@app.get("/")
async def home():
    """메인 페이지"""
    today = datetime.now().strftime("%Y%m%d")
    try:
        count = await db.increment_visits(today)
        # logger.info(f"오늘({today})의 방문자 수가 {count}으로 증가되었습니다.")
    except Exception as e:
        logger.error(f"방문자 수 증가 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")
    
    return FileResponse(str(BASE_DIR / "templates" / "html" / "index.html"))

@app.get("/api/visits/today")
async def get_today_visits():
    """오늘의 방문자 수"""
    today = datetime.now().strftime("%Y%m%d")
    try:
        count = await db.get_today_visits(today)
        # logger.info(f"오늘({today})의 방문자 수 조회: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"오늘의 방문자 수 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

@app.get("/api/meals/{date}")
async def get_meals(date: str):
    """급식 정보 조회"""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        date_str = target_date.strftime("%Y%m%d")

        meals = await db.get_meals(date_str)
        if not meals:
            # logger.info(f"{date_str}의 급식 정보가 데이터베이스에 없으므로 NEIS API를 통해 가져옵니다.")
            meals = await neis_api.fetch_school_meals(target_date, db)
        
        # logger.info(f"{date_str}의 급식 정보 조회 완료. 학교 수: {len(meals)}")
        return meals
    except ValueError:
        logger.warning(f"유효하지 않은 날짜 형식 요청: {date}")
        raise HTTPException(status_code=400, detail="유효하지 않은 날짜 형식입니다.")
    except Exception as e:
        logger.error(f"급식 정보 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

@app.get("/api/review/{date}/{school_code}")
async def get_review(date: str, school_code: str):
    """리뷰 조회 및 생성"""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        date_str = target_date.strftime("%Y%m%d")

        review = await db.get_review(date_str, school_code)
        if not review:
            meals = await db.get_meals(date_str)
            meal = next((m for m in meals if m['school_code'] == school_code), None)

            if meal and meal.get('lunch_menu'):
                try:
                    review_text, nutri_score, pref_score = await ai_client.generate_menu_review(meal['lunch_menu'])
                    error_flag = 0
                    # logger.info(f"리뷰 생성 성공: {date_str}, {school_code}")
                except Exception as e:
                    logger.error(f"리뷰 생성 중 오류 발생: {e}")
                    review_text = "리뷰를 생성하는 중 오류가 발생했습니다."
                    nutri_score = 0
                    pref_score = 0
                    error_flag = 1

                await db.save_review(date_str, school_code, review_text, nutri_score, pref_score, error_flag)

                if error_flag == 0:
                    review = {
                        "review": review_text,
                        "nutri_score": nutri_score,
                        "pref_score": pref_score,
                        "reactions": {"likes": 0}
                    }
                else:
                    review = {
                        "review": review_text,
                        "nutri_score": 0,
                        "pref_score": 0,
                        "nutri_stars": "",
                        "pref_stars": "",
                        "reactions": {"likes": 0}
                    }
            else:
                logger.warning(f"급식 메뉴가 없어서 리뷰를 생성할 수 없습니다: {date_str}, {school_code}")
                raise HTTPException(status_code=404, detail="리뷰를 생성할 수 없습니다.")
        
        # logger.info(f"{date_str}, {school_code}의 리뷰 조회 완료.")
        return review
    except ValueError:
        logger.warning(f"유효하지 않은 날짜 형식 요청: {date}")
        raise HTTPException(status_code=400, detail="유효하지 않은 날짜 형식입니다.")
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"리뷰 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

@app.post("/api/reaction/{date}/{school_code}/{reaction_type}")
async def handle_reaction(date: str, school_code: str, reaction_type: str):
    """반응 처리"""
    try:
        if reaction_type != "like":
            logger.warning(f"유효하지 않은 반응 타입 요청: {reaction_type}")
            raise HTTPException(status_code=400, detail="Invalid reaction type")

        target_date = datetime.strptime(date, "%Y-%m-%d")
        date_str = target_date.strftime("%Y%m%d")

        result = await db.handle_reaction(date_str, school_code, reaction_type)
        
        if result:
            # 반응이 성공적으로 처리된 경우, 모든 클라이언트에게 업데이트 브로드캐스트
            message = json.dumps({
                "type": "reaction",
                "school_code": school_code,
                "likes": result.get("likes", 0)
            })
            await ws_manager.broadcast(message)
            # logger.info(f"반응 처리 및 브로드캐스트 완료: {message}")
        else:
            logger.warning(f"반응 처리 실패: {date_str}, {school_code}, {reaction_type}")

        return result

    except ValueError:
        logger.warning(f"유효하지 않은 날짜 형식 요청: {date}")
        raise HTTPException(status_code=400, detail="유효하지 않은 날짜 형식입니다.")
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"반응 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

@app.get("/api/reactions/{date}")
async def get_all_reactions(date: str):
    """모든 학교의 반응 수 가져오기"""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        date_str = target_date.strftime("%Y%m%d")
        result = await db.handle_reaction_all(date_str)
        # logger.info(f"{date_str}의 모든 학교 반응 수 조회 완료.")
        return result
    except ValueError:
        logger.warning(f"유효하지 않은 날짜 형식 요청: {date}")
        raise HTTPException(status_code=400, detail="유효하지 않은 날짜 형식입니다.")
    except Exception as e:
        logger.error(f"모든 반응 수 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

@app.get("/api/visits/total")
async def get_total_visits():
    """총 방문자 수 조회"""
    try:
        count = await db.get_total_visits()
        # logger.info(f"총 방문자 수 조회 완료: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"총 방문자 수 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

@app.get("/api/dates")
async def get_dates():
    """날짜 범위 조회"""
    try:
        today = datetime.now()
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-3, 4)]
        selected_date = today.strftime("%Y-%m-%d")
        # logger.info(f"날짜 범위 조회 완료: {dates}, 선택된 날짜: {selected_date}")
        return {"dates": dates, "selected_date": selected_date}
    except Exception as e:
        logger.error(f"날짜 범위 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

if __name__ == "__main__":
    # 환경 변수에서 HOST와 PORT 가져오기 (기본값 설정)
    import socket                      # 네트워크 기능
    hostname = socket.gethostname()
    HOST = socket.gethostbyname(hostname)
    PORT = 8080
    
    # uvicorn 서버 실행 (자동 재시작 활성화)
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
