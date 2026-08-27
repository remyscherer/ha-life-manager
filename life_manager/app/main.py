import os
import logging
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import text


API_KEY = os.environ["API_KEY"]

from database import engine
app = FastAPI(title="Life Manager", version="1.7.3")
logger = logging.getLogger("life_manager")


def as_iso(value):
    """Return a JSON-safe ISO-ish representation for DB date/time values."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def as_date(value):
    """Normalize MariaDB date objects and SQLite TEXT values to datetime.date."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    # Supports YYYY-MM-DD and timestamps beginning with YYYY-MM-DD.
    return date.fromisoformat(raw[:10])



class CompleteQuest(BaseModel):
    overcome: bool = False


class RewardWishlistUpdate(BaseModel):
    wishlist: bool


class SavingsGoalReserveUpdate(BaseModel):
    reserved_coins: int


class RewardPurchase(BaseModel):
    quantity: int = Field(default=1, ge=1, le=20)


class RewardPayload(BaseModel):
    name: str
    description: str | None = None
    cost: int = Field(ge=0)
    icon: str | None = None
    active: bool = True
    sort_order: int = 0


class SavingsGoalPayload(BaseModel):
    name: str
    target_coins: int = Field(gt=0)
    reward_id: int | None = None
    active: bool = True



class WeeklyGoalPayload(BaseModel):
    name: str
    goal_type: str = "quest"
    quest_id: int | None = None
    target_count: int = Field(default=1, ge=1, le=100)
    active: bool = True
    sort_order: int = 0



class QuestOccurrencePayload(BaseModel):
    action: str
    target_date: date | str | None = None
    note: str | None = None



class CategoryPayload(BaseModel):
    name: str
    icon: str = "mdi:folder"
    active: bool = True
    sort_order: int = 0


class QuestPayload(BaseModel):
    name: str
    category_id: int
    quest_type: str
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)
    kbr: int | None = Field(default=None, ge=1, le=5)
    xp_mode: str = "formula"
    fixed_xp: int | None = Field(default=None, ge=0)
    frequency_days: int | None = Field(default=None, ge=1)
    project_factor: float | None = Field(default=None, ge=0)
    priority: str = "normal"
    due_date: date | None = None
    active: bool = True
    weekdays: list[int] = Field(default_factory=list)
    interval_days: int | None = Field(default=None, ge=1)
    next_due: date | None = None


def check_api_key(x_api_key: str | None):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def validate_quest_payload(payload: QuestPayload):
    if payload.quest_type not in ("routine", "habit", "training", "project", "milestone"):
        raise HTTPException(status_code=400, detail="Invalid quest_type")
    if payload.xp_mode not in ("fixed", "formula"):
        raise HTTPException(status_code=400, detail="Invalid xp_mode")
    if payload.priority not in ("low", "normal", "high", "critical"):
        raise HTTPException(status_code=400, detail="Invalid priority")
    for weekday in payload.weekdays:
        if weekday < 1 or weekday > 7:
            raise HTTPException(status_code=400, detail="Invalid weekday")


def calculate_quest_xp(quest):
    if quest["xp_mode"] == "fixed":
        return int(quest["fixed_xp"] or 0)

    minutes = quest["estimated_minutes"] or 0
    kbr = quest["kbr"] or 1
    frequency = quest["frequency_days"] or 1
    return max(1, int(round((minutes / 60) * kbr * frequency)))


def coins_for_percentage(percentage: int) -> int:
    if percentage >= 100: return 5
    if percentage >= 80: return 4
    if percentage >= 60: return 3
    if percentage >= 40: return 2
    if percentage >= 20: return 1
    return 0


def level_info(total_xp: int):
    level = (total_xp // 100) + 1
    xp_into_level = total_xp % 100
    return {
        "level": level,
        "xp_into_level": xp_into_level,
        "xp_for_next_level": 100,
        "xp_remaining": 100 - xp_into_level,
        "level_progress_percent": xp_into_level,
    }


def fetch_today(connection):
    today_date = date.today()
    weekday = today_date.isoweekday()

    quests = connection.execute(text("""
        SELECT DISTINCT
            q.id, q.name, q.quest_type, q.xp_mode, q.fixed_xp,
            q.estimated_minutes, q.kbr, q.frequency_days,
            c.name AS category, c.icon AS category_icon
        FROM quests q
        JOIN categories c ON c.id=q.category_id
        JOIN quest_schedules qs ON qs.quest_id=q.id
        WHERE q.active=1
          AND c.active=1
          AND (
            qs.weekday=:weekday
            OR qs.interval_days=1
            OR qs.next_due=:today_date
          )
        ORDER BY c.sort_order, q.id
    """), {"weekday": weekday, "today_date": today_date}).mappings().all()

    completed_rows = connection.execute(text("""
        SELECT qc.quest_id,
               MAX(qc.completed_at) AS completed_at,
               MAX(qc.xp_awarded) AS xp_awarded,
               MAX(qc.willpower_xp) AS willpower_xp
        FROM quest_completions qc
        WHERE DATE(qc.completed_at)=:today_date
        GROUP BY qc.quest_id
    """), {"today_date": today_date}).mappings().all()

    completed_map = {row["quest_id"]: row for row in completed_rows}

    xp_today = int(connection.execute(text("""
        SELECT COALESCE(SUM(amount),0)
        FROM xp_ledger
        WHERE xp_type='normal' AND DATE(created_at)=:d
    """), {"d": today_date}).scalar_one())

    wp_today = int(connection.execute(text("""
        SELECT COALESCE(SUM(amount),0)
        FROM xp_ledger
        WHERE xp_type='willpower' AND DATE(created_at)=:d
    """), {"d": today_date}).scalar_one())

    coin_balance = int(connection.execute(
        text("SELECT COALESCE(SUM(amount),0) FROM coin_ledger")
    ).scalar_one())

    result_quests = []
    possible_xp = 0
    completed_count = 0

    for quest in quests:
        qxp = calculate_quest_xp(quest)
        possible_xp += qxp
        completion = completed_map.get(quest["id"])
        completed = completion is not None
        if completed:
            completed_count += 1

        result_quests.append({
            "id": quest["id"],
            "name": quest["name"],
            "category": quest["category"],
            "category_icon": quest["category_icon"],
            "quest_type": quest["quest_type"],
            "xp": qxp,
            "completed": completed,
            "completed_at": as_iso(completion["completed_at"]) if completion and completion["completed_at"] else None,
            "willpower_xp": int(completion["willpower_xp"] or 0) if completion else 0,
        })

    progress = round((xp_today / possible_xp) * 100) if possible_xp else 0
    progress = min(progress, 100)

    summary = connection.execute(text("""
        SELECT coins_awarded, finalized_at
        FROM daily_summary
        WHERE summary_date=:d
    """), {"d": today_date}).mappings().first()

    return {
        "date": today_date.isoformat(),
        "weekday": weekday,
        "xp_today": xp_today,
        "willpower_xp_today": wp_today,
        "possible_xp": int(possible_xp),
        "progress_percent": progress,
        "completed_count": completed_count,
        "quest_count": len(result_quests),
        "projected_coins": coins_for_percentage(progress),
        "coins_today": int(summary["coins_awarded"]) if summary and summary["finalized_at"] else 0,
        "day_finalized": bool(summary and summary["finalized_at"]),
        "coin_balance": coin_balance,
        "quests": result_quests,
    }


def fetch_player(connection):
    total_xp = int(connection.execute(text("""
        SELECT COALESCE(SUM(amount),0)
        FROM xp_ledger
        WHERE xp_type IN ('normal','bonus')
    """)).scalar_one())

    willpower_xp = int(connection.execute(text("""
        SELECT COALESCE(SUM(amount),0)
        FROM xp_ledger
        WHERE xp_type='willpower'
    """)).scalar_one())

    coin_balance = int(connection.execute(
        text("SELECT COALESCE(SUM(amount),0) FROM coin_ledger")
    ).scalar_one())

    total_completions = int(connection.execute(
        text("SELECT COUNT(*) FROM quest_completions")
    ).scalar_one())

    return {
        "total_xp": total_xp,
        "willpower_xp": willpower_xp,
        "coin_balance": coin_balance,
        "total_completions": total_completions,
        **level_info(total_xp),
    }


def fetch_training_week(connection):
    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    sunday = monday + timedelta(days=6)

    rows = connection.execute(text("""
        SELECT q.id,q.name,qs.weekday,
               CASE WHEN EXISTS (
                 SELECT 1 FROM quest_completions qc
                 WHERE qc.quest_id=q.id
                   AND DATE(qc.completed_at)=DATE(:monday, printf('+%d days', qs.weekday-1))
               ) THEN 1 ELSE 0 END AS completed
        FROM quests q
        JOIN quest_schedules qs ON qs.quest_id=q.id
        WHERE q.quest_type='training'
          AND q.active=1
          AND qs.weekday IS NOT NULL
        ORDER BY qs.weekday,q.id
    """), {"monday": monday}).mappings().all()

    items = [{
        "id": r["id"],
        "name": r["name"],
        "weekday": r["weekday"],
        "date": (monday + timedelta(days=r["weekday"] - 1)).isoformat(),
        "completed": bool(r["completed"]),
    } for r in rows]

    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "completed_count": sum(1 for x in items if x["completed"]),
        "planned_count": len(items),
        "trainings": items,
    }


def fetch_week(connection):
    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    days = []

    for i in range(7):
        d = monday + timedelta(days=i)

        xp = int(connection.execute(text("""
            SELECT COALESCE(SUM(amount),0)
            FROM xp_ledger
            WHERE xp_type='normal' AND DATE(created_at)=:d
        """), {"d": d}).scalar_one())

        wp = int(connection.execute(text("""
            SELECT COALESCE(SUM(amount),0)
            FROM xp_ledger
            WHERE xp_type='willpower' AND DATE(created_at)=:d
        """), {"d": d}).scalar_one())

        completed = int(connection.execute(text("""
            SELECT COUNT(*)
            FROM quest_completions
            WHERE DATE(completed_at)=:d
        """), {"d": d}).scalar_one())

        days.append({
            "date": d.isoformat(),
            "weekday": i + 1,
            "xp": xp,
            "willpower_xp": wp,
            "completed": completed,
        })

    return {
        "week_start": monday.isoformat(),
        "days": days,
        "xp_total": sum(x["xp"] for x in days),
        "willpower_xp_total": sum(x["willpower_xp"] for x in days),
        "completed_total": sum(x["completed"] for x in days),
    }


def calculate_daily_streak(completion_dates, today_date):
    dates = sorted({as_date(x) for x in completion_dates if as_date(x)}, reverse=True)
    if not dates:
        return 0, 0

    best = 1
    run = 1

    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            run += 1
            best = max(best, run)
        else:
            run = 1

    if dates[0] == today_date:
        expected = today_date
    elif dates[0] == today_date - timedelta(days=1):
        expected = today_date - timedelta(days=1)
    else:
        return 0, best

    current = 0
    for d in dates:
        if d == expected:
            current += 1
            expected -= timedelta(days=1)
        elif d < expected:
            break

    return current, best


def fetch_streaks(connection):
    today_date = date.today()

    quests = connection.execute(text("""
        SELECT DISTINCT q.id,q.name,q.quest_type,c.name AS category
        FROM quests q
        JOIN categories c ON c.id=q.category_id
        JOIN quest_schedules qs ON qs.quest_id=q.id
        WHERE q.active=1
          AND (qs.interval_days=1 OR q.quest_type='training')
        ORDER BY c.sort_order,q.id
    """)).mappings().all()

    result = []

    for quest in quests:
        dates = connection.execute(text("""
            SELECT DISTINCT DATE(completed_at) AS d
            FROM quest_completions
            WHERE quest_id=:qid
            ORDER BY d DESC
        """), {"qid": quest["id"]}).scalars().all()

        current, best = calculate_daily_streak(dates, today_date)

        result.append({
            "id": quest["id"],
            "name": quest["name"],
            "category": quest["category"],
            "quest_type": quest["quest_type"],
            "current_streak": current,
            "best_streak": best,
        })

    return {"streaks": result}



def fetch_rewards(connection):
    balance = int(connection.execute(
        text("SELECT COALESCE(SUM(amount),0) FROM coin_ledger")
    ).scalar_one())

    rewards = connection.execute(text("""
        SELECT id,name,description,cost,icon,active,sort_order,wishlist
        FROM rewards
        ORDER BY wishlist DESC, active DESC, sort_order, cost, id
    """)).mappings().all()

    recent_purchases = connection.execute(text("""
        SELECT rp.id,rp.reward_id,r.name,rp.quantity,rp.total_cost,rp.purchased_at
        FROM reward_purchases rp
        JOIN rewards r ON r.id=rp.reward_id
        ORDER BY rp.purchased_at DESC
        LIMIT 20
    """)).mappings().all()

    coin_history = connection.execute(text("""
        SELECT id, created_at, amount, reason
        FROM coin_ledger
        ORDER BY created_at DESC, id DESC
        LIMIT 20
    """)).mappings().all()

    goals = connection.execute(text("""
        SELECT sg.id,sg.name,sg.target_coins,sg.reward_id,sg.active,
               sg.reserved_coins,r.name AS reward_name,r.cost AS reward_cost
        FROM savings_goals sg
        LEFT JOIN rewards r ON r.id=sg.reward_id
        WHERE sg.active=1
        ORDER BY sg.id
    """)).mappings().all()

    reserved_total = sum(int(g["reserved_coins"] or 0) for g in goals)
    available = max(0, balance - reserved_total)

    return {
        "coin_balance": balance,
        "reserved_coins_total": reserved_total,
        "available_unreserved_coins": available,
        "rewards": [{
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "cost": int(r["cost"]),
            "icon": r["icon"],
            "active": bool(r["active"]),
            "wishlist": bool(r["wishlist"]),
            "sort_order": int(r["sort_order"] or 0),
            "can_afford": available >= int(r["cost"]),
            "coins_missing": max(0, int(r["cost"]) - available),
        } for r in rewards],
        "recent_purchases": [{
            "id": x["id"],
            "reward_id": x["reward_id"],
            "name": x["name"],
            "quantity": x["quantity"],
            "total_cost": x["total_cost"],
            "purchased_at": as_iso(x["purchased_at"]),
        } for x in recent_purchases],
        "purchase_history": [{
            "id": x["id"],
            "reward_id": x["reward_id"],
            "reward_name": x["name"],
            "quantity": x["quantity"],
            "total_cost": x["total_cost"],
            "purchased_at": as_iso(x["purchased_at"]),
        } for x in recent_purchases],
        "coin_history": [{
            "id": x["id"],
            "created_at": as_iso(x["created_at"]) if x["created_at"] else None,
            "amount": int(x["amount"]),
            "reason": x["reason"],
        } for x in coin_history],
        "savings_goals": [{
            "id": g["id"],
            "name": g["name"],
            "target_coins": int(g["target_coins"]),
            "reward_id": g["reward_id"],
            "reward_name": g["reward_name"],
            "reward_cost": int(g["reward_cost"]) if g["reward_cost"] is not None else None,
            "active": bool(g["active"]),
            "reserved_coins": int(g["reserved_coins"] or 0),
            "current_coins": balance,
            "progress_percent": min(100, round((balance / int(g["target_coins"])) * 100)) if int(g["target_coins"]) else 0,
            "remaining": max(0, int(g["target_coins"]) - balance),
        } for g in goals],
    }


def fetch_quest_manager(connection):
    categories = connection.execute(text("""
        SELECT id,name,icon,sort_order,active
        FROM categories
        ORDER BY sort_order,id
    """)).mappings().all()

    quests = connection.execute(text("""
        SELECT q.id,q.name,q.category_id,c.name AS category,
               q.quest_type,q.description,q.estimated_minutes,q.kbr,
               q.xp_mode,q.fixed_xp,q.frequency_days,q.project_factor,
               q.priority,q.due_date,
               q.active,q.created_at
        FROM quests q
        JOIN categories c ON c.id=q.category_id
        ORDER BY q.active DESC,c.sort_order,q.name
    """)).mappings().all()

    schedules = connection.execute(text("""
        SELECT id,quest_id,weekday,interval_days,next_due
        FROM quest_schedules
        ORDER BY quest_id,id
    """)).mappings().all()

    schedule_map = {}

    for s in schedules:
        schedule_map.setdefault(s["quest_id"], []).append({
            "id": s["id"],
            "weekday": s["weekday"],
            "interval_days": s["interval_days"],
            "next_due": as_iso(s["next_due"]) if s["next_due"] else None,
        })

    return {
        "categories": [dict(x) for x in categories],
        "quests": [{
            **{k: q[k] for k in q.keys() if k != "created_at"},
            "created_at": as_iso(q["created_at"]) if q["created_at"] else None,
            "schedules": schedule_map.get(q["id"], []),
        } for q in quests],
    }


def replace_schedules(connection, quest_id: int, payload: QuestPayload):
    connection.execute(
        text("DELETE FROM quest_schedules WHERE quest_id=:qid"),
        {"qid": quest_id}
    )

    for weekday in payload.weekdays:
        connection.execute(text("""
            INSERT INTO quest_schedules(quest_id,weekday)
            VALUES(:qid,:weekday)
        """), {"qid": quest_id, "weekday": weekday})

    if payload.interval_days:
        connection.execute(text("""
            INSERT INTO quest_schedules(quest_id,interval_days)
            VALUES(:qid,:interval_days)
        """), {"qid": quest_id, "interval_days": payload.interval_days})

    if payload.next_due:
        connection.execute(text("""
            INSERT INTO quest_schedules(quest_id,next_due)
            VALUES(:qid,:next_due)
        """), {"qid": quest_id, "next_due": payload.next_due})



ACHIEVEMENT_DEFINITIONS = [
    {
        "code": "first_quest",
        "name": "First Step",
        "description": "Erste Quest abgeschlossen",
        "icon": "mdi:flag-checkered",
        "metric": "total_completions",
        "target": 1,
    },
    {
        "code": "ten_quests",
        "name": "Getting Things Done",
        "description": "10 Quests abgeschlossen",
        "icon": "mdi:check-all",
        "metric": "total_completions",
        "target": 10,
    },
    {
        "code": "hundred_quests",
        "name": "Quest Machine",
        "description": "100 Quests abgeschlossen",
        "icon": "mdi:trophy",
        "metric": "total_completions",
        "target": 100,
    },
    {
        "code": "ten_trainings",
        "name": "Training Arc",
        "description": "10 Trainings abgeschlossen",
        "icon": "mdi:dumbbell",
        "metric": "training_completions",
        "target": 10,
    },
    {
        "code": "fifty_trainings",
        "name": "Iron Habit",
        "description": "50 Trainings abgeschlossen",
        "icon": "mdi:weight-lifter",
        "metric": "training_completions",
        "target": 50,
    },
    {
        "code": "first_boss",
        "name": "Boss Fight",
        "description": "Erste KBR-5-Quest besiegt",
        "icon": "mdi:sword-cross",
        "metric": "boss_completions",
        "target": 1,
    },
    {
        "code": "ten_bosses",
        "name": "Boss Hunter",
        "description": "10 Boss Fights besiegt",
        "icon": "mdi:shield-sword",
        "metric": "boss_completions",
        "target": 10,
    },
    {
        "code": "willpower_100",
        "name": "Discipline",
        "description": "100 Willpower XP gesammelt",
        "icon": "mdi:fire",
        "metric": "willpower_xp",
        "target": 100,
    },
]


def sync_achievements(connection):
    for item in ACHIEVEMENT_DEFINITIONS:
        connection.execute(text("""
            INSERT INTO achievements
                (code, name, description, icon, metric, target_value, active)
            VALUES
                (:code, :name, :description, :icon, :metric, :target, 1)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                icon=excluded.icon,
                metric=excluded.metric,
                target_value=excluded.target_value,
                active=1
        """), {
            "code": item["code"],
            "name": item["name"],
            "description": item["description"],
            "icon": item["icon"],
            "metric": item["metric"],
            "target": item["target"],
        })


def achievement_metrics(connection):
    total_completions = int(connection.execute(text(
        "SELECT COUNT(*) FROM quest_completions"
    )).scalar_one())

    training_completions = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions qc
        JOIN quests q ON q.id=qc.quest_id
        WHERE q.quest_type='training'
    """)).scalar_one())

    boss_completions = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions
        WHERE COALESCE(kbr_at_completion,0) >= 5
    """)).scalar_one())

    willpower_xp = int(connection.execute(text("""
        SELECT COALESCE(SUM(amount),0)
        FROM xp_ledger
        WHERE xp_type='willpower'
    """)).scalar_one())

    return {
        "total_completions": total_completions,
        "training_completions": training_completions,
        "boss_completions": boss_completions,
        "willpower_xp": willpower_xp,
    }


def evaluate_achievements(connection):
    sync_achievements(connection)
    metrics = achievement_metrics(connection)

    achievements = connection.execute(text("""
        SELECT id, code, name, description, icon, metric, target_value
        FROM achievements
        WHERE active=1
        ORDER BY id
    """)).mappings().all()

    result = []

    for ach in achievements:
        current = int(metrics.get(ach["metric"], 0))
        target = int(ach["target_value"])
        unlocked = current >= target

        existing = connection.execute(text("""
            SELECT id, unlocked_at
            FROM achievement_unlocks
            WHERE achievement_id=:aid
            LIMIT 1
        """), {"aid": ach["id"]}).mappings().first()

        if unlocked and not existing:
            connection.execute(text("""
                INSERT INTO achievement_unlocks
                    (achievement_id, unlocked_at)
                VALUES
                    (:aid, NOW())
            """), {"aid": ach["id"]})
            existing = connection.execute(text("""
                SELECT id, unlocked_at
                FROM achievement_unlocks
                WHERE achievement_id=:aid
                LIMIT 1
            """), {"aid": ach["id"]}).mappings().first()

        result.append({
            "id": ach["id"],
            "code": ach["code"],
            "name": ach["name"],
            "description": ach["description"],
            "icon": ach["icon"],
            "metric": ach["metric"],
            "current": current,
            "target": target,
            "progress_percent": min(100, round((current / target) * 100)) if target else 100,
            "unlocked": bool(existing),
            "unlocked_at": as_iso(existing["unlocked_at"]) if existing and existing["unlocked_at"] else None,
        })

    return {
        "unlocked_count": sum(1 for x in result if x["unlocked"]),
        "total_count": len(result),
        "achievements": result,
    }


def scheduled_dates_for_quest(connection, quest_id: int, start_date: date, end_date: date):
    schedules = connection.execute(text("""
        SELECT weekday, interval_days, next_due
        FROM quest_schedules
        WHERE quest_id=:qid
    """), {"qid": quest_id}).mappings().all()

    result = set()

    for schedule in schedules:
        weekday = schedule["weekday"]
        interval_days = schedule["interval_days"]
        next_due = as_date(schedule["next_due"])

        if weekday:
            d = start_date
            while d <= end_date:
                if d.isoweekday() == weekday:
                    result.add(d)
                d += timedelta(days=1)

        elif interval_days == 1:
            d = start_date
            while d <= end_date:
                result.add(d)
                d += timedelta(days=1)

        elif next_due:
            # Bei allgemeinen Intervallen ist next_due der aktuelle Anker.
            # Rückwärts und vorwärts vom Anker zählen.
            step = interval_days or 1
            anchor = next_due
            d = anchor
            while d > start_date:
                d -= timedelta(days=step)
            while d <= end_date:
                if d >= start_date:
                    result.add(d)
                d += timedelta(days=step)

    return sorted(result)


def calculate_planned_streak(connection, quest_id: int, today_date: date):
    lookback_start = today_date - timedelta(days=365)
    planned = scheduled_dates_for_quest(connection, quest_id, lookback_start, today_date)

    if not planned:
        return 0, 0

    completed_dates = {as_date(x) for x in connection.execute(text("""
        SELECT DISTINCT DATE(completed_at)
        FROM quest_completions
        WHERE quest_id=:qid
          AND DATE(completed_at) BETWEEN :start AND :end
    """), {
        "qid": quest_id,
        "start": lookback_start,
        "end": today_date,
    }).scalars().all() if as_date(x)}

    # Best streak = aufeinanderfolgende geplante Termine erledigt.
    best = 0
    run = 0
    for d in planned:
        if d in completed_dates:
            run += 1
            best = max(best, run)
        else:
            run = 0

    # Current streak:
    # Heute darf noch offen sein, ohne dass die Streak schon als gebrochen gilt.
    relevant = [d for d in planned if d < today_date or d in completed_dates]
    current = 0
    for d in reversed(relevant):
        if d in completed_dates:
            current += 1
        else:
            break

    return current, best


def fetch_streaks_v2(connection):
    today_date = date.today()

    quests = connection.execute(text("""
        SELECT DISTINCT
            q.id,
            q.name,
            q.quest_type,
            c.name AS category
        FROM quests q
        JOIN categories c ON c.id=q.category_id
        JOIN quest_schedules qs ON qs.quest_id=q.id
        WHERE q.active=1
        ORDER BY c.sort_order, q.id
    """)).mappings().all()

    result = []

    for quest in quests:
        current, best = calculate_planned_streak(connection, quest["id"], today_date)
        result.append({
            "id": quest["id"],
            "name": quest["name"],
            "category": quest["category"],
            "quest_type": quest["quest_type"],
            "current_streak": current,
            "best_streak": best,
            "streak_type": "planned_completions",
        })

    return {"streaks": result}


def fetch_boss_fights(connection):
    rows = connection.execute(text("""
        SELECT
            q.id,
            q.name,
            q.quest_type,
            q.kbr,
            q.xp_mode,
            q.fixed_xp,
            q.estimated_minutes,
            q.frequency_days,
            c.name AS category
        FROM quests q
        JOIN categories c ON c.id=q.category_id
        WHERE q.active=1
          AND COALESCE(q.kbr,0) >= 5
        ORDER BY c.sort_order, q.name
    """)).mappings().all()

    completed_total = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions
        WHERE COALESCE(kbr_at_completion,0) >= 5
    """)).scalar_one())

    return {
        "completed_total": completed_total,
        "active": [{
            "id": q["id"],
            "name": q["name"],
            "category": q["category"],
            "quest_type": q["quest_type"],
            "kbr": int(q["kbr"] or 0),
            "xp": calculate_quest_xp(q),
        } for q in rows],
    }


def planner_reason(candidate):
    reasons = []

    if candidate.get("overdue_days", 0) > 0:
        days = candidate["overdue_days"]
        reasons.append(f"{days} Tag{'e' if days != 1 else ''} überfällig")

    kbr = int(candidate.get("kbr") or 0)
    if kbr >= 5:
        reasons.append("Boss Fight")
    elif kbr >= 4:
        reasons.append("hoher Widerstand")

    minutes = int(candidate.get("estimated_minutes") or 0)
    if 0 < minutes <= 15:
        reasons.append("schnell erledigt")
    elif 0 < minutes <= 30:
        reasons.append("gut einplanbar")

    if candidate.get("quest_type") == "training":
        reasons.append("geplantes Training")

    if candidate.get("quest_type") in ("habit", "routine"):
        reasons.append("Routine stabilisieren")

    if not reasons:
        reasons.append("heute sinnvoll")

    return ", ".join(reasons[:3])




def priority_score(priority):
    return {
        "low": 0,
        "normal": 8,
        "high": 20,
        "critical": 35,
    }.get(priority or "normal", 8)


def fetch_planner(connection, max_minutes: int | None = None):
    today_date = date.today()
    today = fetch_today_effective(connection)

    today_open = [
        quest
        for quest in today["quests"]
        if not quest.get("completed")
    ]

    ids = [int(q["id"]) for q in today_open]
    metadata = {}

    if ids:
        placeholders = ",".join(str(x) for x in ids)

        rows = connection.execute(text(f"""
            SELECT
                q.id,
                q.name,
                q.quest_type,
                q.description,
                q.estimated_minutes,
                q.kbr,
                q.priority,
                q.due_date,
                c.name AS category,
                c.icon AS category_icon,
                MAX(
                    CASE
                        WHEN qs.next_due IS NOT NULL
                             AND qs.next_due < CURDATE()
                        THEN DATEDIFF(CURDATE(), qs.next_due)
                        ELSE 0
                    END
                ) AS schedule_overdue_days
            FROM quests q
            JOIN categories c ON c.id=q.category_id
            LEFT JOIN quest_schedules qs ON qs.quest_id=q.id
            WHERE q.id IN ({placeholders})
            GROUP BY
                q.id, q.name, q.quest_type, q.description,
                q.estimated_minutes, q.kbr, q.priority, q.due_date,
                c.name, c.icon
        """)).mappings().all()

        metadata = {int(row["id"]): row for row in rows}

    candidates = []

    for today_quest in today_open:
        qid = int(today_quest["id"])
        meta = metadata.get(qid)

        estimated_minutes = int(meta["estimated_minutes"] or 0) if meta else 0
        kbr = int(meta["kbr"] or 1) if meta else 1
        quest_type = meta["quest_type"] if meta else today_quest.get("quest_type", "routine")
        category = meta["category"] if meta else today_quest.get("category", "Sonstiges")
        category_icon = meta["category_icon"] if meta else today_quest.get("category_icon")
        priority = (meta["priority"] if meta else "normal") or "normal"
        due_date = meta["due_date"] if meta else None
        schedule_overdue = int(meta["schedule_overdue_days"] or 0) if meta else 0
        description = meta["description"] if meta else None

        due_overdue = 0
        due_in_days = None
        if due_date:
            due_in_days = (due_date - today_date).days
            if due_in_days < 0:
                due_overdue = abs(due_in_days)

        overdue_days = max(schedule_overdue, due_overdue)
        xp = int(today_quest.get("xp") or 0)

        score = 25.0

        # Priority now matters more than trivial task duration.
        score += priority_score(priority)

        # Due date / overdue.
        score += min(50, overdue_days * 10)
        if due_in_days is not None:
            if due_in_days == 0:
                score += 25
            elif due_in_days == 1:
                score += 15
            elif 1 < due_in_days <= 3:
                score += 8

        # KBR / willpower.
        score += kbr * 5

        # XP contribution, capped.
        score += min(18, xp * 0.5)

        # Duration is now only a tiebreaker-like influence.
        if 0 < estimated_minutes <= 10:
            score += 4
        elif 0 < estimated_minutes <= 20:
            score += 3
        elif 0 < estimated_minutes <= 45:
            score += 2
        elif estimated_minutes > 120:
            score -= 5

        if quest_type == "training":
            score += 10

        if kbr >= 5:
            score += 8

        fits_time = True
        if max_minutes is not None and estimated_minutes > 0:
            fits_time = estimated_minutes <= max_minutes
            if not fits_time:
                score -= 40

        reasons = []
        if priority == "critical":
            reasons.append("kritische Priorität")
        elif priority == "high":
            reasons.append("hohe Priorität")

        if overdue_days > 0:
            reasons.append(f"{overdue_days} Tag{'e' if overdue_days != 1 else ''} überfällig")
        elif due_in_days == 0:
            reasons.append("heute fällig")
        elif due_in_days == 1:
            reasons.append("morgen fällig")

        if quest_type == "training":
            reasons.append("geplantes Training")

        if kbr >= 5:
            reasons.append("Boss Fight")
        elif kbr >= 4:
            reasons.append("hoher Widerstand")

        if max_minutes is not None and fits_time:
            reasons.append(f"passt in {max_minutes} Min")

        if not reasons:
            reasons.append("heute sinnvoll")

        candidate = {
            "id": qid,
            "name": today_quest["name"],
            "quest_type": quest_type,
            "description": description,
            "estimated_minutes": estimated_minutes,
            "kbr": kbr,
            "priority": priority,
            "due_date": due_date.isoformat() if due_date else None,
            "category": category,
            "category_icon": category_icon,
            "overdue_days": overdue_days,
            "scheduled_today": True,
            "due_reason": "Heute offen",
            "xp": xp,
            "score": round(score, 1),
            "boss_fight": kbr >= 5,
            "fits_time": fits_time,
            "reason": ", ".join(reasons[:3]),
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda x: (
            not x["fits_time"],
            -x["score"],
            x["estimated_minutes"] if x["estimated_minutes"] > 0 else 9999,
            x["name"],
        )
    )

    top = candidates[:3]
    recommendation = top[0] if top else None

    if recommendation:
        connection.execute(text("""
            INSERT INTO planner_history
                (plan_date, recommendation_quest_id, recommendation_score)
            VALUES
                (:d, :qid, :score)
            ON CONFLICT(plan_date) DO UPDATE SET
                generated_at=NOW(),
                recommendation_quest_id=excluded.recommendation_quest_id,
                recommendation_score=excluded.recommendation_score
        """), {
            "d": today_date,
            "qid": recommendation["id"],
            "score": recommendation["score"],
        })

    return {
        "date": today_date.isoformat(),
        "recommendation": recommendation,
        "focus": top,
        "open_count": len(candidates),
        "today_open_count": len(today_open),
        "planner_candidate_count": len(candidates),
        "max_minutes": max_minutes,
        "day_progress_percent": int(today["progress_percent"]),
        "xp_today": int(today["xp_today"]),
        "possible_xp": int(today["possible_xp"]),
        "projected_coins": int(today["projected_coins"]),
        "algorithm": {
            "version": "1.7.3",
            "description": "Priorität + Fälligkeit + Überfälligkeit + KBR + XP + Dauer + Quest-Typ",
        },
    }


def fetch_weekly_review(connection):
    week = fetch_week(connection)
    training = fetch_training_week(connection)
    streaks = fetch_streaks_v2(connection)
    achievements = evaluate_achievements(connection)

    days = week["days"]
    active_days = sum(1 for d in days if d["completed"] > 0)
    avg_xp = round(week["xp_total"] / 7, 1)

    best_day = None
    if days:
        best_day = max(days, key=lambda d: d["xp"])

    boss_count = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions
        WHERE COALESCE(kbr_at_completion,0) >= 5
          AND YEARWEEK(completed_at, 1)=YEARWEEK(CURDATE(), 1)
    """)).scalar_one())

    overcome_count = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions
        WHERE COALESCE(willpower_xp,0) > 0
          AND YEARWEEK(completed_at, 1)=YEARWEEK(CURDATE(), 1)
    """)).scalar_one())

    insights = []

    if training["planned_count"] > 0:
        ratio = training["completed_count"] / training["planned_count"]
        if ratio >= 1:
            insights.append("Alle geplanten Trainings dieser Woche erledigt.")
        elif ratio >= 0.6:
            insights.append("Der Trainingsplan ist überwiegend auf Kurs.")
        else:
            insights.append("Beim Training ist diese Woche noch Luft nach oben.")

    if overcome_count >= 3:
        insights.append(f"{overcome_count} Aufgaben trotz Widerstand erledigt.")
    elif overcome_count > 0:
        insights.append(f"{overcome_count} Aufgabe{'n' if overcome_count != 1 else ''} trotz Widerstand erledigt.")

    if boss_count > 0:
        insights.append(f"{boss_count} Boss Fight{'s' if boss_count != 1 else ''} diese Woche besiegt.")

    if active_days >= 6:
        insights.append("Sehr konstante Woche mit Aktivität an fast jedem Tag.")
    elif active_days <= 2:
        insights.append("Die Woche war bisher eher punktuell statt konstant.")

    strongest_streak = None
    streak_items = streaks.get("streaks", [])
    if streak_items:
        strongest_streak = max(streak_items, key=lambda x: x["current_streak"])
        if strongest_streak["current_streak"] > 0:
            insights.append(
                f"Stärkste aktuelle Streak: {strongest_streak['name']} "
                f"mit {strongest_streak['current_streak']} geplanten Erfolgen."
            )

    next_focus = []
    if training["planned_count"] and training["completed_count"] < training["planned_count"]:
        next_focus.append("Offene Trainings der Woche abschließen.")
    if overcome_count == 0:
        next_focus.append("Eine bewusst unangenehme Aufgabe angehen.")
    if active_days < 5:
        next_focus.append("Mehr Konstanz über mehrere Tage verteilen.")
    if not next_focus:
        next_focus.append("Aktuelle Routinen stabil halten.")

    return {
        "week_start": week["week_start"],
        "xp_total": int(week["xp_total"]),
        "average_xp_per_day": avg_xp,
        "completed_total": int(week["completed_total"]),
        "willpower_xp_total": int(week["willpower_xp_total"]),
        "active_days": active_days,
        "training_completed": int(training["completed_count"]),
        "training_planned": int(training["planned_count"]),
        "boss_fights": boss_count,
        "overcome_tasks": overcome_count,
        "achievements_unlocked": int(achievements["unlocked_count"]),
        "best_day": best_day,
        "strongest_streak": strongest_streak,
        "insights": insights[:5],
        "next_focus": next_focus[:3],
    }





@app.post("/quests/{quest_id}/occurrence")
def change_quest_occurrence(
    quest_id: int,
    payload: QuestOccurrencePayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    action = payload.action
    if action not in ("skip", "tomorrow", "move", "restore"):
        raise HTTPException(status_code=400, detail="Invalid occurrence action")

    target_date = payload.target_date
    if isinstance(target_date, str):
        raw_target = target_date.strip()
        if raw_target.lower() in ("", "none", "null"):
            target_date = None
        else:
            try:
                target_date = date.fromisoformat(raw_target)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid target_date")

    source_date = date.today()

    with engine.begin() as c:
        exists = c.execute(text(
            "SELECT id FROM quests WHERE id=:qid"
        ), {"qid": quest_id}).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Quest not found")

        if action == "restore":
            c.execute(text("""
                DELETE FROM quest_occurrences
                WHERE quest_id=:qid AND occurrence_date=:d
            """), {"qid": quest_id, "d": source_date})
            return {"success": True, "action": "restore", "quest_id": quest_id}

        if action == "skip":
            status = "skipped"
            target = None
        else:
            status = "moved"
            target = (
                source_date + timedelta(days=1)
                if action == "tomorrow"
                else target_date
            )
            if not target:
                raise HTTPException(status_code=400, detail="target_date required")
            if target <= source_date:
                raise HTTPException(status_code=400, detail="target_date must be in the future")

        source_date_db = source_date.isoformat()
        target_db = target.isoformat() if target else None
        note_db = str(payload.note) if payload.note not in (None, "") else None

        try:
            c.execute(text("""
                INSERT INTO quest_occurrences
                    (quest_id, occurrence_date, status, moved_to, note)
                VALUES
                    (:qid, :d, :status, :target, :note)
                ON CONFLICT(quest_id, occurrence_date) DO UPDATE SET
                    status=excluded.status,
                    moved_to=excluded.moved_to,
                    note=excluded.note,
                    updated_at=NOW()
            """), {
                "qid": int(quest_id),
                "d": source_date_db,
                "status": str(status),
                "target": target_db,
                "note": note_db,
            })
        except Exception as exc:
            logger.exception(
                "Occurrence write failed: quest_id=%s action=%s source=%s target=%s",
                quest_id, action, source_date_db, target_db
            )
            raise HTTPException(
                status_code=500,
                detail=f"Occurrence write failed: {type(exc).__name__}"
            )

    return {
        "success": True,
        "action": action,
        "quest_id": quest_id,
        "source_date": source_date.isoformat(),
        "target_date": target.isoformat() if target else None,
    }


@app.get("/day-plan")
def day_plan():
    with engine.begin() as c:
        return fetch_day_plan(c)


@app.get("/weekly-goals")
def weekly_goals():
    with engine.begin() as c:
        return fetch_weekly_goals(c)


@app.post("/weekly-goals")
def create_weekly_goal(
    payload: WeeklyGoalPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    if payload.goal_type not in ("quest", "quest_type"):
        raise HTTPException(status_code=400, detail="Invalid goal_type")

    with engine.begin() as c:
        result = c.execute(text("""
            INSERT INTO weekly_goals
                (name, goal_type, quest_id, target_count, active, sort_order)
            VALUES
                (:name, :goal_type, :quest_id, :target_count, :active, :sort_order)
        """), payload.model_dump())

    return {"success": True, "goal_id": result.lastrowid}


@app.get("/analytics")
def analytics():
    with engine.begin() as c:
        return fetch_analytics(c)


@app.get("/planner")
def planner(max_minutes: int | None = None):
    if max_minutes is not None:
        max_minutes = max(1, min(max_minutes, 480))
    with engine.begin() as c:
        return fetch_planner(c, max_minutes=max_minutes)


@app.get("/weekly-review")
def weekly_review():
    with engine.begin() as c:
        return fetch_weekly_review(c)




def occurrence_map(connection, for_date):
    rows = connection.execute(text("""
        SELECT quest_id, occurrence_date, status, moved_to, note
        FROM quest_occurrences
        WHERE occurrence_date=:d OR moved_to=:d
    """), {"d": for_date}).mappings().all()

    original = {}
    moved_in = []
    for raw in rows:
        r = dict(raw)
        occurrence_date = as_date(r["occurrence_date"])
        moved_to = as_date(r["moved_to"])
        r["occurrence_date"] = occurrence_date
        r["moved_to"] = moved_to

        if occurrence_date == for_date:
            original[int(r["quest_id"])] = r
        if moved_to == for_date and r["status"] == "moved":
            moved_in.append(r)
    return original, moved_in


def apply_occurrences_to_today(connection, today_payload):
    d = date.fromisoformat(today_payload["date"])
    original, moved_in = occurrence_map(connection, d)

    quests = []
    existing_ids = set()

    for q in today_payload["quests"]:
        qid = int(q["id"])
        occ = original.get(qid)

        if occ and occ["status"] in ("skipped", "moved"):
            continue

        q = dict(q)
        q["occurrence_status"] = "scheduled"
        q["moved_from"] = None
        quests.append(q)
        existing_ids.add(qid)

    # A moved occurrence appears on the target day even if its normal schedule does not.
    for occ in moved_in:
        qid = int(occ["quest_id"])
        if qid in existing_ids:
            continue
        row = connection.execute(text("""
            SELECT q.id,q.name,q.quest_type,q.xp_mode,q.fixed_xp,q.frequency_days,
                   q.project_factor,q.kbr,c.name AS category,c.icon AS category_icon
            FROM quests q
            JOIN categories c ON c.id=q.category_id
            WHERE q.id=:qid AND q.active=1
        """), {"qid": qid}).mappings().first()
        if not row:
            continue

        completed = connection.execute(text("""
            SELECT completed_at, willpower_xp
            FROM quest_completions
            WHERE quest_id=:qid AND DATE(completed_at)=:d
            ORDER BY completed_at DESC LIMIT 1
        """), {"qid": qid, "d": d}).mappings().first()

        quests.append({
            "id": qid,
            "name": row["name"],
            "category": row["category"],
            "category_icon": row["category_icon"],
            "quest_type": row["quest_type"],
            "xp": calculate_quest_xp(row),
            "completed": bool(completed),
            "completed_at": as_iso(completed["completed_at"]) if completed else None,
            "willpower_xp": int(completed["willpower_xp"] or 0) if completed else 0,
            "occurrence_status": "moved",
            "moved_from": as_iso(occ["occurrence_date"]),
        })

    today_payload = dict(today_payload)
    today_payload["quests"] = quests
    today_payload["quest_count"] = len(quests)
    today_payload["completed_count"] = sum(1 for q in quests if q["completed"])
    today_payload["possible_xp"] = sum(int(q["xp"]) for q in quests)
    today_payload["xp_today"] = sum(int(q["xp"]) for q in quests if q["completed"])
    today_payload["willpower_xp_today"] = sum(int(q["willpower_xp"]) for q in quests if q["completed"])
    today_payload["progress_percent"] = round(
        100 * today_payload["xp_today"] / today_payload["possible_xp"]
    ) if today_payload["possible_xp"] else 100
    return today_payload


def fetch_today_effective(connection):
    return apply_occurrences_to_today(connection, fetch_today(connection))


def fetch_weekly_goals(connection):
    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    sunday = monday + timedelta(days=6)

    goals = connection.execute(text("""
        SELECT id, name, goal_type, quest_id, target_count, active, sort_order
        FROM weekly_goals
        WHERE active=1
        ORDER BY sort_order, id
    """)).mappings().all()

    result = []

    for goal in goals:
        current = 0

        if goal["goal_type"] == "quest" and goal["quest_id"]:
            current = int(connection.execute(text("""
                SELECT COUNT(*)
                FROM quest_completions
                WHERE quest_id=:qid
                  AND DATE(completed_at) BETWEEN :start AND :end
            """), {
                "qid": goal["quest_id"],
                "start": monday,
                "end": sunday,
            }).scalar_one())

        elif goal["goal_type"] == "quest_type":
            # Default system goal: training completions per week.
            current = int(connection.execute(text("""
                SELECT COUNT(*)
                FROM quest_completions qc
                JOIN quests q ON q.id=qc.quest_id
                WHERE q.quest_type='training'
                  AND DATE(qc.completed_at) BETWEEN :start AND :end
            """), {
                "start": monday,
                "end": sunday,
            }).scalar_one())

        target = int(goal["target_count"])
        remaining = max(0, target - current)

        result.append({
            "id": goal["id"],
            "name": goal["name"],
            "goal_type": goal["goal_type"],
            "quest_id": goal["quest_id"],
            "target_count": target,
            "current_count": current,
            "remaining": remaining,
            "progress_percent": min(100, round((current / target) * 100)) if target else 100,
            "completed": current >= target,
        })

    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "goals": result,
        "completed_count": sum(1 for x in result if x["completed"]),
        "total_count": len(result),
    }


def fetch_day_plan(connection):
    planner = fetch_planner(connection)
    weekly_goals = fetch_weekly_goals(connection)
    today = fetch_today_effective(connection)

    focus = list(planner.get("focus", []))

    plan_items = []
    used_ids = set()

    # 1. Training first when planned today.
    for item in focus:
        if item["quest_type"] == "training":
            plan_items.append({
                "order": len(plan_items) + 1,
                "quest_id": item["id"],
                "name": item["name"],
                "category": item["category"],
                "estimated_minutes": item["estimated_minutes"],
                "xp": item["xp"],
                "reason": "Heute geplantes Training",
                "kind": "training",
            })
            used_ids.add(item["id"])
            break

    # 2. Habit/routine goals next, prioritizing high priority and due tasks already scored.
    for item in focus:
        if item["id"] in used_ids:
            continue
        if len(plan_items) >= 3:
            break
        plan_items.append({
            "order": len(plan_items) + 1,
            "quest_id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "estimated_minutes": item["estimated_minutes"],
            "xp": item["xp"],
            "reason": item.get("reason") or "Heute sinnvoll",
            "kind": item["quest_type"],
        })
        used_ids.add(item["id"])

    # 3. Add weekly goal guidance if target is at risk / incomplete.
    missing_week = [
        {
            "id": g["id"],
            "name": g["name"],
            "remaining": g["remaining"],
            "target_count": g["target_count"],
            "current_count": g["current_count"],
            "progress_percent": g["progress_percent"],
        }
        for g in weekly_goals["goals"]
        if not g["completed"]
    ]

    today_open = [
        q for q in today["quests"]
        if not q.get("completed")
    ]

    return {
        "date": date.today().isoformat(),
        "plan": plan_items,
        "plan_count": len(plan_items),
        "open_today_count": len(today_open),
        "weekly_goals": weekly_goals,
        "missing_this_week": missing_week,
        "summary": {
            "xp_today": today["xp_today"],
            "possible_xp": today["possible_xp"],
            "progress_percent": today["progress_percent"],
            "projected_coins": today["projected_coins"],
        },
    }



def fetch_analytics(connection):
    today_date = date.today()
    start_30 = today_date - timedelta(days=29)

    category_rows = connection.execute(text("""
        SELECT
            c.name AS category,
            COUNT(qc.id) AS completions,
            COALESCE(SUM(qc.xp_awarded),0) AS xp,
            COALESCE(SUM(qc.willpower_xp),0) AS willpower_xp
        FROM categories c
        LEFT JOIN quests q ON q.category_id=c.id
        LEFT JOIN quest_completions qc
          ON qc.quest_id=q.id
         AND DATE(qc.completed_at) BETWEEN :start AND :end
        WHERE c.active=1
        GROUP BY c.id,c.name
        ORDER BY completions DESC,c.name
    """), {"start": start_30, "end": today_date}).mappings().all()

    kbr_rows = connection.execute(text("""
        SELECT
            COALESCE(kbr_at_completion,0) AS kbr,
            COUNT(*) AS completions,
            COALESCE(SUM(willpower_xp),0) AS willpower_xp
        FROM quest_completions
        WHERE DATE(completed_at) BETWEEN :start AND :end
        GROUP BY COALESCE(kbr_at_completion,0)
        ORDER BY kbr
    """), {"start": start_30, "end": today_date}).mappings().all()

    daily_rows = connection.execute(text("""
        SELECT
            DATE(created_at) AS d,
            COALESCE(SUM(CASE WHEN xp_type='normal' THEN amount ELSE 0 END),0) AS xp,
            COALESCE(SUM(CASE WHEN xp_type='willpower' THEN amount ELSE 0 END),0) AS willpower_xp
        FROM xp_ledger
        WHERE DATE(created_at) BETWEEN :start AND :end
        GROUP BY DATE(created_at)
        ORDER BY d
    """), {"start": start_30, "end": today_date}).mappings().all()

    completion_total = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions
        WHERE DATE(completed_at) BETWEEN :start AND :end
    """), {"start": start_30, "end": today_date}).scalar_one())

    training_total = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions qc
        JOIN quests q ON q.id=qc.quest_id
        WHERE q.quest_type='training'
          AND DATE(qc.completed_at) BETWEEN :start AND :end
    """), {"start": start_30, "end": today_date}).scalar_one())

    boss_total = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_completions
        WHERE COALESCE(kbr_at_completion,0)>=5
          AND DATE(completed_at) BETWEEN :start AND :end
    """), {"start": start_30, "end": today_date}).scalar_one())

    skipped_total = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_occurrences
        WHERE status='skipped'
          AND occurrence_date BETWEEN :start AND :end
    """), {"start": start_30, "end": today_date}).scalar_one())

    moved_total = int(connection.execute(text("""
        SELECT COUNT(*)
        FROM quest_occurrences
        WHERE status='moved'
          AND occurrence_date BETWEEN :start AND :end
    """), {"start": start_30, "end": today_date}).scalar_one())

    insights = []

    if moved_total >= 3:
        insights.append(f"{moved_total} Aufgaben wurden in den letzten 30 Tagen verschoben.")
    if skipped_total >= 3:
        insights.append(f"{skipped_total} Aufgaben wurden in den letzten 30 Tagen ausgelassen.")
    if boss_total > 0:
        insights.append(f"{boss_total} Boss Fight{'s' if boss_total != 1 else ''} in den letzten 30 Tagen abgeschlossen.")
    if training_total >= 12:
        insights.append("Training ist aktuell eine sehr konstante Kategorie.")
    if completion_total == 0:
        insights.append("Noch zu wenig Daten für aussagekräftige Trends.")

    strongest_category = None
    nonzero_categories = [dict(r) for r in category_rows if int(r["completions"] or 0) > 0]
    if nonzero_categories:
        strongest_category = nonzero_categories[0]
        insights.append(f"Stärkste Kategorie: {strongest_category['category']} mit {int(strongest_category['completions'])} Abschlüssen.")

    return {
        "period_days": 30,
        "start_date": start_30.isoformat(),
        "end_date": today_date.isoformat(),
        "completion_total": completion_total,
        "training_total": training_total,
        "boss_total": boss_total,
        "moved_total": moved_total,
        "skipped_total": skipped_total,
        "strongest_category": strongest_category,
        "categories": [{
            "category": r["category"],
            "completions": int(r["completions"] or 0),
            "xp": int(r["xp"] or 0),
            "willpower_xp": int(r["willpower_xp"] or 0),
        } for r in category_rows],
        "kbr": [{
            "kbr": int(r["kbr"] or 0),
            "completions": int(r["completions"] or 0),
            "willpower_xp": int(r["willpower_xp"] or 0),
        } for r in kbr_rows],
        "daily": [{
            "date": as_iso(r["d"]),
            "xp": int(r["xp"] or 0),
            "willpower_xp": int(r["willpower_xp"] or 0),
        } for r in daily_rows],
        "insights": insights[:5],
    }


@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
        schema_version = c.execute(text("""
            SELECT meta_value
            FROM life_manager_meta
            WHERE meta_key='schema_version'
            LIMIT 1
        """)).scalar()
    return {
        "status": "ok",
        "database": "connected",
        "version": "1.7.3",
        "schema_version": schema_version,
    }


@app.get("/dashboard")
def dashboard():
    with engine.begin() as c:
        payload = {
            "today": fetch_today_effective(c),
            "player": fetch_player(c),
            "training": fetch_training_week(c),
            "week": fetch_week(c),
            "streaks": fetch_streaks_v2(c),
            "rewards": fetch_rewards(c),
            "quest_manager": fetch_quest_manager(c),
            "achievements": evaluate_achievements(c),
            "boss_fights": fetch_boss_fights(c),
            "planner": fetch_planner(c),
            "weekly_review": fetch_weekly_review(c),
            "weekly_goals": fetch_weekly_goals(c),
            "day_plan": fetch_day_plan(c),
            "analytics": fetch_analytics(c),
        }

        # Stable Home Assistant transport wrapper.
        # HA only needs to expose the single `data` attribute from now on.
        # Legacy top-level fields remain for backward compatibility.
        return {
            **payload,
            "data": payload,
        }


@app.post("/day/finalize")
def finalize_day(x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    today_date = date.today()

    with engine.begin() as c:
        current = fetch_today(c)

        existing = c.execute(text("""
            SELECT coins_awarded, finalized_at
            FROM daily_summary
            WHERE summary_date=:d
        """), {"d": today_date}).mappings().first()

        if existing and existing["finalized_at"]:
            return {
                "success": True,
                "already_finalized": True,
                "date": today_date.isoformat(),
                "coins_awarded": int(existing["coins_awarded"] or 0),
            }

        coins = coins_for_percentage(current["progress_percent"])

        c.execute(text("""
            INSERT INTO daily_summary
                (summary_date,earned_xp,possible_xp,percentage,
                 coins_awarded,finalized_at)
            VALUES
                (:d,:earned,:possible,:pct,:coins,NOW())
            ON CONFLICT(summary_date) DO UPDATE SET
                earned_xp=excluded.earned_xp,
                possible_xp=excluded.possible_xp,
                percentage=excluded.percentage,
                coins_awarded=excluded.coins_awarded,
                finalized_at=NOW()
        """), {
            "d": today_date,
            "earned": current["xp_today"],
            "possible": current["possible_xp"],
            "pct": current["progress_percent"],
            "coins": coins,
        })

        if coins:
            c.execute(text("""
                INSERT INTO coin_ledger(amount,reason)
                VALUES(:amount,:reason)
            """), {
                "amount": coins,
                "reason": f"Tagesabschluss {today_date.isoformat()} ({current['progress_percent']}%)",
            })

    return {
        "success": True,
        "already_finalized": False,
        "date": today_date.isoformat(),
        "percentage": current["progress_percent"],
        "coins_awarded": coins,
    }



@app.post("/rewards")
def create_reward(
    payload: RewardPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        result = c.execute(text("""
            INSERT INTO rewards
                (name,description,cost,icon,active,sort_order)
            VALUES
                (:name,:description,:cost,:icon,:active,:sort_order)
        """), payload.model_dump())
        reward_id = result.lastrowid

    return {"success": True, "reward_id": reward_id}


@app.put("/rewards/{reward_id}")
def update_reward(
    reward_id: int,
    payload: RewardPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        exists = c.execute(
            text("SELECT id FROM rewards WHERE id=:rid"),
            {"rid": reward_id}
        ).first()

        if not exists:
            raise HTTPException(status_code=404, detail="Reward not found")

        values = payload.model_dump()
        values["rid"] = reward_id

        c.execute(text("""
            UPDATE rewards SET
                name=:name,
                description=:description,
                cost=:cost,
                icon=:icon,
                active=:active,
                sort_order=:sort_order
            WHERE id=:rid
        """), values)

    return {"success": True, "reward_id": reward_id}


@app.post("/rewards/{reward_id}/toggle")
def toggle_reward(
    reward_id: int,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        row = c.execute(
            text("SELECT active FROM rewards WHERE id=:rid"),
            {"rid": reward_id}
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Reward not found")

        active = 0 if row["active"] else 1
        c.execute(
            text("UPDATE rewards SET active=:active WHERE id=:rid"),
            {"active": active, "rid": reward_id}
        )

    return {"success": True, "reward_id": reward_id, "active": bool(active)}


@app.post("/savings-goals")
def create_savings_goal(
    payload: SavingsGoalPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        result = c.execute(text("""
            INSERT INTO savings_goals
                (name,target_coins,reward_id,active)
            VALUES
                (:name,:target_coins,:reward_id,:active)
        """), payload.model_dump())

    return {"success": True, "goal_id": result.lastrowid}


@app.post("/savings-goals/{goal_id}/toggle")
def toggle_savings_goal(
    goal_id: int,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        row = c.execute(
            text("SELECT active FROM savings_goals WHERE id=:gid"),
            {"gid": goal_id}
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Savings goal not found")

        active = 0 if row["active"] else 1
        c.execute(
            text("UPDATE savings_goals SET active=:active WHERE id=:gid"),
            {"active": active, "gid": goal_id}
        )

    return {"success": True, "goal_id": goal_id, "active": bool(active)}


@app.put("/rewards/{reward_id}/wishlist")
def update_reward_wishlist(
    reward_id: int,
    payload: RewardWishlistUpdate,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)
    with engine.begin() as c:
        result = c.execute(text("""
            UPDATE rewards SET wishlist=:wishlist WHERE id=:rid
        """), {"wishlist": 1 if payload.wishlist else 0, "rid": reward_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Reward not found")
    return {"success": True, "reward_id": reward_id, "wishlist": payload.wishlist}


@app.put("/savings-goals/{goal_id}/reserve")
def update_savings_goal_reserve(
    goal_id: int,
    payload: SavingsGoalReserveUpdate,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)
    if payload.reserved_coins < 0:
        raise HTTPException(status_code=400, detail="reserved_coins must be >= 0")

    with engine.begin() as c:
        balance = int(c.execute(
            text("SELECT COALESCE(SUM(amount),0) FROM coin_ledger")
        ).scalar_one())
        other_reserved = int(c.execute(text("""
            SELECT COALESCE(SUM(reserved_coins),0)
            FROM savings_goals
            WHERE active=1 AND id<>:gid
        """), {"gid": goal_id}).scalar_one())

        if other_reserved + payload.reserved_coins > balance:
            raise HTTPException(status_code=400, detail="Not enough free coins")

        result = c.execute(text("""
            UPDATE savings_goals
            SET reserved_coins=:coins
            WHERE id=:gid
        """), {"coins": payload.reserved_coins, "gid": goal_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Savings goal not found")

    return {"success": True, "goal_id": goal_id, "reserved_coins": payload.reserved_coins}


@app.post("/rewards/{reward_id}/purchase")
def purchase_reward(
    reward_id: int,
    payload: RewardPurchase,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        reward = c.execute(text("""
            SELECT id,name,cost,active
            FROM rewards
            WHERE id=:rid
        """), {"rid": reward_id}).mappings().first()

        if not reward or not reward["active"]:
            raise HTTPException(status_code=404, detail="Reward not found")

        total_cost = int(reward["cost"]) * payload.quantity
        balance = int(c.execute(
            text("SELECT COALESCE(SUM(amount),0) FROM coin_ledger")
        ).scalar_one())

        reserved = int(c.execute(text("""
            SELECT COALESCE(SUM(reserved_coins),0)
            FROM savings_goals
            WHERE active=1 AND (reward_id IS NULL OR reward_id<>:rid)
        """), {"rid": reward_id}).scalar_one())
        available = max(0, balance - reserved)

        if available < total_cost:
            raise HTTPException(status_code=400, detail="Not enough unreserved coins")

        c.execute(text("""
            INSERT INTO reward_purchases(reward_id,quantity,total_cost,purchased_at)
            VALUES(:rid,:qty,:cost,NOW())
        """), {
            "rid": reward_id,
            "qty": payload.quantity,
            "cost": total_cost,
        })

        c.execute(text("""
            INSERT INTO coin_ledger(amount,reason)
            VALUES(:amount,:reason)
        """), {
            "amount": -total_cost,
            "reason": f"Reward: {reward['name']} x{payload.quantity}",
        })

    return {
        "success": True,
        "reward_id": reward_id,
        "reward": reward["name"],
        "quantity": payload.quantity,
        "coins_spent": total_cost,
    }




@app.get("/categories")
def list_categories():
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT id,name,icon,sort_order,active
            FROM categories
            ORDER BY sort_order,id
        """)).mappings().all()

    return [{
        "id": row["id"],
        "name": row["name"],
        "icon": row["icon"],
        "sort_order": int(row["sort_order"] or 0),
        "active": bool(row["active"]),
    } for row in rows]


@app.post("/categories")
def create_category(
    payload: CategoryPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name required")

    with engine.begin() as c:
        duplicate = c.execute(text("""
            SELECT id
            FROM categories
            WHERE LOWER(name)=LOWER(:name)
        """), {"name": name}).first()

        if duplicate:
            raise HTTPException(status_code=400, detail="Category already exists")

        result = c.execute(text("""
            INSERT INTO categories(name,icon,sort_order,active)
            VALUES(:name,:icon,:sort_order,:active)
        """), {
            "name": name,
            "icon": payload.icon.strip() or "mdi:folder",
            "sort_order": payload.sort_order,
            "active": 1 if payload.active else 0,
        })

    return {
        "success": True,
        "category_id": result.lastrowid,
    }


@app.put("/categories/{category_id}")
def update_category(
    category_id: int,
    payload: CategoryPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name required")

    with engine.begin() as c:
        existing = c.execute(text("""
            SELECT id
            FROM categories
            WHERE id=:category_id
        """), {"category_id": category_id}).first()

        if not existing:
            raise HTTPException(status_code=404, detail="Category not found")

        duplicate = c.execute(text("""
            SELECT id
            FROM categories
            WHERE LOWER(name)=LOWER(:name)
              AND id<>:category_id
        """), {
            "name": name,
            "category_id": category_id,
        }).first()

        if duplicate:
            raise HTTPException(status_code=400, detail="Category already exists")

        c.execute(text("""
            UPDATE categories
            SET name=:name,
                icon=:icon,
                sort_order=:sort_order,
                active=:active
            WHERE id=:category_id
        """), {
            "name": name,
            "icon": payload.icon.strip() or "mdi:folder",
            "sort_order": payload.sort_order,
            "active": 1 if payload.active else 0,
            "category_id": category_id,
        })

    return {
        "success": True,
        "category_id": category_id,
    }


@app.post("/categories/{category_id}/toggle")
def toggle_category(
    category_id: int,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        row = c.execute(text("""
            SELECT active
            FROM categories
            WHERE id=:category_id
        """), {"category_id": category_id}).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Category not found")

        new_active = not bool(row["active"])

        c.execute(text("""
            UPDATE categories
            SET active=:active
            WHERE id=:category_id
        """), {
            "active": 1 if new_active else 0,
            "category_id": category_id,
        })

    return {
        "success": True,
        "category_id": category_id,
        "active": new_active,
    }


@app.get("/quests")
def list_quests():
    with engine.connect() as c:
        return fetch_quest_manager(c)


@app.post("/quests")
def create_quest(
    payload: QuestPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)
    validate_quest_payload(payload)

    logger.info("Creating quest: %s", payload.name)
    with engine.begin() as c:
        values = payload.model_dump(exclude={"weekdays", "interval_days", "next_due"})

        result = c.execute(text("""
            INSERT INTO quests
            (name,category_id,quest_type,description,estimated_minutes,kbr,
             xp_mode,fixed_xp,frequency_days,project_factor,priority,due_date,active)
            VALUES
            (:name,:category_id,:quest_type,:description,:estimated_minutes,:kbr,
             :xp_mode,:fixed_xp,:frequency_days,:project_factor,:priority,:due_date,:active)
        """), values)

        quest_id = result.lastrowid
        replace_schedules(c, quest_id, payload)

        saved = c.execute(text("""
            SELECT q.id, q.name, q.category_id, c.name AS category,
                   q.quest_type, q.description, q.estimated_minutes, q.kbr,
                   q.xp_mode, q.fixed_xp, q.frequency_days, q.project_factor,
                   q.priority, q.due_date, q.active
            FROM quests q
            JOIN categories c ON c.id=q.category_id
            WHERE q.id=:qid
        """), {"qid": quest_id}).mappings().first()

    logger.info("Quest created: id=%s name=%s", quest_id, payload.name)
    return {"success": True, "quest_id": quest_id, "quest": dict(saved) if saved else None}


@app.put("/quests/{quest_id}")
def update_quest(
    quest_id: int,
    payload: QuestPayload,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)
    validate_quest_payload(payload)

    with engine.begin() as c:
        if not c.execute(
            text("SELECT id FROM quests WHERE id=:qid"),
            {"qid": quest_id}
        ).first():
            raise HTTPException(status_code=404, detail="Quest not found")

        values = payload.model_dump(exclude={"weekdays", "interval_days", "next_due"})
        values["qid"] = quest_id

        c.execute(text("""
            UPDATE quests SET
              name=:name,
              category_id=:category_id,
              quest_type=:quest_type,
              description=:description,
              estimated_minutes=:estimated_minutes,
              kbr=:kbr,
              xp_mode=:xp_mode,
              fixed_xp=:fixed_xp,
              frequency_days=:frequency_days,
              project_factor=:project_factor,
              priority=:priority,
              due_date=:due_date,
              active=:active
            WHERE id=:qid
        """), values)

        replace_schedules(c, quest_id, payload)

        saved = c.execute(text("""
            SELECT q.id, q.name, q.category_id, c.name AS category,
                   q.quest_type, q.description, q.estimated_minutes, q.kbr,
                   q.xp_mode, q.fixed_xp, q.frequency_days, q.project_factor,
                   q.priority, q.due_date, q.active
            FROM quests q
            JOIN categories c ON c.id=q.category_id
            WHERE q.id=:qid
        """), {"qid": quest_id}).mappings().first()

    logger.info("Quest updated: id=%s name=%s", quest_id, payload.name)
    return {"success": True, "quest_id": quest_id, "quest": dict(saved) if saved else None}


@app.post("/quests/{quest_id}/toggle")
def toggle_quest(
    quest_id: int,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        quest = c.execute(
            text("SELECT active FROM quests WHERE id=:qid"),
            {"qid": quest_id}
        ).mappings().first()

        if not quest:
            raise HTTPException(status_code=404, detail="Quest not found")

        new_value = 0 if quest["active"] else 1

        c.execute(
            text("UPDATE quests SET active=:active WHERE id=:qid"),
            {"active": new_value, "qid": quest_id}
        )

    return {"success": True, "quest_id": quest_id, "active": bool(new_value)}


@app.post("/quests/{quest_id}/complete")
def complete_quest(
    quest_id: int,
    payload: CompleteQuest,
    x_api_key: str | None = Header(default=None)
):
    check_api_key(x_api_key)

    with engine.begin() as c:
        quest = c.execute(text("""
            SELECT id,name,quest_type,xp_mode,fixed_xp,
                   estimated_minutes,kbr,frequency_days
            FROM quests
            WHERE id=:qid AND active=1
        """), {"qid": quest_id}).mappings().first()

        if not quest:
            raise HTTPException(status_code=404, detail="Quest not found")

        existing = c.execute(text("""
            SELECT id,xp_awarded,willpower_xp
            FROM quest_completions
            WHERE quest_id=:qid
              AND DATE(completed_at)=CURDATE()
            ORDER BY id DESC
            LIMIT 1
        """), {"qid": quest_id}).mappings().first()

        if existing:
            return {
                "success": True,
                "already_completed": True,
                "quest_id": quest_id,
                "quest": quest["name"],
                "xp": int(existing["xp_awarded"] or 0),
                "willpower_xp": int(existing["willpower_xp"] or 0),
            }

        xp = calculate_quest_xp(quest)
        wp = (15 if int(quest["kbr"] or 0) >= 5 else 10) if payload.overcome else 0

        result = c.execute(text("""
            INSERT INTO quest_completions
            (quest_id,completed_at,xp_awarded,willpower_xp,kbr_at_completion)
            VALUES(:qid,NOW(),:xp,:wp,:kbr)
        """), {
            "qid": quest_id,
            "xp": xp,
            "wp": wp,
            "kbr": quest["kbr"],
        })

        cid = result.lastrowid

        if xp:
            c.execute(text("""
                INSERT INTO xp_ledger
                (amount,xp_type,source_type,source_id,description)
                VALUES(:a,'normal','quest_completion',:sid,:d)
            """), {
                "a": xp,
                "sid": cid,
                "d": quest["name"],
            })

        if wp:
            c.execute(text("""
                INSERT INTO xp_ledger
                (amount,xp_type,source_type,source_id,description)
                VALUES(:a,'willpower','quest_completion',:sid,:d)
            """), {
                "a": wp,
                "sid": cid,
                "d": f"Overcome: {quest['name']}",
            })

    return {
        "success": True,
        "already_completed": False,
        "quest_id": quest_id,
        "quest": quest["name"],
        "xp": xp,
        "willpower_xp": wp,
    }
