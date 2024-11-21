# database.py

import aiosqlite
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
        self._ensure_db_path()

    def _ensure_db_path(self):
        """데이터베이스 경로가 유효한지 확인하고, 필요 시 디렉토리 생성"""
        db_path = Path(self.db_path)
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            await self.conn.execute('PRAGMA foreign_keys = ON;')
            await self._create_tables()
            await self.conn.commit()
            # logger.info("데이터베이스 초기화 완료.")
        except aiosqlite.Error as e:
            logger.error(f"데이터베이스 초기화 중 오류 발생: {e}")

    async def _create_tables(self):
        """테이블 생성"""
        try:
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS meals (
                    date TEXT,
                    school_code TEXT,
                    school_name TEXT,
                    lunch_menu TEXT,
                    PRIMARY KEY (date, school_code)
                )
            ''')
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    date TEXT,
                    school_code TEXT,
                    review_text TEXT,
                    nutri_score REAL,
                    pref_score REAL,
                    error_flag INTEGER DEFAULT 0,
                    PRIMARY KEY (date, school_code)
                )
            ''')
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS reactions (
                    date TEXT,
                    school_code TEXT,
                    likes INTEGER DEFAULT 0,
                    PRIMARY KEY (date, school_code)
                )
            ''')
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS visits (
                    date TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            ''')
            # logger.info("테이블 생성 완료.")
        except aiosqlite.Error as e:
            logger.error(f"테이블 생성 중 오류 발생: {e}")

    async def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            await self.conn.close()
            # logger.info("데이터베이스 연결 종료.")

    async def execute(self, query: str, params: tuple = None, fetch: bool = False) -> list:
        """
        비동기 데이터베이스 실행 함수
        :param query: 실행할 SQL 쿼리
        :param params: 쿼리 파라미터
        :param fetch: 결과를 가져올지 여부
        :return: 쿼리 결과 리스트
        """
        if not self.conn:
            logger.error("데이터베이스 연결이 초기화되지 않았습니다.")
            return []
        try:
            async with self.conn.execute(query, params or ()) as cursor:
                if fetch:
                    rows = await cursor.fetchall()
                    logger.debug(f"쿼리 결과: {rows}")
                    return rows
                await self.conn.commit()
                return []
        except aiosqlite.Error as e:
            logger.error(f"데이터베이스 오류: {e}\n쿼리: {query}\n파라미터: {params}")
            return []
        except Exception as e:
            logger.error(f"예기치 않은 오류 발생: {e}")
            return []

    # 급식 관련 메서드
    async def get_meals(self, date_str: str) -> List[Dict[str, str]]:
        """급식 정보 조회"""
        rows = await self.execute('''
            SELECT school_code, school_name, lunch_menu
            FROM meals
            WHERE date = ? AND lunch_menu != '급식 정보 없음'
        ''', (date_str,), fetch=True)
        return [{"school_code": row[0], "school_name": row[1], "lunch_menu": row[2]} for row in rows]

    async def save_meal(self, date_str: str, school_code: str, school_name: str, menu: str):
        """급식 정보 저장"""
        await self.execute(
            'INSERT OR REPLACE INTO meals (date, school_code, school_name, lunch_menu) VALUES (?, ?, ?, ?)',
            (date_str, school_code, school_name, menu)
        )

    # 리뷰 관련 메서드
    async def get_review(self, date_str: str, school_code: str) -> Optional[Dict]:
        """리뷰 정보 조회"""
        rows = await self.execute('''
            SELECT r.review_text, r.error_flag, r.nutri_score, r.pref_score,
                   COALESCE(rc.likes, 0) as likes
            FROM reviews r
            LEFT JOIN reactions rc ON r.date = rc.date AND r.school_code = rc.school_code
            WHERE r.date = ? AND r.school_code = ?
        ''', (date_str, school_code), fetch=True)

        if rows:
            row = rows[0]
            error_flag = row[1]
            if error_flag:
                # logger.info(f"리뷰 오류 플래그가 설정된 리뷰 발견: 날짜={date_str}, 학교코드={school_code}")
                return None

            nutri_score = float(row[2])
            pref_score = float(row[3])
            
            return {
                "review": row[0],
                "nutri_score": nutri_score,
                "pref_score": pref_score,
                "reactions": {"likes": row[4]}
            }
        return None

    async def save_review(self, date_str: str, school_code: str, review_text: str, nutri_score: float, pref_score: float, error_flag: int = 0):
        """리뷰 저장"""
        await self.execute(
            '''INSERT OR REPLACE INTO reviews 
            (date, school_code, review_text, nutri_score, pref_score, error_flag) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (date_str, school_code, review_text, nutri_score, pref_score, error_flag)
        )

    # 반응 관련 메서드
    async def handle_reaction_all(self, date_str: str) -> Dict[str, Dict[str, int]]:
        """특정 날짜의 모든 반응 조회"""
        result = await self.execute(
            'SELECT school_code, likes FROM reactions WHERE date = ?',
            (date_str,),
            fetch=True
        )
        
        if result:
            reactions = {row[0]: {"likes": row[1]} for row in result}
            return reactions
        return {}

    async def handle_reaction(self, date_str: str, school_code: str, reaction_type: str) -> Dict:
        """반응 처리"""
        if reaction_type not in ('like',):
            logger.warning(f"유효하지 않은 반응 타입: {reaction_type}")
            return {}

        # 레코드가 없으면 생성
        await self.execute(
            'INSERT OR IGNORE INTO reactions (date, school_code, likes) VALUES (?, ?, 0)',
            (date_str, school_code)
        )

        # 좋아요 업데이트
        if reaction_type == 'like':
            await self.execute(
                'UPDATE reactions SET likes = likes + 1 WHERE date = ? AND school_code = ?',
                (date_str, school_code)
            )

        # 업데이트된 값 조회
        result = await self.execute(
            'SELECT likes FROM reactions WHERE date = ? AND school_code = ?',
            (date_str, school_code),
            fetch=True
        )
        
        if result:
            likes = result[0][0]
            return {"school_code": school_code, "likes": likes}
        return {}

    # 방문자 관련 메서드
    async def increment_visits(self, date_str: str) -> int:
        """방문자 수 증가"""
        await self.execute(
            'INSERT INTO visits (date, count) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET count = count + 1',
            (date_str,)
        )
        result = await self.execute('SELECT count FROM visits WHERE date = ?', (date_str,), fetch=True)
        return result[0][0] if result else 0

    async def get_today_visits(self, date_str: str) -> int:
        """오늘의 방문자 수 조회"""
        result = await self.execute('SELECT count FROM visits WHERE date = ?', (date_str,), fetch=True)
        return result[0][0] if result else 0

    async def get_total_visits(self) -> int:
        """총 방문자 수 조회"""
        result = await self.execute('SELECT COALESCE(SUM(count), 0) FROM visits', fetch=True)
        return result[0][0] if result else 0

    async def __aenter__(self):
        await self.init_db()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
