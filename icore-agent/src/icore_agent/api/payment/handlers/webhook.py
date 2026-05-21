"""Payment webhook handlers."""


async def stripe_webhook() -> dict:
    """Handle Stripe webhook callbacks."""
    return {"received": True}
