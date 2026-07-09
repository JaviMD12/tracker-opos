import os

import stripe
from fastapi import APIRouter, Depends, HTTPException

from app.models.usuario import Usuario
from app.services.security import get_current_user

router = APIRouter(prefix="/api/pagos", tags=["pagos"])

# La clave real vive en backend/.env (STRIPE_SECRET_KEY), cargado por app/main.py
# antes de que este router se importe. Nunca hardcodear la clave aqui.
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

DOMINIO_APP = "http://localhost:8000"
PRECIO_PLAN_PRO_CENTIMOS = 999  # 9,99 EUR


@router.post("/checkout")
def crear_sesion_checkout(current_user: Usuario = Depends(get_current_user)):
    """Crea una sesion de Stripe Checkout (modo pago unico) para el Plan Pro."""
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {"name": "Plan Pro - Tracker Oposiciones"},
                        "unit_amount": PRECIO_PLAN_PRO_CENTIMOS,
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{DOMINIO_APP}/?pago=exito",
            cancel_url=f"{DOMINIO_APP}/?pago=cancelado",
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo iniciar el pago con Stripe: {exc.user_message or str(exc)}",
        ) from exc

    return {"session_id": session.id, "url": session.url}
