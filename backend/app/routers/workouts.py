from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.models.workout import Workout
from app.schemas import WorkoutCreate, WorkoutOut
from app.services.security import get_current_user

router = APIRouter(prefix="/api/workouts", tags=["workouts"])


@router.post("", response_model=WorkoutOut)
def crear_workout(
    workout_in: WorkoutCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    workout = Workout(
        fecha=workout_in.fecha or date.today(),
        usuario_id=current_user.id,
        workout_type=workout_in.workout_type,
        notes=workout_in.notes,
        exercise_name=workout_in.exercise_name,
        weight_kg=workout_in.weight_kg,
        reps=workout_in.reps,
        distance_km=workout_in.distance_km,
        duration_minutes=workout_in.duration_minutes,
    )
    db.add(workout)
    db.commit()
    db.refresh(workout)
    return workout


@router.get("/historial", response_model=list[WorkoutOut])
def historial(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(Workout)
        .filter(Workout.usuario_id == current_user.id)
        .order_by(Workout.fecha.desc(), Workout.id.desc())
        .all()
    )
