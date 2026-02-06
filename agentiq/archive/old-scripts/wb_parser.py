"""
WB Feedback Parser - получение отзывов с Wildberries по артикулу товара
Без API-ключа продавца, через публичные API

Два источника данных:
1. fb.wbcon.su - внешний парсер (надёжнее, но с rate limits)
2. feedbacks2.wb.ru - внутренний API WB (требует root ID)

Алгоритм:
1. Пробуем fb.wbcon.su (если доступен)
2. Fallback на feedbacks2.wb.ru через root ID
"""

import requests
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
import json


@dataclass
class Feedback:
    """Структура отзыва"""
    id: str
    text: str
    rating: int  # 1-5
    created_date: str
    user_name: Optional[str] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    answer: Optional[str] = None
    answer_date: Optional[str] = None


class WBConParser:
    """
    Парсер через fb.wbcon.su API
    Преимущества: работает по артикулу напрямую, стабильнее
    Недостатки: rate limits (2 req/min), демо только 3 артикула
    """

    BASE_URL = "https://fb.wbcon.su"

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # SSL certificate issue

    def get_feedbacks(self, article: int, timeout: int = 120) -> tuple[List[Feedback], Dict]:
        """
        Получить отзывы через wbcon API

        Returns:
            tuple: (список отзывов, статистика)
        """
        # 1. Создаём задачу
        try:
            response = self.session.post(
                f"{self.BASE_URL}/create_task_fb",
                json={"article": article},
                timeout=10
            )
            data = response.json()

            if "detail" in data:
                # Ошибка (например, артикул не в демо)
                return [], {"error": data["detail"]}

            task_id = data.get("task_id")
            if not task_id:
                return [], {"error": "No task_id returned"}

        except Exception as e:
            return [], {"error": f"Failed to create task: {e}"}

        # 2. Ждём выполнения
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(5)  # Ждём между проверками

            try:
                status_response = self.session.get(
                    f"{self.BASE_URL}/task_status",
                    params={"task_id": task_id},
                    timeout=10
                )
                status = status_response.json()

                if status.get("error") and "Rate limit" in str(status.get("error", "")):
                    time.sleep(60)  # Ждём при rate limit
                    continue

                if status.get("is_ready"):
                    break

                if status.get("error"):
                    return [], {"error": status["error"]}

            except Exception as e:
                continue

        # 3. Получаем результаты
        try:
            results_response = self.session.get(
                f"{self.BASE_URL}/get_results_fb",
                params={"task_id": task_id},
                timeout=15
            )
            results = results_response.json()

            if not results or not isinstance(results, list):
                return [], {"error": "Empty results"}

            data = results[0]
            feedbacks = []

            for item in data.get("feedbacks", []):
                feedback = Feedback(
                    id=str(item.get("fb_id", "")),
                    text=item.get("fb_text", ""),
                    rating=int(item.get("valuation", 0)),
                    created_date=item.get("fb_created_at", ""),
                    user_name=item.get("user_name"),
                    answer=item.get("answer_text"),
                    answer_date=item.get("answer_created_at"),
                )
                feedbacks.append(feedback)

            stats = {
                "feedback_count": data.get("feedback_count", 0),
                "feedback_count_with_photo": data.get("feedback_count_with_photo", 0),
                "feedback_count_with_text": data.get("feedback_count_with_text", 0),
                "rating": data.get("rating", 0),
                "rating_distribution": {
                    5: data.get("five_valuation_distr", 0),
                    4: data.get("four_valuation_distr", 0),
                    3: data.get("three_valuation_distr", 0),
                    2: data.get("two_valuation_distr", 0),
                    1: data.get("one_valuation_distr", 0),
                }
            }

            return feedbacks, stats

        except Exception as e:
            return [], {"error": f"Failed to get results: {e}"}


class WBFeedbackParser:
    """Парсер отзывов Wildberries по артикулу"""

    # Публичный API для отзывов - работает по root ID, не по артикулу!
    FEEDBACKS_URL = "https://feedbacks2.wb.ru/feedbacks/v2/{root_id}"

    # API для поиска товара и получения root ID
    SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v5/search"

    # API для информации о товаре по артикулу
    CARD_URL = "https://card.wb.ru/cards/v2/detail"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://www.wildberries.ru",
        "Referer": "https://www.wildberries.ru/",
    }

    def __init__(self, nm_id: int):
        self.nm_id = nm_id
        self.root_id = None
        self.product_info = None
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _get_root_id(self) -> Optional[int]:
        """
        Получить root ID товара по артикулу.
        Root ID нужен для получения отзывов.
        """
        if self.root_id:
            return self.root_id

        # Способ 1: через поиск по артикулу
        params = {
            "appType": 1,
            "curr": "rub",
            "dest": -1257786,
            "query": str(self.nm_id),
            "resultset": "catalog",
            "sort": "popular",
            "spp": 30
        }

        try:
            response = self.session.get(self.SEARCH_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            products = data.get("data", {}).get("products", [])
            for product in products:
                if product.get("id") == self.nm_id:
                    self.root_id = product.get("root")
                    self.product_info = {
                        "id": product.get("id"),
                        "name": product.get("name"),
                        "brand": product.get("brand"),
                        "rating": product.get("rating"),
                        "feedbacks_count": product.get("feedbacks") or product.get("nmFeedbacks"),
                        "root": self.root_id,
                    }
                    return self.root_id

            # Если не нашли точное совпадение, берём первый результат
            if products:
                product = products[0]
                self.root_id = product.get("root")
                self.product_info = {
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "brand": product.get("brand"),
                    "rating": product.get("rating"),
                    "feedbacks_count": product.get("feedbacks") or product.get("nmFeedbacks"),
                    "root": self.root_id,
                }
                return self.root_id

        except Exception as e:
            print(f"Ошибка поиска товара: {e}")

        return None

    def get_feedbacks(self, limit: int = 300) -> List[Feedback]:
        """
        Получить отзывы с пагинацией

        Args:
            limit: максимальное количество отзывов для получения (по умолчанию 300)

        Returns:
            Список отзывов
        """
        # Сначала получаем root ID
        root_id = self._get_root_id()
        if not root_id:
            print(f"Не удалось найти товар с артикулом {self.nm_id}")
            return []

        feedbacks = []
        url = self.FEEDBACKS_URL.format(root_id=root_id)

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            feedback_list = data.get("feedbacks", [])
            if not feedback_list:
                print(f"Отзывы не найдены для root_id={root_id}")
                return []

            for item in feedback_list[:limit]:
                feedback = Feedback(
                    id=str(item.get("id", "")),
                    text=item.get("text", ""),
                    rating=item.get("productValuation", 0),
                    created_date=item.get("createdDate", ""),
                    pros=item.get("pros"),
                    cons=item.get("cons"),
                    answer=item.get("answer", {}).get("text") if item.get("answer") else None,
                    answer_date=item.get("answer", {}).get("createdDate") if item.get("answer") else None,
                )
                feedbacks.append(feedback)

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса отзывов: {e}")
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}")

        return feedbacks

    def get_product_info(self) -> Optional[Dict]:
        """Получить информацию о товаре"""
        # Если уже получали через _get_root_id
        if self.product_info:
            return self.product_info

        # Иначе запрашиваем
        self._get_root_id()
        return self.product_info

    def get_stats(self, feedbacks: List[Feedback]) -> Dict:
        """Получить статистику по отзывам"""
        if not feedbacks:
            return {}

        ratings = [f.rating for f in feedbacks]
        with_answer = sum(1 for f in feedbacks if f.answer)

        return {
            "total": len(feedbacks),
            "avg_rating": round(sum(ratings) / len(ratings), 2),
            "with_answer": with_answer,
            "with_answer_percent": round(with_answer / len(feedbacks) * 100, 1),
            "rating_distribution": {
                5: sum(1 for r in ratings if r == 5),
                4: sum(1 for r in ratings if r == 4),
                3: sum(1 for r in ratings if r == 3),
                2: sum(1 for r in ratings if r == 2),
                1: sum(1 for r in ratings if r == 1),
            }
        }


def main():
    """Тестирование парсера на реальных артикулах"""

    # Тест 1: WBCon API (демо артикулы)
    print("\n" + "="*60)
    print("ТЕСТ 1: fb.wbcon.su API (демо)")
    print("="*60)

    wbcon = WBConParser()
    demo_article = 117220345  # Демо артикул

    print(f"\nАртикул: {demo_article}")
    print("Запрашиваем отзывы через wbcon.su...")

    feedbacks, stats = wbcon.get_feedbacks(demo_article)

    if "error" in stats:
        print(f"Ошибка: {stats['error']}")
    else:
        print(f"\n--- Статистика ---")
        print(f"Всего отзывов: {stats.get('feedback_count', 0)}")
        print(f"С текстом: {stats.get('feedback_count_with_text', 0)}")
        print(f"Рейтинг: {stats.get('rating', 0)}")
        print(f"\nРаспределение оценок:")
        for rating, count in sorted(stats.get('rating_distribution', {}).items(), reverse=True):
            bar = '█' * min(count, 50)
            print(f"  {rating}★: {count:3d} {bar}")

        if feedbacks:
            print(f"\n--- Примеры отзывов ({len(feedbacks)} шт) ---")
            for i, f in enumerate(feedbacks[:3]):
                print(f"\n[{i+1}] {f.user_name or 'Аноним'} | {f.rating}★")
                if f.text:
                    print(f"    {f.text[:150]}{'...' if len(f.text) > 150 else ''}")
                if f.answer:
                    print(f"    → Ответ: {f.answer[:80]}...")

    # Тест 2: Прямой WB API
    print("\n" + "="*60)
    print("ТЕСТ 2: Прямой WB API (feedbacks2.wb.ru)")
    print("="*60)

    test_articles = [
        303679043,   # Пряжа для вязания игрушек
    ]

    for article in test_articles:
        print(f"\nАртикул: {article}")

        parser = WBFeedbackParser(article)
        feedbacks = parser.get_feedbacks(limit=50)

        product = parser.get_product_info()
        if product:
            print(f"Товар: {product.get('name', 'N/A')}")
            print(f"Бренд: {product.get('brand', 'N/A')}")
            print(f"Root ID: {product.get('root', 'N/A')}")

        if feedbacks:
            stats = parser.get_stats(feedbacks)
            print(f"\n--- Статистика ---")
            print(f"Получено: {stats['total']} отзывов")
            print(f"Средняя оценка: {stats['avg_rating']}")
            print(f"С ответом: {stats['with_answer']} ({stats['with_answer_percent']}%)")

            print(f"\n--- Примеры отзывов ---")
            for i, f in enumerate(feedbacks[:2]):
                print(f"\n[{i+1}] {f.rating}★ | {f.created_date[:10] if f.created_date else 'N/A'}")
                if f.text:
                    print(f"    {f.text[:120]}{'...' if len(f.text) > 120 else ''}")
        else:
            print("Отзывы не получены")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")  # Suppress SSL warnings
    main()
