import os
import logging
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text


MYSQL_HOST = os.environ["MYSQL_HOST"]
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
API_KEY = os.environ["API_KEY"]

DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
app = FastAPI(title="Life Manager", version="0.7.3")
logger = logging.getLogger("life_manager")


class CompleteQuest(BaseModel):
    overcome: bool = False


class RewardPurchase(BaseModel):
    quantity: int = Field(default=1, ge=1, le=20)


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
            "completed_at": completion["completed_at"].isoformat() if completion and completion["completed_at"] else None,
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
                   AND DATE(qc.completed_at)=DATE_ADD(:monday, INTERVAL (qs.weekday-1) DAY)
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
    dates = sorted(set(completion_dates), reverse=True)
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
        SELECT id,name,description,cost,icon,active,sort_order
        FROM rewards
        WHERE active=1
        ORDER BY sort_order,cost,id
    """)).mappings().all()

    recent = connection.execute(text("""
        SELECT rp.id,rp.reward_id,r.name,rp.quantity,rp.total_cost,rp.purchased_at
        FROM reward_purchases rp
        JOIN rewards r ON r.id=rp.reward_id
        ORDER BY rp.purchased_at DESC
        LIMIT 10
    """)).mappings().all()

    return {
        "coin_balance": balance,
        "rewards": [{
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "cost": int(r["cost"]),
            "icon": r["icon"],
            "can_afford": balance >= int(r["cost"]),
        } for r in rewards],
        "recent_purchases": [{
            "id": x["id"],
            "reward_id": x["reward_id"],
            "name": x["name"],
            "quantity": x["quantity"],
            "total_cost": x["total_cost"],
            "purchased_at": x["purchased_at"].isoformat(),
        } for x in recent],
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
            "next_due": s["next_due"].isoformat() if s["next_due"] else None,
        })

    return {
        "categories": [dict(x) for x in categories],
        "quests": [{
            **{k: q[k] for k in q.keys() if k != "created_at"},
            "created_at": q["created_at"].isoformat() if q["created_at"] else None,
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


@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "version": "0.7.3"}


@app.get("/dashboard")
def dashboard():
    with engine.connect() as c:
        return {
            "today": fetch_today(c),
            "player": fetch_player(c),
            "training": fetch_training_week(c),
            "week": fetch_week(c),
            "streaks": fetch_streaks(c),
            "rewards": fetch_rewards(c),
            "quest_manager": fetch_quest_manager(c),
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
            ON DUPLICATE KEY UPDATE
                earned_xp=VALUES(earned_xp),
                possible_xp=VALUES(possible_xp),
                percentage=VALUES(percentage),
                coins_awarded=VALUES(coins_awarded),
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

        if balance < total_cost:
            raise HTTPException(status_code=400, detail="Not enough coins")

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
             xp_mode,fixed_xp,frequency_days,project_factor,active)
            VALUES
            (:name,:category_id,:quest_type,:description,:estimated_minutes,:kbr,
             :xp_mode,:fixed_xp,:frequency_days,:project_factor,:active)
        """), values)

        quest_id = result.lastrowid
        replace_schedules(c, quest_id, payload)

        saved = c.execute(text("""
            SELECT q.id, q.name, q.category_id, c.name AS category,
                   q.quest_type, q.description, q.estimated_minutes, q.kbr,
                   q.xp_mode, q.fixed_xp, q.frequency_days, q.project_factor,
                   q.active
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
              active=:active
            WHERE id=:qid
        """), values)

        replace_schedules(c, quest_id, payload)

        saved = c.execute(text("""
            SELECT q.id, q.name, q.category_id, c.name AS category,
                   q.quest_type, q.description, q.estimated_minutes, q.kbr,
                   q.xp_mode, q.fixed_xp, q.frequency_days, q.project_factor,
                   q.active
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
        wp = 10 if payload.overcome else 0

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
