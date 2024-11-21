import os
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

class NeisAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://open.neis.go.kr/hub"
        
    async def get_schools(self, atpt_code: str = 'T10', school_type: str = '고등학교') -> List[Dict[str, Any]]:
        """학교 목록 조회"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/schoolInfo",
                    params={
                        'KEY': self.api_key,
                        'Type': 'json',
                        'pIndex': '1',
                        'pSize': '1000',
                        'ATPT_OFCDC_SC_CODE': atpt_code,
                        'SCHUL_KND_SC_NM': school_type
                    }
                )
                
                data = response.json()
                if 'schoolInfo' in data:
                    schools = data['schoolInfo'][1]['row']
                    return sorted(
                        schools,
                        key=lambda x: self._normalize_school_name(x['SCHUL_NM'])
                    )
                return []
                
            except Exception as e:
                print(f"Error fetching schools: {str(e)}")
                return []
                
    async def get_meal(self, school_code: str, date: str, atpt_code: str = 'T10') -> Optional[str]:
        """급식 정보 조회"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/mealServiceDietInfo",
                    params={
                        'KEY': self.api_key,
                        'Type': 'json',
                        'pIndex': '1',
                        'pSize': '100',
                        'ATPT_OFCDC_SC_CODE': atpt_code,
                        'SD_SCHUL_CODE': school_code,
                        'MLSV_YMD': date
                    }
                )
                
                data = response.json()
                if 'mealServiceDietInfo' in data:
                    menu = data['mealServiceDietInfo'][1]['row'][0]['DDISH_NM']
                    return self._process_menu(menu)
                return None
                
            except Exception as e:
                print(f"Error fetching meal for school {school_code}: {str(e)}")
                return None

    def _normalize_school_name(self, name: str) -> str:
        """학교명 정규화"""
        return name

    def _process_menu(self, menu: str) -> str:
        """메뉴 문자열 처리"""
        return ', '.join([
            item.split("(")[0].strip()
            for item in menu.split("<br/>")
        ])

    def validate_api_key(self) -> bool:
        """API 키 유효성 검증"""
        if not self.api_key:
            print("NEIS API key is not set")
            return False
        return True

class NeisService:
    def __init__(self, api_key: str):
        self.api = NeisAPI(api_key)
        
    async def fetch_school_meals(self, target_date, db) -> List[Dict[str, Any]]:
        """학교 급식 정보 조회 및 업데이트"""
        try:
            if not self.api.validate_api_key():
                raise Exception("Invalid NEIS API key")

            date_str = target_date.strftime("%Y%m%d")
            
            # 학교 목록 조회
            schools = await self.api.get_schools()
            if not schools:
                raise Exception("Failed to fetch school list")

            # 각 학교의 급식 정보 조회
            tasks = []
            for school in schools:
                tasks.append(self._fetch_and_save_meal(school, date_str, db))

            await asyncio.gather(*tasks)

            # 저장된 급식 정보 반환
            return await db.get_meals(date_str)

        except Exception as e:
            print(f"Error in fetch_school_meals: {str(e)}")
            raise HTTPException(status_code=500, detail="급식 정보를 가져오는데 실패했습니다.")

    async def _fetch_and_save_meal(self, school: Dict[str, Any], date_str: str, db) -> None:
        """개별 학교 급식 정보 조회 및 저장"""
        try:
            school_name = self.api._normalize_school_name(school['SCHUL_NM'])
            school_code = school['SD_SCHUL_CODE']
            
            menu = await self.api.get_meal(school_code, date_str)
            if menu is None:
                menu = "급식 정보 없음"
                
            await db.save_meal(date_str, school_code, school_name, menu)
            
        except Exception as e:
            print(f"Error processing meal for {school_name}: {str(e)}")
            await db.save_meal(date_str, school_code, school_name, "급식 정보 없음")