import json
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.services.security import get_current_user

router = APIRouter(prefix="/api/pagos", tags=["pagos"])

# La clave real vive en backend/.env (STRIPE_SECRET_KEY), cargado por app/main.py
# antes de que este router se importe. Nunca hardcodear la clave aqui.
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

DOMINIO_APP = os.environ.get("DOMINIO_APP", "http://localhost:8000")
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
            # Permite identificar al usuario en el webhook de confirmacion
            # (checkout.session.completed), que no lleva JWT propio.
            client_reference_id=str(current_user.id),
            success_url=f"{DOMINIO_APP}/?pago=exito",
            cancel_url=f"{DOMINIO_APP}/?pago=cancelado",
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo iniciar el pago con Stripe: {exc.user_message or str(exc)}",
        ) from exc

    return {"session_id": session.id, "url": session.url}


@router.post("/webhook")
async def webhook_stripe(request: Request, db: Session = Depends(get_db)):
    """Recibe la confirmacion real de pago de Stripe y activa el Plan Pro.

    Sin esto, is_pro nunca pasa a True: el checkout por si solo no confirma
    que el pago se completo, solo abre la sesion. En local, Stripe solo
    puede llamar a esta URL a traves de `stripe listen --forward-to
    localhost:.../api/pagos/webhook` (o en produccion, con la URL publica
    dada de alta en el Dashboard de Stripe).
    """
    payload = await request.body()
    firma = request.headers.get("stripe-signature")

    try:
        # construct_event ya valida la firma; nos quedamos con el JSON plano
        # (en vez del StripeObject que devuelve) para no depender de su API
        # de atributos/objetos anidados al leer los campos que necesitamos.
        stripe.Webhook.construct_event(payload, firma, STRIPE_WEBHOOK_SECRET)
        evento = json.loads(payload)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail="Webhook de Stripe invalido") from exc

    if evento.get("type") == "checkout.session.completed":
        sesion = evento.get("data", {}).get("object", {})
        usuario_id = sesion.get("client_reference_id")
        if usuario_id:
            usuario = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
            if usuario:
                usuario.is_pro = True
                # Necesario para poder abrir despues el Portal de Cliente de
                # Stripe (POST /api/pagos/portal), que requiere el customer id.
                stripe_customer_id = sesion.get("customer")
                if stripe_customer_id:
                    usuario.stripe_customer_id = stripe_customer_id
                db.commit()

    return {"received": True}


@router.post("/portal")
def crear_sesion_portal(
    request: Request, current_user: Usuario = Depends(get_current_user)
):
    """Crea una sesion del Portal de Cliente de Stripe para que el usuario
    gestione tarjeta, facturas y cancelacion de su suscripcion de forma
    autonoma, sin pasar por soporte."""
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se encontro un cliente de Stripe asociado a esta cuenta. "
                "Si pagaste antes de esta actualizacion, contacta con soporte."
            ),
        )

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=request.headers.get("referer", DOMINIO_APP),
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo abrir el portal de Stripe: {exc.user_message or str(exc)}",
        ) from exc

    return {"url": session.url}
